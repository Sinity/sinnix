# CLI wrapper-builder machinery for clis.nix: the shared npm bootstrap
# prelude and the per-backend launcher-script builders.
# Plain helper (not a NixOS module) — imported directly by clis.nix's
# configFn, not picked up by auto-import.
{
  lib,
  pkgs,
  scriptPkgs,
  agentRuntimePath,
  hermesRuntimePath,
  agentScopeExec,
  sinnixCfg,
  user,
}:
let
  claudeTmpRoot = "${sinnixCfg.paths.realmRoot}/tmp/claude-code";
  # Mirrors environment.sessionVariables.TMPDIR in profiles/workstation.nix;
  # the wrappers re-assert it because inheritance is not guaranteed.
  shellTmpRoot = "${sinnixCfg.paths.realmRoot}/tmp/shell";

  # Shared npm bootstrap prelude — delegates state-dir setup, first-run npm
  # install, and launcher regeneration to the packaged
  # sinnix-agent-npm-bootstrap script (scripts/sinnix-agent-npm-bootstrap).
  # The long-lived agent process launches directly via the generated
  # launch.sh, not through buildFHSEnv/bubblewrap, so sudo and other
  # privileged helpers do not inherit no_new_privileges. `STATE` is
  # recomputed here (not exported by the bootstrap subprocess) because the
  # wrapper needs it below for the final agent-scope-exec/launch call.
  mkNpmBootstrap =
    {
      stateDir,
      npmPackage,
      binaryName,
    }:
    ''
      STATE="$HOME/.local/state/${stateDir}"
      # Guarantee the NVMe scratch TMPDIR rather than trusting inheritance.
      # environment.sessionVariables.TMPDIR (profiles/workstation.nix) only
      # reaches processes whose session imported it; a long-lived agent CLI
      # started outside that path runs with TMPDIR unset, so every devshell
      # and test run underneath it falls back to the 6 GiB /tmp tmpfs and
      # refills it (confirmed 2026-08-03: one agent session exhausted /tmp
      # three times in a single turn, truncating shell heredocs mid-write,
      # while `systemctl --user show-environment` correctly showed the
      # variable set).
      if [ -z "''${TMPDIR:-}" ] && [ -d ${lib.escapeShellArg sinnixCfg.paths.realmRoot} ]; then
        export TMPDIR=${lib.escapeShellArg shellTmpRoot}
        ${pkgs.coreutils}/bin/install -d -m 1777 "$TMPDIR" 2>/dev/null || true
      fi
      ${scriptPkgs.sinnix-agent-npm-bootstrap}/bin/sinnix-agent-npm-bootstrap \
        ${lib.escapeShellArg stateDir} \
        ${lib.escapeShellArg npmPackage} \
        ${lib.escapeShellArg binaryName} \
        ${lib.escapeShellArg agentRuntimePath}
    '';

  # Resolves an agenix secret name to its runtime path, honoring a live
  # config override under sinnix.secrets.paths.<name> the same way
  # clis.nix's former per-secret `deepseekSecretPath` local did (that was
  # `lib.attrByPath [ "sinnix" "secrets" "paths" name ] default config`;
  # sinnixCfg here already IS `config.sinnix`, so the attrByPath drops the
  # leading "sinnix" segment).
  resolveSecretPath =
    secretName: lib.attrByPath [ "secrets" "paths" secretName ] "/run/agenix/${secretName}" sinnixCfg;

  # Shared backend-switch env builder for the claude-deepseek/claude-local
  # wrappers (see flake/data/agent-lanes.nix claudeLanes): points Claude
  # Code's native Anthropic-protocol client at a non-Anthropic endpoint and
  # fans one model name out across every ANTHROPIC_*MODEL var Claude Code
  # reads. `name` is the lane name (e.g. "deepseek"); it drives the
  # intermediate shell variable name and the wrapper's own error-caller name
  # so error text stays wrapper-specific without extra data fields.
  mkClaudeBackendEnv =
    {
      name,
      baseUrl,
      model,
      # Either { secretName = "<agenix secret>"; } (read at launch, wrapper
      # exits loudly if unreadable) or { literal = "<static token>"; } (a
      # loopback gateway that enforces no real auth but still needs a
      # non-empty token).
      authToken,
    }:
    let
      modelVar = "${lib.toUpper name}_MODEL";
      authFragment =
        if authToken ? secretName then
          let
            path = resolveSecretPath authToken.secretName;
          in
          ''
            if [ ! -r ${lib.escapeShellArg path} ]; then
              echo "claude-${name}: cannot read ${path}" >&2
              exit 1
            fi
            export ANTHROPIC_BASE_URL="${baseUrl}"
            ANTHROPIC_AUTH_TOKEN="$(<${lib.escapeShellArg path})"
            export ANTHROPIC_AUTH_TOKEN
          ''
        else
          ''
            export ANTHROPIC_BASE_URL="${baseUrl}"
            export ANTHROPIC_AUTH_TOKEN="${authToken.literal}"
          '';
    in
    ''
      ${authFragment}
      ${modelVar}="${model}"
      export ANTHROPIC_MODEL="$${modelVar}"
      export ANTHROPIC_DEFAULT_OPUS_MODEL="$${modelVar}"
      export ANTHROPIC_DEFAULT_SONNET_MODEL="$${modelVar}"
      export ANTHROPIC_DEFAULT_HAIKU_MODEL="$${modelVar}"
      export CLAUDE_CODE_SUBAGENT_MODEL="$${modelVar}"
    '';

  # Shared backend-switch env builder for the codex-deepseek/codex-local
  # wrappers (see flake/data/agent-lanes.nix codexLanes): the layered
  # `<profile>.config.toml` (mcp.nix's client-profiles.nix) already carries
  # model + model_provider + the full MCP table, so the wrapper only needs
  # to export the one env var that provider's `env_key` names.
  mkCodexBackendEnv =
    {
      name,
      varName,
      # Either secretName (agenix, read-checked at launch) or literal (a
      # static loopback dev token) — exactly one is set per lane.
      secretName ? null,
      literal ? null,
    }:
    if secretName != null then
      let
        path = resolveSecretPath secretName;
      in
      ''
        if [ ! -r ${lib.escapeShellArg path} ]; then
          echo "codex-${name}: cannot read ${path}" >&2
          exit 1
        fi
        ${varName}="$(<${lib.escapeShellArg path})"
        export ${varName}
      ''
    else
      ''export ${varName}="${literal}"'';

  mkClaudeCodeWrapper =
    {
      mcpConfigName ? "mcp",
      profile ?
        if mcpConfigName == "mcp-lean" then
          "lean"
        else if mcpConfigName == "mcp-browser" then
          "browser"
        else
          "full",
      # Extra shell injected after the npm bootstrap and before launch — used
      # to point Claude Code at a non-Anthropic backend (DeepSeek, local
      # gateway) via ANTHROPIC_BASE_URL / ANTHROPIC_MODEL / auth env vars.
      extraEnv ? "",
    }:
    {
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        ${mkNpmBootstrap {
          stateDir = "claude-code";
          npmPackage = "@anthropic-ai/claude-code";
          binaryName = "claude";
        }}

        ${extraEnv}

        # Claude Code does not use the ordinary TMPDIR for Bash/task output
        # captures. Its supported override is CLAUDE_CODE_TMPDIR; without it,
        # concurrent subagents accumulate under /tmp/claude-$UID and can
        # exhaust the workstation's bounded /tmp tmpfs (sinnix-77w).
        if [ -z "''${CLAUDE_CODE_TMPDIR:-}" ]; then
          if [ -d "${sinnixCfg.paths.realmRoot}" ]; then
            export CLAUDE_CODE_TMPDIR=${lib.escapeShellArg claudeTmpRoot}
          else
            export CLAUDE_CODE_TMPDIR="''${TMPDIR:-/tmp}/claude-code-$UID"
          fi
        fi
        ${pkgs.coreutils}/bin/install -d -m 0700 "$CLAUDE_CODE_TMPDIR"

        export SINNIX_CLAUDE_PROFILE=${lib.escapeShellArg profile}
        mcp_args=()
        MCP_CONFIG="$HOME/.config/claude/${mcpConfigName}.json"
        if [ -r "$MCP_CONFIG" ]; then
          mcp_args=(--mcp-config "$MCP_CONFIG" --strict-mcp-config)
        fi

        claude_args=(
          "''${mcp_args[@]}"
        )
        if [ -d "${sinnixCfg.paths.realmRoot}" ]; then
          claude_args+=(--add-dir "${sinnixCfg.paths.realmRoot}" "/home/${user}")
        else
          claude_args+=(--add-dir "/home/${user}")
        fi

        exec ${agentScopeExec} "$STATE/launch.sh" "''${claude_args[@]}" "$@"
      '';
      executable = true;
      force = true;
    };
  mkCodexWrapper =
    {
      profile,
      # Extra shell injected after the npm bootstrap — used to export the
      # provider API key the layered `<profile>.config.toml` expects.
      extraEnv ? "",
    }:
    {
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        ${mkNpmBootstrap {
          stateDir = "codex";
          npmPackage = "@openai/codex";
          binaryName = "codex";
        }}

        ${extraEnv}

        export SINNIX_CODEX_PROFILE=${lib.escapeShellArg profile}
        codex_args=(--profile ${lib.escapeShellArg profile})

        exec ${agentScopeExec} "$STATE/launch.sh" "''${codex_args[@]}" "$@"
      '';
      executable = true;
      force = true;
    };
  mkGrokWrapper = {
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      if [ ! -x "$HOME/.grok/bin/grok" ]; then
        echo "grok-sinnix: install the official Grok CLI first: curl -fsSL https://x.ai/cli/install.sh | bash" >&2
        exit 1
      fi
      exec ${agentScopeExec} "$HOME/.grok/bin/grok" "$@"
    '';
    executable = true;
    force = true;
  };
  mkAntigravityWrapper = {
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      if [ ! -x "$HOME/.local/bin/agy" ]; then
        echo "agy-sinnix: install the official Antigravity CLI first: curl -fsSL https://antigravity.google/cli/install.sh | bash" >&2
        exit 1
      fi
      exec ${agentScopeExec} "$HOME/.local/bin/agy" "$@"
    '';
    executable = true;
    force = true;
  };
  # Env-only prelude for Hermes wrappers. PATH/HERMES_HOME/HERMES_INSTALL_DIR
  # must be exported here (not in a subprocess) because the final `exec` of
  # the hermes binary below needs to inherit them. The actual clone/sync/
  # scaffold bootstrap logic lives in scripts/sinnix-ensure-hermes, which
  # runs as a subprocess relying on this already-exported PATH/env.
  hermesBootstrap = ''
    export HERMES_HOME="''${HERMES_HOME:-$HOME/.hermes}"
    export HERMES_INSTALL_DIR="''${HERMES_INSTALL_DIR:-$HERMES_HOME/hermes-agent}"
    export PATH="${hermesRuntimePath}:$PATH"
    export UV_NO_CONFIG=1
    export UV_PYTHON="${pkgs.python313}/bin/python3"
    export LD_LIBRARY_PATH="${
      lib.makeLibraryPath [
        pkgs.portaudio
        pkgs.ffmpeg
        pkgs.zlib
      ]
    }:''${LD_LIBRARY_PATH:-}"
    # NeMo Relay reads exporter settings from its launch environment. ATIF stays
    # beneath HERMES_HOME so Polylogue's native Hermes watcher discovers each
    # JSON trajectory; the neighboring ATOF JSONL preserves raw diagnostics.
    export HERMES_NEMO_RELAY_ATOF_ENABLED=1
    export HERMES_NEMO_RELAY_ATOF_OUTPUT_DIRECTORY="$HERMES_HOME/observability/nemo-relay/atof"
    export HERMES_NEMO_RELAY_ATOF_FILENAME="events.jsonl"
    export HERMES_NEMO_RELAY_ATOF_MODE=append
    export HERMES_NEMO_RELAY_ATIF_ENABLED=1
    export HERMES_NEMO_RELAY_ATIF_OUTPUT_DIRECTORY="$HERMES_HOME/observability/nemo-relay/atif"
    export HERMES_NEMO_RELAY_ATIF_FILENAME_TEMPLATE="trajectory-{session_id}.json"
    export HERMES_NEMO_RELAY_ATIF_AGENT_NAME="Sinnix Hermes Agent"
    export HERMES_NEMO_RELAY_ATIF_AGENT_VERSION="local"
    export HERMES_NEMO_RELAY_ATIF_SUBAGENT_EXPORT_MODE=all
  '';
  ensureHermes = "${scriptPkgs.sinnix-ensure-hermes}/bin/sinnix-ensure-hermes";
  mkHermesWrapper =
    {
      entrypoint ? "hermes",
      extraPrelude ? "",
      profile ? null,
    }:
    {
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        ${lib.optionalString (profile != null) ''
          export HERMES_HOME="$HOME/.hermes/profiles/${profile}"
          export HERMES_INSTALL_DIR="$HOME/.hermes/hermes-agent"
        ''}
        ${hermesBootstrap}

        ${ensureHermes}
        ${extraPrelude}

        exec "$HERMES_INSTALL_DIR/venv/bin/${entrypoint}" "$@"
      '';
      executable = true;
      force = true;
    };
in
{
  inherit
    mkNpmBootstrap
    resolveSecretPath
    mkClaudeBackendEnv
    mkCodexBackendEnv
    mkClaudeCodeWrapper
    mkCodexWrapper
    mkGrokWrapper
    mkAntigravityWrapper
    hermesBootstrap
    ensureHermes
    mkHermesWrapper
    ;
}
