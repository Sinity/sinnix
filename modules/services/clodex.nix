{
  mkServiceModule,
  config,
  lib,
  pkgs,
  ...
}@args:
let
  user = config.sinnix.user.name;
  clodex = "/home/${user}/.local/bin/clodex";
in
mkServiceModule {
  name = "clodex";
  description = "Local Clodex proxy for subscription-authenticated Claude Code sessions";
  docs = "docs/clodex.md";
  surface = {
    unit = "sinnix-clodex.service";
    manager = "user";
    resourceClass = "ordinary";
    notifyOnFailure = true;
    operatorRestart = true;
  };
  configFn =
    { cfg, ... }:
    let
      reconcileAliases = pkgs.writeShellScript "sinnix-clodex-aliases" ''
        set -euo pipefail
        cli=${lib.escapeShellArg clodex}
        models="$($cli models --json)"
        for alias in $(printf '%s' "$models" | ${pkgs.jq}/bin/jq -r '.[] | (.aliases // [.alias // empty])[]'); do
          case "$alias" in
            ${
              if cfg.aliases == { } then
                "__sinnix_no_declared_alias__"
              else
                lib.concatStringsSep "|" (lib.attrNames cfg.aliases)
            }) ;;
            *) "$cli" models --unalias "$alias" >/dev/null ;;
          esac
        done
        ${lib.concatMapStringsSep "\n" (name: ''
          "$cli" models --alias ${lib.escapeShellArg "${name}=${cfg.aliases.${name}}"}
        '') (lib.attrNames cfg.aliases)}
      '';
    in
    {
      home-manager.users.${user}.systemd.user.services.sinnix-clodex = {
        Unit = {
          Description = "Local Clodex proxy for Claude Code";
          # Before device-code OAuth finishes, leave this enabled unit inactive
          # rather than crash-looping a credential-dependent service.
          ConditionPathExists = "/home/${user}/.clodex/providers.json";
          After = [ "graphical-session.target" ];
        };
        Service =
          (lib.sinnix.mkRuntimeServiceConfig {
            runtimeInventory = config.sinnix.runtime.inventory;
            unit = "sinnix-clodex.service";
            manager = "user";
          })
          // {
            Type = "simple";
            # Reconcile the native alias registry before validating its patch.
            # A stale patch skips startup without rewriting Claude or looping.
            # Unit values are single lines: each pre-start step is a store
            # script, not an inline shell body.
            ExecCondition = "${pkgs.writeShellScript "sinnix-clodex-patch-check" ''
              set +e
              (
              set -euo pipefail
              models="$(${lib.escapeShellArg clodex} models --json)"
              ${lib.concatMapStringsSep "\n" (target: ''
                if ! printf '%s' "$models" | ${pkgs.jq}/bin/jq -e --arg target ${lib.escapeShellArg target} 'any(.[]; .id == $target)' >/dev/null; then
                  echo "clodex: required favorite ${target} is missing; save it with clodex models and repatch before starting the proxy" >&2
                  exit 78
                fi
              '') (lib.unique (lib.attrValues cfg.aliases))}
              ${reconcileAliases}
              models="$(${lib.escapeShellArg clodex} models --json)"
              manifest="/home/${user}/.clodex/patch-state.json"
              if [ ! -r "$manifest" ]; then
                echo "clodex: Claude Code is not patched; run clodex patch, then systemctl --user start sinnix-clodex" >&2
                exit 78
              fi
              # Clodex 2.18.10 / transform 15 projects native effort to high.
              # Compare every favorite, alias, label and selected context window.
              printf '%s' "$models" | ${pkgs.python3}/bin/python3 -c '
              import errno, hashlib, json, pathlib, stat, sys
              models = json.load(sys.stdin)
              manifest = json.loads(pathlib.Path(sys.argv[1]).read_text())
              preferences = json.loads(pathlib.Path(sys.argv[2]).read_text())
              entries = []
              for model in sorted(models, key=lambda model: model["id"]):
                  aliases = model.get("aliases", [])
                  context = model["context"]["effective"]
                  effort = model.get("effort")
                  levels = [level for level in ("low", "medium", "high", "xhigh", "max") if effort and level in effort["levels"]]
                  valid_effort = effort and all(level in levels for level in ("low", "medium", "high")) and effort["default"] in levels
                  entry = [model["id"], aliases[0] if aliases else None,
                           context if context > 0 and context != 200000 else None,
                           model["displayName"].strip() or None,
                           levels if valid_effort else None, "high" if valid_effort else None]
                  if len(aliases) > 1:
                      entry.append(aliases[1:])
                  entries.append(entry)
              payload = [15, entries]
              if preferences.get("localPatchesEnabled") is True:
                  path = pathlib.Path(sys.argv[2]).parent / "local-patches.mjs"
                  try:
                      info = path.stat()
                      if not stat.S_ISREG(info.st_mode):
                          raise OSError(errno.EINVAL, "not a regular file")
                      if info.st_size > 1048576:
                          raise OSError(errno.EFBIG, "module exceeds 1 MiB")
                      content = path.read_bytes()
                      if len(content) > 1048576:
                          raise OSError(errno.EFBIG, "module exceeds 1 MiB")
                      local_digest = hashlib.sha256(content).hexdigest()
                      try:
                          content.decode("utf-8")
                          identity = "v1:" + local_digest
                      except UnicodeDecodeError:
                          identity = "v1:invalid-utf8:" + local_digest
                  except OSError as error:
                      identity = "v1:unavailable:" + errno.errorcode.get(error.errno, "UNKNOWN")
                  payload.append(["local-patches", identity])
              digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
              if digest != manifest["configHash"]:
                  sys.exit("clodex: favorite or alias patch is stale; run clodex patch before starting the proxy")
              ' "$manifest" "/home/${user}/.clodex/config.json" || exit 78
              binary="$(${pkgs.jq}/bin/jq -er '.binaryPath' "$manifest")"
              expected="$(${pkgs.jq}/bin/jq -er '.claudeVersion' "$manifest")"
              if [ ! -x "$binary" ]; then
                echo "clodex: patched Claude Code binary is missing: $binary; run clodex patch, then systemctl --user start sinnix-clodex" >&2
                exit 78
              fi
              actual="$($binary --version 2>/dev/null | ${pkgs.gnugrep}/bin/grep -Eo '[0-9]+(\.[0-9]+)+' | ${pkgs.coreutils}/bin/head -n1 || true)"
              size="$(${pkgs.coreutils}/bin/stat -c '%s' "$binary")"
              patched_size="$(${pkgs.jq}/bin/jq -er '.patchedSize' "$manifest")"
              patched_sha="$(${pkgs.jq}/bin/jq -er '.patchedSha256 | select(test("^[0-9a-f]{64}$"))' "$manifest")"
              actual_sha="$(${pkgs.coreutils}/bin/sha256sum "$binary")"
              actual_sha="''${actual_sha%% *}"
              if [ -z "$actual" ] || [ "$actual" != "$expected" ] || [ "$size" != "$patched_size" ] || [ "$actual_sha" != "$patched_sha" ]; then
                echo "clodex: Claude Code patch is stale (expected $expected/$patched_size, found ''${actual:-unknown}/$size); run clodex patch, then systemctl --user start sinnix-clodex" >&2
                exit 78
              fi
              )
              status=$?
              case "$status" in
                0) exit 0 ;;
                78) exit 1 ;;
                *) exit 255 ;;
              esac
            ''}";
            ExecStart = "/home/${user}/.local/bin/sinnix-clodex-server";
            Environment = [
              "CLODEX_CREDENTIAL_HELPER=/home/${user}/.local/bin/sinnix-clodex-credential-helper"
            ];
            Restart = "on-failure";
            RestartSec = "5s";
            UMask = "0077";
          };
        Install.WantedBy = [ "default.target" ];
      };
    };
  extraOptions.aliases = lib.mkOption {
    type = lib.types.attrsOf lib.types.str;
    default = {
      sol = "clodex:openai-oauth:gpt-6-sol";
      # Existing clients may still request terra; route new calls to Sol.
      terra = "clodex:openai-oauth:gpt-6-sol";
      astra = "clodex:openai-oauth:gpt-6-astra";
      luna = "clodex:openai-oauth:gpt-6-luna";
    };
    description = "Exact Clodex model aliases reconciled before the bridge starts.";
  };
} args
