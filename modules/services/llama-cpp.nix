# llama.cpp inference profiles rendered through one service plane. Profile
# data owns model/fit arguments; this module owns units, lifecycle and policy.
{
  mkServiceModule,
  lib,
  pkgs,
  helpers,
  ...
}@args:
let
  profileType = lib.types.submodule {
    options = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = true;
      };
      description = lib.mkOption { type = lib.types.str; };
      portKey = lib.mkOption { type = lib.types.str; };
      model = lib.mkOption { type = lib.types.str; };
      requiresCuda = lib.mkOption { type = lib.types.bool; };
      dynamicUser = lib.mkOption { type = lib.types.bool; };
      idleTimeout = lib.mkOption { type = lib.types.str; };
      readinessTimeout = lib.mkOption { type = lib.types.ints.positive; };
      arguments = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ ];
      };
    };
  };
in
mkServiceModule {
  name = "llama-cpp";
  description = "profiled llama.cpp inference plane";
  docs = "docs/local-ai-activation.md";
  extraOptions.profiles = args.lib.mkOption {
    type = args.lib.types.attrsOf profileType;
    default = helpers.data.localModels.llamaCppProfiles;
    description = "Named llama.cpp endpoints rendered as systemd services.";
  };
  configFn =
    {
      cfg,
      config,
      lib,
      pkgs,
      helpers,
      ...
    }:
    let
      user = config.sinnix.user.name;
      modelRoot = config.sinnix.paths.modelsRoot;
      enabledProfiles = lib.filterAttrs (_: profile: profile.enable) cfg.profiles;
      portFor = profile: helpers.data.ports.${profile.portKey};
      mkSurface = name: profile: {
        unit = "${name}.service";
        resourceClass = "ordinary";
        ai = {
          backendKind = "native";
          inherit (profile) requiresCuda;
        };
        activation = {
          mode = "socket-proxy";
          publicEndpoint = "127.0.0.1:${toString (portFor profile).public}";
          backendEndpoint = "127.0.0.1:${toString (portFor profile).backend}";
          inherit (profile) idleTimeout readinessTimeout;
          exclusiveResource = if profile.requiresCuda then "gpu-inference" else null;
          dependsOn = [ "${name}-proxy" ];
        };
        observe = {
          enable = true;
          restartable = true;
        };
      };
      mkExecStart =
        profile:
        lib.escapeShellArgs (
          [
            "${if profile.requiresCuda then pkgs.llama-cpp-cuda else pkgs.llama-cpp}/bin/llama-server"
            "--model"
            "${modelRoot}/gguf/${profile.model}"
            "--host"
            "127.0.0.1"
            "--port"
            (toString (portFor profile).backend)
          ]
          ++ profile.arguments
        );
      mkService = name: profile: {
        description = profile.description;
        wantedBy = [ ];
        after = [ "network.target" ];
        partOf = [ "${name}-proxy.service" ];
        serviceConfig = lib.mkMerge [
          { ExecStart = mkExecStart profile; }
          (
            if profile.dynamicUser then
              {
                DynamicUser = true;
                StateDirectory = name;
                CacheDirectory = name;
                WorkingDirectory = "/var/lib/${name}";
                Environment = [ "LLAMA_CACHE=/var/cache/${name}" ];
                AmbientCapabilities = [ "" ];
                CapabilityBoundingSet = [ "" ];
                LockPersonality = true;
                MemoryDenyWriteExecute = true;
                NoNewPrivileges = true;
                PrivateMounts = true;
                PrivateTmp = true;
                PrivateUsers = true;
                ProcSubset = "pid";
                ProtectClock = true;
                ProtectControlGroups = true;
                ProtectHome = true;
                ProtectHostname = true;
                ProtectKernelLogs = true;
                ProtectKernelModules = true;
                ProtectKernelTunables = true;
                ProtectProc = "invisible";
                ProtectSystem = "strict";
                RemoveIPC = true;
                RestrictAddressFamilies = [
                  "AF_INET"
                  "AF_INET6"
                  "AF_UNIX"
                ];
                RestrictNamespaces = true;
                RestrictRealtime = true;
                RestrictSUIDSGID = true;
                SystemCallArchitectures = "native";
                SystemCallErrorNumber = "EPERM";
                SystemCallFilter = [
                  "@system-service"
                  "~@privileged"
                ];
              }
            else
              {
                User = user;
                Group = "users";
                SupplementaryGroups = [
                  "video"
                  "render"
                ];
              }
          )
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "${name}.service";
          })
          (lib.sinnix.systemd.mkRestartPolicy {
            strategy = "on-failure";
            delaySec = if profile.dynamicUser then 300 else 30;
          })
        ];
      };
    in
    {
      sinnix.runtime.surfaces = lib.mapAttrs mkSurface enabledProfiles;
      systemd.services = lib.mapAttrs mkService enabledProfiles;
      systemd.tmpfiles.rules = [ "d ${modelRoot}/gguf 0755 ${user} users -" ];
      sinnix.runtime.dataStores.llama-cpp-models = {
        path = "${modelRoot}/gguf";
        class = "cache";
      };
    };
} args
