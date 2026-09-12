# sinnix-ai — on-demand control plane for the local AI services
# (stt, tts, kokoro, ollama, litellm, llama-cpp profiles, comfyui, musicgen,
# ocr, open-webui). The module declares the live
# service and runtime surfaces; scripts/sinnix-ai is a thin inventory/action
# reader.
{
  config,
  lib,
  pkgs,
  helpers,
  ...
}:
let
  scriptPkgs = helpers.mkSinnixPackagesFor pkgs;
  systemdSocketProxyd = "${pkgs.systemd}/lib/systemd/systemd-socket-proxyd";

  # Backends declare `partOf` and NOTHING stronger. PartOf propagates
  # stop/restart only, which frees the GPU when the proxy idles out. BindsTo
  # also implies Requires, so any backend start pulls in the proxy outside
  # socket activation, where systemd-socket-proxyd has no listen fds, exits 1,
  # and propagates that failure back into the backend.
  #
  # Every value the front door needs is read from the backend's own runtime
  # surface: endpoints, the idle window, the readiness bound, and the
  # admission key. The backend module is the single place any of them is
  # written, so a proxy cannot drift from the service it fronts.
  #
  # idleTimeout/readinessTimeout have no default: the right value differs per
  # backend. The proxy forwards as soon as ExecStart runs, but backends bind
  # their port only after loading weights (~2s to ~105s) and it does not
  # retry -- requires+after order unit starts, not port binds. waitForBackend
  # gates ExecStart on a real TCP accept, so a cold request is slow, not
  # refused.
  mkProxy =
    name:
    let
      surface = config.sinnix.runtime.surfaces.${name};
      backendUnit = surface.unit;
      inherit (surface.activation)
        publicEndpoint
        backendEndpoint
        idleTimeout
        readinessTimeout
        exclusiveResource
        ;
      backendParts = lib.splitString ":" backendEndpoint;
      backendHost = lib.elemAt backendParts 0;
      backendPort = lib.elemAt backendParts 1;
      proxy = "${name}-proxy";
      waitForBackend = pkgs.writeShellApplication {
        name = "${proxy}-wait-backend";
        runtimeInputs = [ pkgs.coreutils ];
        text = ''
          deadline=$((SECONDS + ${toString readinessTimeout}))
          until (exec 3<>"/dev/tcp/${backendHost}/${backendPort}") 2>/dev/null; do
            if [ "$SECONDS" -ge "$deadline" ]; then
              echo "${proxy}: timed out after ${toString readinessTimeout}s waiting for ${backendUnit} to listen on ${backendEndpoint}" >&2
              exit 1
            fi
            sleep 0.2
          done
        '';
      };
    in
    {
      inherit proxy backendUnit exclusiveResource;
      socket = {
        description = "Socket activation front door for ${backendUnit}";
        wantedBy = [ "sockets.target" ];
        listenStreams = [ publicEndpoint ];
        socketConfig = {
          # systemd's default (200 triggers in 2s) is sized for cheap
          # short-lived handlers. A cold model load holds the accept backlog
          # for as long as readinessTimeout, and an impatient client retrying
          # without backoff can spend that budget in one burst -- after which
          # the socket is dead for good, with no automatic recovery anywhere.
          # Allow a generous burst over a long window instead: the limit
          # exists to catch a genuine activation loop, not client impatience.
          TriggerLimitIntervalSec = "60s";
          TriggerLimitBurst = 2000;
        };
      };
      service = {
        description = "Idle-aware socket proxy for ${backendUnit}";
        requires = [ backendUnit ];
        after = [ backendUnit ];
        serviceConfig = {
          ExecStartPre = "${waitForBackend}/bin/${proxy}-wait-backend";
          ExecStart = "${systemdSocketProxyd} --exit-idle-time=${idleTimeout} ${backendEndpoint}";
          Restart = "no";
        };
      };
    };

  # AI membership and activation are both owned by the backend surface.
  backendNames = lib.naturalSort (
    lib.attrNames (
      lib.filterAttrs (
        _: surface: surface.ai != null && surface.activation.mode == "socket-proxy"
      ) config.sinnix.runtime.surfaces
    )
  );
  proxies = lib.genAttrs backendNames mkProxy;
  enabledProxies = proxies;

  # Every rendered fragment is gated on its own backend's enable flag alone.
  forEachProxy = render: lib.mkMerge (lib.mapAttrsToList (_: render) enabledProxies);

  # ── Exclusive-resource admission mesh ────────────────────────────────────
  # Backends whose surface names the same `exclusiveResource` hold it alone:
  # each one's (service, proxy) pair conflicts with every peer's. Computing the
  # pairwise matrix from the declared keys keeps a newly admitted backend from
  # landing asymmetric, and keeps a backend that drops the key from leaving a
  # one-sided edge behind. CPU-only or CPU-pinned backends (stt, kokoro,
  # litellm, llama-cpp) declare no key and coexist with a resident model.
  meshMembers = lib.filterAttrs (_: proxy: proxy.exclusiveResource != null) enabledProxies;
  exclusivityConflicts = lib.mkMerge (
    lib.mapAttrsToList (
      name: proxy:
      let
        peerUnits =
          lib.concatMap
            (peer: [
              peer.backendUnit
              "${peer.proxy}.service"
            ])
            (
              lib.attrValues (
                lib.filterAttrs (
                  peerName: peer: peerName != name && peer.exclusiveResource == proxy.exclusiveResource
                ) meshMembers
              )
            );
      in
      {
        ${lib.removeSuffix ".service" proxy.backendUnit}.conflicts = peerUnits;
        ${proxy.proxy}.conflicts = peerUnits;
      }
    ) meshMembers
  );

in
{
  environment.systemPackages = [ scriptPkgs.sinnix-ai ];
  systemd.sockets = forEachProxy (proxy: {
    ${proxy.proxy} = proxy.socket;
  });
  systemd.services = lib.mkMerge [
    (forEachProxy (proxy: {
      ${proxy.proxy} = proxy.service;
    }))
    exclusivityConflicts
  ];
}
