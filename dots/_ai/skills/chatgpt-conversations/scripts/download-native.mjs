import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

export function validateRequests(requests) {
  if (!Array.isArray(requests) || !requests.length) throw Error('Requests must be a nonempty array');
  const names = new Set();
  for (const item of requests) {
    if (!item || typeof item.name !== 'string' || !item.name || path.basename(item.name) !== item.name || ['.', '..'].includes(item.name)) throw Error('A request needs a plain filename');
    if (names.has(item.name)) throw Error('Duplicate destination filename');
    names.add(item.name);
    if (item.kind === 'link' && (typeof item.message_id !== 'string' || !item.message_id || typeof item.sandbox_path !== 'string' || !item.sandbox_path.startsWith('/mnt/data/'))) throw Error('A link needs its native message ID and sandbox path');
    if (item.kind === 'upload' && !/^file_[A-Za-z0-9_-]+$/.test(item.file_id || '')) throw Error('An upload needs its native file ID');
    if (!['link', 'upload'].includes(item.kind)) throw Error('Unknown request kind');
    if (item.expected_bytes !== undefined && (!Number.isSafeInteger(item.expected_bytes) || item.expected_bytes < 0)) throw Error('Invalid expected byte count');
  }
}

export function matchesDownload(name, candidate) {
  if (candidate === name) return true;
  const escape = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const extension = path.extname(name), stem = extension ? name.slice(0, -extension.length) : name;
  return new RegExp('^' + escape(stem) + ' \\([0-9]+\\)' + escape(extension) + '$').test(candidate);
}

export function downloadExpression(item, conversationId) {
  return `(async () => {
    const item = ${JSON.stringify(item)}, expectedConversation = ${JSON.stringify(conversationId)};
    const conversationId = new URL(location.href).pathname.match(/^\\/c\\/([^/?#]+)/)?.[1];
    if (location.origin !== 'https://chatgpt.com' || conversationId !== expectedConversation) throw Error('Page changed');
    const session = await fetch('/api/auth/session', {credentials: 'include', cache: 'no-store', signal: AbortSignal.timeout(15000)});
    if (!session.ok) return {started: false, error: 'session_http_' + session.status};
    const s = await session.json(), token = s.accessToken || s.access_token || s.session?.accessToken || s.session?.access_token;
    if (!token) return {started: false, error: 'session_missing_access_token'};
    const headers = {Authorization: 'Bearer ' + token}, account = s.account?.id || s.session?.account?.id || s.account_id;
    if (account) headers['ChatGPT-Account-Id'] = account;
    const endpoint = item.kind === 'upload' ? '/backend-api/files/' + encodeURIComponent(item.file_id) + '/download' :
      '/backend-api/conversation/' + encodeURIComponent(conversationId) + '/interpreter/download?' + new URLSearchParams({message_id: item.message_id, sandbox_path: item.sandbox_path, download_intent: 'true'});
    const response = await fetch(endpoint, {credentials: 'include', headers, signal: AbortSignal.timeout(25000)});
    if (!response.ok) return {started: false, error: 'file_http_' + response.status};
    const p = await response.json();
    if (typeof p.download_url !== 'string' || new URL(p.download_url).protocol !== 'https:') return {started: false, error: 'download_url_missing_or_invalid'};
    const anchor = document.createElement('a');
    anchor.href = p.download_url; anchor.download = item.name;
    document.body.append(anchor); anchor.click(); anchor.remove();
    return {started: true, provider_filename: p.file_name || null, provider_bytes: p.file_size_bytes ?? null};
  })()`;
}

