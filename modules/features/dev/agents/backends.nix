# CLI wrapper-builder machinery for clis.nix: the shared npm bootstrap
# prelude and the per-backend (Claude/Codex/Hermes) launcher-script builders.
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
      ${scriptPkgs.sinnix-agent-npm-bootstrap}/bin/sinnix-agent-npm-bootstrap \
        ${lib.escapeShellArg stateDir} \
        ${lib.escapeShellArg npmPackage} \
        ${lib.escapeShellArg binaryName} \
        ${lib.escapeShellArg agentRuntimePath}
    '';

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
  hermesConfigureLocal = "${scriptPkgs.sinnix-hermes-configure-local}/bin/sinnix-hermes-configure-local";
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
    mkClaudeCodeWrapper
    mkCodexWrapper
    hermesBootstrap
    ensureHermes
    hermesConfigureLocal
    mkHermesWrapper
    ;
}
