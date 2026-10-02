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
- Chrome uses `/etc/sinnix/openai-proxy.pac`; only ChatGPT/OpenAI origins are
  proxied and every other site is `DIRECT`.

The lane is fail-closed for participating clients: if the tunnel/proxy is down,
their proxied OpenAI requests fail rather than falling back through the host
route. Disabling the service also removes the Chrome PAC launch flag.

Existing Chrome and desktop processes need a relaunch to use changed launch
flags. The profile expires annually; renew it through Proton Downloads and
replace the encrypted deployment input before expiry. DNS lookup by the proxy
uses the host resolver; this lane scopes egress, not host-wide DNS privacy.
