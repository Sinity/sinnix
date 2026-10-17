"""Run the same admission cases against real pinned HTTP libraries and packages."""
import gzip
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        url = attrs.get('src') if tag == 'script' else attrs.get('href') if tag == 'link' and attrs.get('rel') in {'stylesheet', 'modulepreload'} else None
        if url:
            parsed = urllib.parse.urlsplit(url)
            if not parsed.scheme and not parsed.netloc:
                self.links.append(urllib.parse.urljoin('/', url))

def run(server, fixture=False, restricted_cors=False, child=False, unmanaged=False):
    with tempfile.TemporaryDirectory() as work:
        root = Path(work)
        models = root / 'models'
        models.mkdir()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        public = 18081 if port != 18081 else 18083
        origins = ','.join(f'http://{host}:{p}' for host in ['127.0.0.1', 'localhost', '[::1]'] for p in [public, port])
        env = {'PATH': os.environ.get('PATH', ''), 'HOME': work, 'TMPDIR': work, 'LLAMA_CACHE': str(root / 'cache'), 'CUDA_VISIBLE_DEVICES': '', 'SINNIX_LLAMA_ALLOWED_ORIGINS': origins}
        args = [server, str(port)] if fixture else [server, '--host', '127.0.0.1', '--port', str(port), '--models-dir', str(models), '--no-models-autoload', '--offline', '--threads-http', '2']
        if child:
            assert fixture  # Exercise the exact HTTP policy without starting a model child.
            env['LLAMA_SERVER_ROUTER_PORT'] = str(public)
            env['SINNIX_LLAMA_ALLOWED_ORIGINS'] = ','.join(f'http://{host}:{public}' for host in ['127.0.0.1', 'localhost', '[::1]'])
        if unmanaged:
            env.pop('SINNIX_LLAMA_ALLOWED_ORIGINS')
        if restricted_cors:
            limited = f'http://localhost:{public}'
            if fixture:
                env['FIXTURE_CORS_ORIGINS'] = limited
            else:
                args += ['--cors-origins', limited]
        with (root / 'server.log').open('wb') as log:
            process = subprocess.Popen(args, env=env, stdout=log, stderr=log)
            try:
                base = f'http://127.0.0.1:{port}'

                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

                def request(headers=None, path='/v1/models', data=None, method=None):
                    req = urllib.request.Request(base + path, headers=headers or {}, data=data, method=method)
                    try:
                        with opener.open(req, timeout=3) as response:
                            return response.status, response.headers, response.read()
                    except urllib.error.HTTPError as response:
                        return response.code, response.headers, response.read()

                deadline = time.monotonic() + 20
                while True:
                    try:
                        if request()[0] == 200:
                            break
                    except OSError:
                        pass
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise AssertionError('server did not become ready: ' + (root / 'server.log').read_text()[-2000:])
                    time.sleep(.05)

                assert json.loads(request()[2])['data'] == []
                trusted = f'http://localhost:{public}'
                status, headers, _ = request({'Host': f'localhost:{public}', 'Origin': trusted, 'Sec-Fetch-Site': 'same-origin'})
                assert status == 200 and headers.get('Access-Control-Allow-Origin') == trusted
                if restricted_cors:
                    status, headers, _ = request({'Origin': f'http://127.0.0.1:{port}'})
                    assert status == 200 and headers.get('Access-Control-Allow-Origin') is None
                assert request({'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'cors'})[0] == 200
                assert request({'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document', 'Sec-Fetch-User': '?1'})[0] == 200
                if fixture:
                    assert request({'Origin': trusted}, '/stream')[2] == b'data: fixture\n\n'
                else:
                    status, headers, html = request({'Accept-Encoding': 'gzip', 'Sec-Fetch-Site': 'none', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document', 'Sec-Fetch-User': '?1'}, '/')
                    assert status == 200, ('UI document', status)
                    if headers.get('Content-Encoding') == 'gzip':
                        html = gzip.decompress(html)
                    assert b'<html' in html.lower()
                    assets = Assets()
                    assets.feed(html.decode('utf-8'))
                    for asset in set(assets.links):
                        assert request({'Accept-Encoding': 'gzip', 'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'cors'}, asset)[0] == 200, asset

                status, headers, _ = request({'Origin': trusted, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'}, method='OPTIONS')
                assert status == 200 and headers.get('Access-Control-Allow-Origin') == trusted
                if fixture:
                    data = b'{"fixture":"complete body"}'
                    for headers in [{'Content-Type': 'application/json'}, {'Content-Type': 'application/json', 'Host': f'localhost:{public}', 'Origin': trusted, 'Sec-Fetch-Site': 'same-origin'}]:
                        status, _, returned = request(headers, data=data, method='POST')
                        assert status == 200 and returned == data

                before = int(request(path='/count')[2]) if fixture else None
                for refused in [
                    {'Host': 'foreign.example'},
                    {'Host': f'127.0.0.1:{public + 1}'},
                    {'Origin': 'https://foreign.example'},
                    {'Origin': 'null'},
                    {'Origin': 'http://127.0.0.1:8883'},
                    {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'cors'},
                    {'Sec-Fetch-Site': 'same-site', 'Sec-Fetch-Mode': 'no-cors'},
                    {'Sec-Fetch-Mode': 'cors'},
                ]:
                    status, headers, _ = request(refused)
                    assert status == 403, (refused, status)
                    assert headers.get('Access-Control-Allow-Origin') is None
                    assert headers.get('Connection', '').lower() == 'close'
                for extra in [
                    'Host: foreign.example\r\n',
                    'Origin: null\r\nOrigin: null\r\n',
                    'Sec-Fetch-Site: same-origin\r\nSec-Fetch-Site: same-origin\r\n',
                    'Origin: https://foreign.example\r\n',
                    'Sec-Fetch-Site: cross-site\r\nSec-Fetch-Mode: no-cors\r\n',
                ]:
                    # Never send the declared body. Refusal must precede its read,
                    # and the connection must close rather than retaining a waiter.
                    with socket.create_connection(('127.0.0.1', port), timeout=3) as client:
                        client.settimeout(3)
                        client.sendall((f'POST /v1/models HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n' + extra + 'Content-Type: application/json\r\nContent-Length: 1000000\r\n\r\n').encode())
                        reply = b''
                        while part := client.recv(4096):
                            reply += part
                        assert int(reply.split(b' ', 2)[1]) in {400, 403}, reply[:200]
                if fixture:
                    assert int(request(path='/count')[2]) == before
                print(Path(server).name, 'native/UI/navigation/stream and 13 refusal controls passed', flush=True)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    run(sys.argv[1], fixture='--fixture' in sys.argv[2:])
    run(sys.argv[1], fixture='--fixture' in sys.argv[2:], restricted_cors=True)
    if '--fixture' in sys.argv[2:]:
        run(sys.argv[1], fixture=True, child=True)
        run(sys.argv[1], fixture=True, child=True, unmanaged=True)
