// Xiaomi cloud vendor witness: one sync pass (sinnix-ogll).
//
// Second independent witness to the band's data, read from Xiaomi's cloud
// instead of the phone -- no BLE contention, no Health Connect, no screen.
// Measured 2026-08-17 before this service existed: the cloud held heart
// rate two hours FRESHER than Health Connect, because Mi Fitness syncs the
// cloud silently while HC waits for its manual Sync button; and the cloud
// sleep summaries carry sleep_score, REM duration and per-segment detail
// that the HC write path never gets.
//
// The Xiaomi protocol client is upstream GPL-3 source (miband-bot), fetched
// pinned by the derivation and imported at runtime -- deliberately not
// vendored into this repository. This file only orchestrates: fetch the
// recent window per metric, and append envelopes to the lane.
//
// Write-on-change: every envelope carries a content hash, and a state file
// remembers the hash last written per (kind, day). Xiaomi revises a day's
// data as more band syncs land, so the same day is legitimately re-fetched
// every pass; a revision is appended (the history of revisions is
// evidence), an identical re-read is not. Raw fidelity: the `data` field
// is the complete parsed API item, never a reduction of it.
//
// Three planes, all measured against this account (EU, de shard):
// - AGGREGATED (vendor_sleep / vendor_*_day): get_aggregated_fitness_data_
//   by_time daily summaries. Own uid works as relative_uid;
//   get_latest_fitness_data and relatives/* are family-care surfaces
//   answering -8/-6 for self and are not used.
// - RAW (vendor_raw_*): get_fitness_data_by_time returns the band's dense
//   series -- ~2-minute heart rate, continuous SpO2 and stress, 5-minute
//   steps/calories, per-night sleep objects with avg_breath -- densities
//   Health Connect never sees. Each record carries the writing device id
//   in `sid` (the phone's synthetic records use an "hlth.gen_" prefix),
//   which is also how the band's device id is DISCOVERED here.
// - FDS (vendor_sleep_details): per-sleep-segment blob files keyed by
//   (wake_up_time, timezone, daily-type 8) holding the minute-level
//   nighttime HR/SpO2 series. gen_download_url requires did = the BAND'S
//   sid -- upstream passes the user id there, which answers -6 "device
//   not exist" for self access (verified 2026-08-17); the sid variant
//   mints a real FDS URL. Blobs arrive AES-wrapped only when the
//   response carries obj_key; otherwise gzip/zlib/raw.

import { decodeFdsAes, MiHealthClient, XiaomiAuth } from "./upstream/src/xiaomi/client.ts";
import {
  FDS_ALL_DAY_FILE_TYPE,
  FDS_SLEEP_DAILY_TYPE,
  decompressOrRawFdsContent,
  genDataIdKeyBytes,
  normalizeTimezoneTo15Min,
  parseAllDaySleepBytes,
} from "./upstream/src/xiaomi/fds.ts";
import { createHash } from "node:crypto";

const STATE_DIR = process.env.XIAOMI_WITNESS_STATE ?? "/realm/state/xiaomi-witness";
const LANE_DIR = process.env.XIAOMI_WITNESS_LANE ?? "/realm/data/captures/xiaomi-cloud";
const BASE = process.env.MI_HEALTH_BASE ?? "https://de.hlth.io.mi.com";
const WINDOW_DAYS = Number(process.env.XIAOMI_WITNESS_WINDOW_DAYS ?? "3");
const PARSER_VERSION = 2;

// Keys the raw plane actually serves for this band (probed 2026-08-17;
// single_*, energy, vitality, training_load, sleep_breathing, weight and
// exercise all answer empty). An unknown key is a normal per-lane failure,
// so extending this list is safe.
const RAW_KEYS = [
  "heart_rate",
  "sleep",
  "steps",
  "spo2",
  "stress",
  "calories",
  "intensity",
  "resting_heart_rate",
  "valid_stand",
];

const TOKEN_PATH = `${STATE_DIR}/auth-token.json`;
const SEEN_PATH = `${STATE_DIR}/seen-hashes.json`;

type Envelope = {
  kind: string;
  day: string | null;
  fetched_at: string;
  base: string;
  window_days: number;
  parser_version: number;
  content_sha256: string;
  data: unknown;
};

function isoDay(epochSeconds: number | undefined): string | null {
  if (!epochSeconds || !Number.isFinite(epochSeconds)) return null;
  return new Date(epochSeconds * 1000).toISOString().slice(0, 10);
}

