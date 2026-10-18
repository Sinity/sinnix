// Xiaomi cloud capture: one sync pass (sinnix-ogll).
//
// A second, independent source for the band data, read from Xiaomi's cloud
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

// Handle informational/invalid requests before importing the credential client.
const args = process.argv.slice(2);
if (args.length > 0) {
  const help = args.length === 1 && (args[0] === "--help" || args[0] === "-h");
  const usage = "Usage: sinnix capture-xiaomi-cloud\n\nRun one cloud sync pass. Takes no arguments.";
  if (help) console.log(usage);
  else console.error(usage);
  process.exit(help ? 0 : 2);
}

// Overlap delayed uploads normally; recovery may explicitly widen to 35 days.
const WINDOW_DAYS = Number(process.env.XIAOMI_CLOUD_WINDOW_DAYS ?? "7");
if (!Number.isInteger(WINDOW_DAYS) || WINDOW_DAYS < 1 || WINDOW_DAYS > 35) {
  console.error("XIAOMI_CLOUD_WINDOW_DAYS must be an integer from 1 to 35");
  process.exit(64);
}

const { MiHealthClient, XiaomiAuth } = await import("./upstream/src/xiaomi/client.ts");

process.umask(0o077);

const STATE_DIR = process.env.XIAOMI_CLOUD_STATE ?? "/realm/state/xiaomi-witness";
// The service passes both of these; the defaults are for running this file by
// hand and deliberately name the same places the module does.
const LANE_DIR = process.env.XIAOMI_CLOUD_LANE ?? "/realm/health/xiaomi-cloud";
const BASE = process.env.MI_HEALTH_BASE ?? "https://de.hlth.io.mi.com";
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
// Written when the cloud refuses to refresh the token. The service unit
// carries ConditionPathExists=!<marker>, so the timer keeps firing but the
// pass is skipped until the login flow clears it.
const EXPIRED_MARKER = `${STATE_DIR}/credential-expired`;

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
let credentialFailures = 0;

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
  if (/serviceToken|token refresh|401|403/i.test((error as Error).message ?? "")) {
    credentialFailures += 1;
  }
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
const rawEnd = Math.trunc(Date.now() / 1000);
// Each revision describes a UTC day. Never let a rolling first-day suffix
// supersede a complete day merely because it was fetched more recently.
const rawStart = Math.floor((rawEnd - WINDOW_DAYS * 86_400) / 86_400) * 86_400;

for (const key of RAW_KEYS) {
  try {
    const byDay = new Map<string, unknown[]>();
    // The vendor can silently truncate multi-day responses below our requested limit.
    // Read one UTC day per request for ordinary and recovery passes alike.
    const batchSeconds = 86_400;
    for (let start = rawStart; start <= rawEnd;) {
      const end = Math.min(start + batchSeconds - 1, rawEnd);
      const items = await client.getFitnessData(uid, key, start, end, 100_000);
      if (items.length >= 100_000) {
        throw new Error("raw response reached its record limit; refusing an incomplete day revision");
      }
      if (WINDOW_DAYS > 7) {
        console.log(`capture-xiaomi-cloud raw-window: key=${key} start=${start} end=${end} count=${items.length}`);
      }
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
      start = end + 1;
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

// A quiet successful pass otherwise writes nothing, leaving readers unable to
// distinguish healthy write-on-change behavior from a stream whose newest
// records are only failures. Keep one small status receipt per scheduled pass.
pending.push(
  JSON.stringify({
    kind: "vendor_sync_pass",
    day: null,
    fetched_at: fetchedAt,
    base: BASE,
    window_days: WINDOW_DAYS,
    parser_version: PARSER_VERSION,
    appended,
    unchanged,
    failures,
    band_sids: [...bandSids],
  }),
);

if (pending.length > 0) {
  const { appendFileSync, mkdirSync } = await import("node:fs");
  mkdirSync(LANE_DIR, { recursive: true });
  appendFileSync(dayFile, pending.join("\n") + "\n");
}
await Bun.write(SEEN_PATH, JSON.stringify(seen, null, 2) + "\n");

console.log(
  `capture-xiaomi-cloud: appended=${appended} unchanged=${unchanged} failures=${failures} sids=${[...bandSids].join(",") || "-"} -> ${dayFile}`,
);
// Partial failure still lands what it fetched; only a broadly failed pass
// should alarm. An expired credential alarms once: the marker makes every
// later pass a skipped unit rather than a failed one.
if (failures >= 5 && credentialFailures === failures) {
  const { writeFileSync } = await import("node:fs");
  writeFileSync(
    EXPIRED_MARKER,
    JSON.stringify({ fetched_at: fetchedAt, failures, reason: "token refresh refused" }) + "\n",
  );
  console.error(`capture-xiaomi-cloud: credential expired; run sinnix xiaomi-cloud-login to resume`);
}
process.exit(failures >= 5 ? 1 : 0);
