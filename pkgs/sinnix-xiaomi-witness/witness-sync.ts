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
// aggregate as more band data syncs in, so the same day is legitimately
// re-fetched every pass; a revision is appended (the history of revisions
// is evidence), an identical re-read is not (an unchanged day re-written
// 48x/day is the duplication defect the health coverage report exists to
// catch). Raw fidelity: the `data` field is the complete parsed API item,
// not a reduction of it.
//
// Endpoint notes, all measured against this account (EU, de shard):
// - get_aggregated_fitness_data_by_time / get_fitness_data_by_time accept
//   the OWN uid as relative_uid and return real data.
// - get_latest_fitness_data and the relatives/* endpoints are family-care
//   surfaces: they answer -8/-6 for self and are not used here.
// - The FDS sleep-detail blobs need the band's device id (did), which this
//   client cannot discover yet -- follow-up on the bead.

import { MiHealthClient, XiaomiAuth } from "./upstream/src/xiaomi/client.ts";

const STATE_DIR = process.env.XIAOMI_WITNESS_STATE ?? "/realm/state/xiaomi-witness";
const LANE_DIR = process.env.XIAOMI_WITNESS_LANE ?? "/realm/data/captures/xiaomi-cloud";
const BASE = process.env.MI_HEALTH_BASE ?? "https://de.hlth.io.mi.com";
const WINDOW_DAYS = Number(process.env.XIAOMI_WITNESS_WINDOW_DAYS ?? "3");
const PARSER_VERSION = 1;

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

async function record(kind: string, day: string | null, data: unknown): Promise<void> {
  const body = JSON.stringify(data);
  const hash = await sha256(body);
  const key = `${kind}:${day ?? "latest"}`;
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

async function lane(name: string, run: () => Promise<Array<{ time?: number }>>): Promise<void> {
  try {
    for (const item of await run()) {
      await record(name, isoDay(item.time), item);
    }
  } catch (error) {
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
}

await lane("vendor_sleep", () => client.getSleep(uid, WINDOW_DAYS));
await lane("vendor_hr_day", () => client.getHeartRate(uid, WINDOW_DAYS));
await lane("vendor_spo2_day", () => client.getSpo2History(uid, WINDOW_DAYS));
await lane("vendor_steps_day", () => client.getSteps(uid, WINDOW_DAYS));
await lane("vendor_stress_day", () =>
  client.getAggregatedData(uid, "stress", Math.trunc(Date.now() / 1000) - WINDOW_DAYS * 86_400, Math.trunc(Date.now() / 1000), WINDOW_DAYS + 1),
);

if (pending.length > 0) {
  const { appendFileSync, mkdirSync } = await import("node:fs");
  mkdirSync(LANE_DIR, { recursive: true });
  appendFileSync(dayFile, pending.join("\n") + "\n");
}
await Bun.write(SEEN_PATH, JSON.stringify(seen, null, 2) + "\n");

console.log(
  `xiaomi-witness: appended=${appended} unchanged=${unchanged} failures=${failures} -> ${dayFile}`,
);
// Partial failure still lands what it fetched; only a fully failed pass
// (every lane down, usually an expired token) should alarm.
process.exit(failures >= 5 ? 1 : 0);