function inventory(directory) {
  const result = new Map();
  for (const name of fs.readdirSync(directory)) {
    try { const stat = fs.statSync(path.join(directory, name)); if (stat.isFile()) result.set(name, stat.ino); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  return result;
}

async function hash(filename) {
  const digest = crypto.createHash('sha256');
  for await (const bytes of fs.createReadStream(filename)) digest.update(bytes);
  return digest.digest('hex');
}

export async function collect(pageId, requestsPath, destination) {
  const requests = JSON.parse(fs.readFileSync(requestsPath, 'utf8'));
  validateRequests(requests);
  const timeout = process.env.SINNIX_CHATGPT_DOWNLOAD_TIMEOUT_SEC || '120';
  if (!/^[1-9][0-9]*$/.test(timeout)) throw Error('SINNIX_CHATGPT_DOWNLOAD_TIMEOUT_SEC must be a positive integer');
  const targets = await (await fetch((process.env.CDP_BASE || 'http://127.0.0.1:9222') + '/json', {signal: AbortSignal.timeout(15000)})).json();
  const target = targets.find(t => t.id === pageId), conversationId = target?.url?.match(/^https:\/\/chatgpt\.com\/c\/([^/?#]+)/)?.[1];
  if (!conversationId) throw Error('Selected page is not an open ChatGPT conversation');
  const downloads = execFileSync('xdg-user-dir', ['DOWNLOAD'], {encoding: 'utf8'}).trim();
  if (!fs.statSync(downloads).isDirectory()) throw Error('Downloads directory unavailable');
  fs.mkdirSync(destination, {recursive: true, mode: 0o700});
  const receiptPath = path.join(destination, 'native-downloads.json');
  const receiptFd = fs.openSync(receiptPath, 'wx', 0o600);
  fs.closeSync(receiptFd);
  const receipt = {schema: 'chatgpt-native-downloads-v1', page_id: pageId, conversation_url: target.url, started_at: new Date().toISOString(), complete: false, files: []};
  const save = () => fs.writeFileSync(receiptPath, JSON.stringify(receipt, null, 2) + '\n', {mode: 0o600});
  save();
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  let sequence = 0;
  const pending = new Map();
  socket.onmessage = event => {
    const message = JSON.parse(event.data), request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id); clearTimeout(request.timer);
    message.error ? request.reject(Error('CDP request failed')) : request.resolve(message.result);
  };
  const call = (method, params) => new Promise((resolve, reject) => {
    const id = ++sequence, timer = setTimeout(() => {pending.delete(id); reject(Error(method + ' timeout'));}, 45000);
    pending.set(id, {resolve, reject, timer}); socket.send(JSON.stringify({id, method, params}));
  });
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(Error('CDP connection timeout')), 15000);
      socket.onopen = () => {clearTimeout(timer); resolve();};
      socket.onerror = () => {clearTimeout(timer); reject(Error('CDP connection failed'));};
    });
    for (const item of requests) {
      const output = path.join(destination, item.name);
      if (fs.existsSync(output)) throw Error('Destination file already exists');
      const before = inventory(downloads), began = Date.now();
      const response = await call('Runtime.evaluate', {expression: downloadExpression(item, conversationId), returnByValue: true, awaitPromise: true, userGesture: true});
      if (response.exceptionDetails || !response.result?.value) throw Error('Native download script failed');
      const started = response.result.value, record = {...item, ...started, started_at: new Date(began).toISOString()};
      receipt.files.push(record); save();
      if (!started.started) {record.status = 'unavailable'; save(); continue;}
      // Content-Disposition can override the requested anchor download name.
      const names = [item.name];
      if (started.provider_filename && path.basename(started.provider_filename) === started.provider_filename && !['.', '..'].includes(started.provider_filename)) names.push(started.provider_filename);
      const deadline = Date.now() + Number(timeout) * 1000;
      let found;
      while (Date.now() < deadline) {
        const candidates = [...inventory(downloads)].filter(([name, inode]) => names.some(expected => matchesDownload(expected, name)) && before.get(name) !== inode);
        if (candidates.length > 1) throw Error('Multiple matching downloads');
        if (candidates.length === 1) {found = path.join(downloads, candidates[0][0]); break;}
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      if (!found) {record.status = 'timed_out'; save(); continue;}
      const bytes = fs.statSync(found).size;
      if (started.provider_bytes !== null && bytes !== started.provider_bytes) throw Error('Provider byte count mismatch');
      if (item.expected_bytes !== undefined && bytes !== item.expected_bytes) throw Error('Native attachment byte count mismatch');
      fs.copyFileSync(found, output, fs.constants.COPYFILE_EXCL); fs.chmodSync(output, 0o600);
      Object.assign(record, {status: 'downloaded', path: path.resolve(output), download_path: found, bytes, sha256: await hash(output), elapsed_s: (Date.now() - began) / 1000}); save();
    }
    receipt.complete = receipt.files.length === requests.length && receipt.files.every(file => file.status === 'downloaded');
    receipt.finished_at = new Date().toISOString(); save();
    return receipt;
  } catch (error) {
    receipt.error = error.message; save(); throw error;
  } finally {
    for (const request of pending.values()) {clearTimeout(request.timer); request.reject(Error('CDP connection closed'));}
    socket.close();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(fs.realpathSync(process.argv[1])).href) {
  const [pageId, requestsPath, destination] = process.argv.slice(2);
  if (!pageId || !requestsPath || !destination) throw Error('Usage: download-native.mjs PAGE_ID REQUESTS_JSON DESTINATION');
  try {
    const receipt = await collect(pageId, requestsPath, destination);
    console.log(JSON.stringify(receipt));
    if (!receipt.complete) process.exitCode = 1;
  } catch (error) {console.error(error.message); process.exitCode = 1;}
}
