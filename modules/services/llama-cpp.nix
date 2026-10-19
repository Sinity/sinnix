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
      # The server listens only on a Unix socket (llama-server binds one when
      # --host ends in .sock), so the Caddy front door is its sole TCP entry point.
      backendSocket = name: "/run/${name}/llama.sock";
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
          backendEndpoint = backendSocket name;
          inherit (profile) idleTimeout readinessTimeout;
          exclusiveResource = if profile.requiresCuda then "gpu-inference" else null;
        };
        observe = {
          enable = true;
          restartable = true;
        };
      };
      mkExecStart =
        name: profile:
        lib.escapeShellArgs (
          [
            "${if profile.requiresCuda then pkgs.llama-cpp-cuda else pkgs.llama-cpp}/bin/llama-server"
            "--model"
            "${modelRoot}/gguf/${profile.model}"
            "--host"
            (backendSocket name)
          ]
          ++ profile.arguments
        );
      mkService = name: profile: {
        description = profile.description;
        wantedBy = [ ];
        after = [ "network.target" ];
        serviceConfig = lib.mkMerge [
          {
            ExecStart = mkExecStart name profile;
            RuntimeDirectory = name;
          }
          (
            if profile.dynamicUser then
              {
                DynamicUser = true;
                StateDirectory = name;
                CacheDirectory = name;
                WorkingDirectory = "/var/lib/${name}";
                Environment = [ "LLAMA_CACHE=/var/cache/${name}" ];
                NoNewPrivileges = true;
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
    };
} args
