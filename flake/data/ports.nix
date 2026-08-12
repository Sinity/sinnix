# Loopback/tailnet port allocations for sinnix-prime, in one place.
#
# WHY THIS FILE EXISTS. Ports were previously written as literals wherever a
# service happened to need one. On 2026-08-13 two services landed in the same
# session both claiming 8880 (the web hub and the Kokoro TTS proxy); the
# collision only surfaced at activation, as
# `kokoro-proxy.socket: Address already in use`. Nothing in eval could have
# caught it, because nothing knew both numbers existed.
#
# This is the same shape the repo already uses for resource classes in
# runtime-defaults.nix: declare the facts once as data, assert over them at
# eval time, and let modules consume by name. A module that says
# `ports.kokoro.public` cannot silently collide with one that says
# `ports.hub.self`, and adding a duplicate fails the build rather than the
# machine.
#
# CONVENTION. Every entry is a loopback port unless a comment says otherwise.
# Socket-activated AI backends follow the docs/local-ai-activation.md pattern:
# a PUBLIC front door that clients use, and a PRIVATE backend the
# systemd-socket-proxyd unit forwards to. Keep those adjacent so the pairing is
# obvious.
#
# WHY NOT UNIX SOCKETS EVERYWHERE. Where a service is genuinely local-only and
# speaks a protocol we control, a unix socket IS better -- filesystem
# permissions instead of "anything on loopback", no port space, no collisions
# at all. The ops-reducer already does this (%t/sinnix/ops.sock). TCP survives
# here for the cases that need it: OpenAI-compatible HTTP clients, containers
# with their own network namespace, and anything reached across the tailnet.
{
  # ── Operator surfaces ────────────────────────────────────────────────────
  hub = {
    self = 8880; # Caddy: dashboard, reports, AI panel (loopback + tailscale0)
    openWebui = 8881; # tailnet republish of the Open WebUI frontend
    comfyui = 8882; # tailnet republish of the ComfyUI frontend
    koboldcpp = 8883; # tailnet republish of the KoboldCpp frontend
  };
  opsReducer = 3090; # read-only current-state reducer (also a unix socket)

  # ── Local AI backends (public front door / private backend) ──────────────
  ollama = {
    public = 11434;
    backend = 11435;
  };
  koboldcpp = {
    public = 5001;
    backend = 5002;
  };
  litellm = {
    public = 4000;
    backend = 4001;
  };
  whisper = {
    public = 8090; # OpenAI-compatible /v1/audio/transcriptions (STT hub)
    backend = 8091;
  };
  kokoro = {
    public = 8890; # OpenAI-compatible /v1/audio/speech (TTS)
    backend = 8891; # NB: the container listens on 8880 *inside* its namespace
  };
  openWebui = 8080;
  comfyui = 8188;
  tts = 8000; # OpenedAI-Speech bridge (container)
  llamaCpp = 8081; # reranker (/v1/rerank)

  # ── Other ────────────────────────────────────────────────────────────────
  chromeDevtools = 9222; # live Chrome remote-debugging port
}