async function sha256(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const auth = XiaomiAuth.fromToken(TOKEN_PATH);
const uid = Number(auth.token.user_id);
if (!uid) {
  console.error(`no user_id in ${TOKEN_PATH}; run the login flow first`);
  process.exit(64);
}
const client = new MiHealthClient(auth, BASE);

let seen: Record<string, string> = {};
try {
  seen = JSON.parse(await Bun.file(SEEN_PATH).text());
} catch {
  // First run.
}

const fetchedAt = new Date().toISOString();
const dayFile = `${LANE_DIR}/xiaomi-cloud-${fetchedAt.slice(0, 10).replaceAll("-", "")}.jsonl`;
const pending: string[] = [];
let appended = 0;
let unchanged = 0;
let failures = 0;

async function record(kind: string, day: string | null, data: unknown, subkey?: string): Promise<void> {
  const body = JSON.stringify(data);
  const hash = await sha256(body);
  const key = `${kind}:${day ?? "latest"}${subkey ? `:${subkey}` : ""}`;
  if (seen[key] === hash) {
    unchanged += 1;
    return;
  }
  seen[key] = hash;
  const envelope: Envelope = {
    kind,
    day,
    fetched_at: fetchedAt,
    base: BASE,
    window_days: WINDOW_DAYS,
    parser_version: PARSER_VERSION,
    content_sha256: hash,
    data,
  };
  pending.push(JSON.stringify(envelope));
  appended += 1;
}

function fetchFailed(name: string, error: unknown): void {
  failures += 1;
  pending.push(
    JSON.stringify({
      kind: "vendor_fetch_failed",
      lane: name,
      fetched_at: fetchedAt,
      base: BASE,
      reason: (error as Error).message,
    }),
  );
  console.error(`${name}: ${(error as Error).message}`);
}

async function lane<T extends { time?: number }>(name: string, run: () => Promise<Array<T>>): Promise<Array<T>> {
  try {
    const items = await run();
    for (const item of items) {
      await record(name, isoDay(item.time), item);
    }
    return items;
  } catch (error) {
    fetchFailed(name, error);
    return [];
  }
}

// -- Aggregated plane -------------------------------------------------------

type SleepSegment = { bedtime?: number; wake_up_time?: number; timezone?: number };
type SleepItem = { time?: number; segment_details?: SleepSegment[] };

const sleepItems = await lane<SleepItem>("vendor_sleep", () => client.getSleep(uid, WINDOW_DAYS));
await lane("vendor_hr_day", () => client.getHeartRate(uid, WINDOW_DAYS));
await lane("vendor_spo2_day", () => client.getSpo2History(uid, WINDOW_DAYS));
await lane("vendor_steps_day", () => client.getSteps(uid, WINDOW_DAYS));
await lane("vendor_stress_day", () =>
  client.getAggregatedData(
    uid,
    "stress",
    Math.trunc(Date.now() / 1000) - WINDOW_DAYS * 86_400,
    Math.trunc(Date.now() / 1000),
    WINDOW_DAYS + 1,
  ),
);

// -- Raw plane --------------------------------------------------------------
// One envelope per (key, day): the day's complete record array, so a sync
// burst that adds samples revises the whole day once instead of appending
// per sample. Values are parsed from their JSON strings; a string that is
// not JSON rides through untouched.

const bandSids = new Set<string>();
const rawStart = Math.trunc(Date.now() / 1000) - WINDOW_DAYS * 86_400;
const rawEnd = Math.trunc(Date.now() / 1000);

for (const key of RAW_KEYS) {
  try {
    const items = await client.getFitnessData(uid, key, rawStart, rawEnd, 100_000);
    const byDay = new Map<string, unknown[]>();
    for (const item of items as Array<{ sid?: string; time?: number; value?: unknown }>) {
      if (typeof item.sid === "string" && item.sid && !item.sid.startsWith("hlth.gen_")) bandSids.add(item.sid);
      const day = isoDay(item.time) ?? "unknown";
      let value = item.value;
      if (typeof value === "string") {
        try {
          value = JSON.parse(value);
        } catch {
          // Not JSON; keep the raw string.
        }
      }
      const bucket = byDay.get(day) ?? [];
      bucket.push({ ...item, value });
      byDay.set(day, bucket);
    }
    for (const [day, records] of byDay) {
      records.sort((a, b) => ((a as { time?: number }).time ?? 0) - ((b as { time?: number }).time ?? 0));
      await record(`vendor_raw_${key}`, day === "unknown" ? null : day, { key, count: records.length, records });
    }
  } catch (error) {
    fetchFailed(`vendor_raw_${key}`, error);
  }
}

// -- FDS plane --------------------------------------------------------------

function urlSafeB64(input: Uint8Array): string {
  return Buffer.from(input).toString("base64").replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}

async function fetchSleepDetails(sid: string, wakeUpTime: number, timezone: number): Promise<Uint8Array | null> {
  const key = genDataIdKeyBytes(
    wakeUpTime,
    normalizeTimezoneTo15Min(timezone),
    FDS_SLEEP_DAILY_TYPE,
    FDS_ALL_DAY_FILE_TYPE,
  );
  const suffix = `${urlSafeB64(key)}_${urlSafeB64(createHash("sha1").update(String(uid)).digest())}`;
  const response = await client.request("GET", "/healthapp/service/gen_download_url", {
    did: sid,
    relative_uid: uid,
    items: [{ timestamp: wakeUpTime, suffix }],
  });
  const info = (response.result as Record<string, unknown> | undefined)?.[`${suffix}_${wakeUpTime}`] as
    | Record<string, unknown>
    | undefined;
  const url = typeof info?.url === "string" ? info.url : "";
  if (!url) return null;
  const blob = await fetch(url, { signal: AbortSignal.timeout(30_000) });
  // gen_download_url mints signed URLs without checking existence; storage
  // 404 means the app never uploaded this blob. Band 10 measured 2026-08-17:
  // no night in a 200-key (anchor x type-byte) sweep existed -- its
  // nighttime series live on the raw plane instead (~1/min heart rate, SpO2
  // during sleep, captured above as vendor_raw_*). The lane stays armed for
  // firmware that resumes uploading; absence is a normal state, not a
  // failure.
  if (blob.status === 404) return null;
  if (!blob.ok) throw new Error(`FDS download HTTP ${blob.status}`);
  const content = new Uint8Array(await blob.arrayBuffer());
  const objKey = typeof info?.obj_key === "string" ? info.obj_key : "";
  return objKey ? new Uint8Array(decodeFdsAes(content, objKey)) : decompressOrRawFdsContent(content);
}

// One blob per sleep segment (long sleep or nap). A missing blob is a
// normal state for a fresh night, not a failure. Raw-first: the decrypted
// bytes ride along base64 even when the parser cannot read them, so a
// future firmware format bump costs analysis, never data.
for (const item of sleepItems) {
  for (const segment of item.segment_details ?? []) {
    if (!segment.wake_up_time) continue;
    try {
      let content: Uint8Array | null = null;
      let usedSid: string | null = null;
      for (const sid of bandSids) {
        content = await fetchSleepDetails(sid, segment.wake_up_time, segment.timezone ?? 0);
        if (content) {
          usedSid = sid;
          break;
        }
      }
      if (!content) continue;
      const parsed = parseAllDaySleepBytes(content);
      await record(
        "vendor_sleep_details",
        isoDay(segment.wake_up_time),
        {
          sid: usedSid,
          bedtime: segment.bedtime ?? null,
          wake_up_time: segment.wake_up_time,
          timezone: segment.timezone ?? null,
          report: parsed?.report ?? null,
          records: parsed?.records ?? null,
          raw_b64: Buffer.from(content).toString("base64"),
        },
        String(segment.wake_up_time),
      );
    } catch (error) {
      fetchFailed("vendor_sleep_details", error);
    }
  }
}

// -- Flush ------------------------------------------------------------------

if (pending.length > 0) {
  const { appendFileSync, mkdirSync } = await import("node:fs");
  mkdirSync(LANE_DIR, { recursive: true });
  appendFileSync(dayFile, pending.join("\n") + "\n");
}
await Bun.write(SEEN_PATH, JSON.stringify(seen, null, 2) + "\n");

console.log(
  `xiaomi-witness: appended=${appended} unchanged=${unchanged} failures=${failures} sids=${[...bandSids].join(",") || "-"} -> ${dayFile}`,
);
// Partial failure still lands what it fetched; only a broadly failed pass
// (usually an expired token) should alarm.
process.exit(failures >= 5 ? 1 : 0);
