# The pi coding agent: launcher, declared settings, tool servers and packages.
# Plain helper (not a NixOS module), imported by clis.nix's configFn.
#
# Pi itself is the upstream flake's package at a pinned release, so nothing is
# installed or updated at run time. Its agent directory, ~/.pi/agent, stays
# pi's own: credentials, sessions and the settings file it writes to.
#
# Models. The default is the ChatGPT subscription through pi's `openai`
# provider ("Sign in with ChatGPT"; `pi auth login openai`). Claude models
# come from the Claude Code provider package, which runs each turn through the
# installed Claude Code CLI and so through the Claude plan it is signed in to.
# Pi's own `anthropic` sign-in is not used: pi states that it is billed per
# token. No provider is ever selected by a key that happens to be in the
# environment: the launcher removes them, and a metered key is used only when
# one is stored on purpose with `pi auth login <provider> --api-key`.
#
# Instructions and skills. Pi reads ~/.pi/agent/AGENTS.md (linked to the
# global instruction file by clis.nix) and ~/.agents/skills (linked by
# mcp.nix) on its own. Presets (dots/pi) drop the global file again.
{
  lib,
  pkgs,
  piPackage,
  piPackages,
  mcpRegistry,
  agentScopePrelude,
  scratchTmpPrelude,
  agentRuntimePath,
  dotsRoot,
}:
let
  jsonFormat = pkgs.formats.json { };

  # The files in dots/pi/presets are the sole launcher-name registry.
  presetNames = map (name: lib.removeSuffix ".json" name) (
    lib.filter (name: lib.hasSuffix ".json" name) (
      lib.attrNames (builtins.readDir ../../../../dots/pi/presets)
    )
  );
  presetLaunchers = lib.genAttrs presetNames (name: {
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail
      exec "$HOME/.local/bin/pi" --preset ${lib.escapeShellArg name} "$@"
    '';
    executable = true;
    force = true;
  });

  # The settings Sinnix declares. Pi writes its own keys into the same file
  # (a device id for the ChatGPT sign-in, what it last showed), so activation
  # merges these over the file instead of replacing it: declared keys win,
  # pi's survive. A key dropped from here stays in the file until removed by
  # hand.
  settings = {
    defaultProvider = "openai";
    defaultModel = "gpt-6.2-sol";
    # No install or update reports; the launcher also skips the version check.
    enableInstallTelemetry = false;
    # Local paths: pi loads them in place and installs nothing. Sinnix's own
    # package comes first so its command guard sees a tool call before any
    # other extension, and is read live from the checkout like the skills.
    packages = [
      "${dotsRoot}/pi"
    ]
    ++ map (path: "${piPackages}/${path}") piPackages.packagePaths;
  };
  settingsFile = jsonFormat.generate "pi-settings.json" settings;

  mcpConfigFile = jsonFormat.generate "pi-mcp.json" {
    mcpServers = lib.mapAttrs mcpRegistry.renderPiServer (
      mcpRegistry.selectClientServersForProfile "default" "pi"
    );
  };

  # Sourced by the launcher, and by the check that holds it against the key
  # names pi's own source reads. Everything that names an API key goes, not
  # only pi's list: the web-access package reads a further thirty. The
  # documentation server's key stays; it is a tool-server credential that
  # the rendered mcp.json refers to, not a model key.
  unsetProviderKeys = pkgs.writeText "pi-unset-provider-keys.sh" ''
    while IFS= read -r -d "" entry; do
      name="''${entry%%=*}"
      case "$name" in
        CONTEXT7_API_KEY) ;;
        *API_KEY* | *APIKEY* | HF_TOKEN | COPILOT_GITHUB_TOKEN | \
          ANTHROPIC_AUTH_TOKEN | ANTHROPIC_OAUTH_TOKEN | ANTHROPIC_IDENTITY_TOKEN_FILE | \
          ANTHROPIC_FEDERATION_RULE_ID | AWS_PROFILE | AWS_ACCESS_KEY_ID | \
          AWS_SECRET_ACCESS_KEY | AWS_SESSION_TOKEN | AWS_BEARER_TOKEN_BEDROCK | \
          AWS_WEB_IDENTITY_TOKEN_FILE | AWS_CONTAINER_CREDENTIALS_RELATIVE_URI | \
          AWS_CONTAINER_CREDENTIALS_FULL_URI | GOOGLE_CLOUD_LOCATION)
          unset "$name"
          ;;
      esac
    done < <(${pkgs.coreutils}/bin/env -0)
  '';

  wrapper = {
    text = ''
      #!/usr/bin/env bash
      set -euo pipefail

      ${agentScopePrelude}

      # The managed command directory first, so a `pi` or `claude` started
      # from inside pi is the managed one.
      export PATH="$HOME/.local/bin:${agentRuntimePath}:$PATH"
      ${scratchTmpPrelude}

      source ${unsetProviderKeys}

      export PI_SKIP_VERSION_CHECK=1
      export PI_TELEMETRY=0

      # The Claude Code provider starts Claude Code itself with its own
      # arguments, so it gets the installed program, not the Sinnix launcher
      # (which adds tool servers and directories meant for a person's session).
      export PI_CLAUDE_CODE_COMMAND="$HOME/.local/state/claude-code/npm/bin/claude"
      export PI_CLAUDE_CODE_CONFIG_DIR="''${CLAUDE_CONFIG_DIR:-$HOME/.config/claude}"
      export CLAUDE_CODE_TMPDIR="''${CLAUDE_CODE_TMPDIR:-''${TMPDIR:-/tmp}}"

      exec ${piPackage}/bin/pi "$@"
    '';
    executable = true;
    force = true;
  };

  # Runs at Home Manager activation, after ~/.pi is in place.
  activation = ''
    pi_agent="$HOME/.pi/agent"
    run mkdir -p "$pi_agent"
    run chmod 700 "$HOME/.pi"
    run ln -sfn "$HOME/.config/claude/CLAUDE.md" "$pi_agent/AGENTS.md"
    run ln -sfn ${mcpConfigFile} "$pi_agent/mcp.json"
    pi_settings="$pi_agent/settings.json"
    if [ ! -s "$pi_settings" ]; then
      run ${pkgs.coreutils}/bin/install -m 0600 ${settingsFile} "$pi_settings"
    elif merged="$(${pkgs.jq}/bin/jq -s '.[0] * .[1]' "$pi_settings" ${settingsFile})"; then
      if [ -z "''${DRY_RUN:-}" ]; then
        printf '%s\n' "$merged" >"$pi_settings.sinnix-new"
        chmod 600 "$pi_settings.sinnix-new"
        mv "$pi_settings.sinnix-new" "$pi_settings"
      fi
    else
      echo "sinnix: $pi_settings is not valid JSON; declared pi settings were not applied" >&2
    fi
  '';
in
{
  inherit
    settings
    settingsFile
    mcpConfigFile
    unsetProviderKeys
    wrapper
    presetLaunchers
    activation
    ;
}
