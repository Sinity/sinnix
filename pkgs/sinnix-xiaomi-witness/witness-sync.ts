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
// Two planes, both measured against this account (EU, de shard):
// - AGGREGATED (vendor_sleep / vendor_*_day): get_aggregated_fitness_data_
//   by_time daily summaries. Own uid works as relative_uid;
//   get_latest_fitness_data and relatives/* are family-care surfaces
//   answering -8/-6 for self and are not used.
// - RAW (vendor_raw_*): get_fitness_data_by_time returns the band's dense
//   series -- ~2-minute heart rate, continuous SpO2 and stress, 5-minute
//   steps/calories, and a per-night sleep object carrying the complete
//   minute-level stage transition list plus avg_breath and sleep_efficiency.
//   Each record names its writing device in `sid` (the phone's synthetic
//   records use an "hlth.gen_" prefix).
//
// Both planes are kept, because neither derives from the other. Checked
// field by field 2026-08-17: the aggregates carry vendor-COMPUTED numbers
// with no raw counterpart -- personalized heart-rate zone durations,
// abnormal_hr_count, lack_spo2_count, the stress band histogram, and the
// sleep_score -- and the raw plane carries the samples the aggregates
// reduce. Dropping either would lose data that cannot be recomputed here.
//
// There WAS a third plane. Xiaomi's FDS blob store serves per-night detail
// files, and this file used to fetch them: mint a signed URL from
// gen_download_url (did = the band's sid, not the user id -- upstream's
// version answers -6 "device not exist" for self access), download, AES-
// unwrap under the response's obj_key, parse. It never once returned a
// blob. A 200-key sweep over every anchor x type-byte combination found no
// object for any night: this band does not upload them. The capability that
// path existed to deliver -- minute-level sleep staging -- arrives on the
// raw plane instead, in vendor_raw_sleep's `items[]`. So it is gone rather
// than "armed": a request per sleep segment per pass, forever, for data
// already in hand.

import { MiHealthClient, XiaomiAuth } from "./upstream/src/xiaomi/client.ts";

const STATE_DIR = process.env.XIAOMI_WITNESS_STATE ?? "/realm/state/xiaomi-witness";
// The service passes both of these; the defaults are for running this file by
// hand and deliberately name the same places the module does.
const LANE_DIR = process.env.XIAOMI_WITNESS_LANE ?? "/realm/data/health/xiaomi-cloud";
const BASE = process.env.MI_HEALTH_BASE ?? "https://de.hlth.io.mi.com";
// Seven days, not three. The cloud is the SLOW plane, measured 2026-08-17:
// Health Connect held band data from an hour ago while Xiaomi's servers had
// nothing newer than the previous afternoon, and forcing Mi Fitness's own
// sync job moved neither. A window has to outlast however long the app
// takes to upload, because a day that ages past its edge is never fetched
// at all -- the fetch is windowed, so a gap here is permanent, not late.
const WINDOW_DAYS = Number(process.env.XIAOMI_WITNESS_WINDOW_DAYS ?? "7");
const PARSER_VERSION = 2;

// Keys the raw plane actually serves for this band (probed 2026-08-17;
// single_*, energy, vitality, training_load, sleep_breathing, weight and
// exercise all answer empty). An unknown key is a normal per-lane failure,
// so extending this list is safe.
//
// `intensity` was here and is not: three days of fetching produced exactly
// one record, whose value was `{time}` -- a timestamp with no measurement
// attached. An endpoint that answers with the shape of data but none of it
// is worse than one that answers empty, because it mints a lane that looks
// alive on every dashboard that counts lanes.
const RAW_KEYS = [
  "heart_rate",
  "sleep",
  "steps",
  "spo2",
  "stress",
  "calories",
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

await lane("vendor_sleep", () => client.getSleep(uid, WINDOW_DAYS));
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
