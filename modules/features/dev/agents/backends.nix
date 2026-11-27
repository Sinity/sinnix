# CLI wrapper-builder machinery for clis.nix: the shared npm bootstrap
# prelude and the per-backend launcher-script builders.
# Plain helper (not a NixOS module) — imported directly by clis.nix's
# configFn, not picked up by auto-import.
{
  lib,
  pkgs,
  scriptPkgs,
  runtimeDefaults,
  agentRuntimePath,
  hermesRuntimePath,
  sinnixCfg,
  user,
}:
let
  npmRecoverySources = import ../../../../flake/data/agent-cli-sources.nix { inherit pkgs; };
  # Mirrors environment.sessionVariables.TMPDIR in modules/profiles/workstation.nix;
  # the wrappers re-assert it because inheritance is not guaranteed.
  shellTmpRoot = "${sinnixCfg.paths.realmRoot}/tmp/work";

  # Guarantee the NVMe scratch TMPDIR rather than trusting inheritance:
  # environment.sessionVariables.TMPDIR (modules/profiles/workstation.nix) only
  # reaches processes whose session imported it, so an agent CLI started
  # outside that path runs with TMPDIR unset and everything beneath it
  # fills the bounded /tmp tmpfs, truncating shell heredocs mid-write.
  scratchTmpPrelude = ''
    if [ -z "''${TMPDIR:-}" ] && [ -d ${lib.escapeShellArg sinnixCfg.paths.realmRoot} ]; then
      export TMPDIR=${lib.escapeShellArg shellTmpRoot}
      ${pkgs.coreutils}/bin/install -d -m 0700 "$TMPDIR" 2>/dev/null || true
    fi
  '';

  # Shared npm bootstrap prelude — delegates state-dir setup and first-run npm
  # recovery to scripts/sinnix-agent-npm-bootstrap. The agent executable is
  # invoked directly after setup, not through a generated launcher or
  # buildFHSEnv/bubblewrap, so sudo and other privileged helpers do not
  # inherit no_new_privileges. `STATE` is recomputed here because the
  # bootstrap subprocess cannot export it back to the wrapper.
  mkNpmBootstrap =
    {
      stateDir,
      npmPackage,
      binaryName,
    }:
    ''
      STATE="$HOME/.local/state/${stateDir}"
      # The bootstrap is a subprocess. Keep the npm prefix and runtime PATH in
      # this wrapper too, because the final direct exec must not depend on the
      # removed launch.sh to reconstruct them. Keep the managed command
      # directory ahead of the private npm prefix: Codex can launch further
      # interactive app processes, and their `codex` lookup must re-enter the
      # managed wrapper instead of bypassing the default configuration. The wrapper
      # invokes the private binary by its absolute path below, so this does
      # not affect its own final exec or the writable ~/.codex overlay.
      export npm_config_prefix="$STATE/npm"
      export NPM_CONFIG_PREFIX="$STATE/npm"
      export PATH="$HOME/.local/bin:${agentRuntimePath}:$STATE/npm/bin:$PATH"
      ${scratchTmpPrelude}
        ${scriptPkgs.sinnix-agent-npm-bootstrap}/bin/sinnix-agent-npm-bootstrap \
        ${lib.escapeShellArg stateDir} \
        ${lib.escapeShellArg npmPackage} \
        ${lib.escapeShellArg binaryName} \
        ${lib.escapeShellArg agentRuntimePath} \
        ${lib.escapeShellArg (toString npmRecoverySources.${npmPackage})}
    '';

  # Put the outermost interactive agent process in the same cgroup tree as
  # declared agent work. A process already inside one of
  # runtimeDefaults.agentContainedSlices stays there: re-execing out of a
  # queued task's scope drops the lane's MemoryMax and leaves the agent
  # behind when the task is cancelled.
  #
  # An invocation that is not an agent session stays where it was started and
  # gets no scope: a version or help query, and each backend's
  # `helperInvocations` (its leading arguments). Every scope is a unit start
  # in the journal, and other programs start such helpers every few seconds.
  mkAgentScopePrelude =
    {
      helperInvocations ? [ ],
    }:
    let
      helperPatterns = lib.concatMapStringsSep " | " (
        invocation: "${lib.escapeShellArg invocation} | ${lib.escapeShellArg "${invocation} "}*"
      ) (agentHelperInvocations ++ helperInvocations);
    in
    ''
      case "''${1:-} ''${2:-}" in
        ${helperPatterns}) ;;
        *)
          case "$(< /proc/self/cgroup)" in
            ${runtimeDefaults.agentContainedCasePattern}) ;;
            *)
              # Agent CLIs rank just above Chrome's foreground renderers
              # (200) as global OOM victims, and below the jobs and tools
              # they start.
              echo 300 >/proc/self/oom_score_adj 2>/dev/null || true
              exec ${pkgs.systemd}/bin/systemd-run --user --scope --quiet \
                --description="Agent CLI" --slice=agent-cli.slice -- "$0" "$@"
              ;;
          esac
          ;;
      esac
      # Build tools default to one job per core. Agents shell out to source
      # builds (a `uv sync` without a wheel, cargo, cmake) from inside
      # agent-cli.slice; a bounded default keeps one such build from filling the
      # slice. An explicit caller setting still wins.
      export CMAKE_BUILD_PARALLEL_LEVEL="''${CMAKE_BUILD_PARALLEL_LEVEL:-4}"
      export MAKEFLAGS="''${MAKEFLAGS:--j4}"
      export CARGO_BUILD_JOBS="''${CARGO_BUILD_JOBS:-4}"
      export UV_CONCURRENT_BUILDS="''${UV_CONCURRENT_BUILDS:-2}"
      export MAX_JOBS="''${MAX_JOBS:-4}"
    '';
  agentHelperInvocations = [
    "--version"
    "--help"
  ];
  # Codex's `app-server proxy` is a stdio-to-socket relay to the running app
  # server, not a session.
  codexHelperInvocations = [ "app-server proxy" ];
  agentScopePrelude = mkAgentScopePrelude { };

  claudeConfigPrelude = ''
    # Keep the atomically replaced global JSON inside the persisted directory.
    export CLAUDE_CONFIG_DIR="''${CLAUDE_CONFIG_DIR:-$HOME/.config/claude}"
  '';

  # Claude Code's scratch location and selected profile.
  mkClaudeScratchPrelude =
    { profile }:
    ''
      ${claudeConfigPrelude}
      if [ -z "''${CLAUDE_CODE_TMPDIR:-}" ]; then
        export CLAUDE_CODE_TMPDIR="''${TMPDIR:-/tmp}"
      fi
      ${pkgs.coreutils}/bin/install -d -m 0700 "$CLAUDE_CODE_TMPDIR"

      export SINNIX_CLAUDE_PROFILE=${lib.escapeShellArg profile}
      # Tool commands and MCP servers get their own memory budget in
      # agent-tool.slice, so a wave of heavy tool runs cannot throttle the
      # Claude process that supervises them.
      export CLAUDE_CODE_SHELL_PREFIX=${lib.escapeShellArg "${scriptPkgs.agent-tool-command}/bin/agent-tool-command"}
    '';

  mkClaudeLaunchArgs = mcpConfigName: ''
    mcp_args=()
    MCP_CONFIG="$HOME/.config/claude/${mcpConfigName}.json"
    if [ -r "$MCP_CONFIG" ]; then
      mcp_args=(--mcp-config "$MCP_CONFIG" --strict-mcp-config)
    fi

    claude_args=("''${mcp_args[@]}")
    # --add-dir accepts multiple values and would consume a following
    # subcommand such as `mcp list` when passed as separate words.
    if [ -d "${sinnixCfg.paths.realmRoot}" ]; then
      claude_args+=(--add-dir=${lib.escapeShellArg sinnixCfg.paths.realmRoot} --add-dir=/home/${user})
    else
      claude_args+=(--add-dir=/home/${user})
    fi
    # One debug log per launch: a frozen session leaves a transcript that
    # simply stops, and this log shows what the process did last (hooks,
    # messaging, file writes); the investigate skill's freeze checklist reads
    # it. The claude-* trees are retained and excluded from automatic scratch
    # cleanup.
    claude_debug_dir="$CLAUDE_CODE_TMPDIR/claude-debug"
    ${pkgs.coreutils}/bin/install -d -m 0700 "$claude_debug_dir"
    claude_args+=(--debug-file="$claude_debug_dir/$(${pkgs.coreutils}/bin/date +%Y%m%dT%H%M%S)-$$.log")
  '';

  mkClaudeCodeWrapper =
    {
      mcpConfigName,
      profile,
    }:
    {
      text = ''
        #!/usr/bin/env bash
        set -euo pipefail

        ${agentScopePrelude}

        ${mkNpmBootstrap {
          stateDir = "claude-code";
          npmPackage = "@anthropic-ai/claude-code";
          binaryName = "claude";
        }}

        # Claude Code does not use the ordinary TMPDIR for Bash/task output
        # captures. Its supported override is CLAUDE_CODE_TMPDIR; without it,
        # concurrent subagents accumulate under /tmp/claude-$UID and can
        # exhaust the workstation's bounded /tmp tmpfs.
        ${mkClaudeScratchPrelude { inherit profile; }}${mkClaudeLaunchArgs mcpConfigName}
        exec "$STATE/npm/bin/claude" "''${claude_args[@]}" "$@"
      '';
      executable = true;
      force = true;
    };
  # The default Codex command reads the generated system config and reaches
  # OpenAI through the host's egress proxy when one is declared.
  mkCodexWrapper = {
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      ${mkAgentScopePrelude { helperInvocations = codexHelperInvocations; }}

      ${mkNpmBootstrap {
        stateDir = "codex";
        npmPackage = "@openai/codex";
        binaryName = "codex";
      }}

      if [ -r /etc/sinnix/openai-proxy-url ]; then
        read -r proxy_url </etc/sinnix/openai-proxy-url
        export HTTP_PROXY="$proxy_url" HTTPS_PROXY="$proxy_url"
        export http_proxy="$proxy_url" https_proxy="$proxy_url"
        export NO_PROXY="127.0.0.1,localhost,::1"
        export no_proxy="$NO_PROXY"
      fi

      exec "$STATE/npm/bin/codex" "$@"
    '';
    executable = true;
    force = true;
  };
  # Env-only prelude for Hermes wrappers. PATH/HERMES_HOME/HERMES_INSTALL_DIR
  # must be exported here rather than in a subprocess: the final `exec` of the
  # hermes binary inherits them, and scripts/sinnix-ensure-hermes (which does
  # the clone/sync/scaffold) runs as a subprocess relying on this env.
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

        ${agentScopePrelude}

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
    agentScopePrelude
    mkAgentScopePrelude
    codexHelperInvocations
    mkClaudeScratchPrelude
    mkClaudeLaunchArgs
    mkClaudeCodeWrapper
    mkCodexWrapper
    scratchTmpPrelude
    hermesBootstrap
    ensureHermes
    mkHermesWrapper
    ;
}
