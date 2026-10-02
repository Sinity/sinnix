# Proton/OpenAI scoped egress

`sinnix.services.proton-openai` keeps ordinary host traffic on the normal
network while routing selected OpenAI surfaces through one Proton WireGuard
profile.

The generated Proton profile is deployed by agenix as
`/run/agenix/proton-openai-wireguard`. The module creates a WireGuard
interface without changing the host default route, installs a source-policy
routing table for the tunnel address, and runs a loopback-only tinyproxy whose
outbound sockets bind to that address.

Consumers:

- ChatGPT desktop reads `/etc/sinnix/openai-proxy-url` and starts
  Electron/Chromium with `--proxy-server`.
- The default subscription-authenticated `codex` wrapper exports HTTP(S)
  proxy variables. `codex-deepseek` and `codex-local` remain direct.
- Chrome receives an inline data URL rendered from the same script as
  `/etc/sinnix/openai-proxy.pac`; only ChatGPT/OpenAI origins are
  proxied and every other site is `DIRECT`.

The lane is fail-closed for participating clients: if the tunnel/proxy is down,
their proxied OpenAI requests fail rather than falling back through the host
route. Disabling the service also removes the Chrome PAC launch flag.

Existing Chrome and desktop processes need a relaunch to use changed launch
flags. The profile expires annually; renew it through Proton Downloads and
replace the encrypted deployment input before expiry. DNS lookup by the proxy
uses the host resolver; this lane scopes egress, not host-wide DNS privacy.

## Rooted Android phone

`pkgs/phone-openai-vpn/route.sh` creates a kernel WireGuard interface and routes
only the installed `com.openai.chatgpt` UID through table 201. It derives the
UID from Package Manager at each start. Tailscale keeps the Android VPN slot,
and other applications keep their existing routes. Interface-scoped IPv4
masquerading handles source addresses retained by Android's network service.
App IPv6 is terminal because the phone kernel does not provide IPv6 NAT.

The phone needs root, kernel WireGuard support, and `wireguard-tools` in the
existing Sinnix Debian chroot. Use a separate Proton-generated profile from
the desktop's profile. The root-only deployment lives in
`/data/adb/sinnix/proton-openai/`: `profile.conf` mode 0600 and `route.sh`
mode 0700. `service.sh` is installed as
`/data/adb/service.d/sinnix-proton-openai.sh` mode 0700. Magisk invokes it
once at boot and retains errors in that private directory's `boot.log`.

With an explicitly selected ADB device, root can invoke `route.sh up`,
`route.sh status`, or `route.sh down`. Down intentionally restores ordinary
ChatGPT routing; a failed tunnel while enabled keeps the app's terminal
routes. Redeploy the tracked scripts when changing them. Verify both a request
under the app UID and an ordinary request, plus an outage test and invocation
of the boot hook. A successful hook invocation does not verify a reboot.
