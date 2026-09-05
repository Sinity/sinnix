// Interactive login for the Xiaomi cloud witness: mints a QR ticket and
// waits for confirmation, then saves the token where the sync entry reads
// it and probes the API once.
//
// No scanning required, despite the QR: the printed LOGIN_URL, opened in
// any browser holding an authenticated Xiaomi web session (the operator's
// Chrome qualifies -- the mi-unlock automation lives off the same session),
// renders a "Confirm sign-in" page whose button completes the login. That
// makes re-login agent-drivable end to end:
//
//   sinnix xiaomi-witness-login          # prints LOGIN_URL, waits
//   sinnix-chrome-control agent-window --url <LOGIN_URL>   # then click Sign in
//
// The Mi Fitness app's scanner refuses this QR (it is minted for the
// sid=miothealth realm, the CN Mi Health app), which is why the browser
// route is the primary one, not a fallback.

import { MiHealthClient, XiaomiAuth } from "./upstream/src/xiaomi/client.ts";

const STATE_DIR = process.env.XIAOMI_WITNESS_STATE ?? "/realm/state/xiaomi-witness";
const BASE = process.env.MI_HEALTH_BASE ?? "https://de.hlth.io.mi.com";
const TOKEN_PATH = `${STATE_DIR}/auth-token.json`;

const auth = new XiaomiAuth();
console.log("requesting login ticket…");
const token = await auth.loginQr(async (qrImageUrl, loginUrl) => {
  console.log(`QR_IMAGE_URL=${qrImageUrl}`);
  console.log(`LOGIN_URL=${loginUrl}`);
  console.log("open LOGIN_URL in an authenticated browser and confirm (300s window)…");
});
auth.saveToken(TOKEN_PATH);
const { rmSync } = await import("node:fs");
rmSync(`${STATE_DIR}/credential-expired`, { force: true });
console.log(`TOKEN_SAVED user_id=${token.user_id} -> ${TOKEN_PATH}`);

const client = new MiHealthClient(auth, BASE);
const steps = await client.getSteps(Number(token.user_id), 2);
console.log(`API_OK base=${BASE} step_days=${steps.length}`);
