# Loopback/tailnet port allocations for sinnix-prime, in one place.
#
# WHY THIS FILE EXISTS. Ports written as literals at each use site collide
# silently: nothing at eval time knows both numbers exist, so the first
# symptom is an activation-time `Address already in use` on whichever unit
# loses the race. Declared once as data and asserted over at eval time (the
# same shape as runtime-defaults.nix's resource classes), a duplicate fails
# the build instead of the machine, and modules consume ports by name.
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
  stt = {
    public = 8090; # OpenAI-compatible /v1/audio/transcriptions (STT hub)
    backend = 8091;
  };
  kokoro = {
    public = 8890; # OpenAI-compatible /v1/audio/speech (TTS)
    backend = 8891; # NB: the container listens on 8880 *inside* its namespace
  };
  openWebui = 8080;
  # ComfyUI, TTS, MusicGen, and OCR are OCI containers (CDI GPU passthrough)
  # in the same public/backend socket-proxy shape as the native backends
  # above: the container publishes on the PRIVATE backend port only, and
  # systemd-socket-proxyd answers the PUBLIC port clients already know
  # (modules/services/ai-control.nix).
  comfyui = {
    public = 8188;
    backend = 8189;
  };
  tts = {
    public = 8000; # OpenedAI-Speech bridge (container)
    backend = 8001;
  };
  musicgen = {
    public = 8010;
    backend = 8011;
  };
  ocr = {
    public = 8020;
    backend = 8021;
  };
  llamaCpp = {
    public = 8081; # reranker (/v1/rerank)
    backend = 8082;
  };
  museGlimmer = {
    public = 8083; # direct OpenAI-compatible Glimmer endpoint
    backend = 8084;
  };

  # ── Other ────────────────────────────────────────────────────────────────
  chromeDevtools = 9222; # live Chrome remote-debugging port
  phoneStream = 8940; # persistent phone->prime telemetry push (tailscale0 only)
}
