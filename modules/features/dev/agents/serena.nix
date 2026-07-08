# Serena LSP-backed MCP wrapper: version pin, generated serena_config.yml,
# and the per-commandName wrapper-script builder (serena / serena-hooks).
# Plain helper (not a NixOS module) — imported directly by mcp.nix's
# configFn, not picked up by auto-import.
{
  lib,
  pkgs,
  scriptPkgs,
}:
let
  serenaVersion = "1.5.3";
  serenaRuntimePath = lib.makeBinPath [
    pkgs.bash
    pkgs.coreutils
    pkgs.git
    pkgs.gnugrep
    pkgs.nodejs_22
    pkgs.pyright
    pkgs.python313
    pkgs.rust-analyzer
    pkgs.uv
  ];
  serenaConfigFile = pkgs.writeText "serena_config.yml" ''
    language_backend: LSP
    line_ending: lf
    gui_log_window: false
    web_dashboard: true
    web_dashboard_open_on_launch: false
    web_dashboard_listen_address: 127.0.0.1
    web_dashboard_trusted_hosts:
      - 127.0.0.1
      - localhost
    log_level: 20
    trace_lsp_communication: false
    tool_timeout: 240
    default_max_tool_answer_chars: 150000
    symbol_info_budget: 10
    base_modes:
      - interactive
      - editing
    default_modes: []
    ignored_paths:
      - .direnv
      - .git
      - .venv
      - node_modules
      - target
      - __pycache__
    project_serena_folder_location: "$projectDir/.serena"
    projects:
      - /realm/project/sinex
      - /realm/project/polylogue
      - /realm/project/sinity-lynchpin
      - /realm/project/sinnix
  '';
  # Thin per-commandName Nix wrapper: exports every Nix-time value the
  # bootstrap/dispatch logic needs (version pin, generated config store
  # path, uv/python/cmp store paths, runtime PATH) as env vars, then
  # execs the packaged script that owns the actual logic
  # (scripts/sinnix-serena-wrapper). Mirrors the
  # SINNIX_MCP_CHROME_DEVTOOLS_BIN handoff used for
  # mcp-chrome-devtools-private in browser.nix.
  mkSerenaWrapper = commandName: ''
    #!${pkgs.runtimeShell}
    set -euo pipefail
    export SINNIX_SERENA_COMMAND_NAME=${lib.escapeShellArg commandName}
    export SINNIX_SERENA_VERSION=${lib.escapeShellArg serenaVersion}
    export SINNIX_SERENA_CONFIG_FILE=${lib.escapeShellArg (toString serenaConfigFile)}
    export SINNIX_SERENA_RUNTIME_PATH=${lib.escapeShellArg serenaRuntimePath}
    export SINNIX_SERENA_UV_BIN=${lib.escapeShellArg "${pkgs.uv}/bin/uv"}
    export SINNIX_SERENA_PYTHON_BIN=${lib.escapeShellArg "${pkgs.python313}/bin/python3"}
    export SINNIX_SERENA_CMP_BIN=${lib.escapeShellArg "${pkgs.diffutils}/bin/cmp"}
    exec ${scriptPkgs.sinnix-serena-wrapper}/bin/sinnix-serena-wrapper "$@"
  '';
in
{
  inherit serenaVersion serenaConfigFile mkSerenaWrapper;
}
