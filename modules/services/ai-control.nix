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
  httpProxy = import ../lib/ai-http-proxy.nix { inherit lib; };
  systemdSocketProxyd = "${pkgs.systemd}/lib/systemd/systemd-socket-proxyd";

  # The backend and proxy bind their lifetimes to each other. The proxy
  # orders after the backend and its listening socket; the backend MUST NOT
  # order after the proxy, or cold/manual startup would have an ordering cycle.
  # Requiring the socket on the proxy supplies listen FDs even on a manual
  # backend start. PartOf additionally propagates explicit proxy restarts.
  # BindsTo is needed for a natural idle exit, which PartOf alone does not
  # propagate to the backend.
  #
  # Every value the proxy needs is read from the backend's own runtime
  # surface: endpoints, the idle window, the readiness bound, and the
  # admission key. The backend module is the single place any of them is
  # written, so a proxy cannot drift from the service it fronts.
  #
  # idleTimeout/readinessTimeout have no default: the right value differs per
  # backend. The proxy forwards as soon as ExecStart runs, but backends bind
  # their listener only after loading weights (~2s to ~105s) and it does not
  # retry -- requires+after order unit starts, not binds. waitForBackend
  # gates ExecStart on a real accept, so a cold request is slow, not
  # refused.
  mkProxy =
    name:
    let
      surface = config.sinnix.runtime.units.${name};
      backendUnit = surface.unit;
      inherit (surface.activation)
        publicEndpoint
        backendEndpoint
        idleTimeout
        readinessTimeout
        exclusiveResource
        ;
      # A backend endpoint is host:port, or an absolute path for a backend
      # that listens only on a Unix socket.
      unixBackend = lib.hasPrefix "/" backendEndpoint;
      backendParts = lib.splitString ":" backendEndpoint;
      listening =
        if unixBackend then
          "${pkgs.curl}/bin/curl --silent --output /dev/null --unix-socket ${backendEndpoint} http://localhost/"
        else
          ''(exec 3<>"/dev/tcp/${lib.elemAt backendParts 0}/${lib.elemAt backendParts 1}") 2>/dev/null'';
      proxy = "${name}-proxy";
      socketPath = "/run/sinnix-ai/${proxy}.sock";
      waitForBackend = pkgs.writeShellApplication {
        name = "${proxy}-wait-backend";
        runtimeInputs = [ pkgs.coreutils ];
        text = ''
          deadline=$((SECONDS + ${toString readinessTimeout}))
          until ${listening}; do
            if [ "$SECONDS" -ge "$deadline" ]; then
              echo "${proxy}: timed out after ${toString readinessTimeout}s waiting for ${backendUnit} to listen on ${backendEndpoint}" >&2
              exit 1
            fi
            sleep 0.2
          done
        '';
      };
      socket = {
        description = "Private activation socket for ${backendUnit}";
        wantedBy = [ "sockets.target" ];
        listenStreams = [ socketPath ];
        socketConfig = {
          SocketUser = config.sinnix.user.name;
          SocketGroup = config.services.caddy.group;
          SocketMode = "0660";
          DirectoryMode = "0755";
          RemoveOnStop = true;
          # systemd's default (200 triggers in 2s) is sized for cheap
          # short-lived handlers. A cold model load holds the accept backlog
          # for as long as readinessTimeout, and an impatient client retrying
          # without backoff can spend that budget in one burst -- after which
          # the socket is dead for good, with no automatic recovery anywhere.
          # Allow a generous burst over a long window instead: the limit
          # exists to catch a genuine activation loop, not client impatience.
          TriggerLimitIntervalSec = "60s";
          TriggerLimitBurst = 2000;
          Service = "${proxy}.service";
        };
      };
      # NixOS activation does not restart a changed .socket unit, so a changed
      # definition would keep its old listener until reboot. Naming the unit
      # after a hash of its definition makes a change a removed unit plus a
      # new one, which activation stops and starts natively.
      socketUnit = "${proxy}-${
        builtins.substring 0 8 (builtins.hashString "sha256" (builtins.toJSON socket))
      }";
    in
    {
      inherit
        proxy
        backendUnit
        exclusiveResource
        socket
        socketUnit
        ;
      consumers = surface.activation.consumers or [ ];
      httpConfig = httpProxy {
        inherit publicEndpoint backendEndpoint socketPath;
        inherit (surface.ai) browserRequests;
      };
      service = {
        description = "Idle-aware socket proxy for ${backendUnit}";
        requires = [ backendUnit ];
        # Closing/replacing the activation socket must also release the old
        # proxy's listen FD and backend, including during a host switch.
        bindsTo = [
          backendUnit
          "${socketUnit}.socket"
        ];
        after = [
          backendUnit
          "${socketUnit}.socket"
        ];
        serviceConfig = {
          # Preserve descriptor association across manager reloads and cold
          # manual starts, not only an earlier socket-triggered activation.
          Sockets = [ "${socketUnit}.socket" ];
          ExecStartPre = "${waitForBackend}/bin/${proxy}-wait-backend";
          ExecStart = "${systemdSocketProxyd} --exit-idle-time=${idleTimeout} ${backendEndpoint}";
          Restart = "no";
        };
      };
    };

  # AI membership and activation are both owned by the backend surface.
  backendNames = lib.naturalSort (
    lib.attrNames (
      lib.filterAttrs (_: surface: surface.ai != null && surface.activation.mode == "socket-proxy") (
        builtins.removeAttrs config.sinnix.runtime.units [ "ai-http" ]
      )
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
  # Keep membership unconditional: conditioning this registry entry on a
  # query of the same registry creates a module fixed-point recursion.
  # Observation follows the actual Caddy enablement instead.
  sinnix.runtime.units.ai-http = {
    unit = "caddy.service";
    ai = null;
    resourceClass = "ordinary";
    notifyOnFailure = backendNames != [ ];
    operatorRestart = backendNames != [ ];
  };
  services.caddy = lib.mkIf (backendNames != [ ]) {
    enable = true;
    # The native reload route uses this owner-only Unix admin socket, never
    # an additional loopback HTTP administration endpoint.
    globalConfig = "admin unix//run/caddy/admin.sock\nauto_https off\npersist_config off\ngrace_period 5s";
    extraConfig = lib.concatMapStringsSep "\n" (name: proxies.${name}.httpConfig) backendNames;
  };
  systemd.sockets = forEachProxy (proxy: {
    ${proxy.socketUnit} = proxy.socket;
  });
  systemd.services = lib.mkMerge [
    {
      caddy = lib.mkIf (backendNames != [ ]) {
        wants = map (name: "${proxies.${name}.socketUnit}.socket") backendNames;
        after = map (name: "${proxies.${name}.socketUnit}.socket") backendNames;
        serviceConfig = {
          RuntimeDirectory = "caddy";
          RuntimeDirectoryMode = "0700";
        };
      };
    }

    (forEachProxy (
      proxy:
      lib.mkMerge [
        {
          ${proxy.proxy} = proxy.service;
          ${lib.removeSuffix ".service" proxy.backendUnit} = {
            partOf = [ "${proxy.proxy}.service" ];
            bindsTo = [ "${proxy.proxy}.service" ];
          };
        }
        (lib.mkMerge (
          map (consumer: {
            ${consumer.unit} = {
              requires = [ "caddy.service" ];
              after = [ "caddy.service" ];
            };
          }) proxy.consumers
        ))
      ]
    ))
    exclusivityConflicts
  ];
}
