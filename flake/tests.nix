# Config Assertion Tests
#
# Fast tests that verify NixOS configurations evaluate correctly.
# No VM boot - just checks that options are set as expected.
#
# Run all: nix flake check
# Run one: nix build .#checks.x86_64-linux.nixos-dev-shell
{ inputs, ... }:
let
  inherit (inputs.nixpkgs) lib;
  pkgsFor = system: inputs.nixpkgs.legacyPackages.${system};

  mkSpecChecks =
    system:
    let
      # Import test infrastructure only when checks are requested.
      testLib = import ./test-lib.nix { inherit inputs lib; };
      inherit (testLib)
        mountTmpfsRoots
        baseTestConfig
        mkFeatureTest
        mkServiceTest
        mkBundleTest
        mkSystemChecks
        ;

      # Helper to get HM config for assertions
      hmFor = config: config.home-manager.users.${config.sinnix.user.name};

      testSpecs = [
        # === Feature Tests (using DSL) ===
        (mkFeatureTest {
      name = "dev-shell";
      feature = "sinnix.features.dev.shell.enable";
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = hm.programs.zsh.enable;
            message = "Zsh must be enabled";
          }
          {
            assertion = hm.programs.starship.enable;
            message = "Starship must be enabled";
          }
          {
            assertion = hm.programs.atuin.enable;
            message = "Atuin must be enabled";
          }
          {
            assertion = hm.programs.fzf.enable;
            message = "FZF must be enabled";
          }
          {
            assertion = hm.programs.zoxide.enable;
            message = "Zoxide must be enabled";
          }
          {
            assertion = hm.home.file ? ".local/bin/claude";
            message = "Claude wrapper must exist";
          }
          {
            assertion = builtins.match ".*\\$\\*.*" (hm.home.file.".local/bin/claude-team".text or "") == null;
            message = "Claude team wrapper must not flatten arguments via $*";
          }
          {
            assertion = hm.home.file ? ".local/bin/codex";
            message = "Codex wrapper must exist";
          }
          {
            assertion =
              builtins.match ".*/bin/lynchpin-python" hm.home.sessionVariables.LYNCHPIN_PYTHON != null;
            message = "Dev shell must export the system-wide Lynchpin API interpreter path";
          }
          {
            assertion =
              builtins.match ".*/bin/polylogue-python" hm.home.sessionVariables.POLYLOGUE_PYTHON != null;
            message = "Dev shell must export the system-wide Polylogue API interpreter path";
          }
          {
            assertion = builtins.match ".*render-agents.*" (hm.home.file.".local/bin/codex".text or "") == null;
            message = "Codex wrapper must not render AGENTS on every launch";
          }
          {
            assertion = hm.home.file ? ".local/bin/gemini";
            message = "Gemini wrapper must exist";
          }
          {
            assertion =
              builtins.match ".*render-agents.*" (hm.home.file.".local/bin/gemini".text or "") == null;
            message = "Gemini wrapper must not render instructions on every launch";
          }
          {
            assertion =
              let
                geminiText = hm.home.file.".local/bin/gemini".text or "";
              in
              lib.hasInfix "GEMINI_BIN=" geminiText
              && lib.hasInfix "/bin/gemini" geminiText
              && builtins.match ".*npx.*" geminiText == null
              && builtins.match ".*bundle/index\\.js.*" geminiText == null;
            message = "Gemini wrapper must launch the packaged binary directly";
          }
          {
            assertion = hm.xdg.configFile ? "claude/skills";
            message = "Claude skills symlink must exist";
          }
          {
            assertion = hm.home.activation ? renderGlobalCodexAgents;
            message = "Global Codex AGENTS render activation must exist";
          }
          {
            assertion = hm.home.activation ? renderGlobalGeminiAgents;
            message = "Global Gemini instruction render activation must exist";
          }
          {
            assertion = hm.programs.zsh.shellAliases.ccusage == "ccusage";
            message = "ccusage alias must resolve to the packaged CLI";
          }
          {
            assertion = builtins.any (name: lib.hasPrefix "lynchpin-python" name) (
              map (pkg: pkg.name or "") hm.home.packages
            );
            message = "Dev shell must install the Lynchpin API interpreter wrapper";
          }
          {
            assertion = builtins.any (name: lib.hasPrefix "polylogue-python" name) (
              map (pkg: pkg.name or "") hm.home.packages
            );
            message = "Dev shell must install the Polylogue API interpreter wrapper";
          }
          {
            assertion = lib.hasInfix "unsetopt prompt_sp" hm.programs.zsh.initContent;
            message = "Zsh init must disable PROMPT_SP to avoid stray partial-line prompt markers";
          }
        ];
    })

    (mkFeatureTest {
      name = "dev-git";
      feature = "sinnix.features.dev.git.enable";
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = hm.programs.git.enable;
            message = "Git must be enabled";
          }
          {
            assertion = hm.programs.delta.enable;
            message = "Delta must be enabled";
          }
        ];
    })

    (mkFeatureTest {
      name = "dev-mcp-servers";
      feature = "sinnix.features.dev.mcp-servers.enable";
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = hm.home.file ? ".codex/config.toml";
            message = "Codex config must be linked";
          }
          {
            assertion = hm.home.file ? ".codex/skills";
            message = "Codex skills must be linked from the dedicated dots/codex/skills tree";
          }
          {
            assertion =
              builtins.match ".*zsh -lc.*" (
                builtins.readFile ../dots/codex/skills/agent-orchestration/scripts/launch_agent_tabs.sh
              ) == null;
            message = "Agent launcher must not wrap kitty launches in zsh -lc";
          }
          {
            assertion =
              let
                context7Source = hm.home.file.".local/bin/mcp-context7".source or "";
                firecrawlSource = hm.home.file.".local/bin/mcp-firecrawl".source or "";
                polylogueSource = hm.home.file.".local/bin/mcp-polylogue".source or "";
                codexConfig = builtins.readFile ../dots/codex/config.toml;
                claudeSettings = builtins.fromJSON (builtins.readFile ../dots/claude/settings.json);
              in
              lib.hasInfix "/bin/mcp-context7" context7Source
              && lib.hasInfix "/bin/mcp-firecrawl" firecrawlSource
              && lib.hasInfix "/bin/mcp-polylogue" polylogueSource
              && lib.hasInfix "[mcp_servers.polylogue]" codexConfig
              && lib.hasInfix "command = \"mcp-polylogue\"" codexConfig
              && claudeSettings.mcpServers.polylogue.command == "mcp-polylogue";
            message = "MCP wrappers and agent configs must expose the packaged Polylogue server directly";
          }
        ];
    })

    (mkFeatureTest {
      name = "dev-editors-antigravity";
      feature = "sinnix.features.dev.editors.enable";
      extraModules = [
        ({ ... }: {
          sinnix.features.dev.editors.antigravity.enable = true;
        })
      ];
      assertions =
        config:
        let
          hasAntigravityDir =
            entry:
            if builtins.isAttrs entry then
              (entry.directory or null) == ".config/Antigravity"
            else
              entry == ".config/Antigravity";
        in
        [
          {
            assertion = builtins.any hasAntigravityDir config.sinnix.persistence.home.directories;
            message = "Antigravity state must be persisted under ~/.config/Antigravity";
          }
        ];
    })

    (mkFeatureTest {
      name = "cli-polylogue";
      feature = "sinnix.features.cli.polylogue.enable";
      assertions =
        config:
        let
          packageNames = map (pkg: pkg.name or "") (hmFor config).home.packages;
        in
        [
          {
            assertion =
              builtins.any (name: lib.hasPrefix "polylogue" name) packageNames
              && builtins.any (name: lib.hasPrefix "polylogue-python" name) packageNames;
            message = "Polylogue feature must install the packaged Polylogue CLI and API wrappers";
          }
        ];
    })

    (mkFeatureTest {
      name = "desktop-mime";
      feature = "sinnix.features.desktop.mime.enable";
      assertions =
        config:
        let
          defaultApps = (hmFor config).xdg.mimeApps.defaultApplications;
        in
        [
          {
            assertion = defaultApps."x-scheme-handler/http" == [ "google-chrome.desktop" ];
            message = "HTTP links must default to Google Chrome";
          }
          {
            assertion = defaultApps."x-scheme-handler/https" == [ "google-chrome.desktop" ];
            message = "HTTPS links must default to Google Chrome";
          }
          {
            assertion = defaultApps."text/html" == [ "google-chrome.desktop" ];
            message = "HTML documents must default to Google Chrome";
          }
        ];
    })

    (mkFeatureTest {
      name = "desktop-hyprland";
      feature = "sinnix.features.desktop.hyprland.enable";
      extraModules = [
        (
          { lib, ... }:
          {
            hardware.graphics.enable = lib.mkForce false;
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.programs.hyprland.enable;
          message = "Hyprland must be enabled";
        }
        {
          assertion = config.programs.hyprland.withUWSM;
          message = "UWSM must be enabled";
        }
        {
          assertion = lib.hasInfix "exec uwsm start hyprland-uwsm.desktop" (
            (hmFor config).programs.zsh.loginExtra or ""
          );
          message = "TTY Hyprland login must stay unwrapped by default";
        }
      ];
    })

    (mkFeatureTest {
      name = "desktop-audio";
      feature = "sinnix.features.desktop.audio.enable";
      assertions =
        config:
        let
          wireplumber = config.services.pipewire.wireplumber.extraConfig;
          xm4Rules = wireplumber."12-preferred-xm4-output"."monitor.bluez.rules" or [ ];
          isXm4Rule =
            rule:
            (builtins.elemAt (rule.matches or [ ]) 0)."node.name" or null
            == "~bluez_output.*AC_80_0A_D4_08_48.*"
            && (rule.actions.update-props."priority.session" or null) == 2100
            && (rule.actions.update-props."priority.driver" or null) == 2100;
        in
        [
          {
            assertion = config.services.pipewire.enable or false;
            message = "Desktop audio must enable PipeWire";
          }
          {
            assertion = config.services.pipewire.wireplumber.enable or false;
            message = "Desktop audio must enable WirePlumber";
          }
          {
            assertion = builtins.any isXm4Rule xm4Rules;
            message = "WH-1000XM4 must be preferred as the default Bluetooth sink when it appears";
          }
        ];
    })

    (mkFeatureTest {
      name = "desktop-common-apps";
      feature = "sinnix.features.desktop.common-apps.enable";
      assertions =
        config:
        let
          hm = hmFor config;
          packageNames = map (pkg: pkg.name or "") hm.home.packages;
          yaziConfig = builtins.readFile ../dots/yazi/yazi.toml;
        in
        [
          {
            assertion = hm.xdg.configFile ? "yazi/yazi.toml";
            message = "Common desktop apps must link the Yazi config";
          }
          {
            assertion = hm.xdg.configFile ? "yazi/plugins/sinnix-video-preview.yazi/main.lua";
            message = "Common desktop apps must link the custom Yazi video preview plugin";
          }
          {
            assertion = builtins.any (name: lib.hasPrefix "media-preview-cache" name) packageNames;
            message = "Common desktop apps must install the media preview cache helper";
          }
          {
            assertion =
              lib.hasInfix "image_delay = 0" yaziConfig
              && lib.hasInfix "run = \"sinnix-video-preview\"" yaziConfig;
            message = "Yazi must use the custom instant video preview configuration";
          }
        ];
    })

    (mkFeatureTest {
      name = "desktop-terminal";
      feature = "sinnix.features.desktop.terminal.enable";
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = hm.programs.kitty.enable;
            message = "Kitty must be enabled";
          }
          {
            assertion =
              hm.programs.kitty.settings.shell == "${hm.home.homeDirectory}/.local/bin/sinnix-captured-shell";
            message = "Kitty must launch through the capture wrapper";
          }
          {
            assertion = hm.programs.kitty.settings.open_url_with == "xdg-open";
            message = "Kitty URL opening must stay delegated to xdg-open";
          }
          {
            assertion = hm.programs.kitty.settings.allow_remote_control == "socket-only";
            message = "Kitty remote control must stay socket-only";
          }
          {
            assertion = hm.programs.kitty.shellIntegration.mode == "no-prompt-mark no-title no-cursor";
            message = "Kitty shell integration must disable prompt/title/cursor features that interfere with the custom zsh prompt";
          }
        ];
    })

    (mkFeatureTest {
      name = "desktop-browser";
      feature = "sinnix.features.desktop.browser.enable";
      assertions =
        config:
        let
          hm = hmFor config;
          quteConfig = builtins.readFile ../dots/qutebrowser/config.py;
          chromePkgs = builtins.filter (pkg: (pkg.pname or "") == "google-chrome") hm.home.packages;
          chromePkg = if chromePkgs == [ ] then null else builtins.head chromePkgs;
          chromeDesktop =
            if chromePkg == null then
              ""
            else
              builtins.readFile "${chromePkg}/share/applications/google-chrome.desktop";
        in
        [
          {
            assertion = hm.xdg.configFile ? "qutebrowser/config.py";
            message = "Qutebrowser config must be linked";
          }
          {
            assertion = builtins.match ".*configfiles\\.read_autoconfig.*" quteConfig == null;
            message = "Qutebrowser config must target the pinned modern API directly";
          }
          {
            assertion = builtins.match ".*except Exception:.*" quteConfig == null;
            message = "Qutebrowser config must not silently swallow broad exceptions";
          }
          {
            assertion =
              chromePkg != null
              && !(lib.hasPrefix "google-chrome-trigger-capture" (chromePkg.name or ""))
              && builtins.match ".*Exec=.*/bin/google-chrome-stable.*" chromeDesktop != null;
            message = "Chrome desktop entry must point at the normal binary by default";
          }
        ];
    })

    (mkFeatureTest {
      name = "desktop-gaming";
      feature = "sinnix.features.desktop.gaming.enable";
      assertions =
        config:
        let
          hm = hmFor config;
          packageNames = map (pkg: pkg.name or "") hm.home.packages;
        in
        [
          {
            assertion = builtins.any (name: name == "factorio-steam") packageNames;
            message = "Gaming feature must install the factorio-steam launcher";
          }
          {
            assertion = config.sinnix.features.desktop.gaming.factorio.username == "Sinityy";
            message = "Gaming feature must preserve the nested Factorio username option";
          }
        ];
    })

    {
      name = "networking-resolved-router-authority";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "networking-test";
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.networking.networkmanager.dns == "systemd-resolved";
          message = "NetworkManager must keep using systemd-resolved as the local stub";
        }
        {
          assertion = config.services.resolved.enable;
          message = "systemd-resolved must stay enabled";
        }
        {
          assertion = config.services.resolved.settings.Resolve.DNSSEC == false;
          message = "Local systemd-resolved DNSSEC must be disabled when the router is the DNS authority";
        }
        {
          assertion = config.services.resolved.settings.Resolve.FallbackDNS == "";
          message = "Local systemd-resolved fallback DNS must be disabled when the router is authoritative";
        }
      ];
    }

    {
      name = "nextcloud-storage-wiring";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "nextcloud-storage-test";
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.age.secrets ? "nextcloud-address";
          message = "Agenix must define the nextcloud-address secret";
        }
        {
          assertion = config.age.secrets ? "borg-passphrase";
          message = "Agenix must define the borg-passphrase secret";
        }
        {
          assertion = config.age.secrets ? "nextcloud-webdav-credentials";
          message = "Agenix must still define the Nextcloud credentials secret";
        }
        {
          assertion = config.services.borgbackup.jobs.realm.encryption.mode == "repokey-blake2";
          message = "Realm Borg job must use repokey-blake2";
        }
        {
          assertion = config.services.borgbackup.jobs.var.encryption.mode == "repokey-blake2";
          message = "System Borg job must use repokey-blake2";
        }
        {
          assertion = config.programs.fuse.userAllowOther;
          message = "The rclone Nextcloud mount must permit allow_other";
        }
        {
          assertion = config.system.activationScripts ? nextcloudRcloneRuntime;
          message = "Nextcloud rclone mount units must be rendered at activation time from secrets";
        }
        {
          assertion = lib.hasInfix "runtime_unit_dir=/run/systemd/system" config.system.activationScripts.nextcloudRcloneRuntime.text;
          message = "Nextcloud runtime mount units must be rendered under /run/systemd/system";
        }
        {
          assertion = lib.hasInfix "Type=rclone" config.system.activationScripts.nextcloudRcloneRuntime.text;
          message = "Nextcloud runtime mount units must use the rclone mount helper";
        }
        {
          assertion = lib.hasInfix "/nextcloud/remote.php/dav/files/" config.system.activationScripts.nextcloudRcloneRuntime.text;
          message = "Nextcloud runtime wiring must target the actual /nextcloud WebDAV endpoint";
        }
        {
          assertion = lib.hasInfix "no_check_certificate" config.system.activationScripts.nextcloudRcloneRuntime.text;
          message = "Nextcloud runtime wiring must explicitly handle the hostname-mismatched LAN cert";
        }
      ];
    }

    # === Service Tests (using DSL) ===
    (mkServiceTest {
      name = "services-below";
      service = "below";
      assertions = config: [
        {
          assertion = config.systemd.services ? below;
          message = "Below service must exist";
        }
        {
          assertion = config.environment.systemPackages != [ ];
          message = "Below package must be installed";
        }
      ];
    })

    (mkServiceTest {
      name = "services-power-watchdog";
      service = "power-watchdog";
      assertions = config: [
        {
          assertion = config.systemd.services ? power-watchdog;
          message = "power-watchdog service must exist";
        }
      ];
    })

    (mkServiceTest {
      name = "services-transmission";
      service = "transmission";
      assertions = config: [
        {
          assertion = config.services.transmission.enable;
          message = "Transmission must be enabled";
        }
        {
          assertion = config.systemd.services.transmission.unitConfig ? RequiresMountsFor;
          message = "Transmission must declare required mounts";
        }
      ];
    })

    (mkServiceTest {
      name = "services-terminal-capture";
      service = "terminal-capture";
      assertions = config: [
        {
          assertion = builtins.any (
            rule: builtins.match ".*captures/asciinema.*" rule != null
          ) config.systemd.tmpfiles.rules;
          message = "Asciinema captures directory tmpfiles entry must exist";
        }
        {
          assertion = (hmFor config).home.file ? ".local/bin/sinnix-captured-shell";
          message = "The terminal capture launcher must be linked into ~/.local/bin";
        }
        {
          assertion =
            (hmFor config).home.sessionVariables.SINNIX_CAPTURE_ROOT == "/realm/data/captures/asciinema";
          message = "The capture root session variable must point at the canonical asciinema directory";
        }
        {
          assertion = (hmFor config).home.sessionVariables.SINNIX_CAPTURE_TERMINAL == "kitty";
          message = "The capture terminal session variable must identify Kitty";
        }
        {
          assertion = lib.hasInfix "sinnix-terminal-capture-hooks.zsh" (hmFor config)
          .programs.zsh.initContent;
          message = "The zsh init path must source the terminal capture hooks";
        }
        {
          assertion =
            builtins.match ".*SUCCESS_BACKOFF_SECONDS.*sleep.*" (builtins.readFile ../scripts/rawlog-loop)
            != null;
          message = "rawlog-loop must back off after fast success exits";
        }
      ];
    })

    (mkServiceTest {
      name = "services-sentinel";
      service = "sentinel";
      assertions = config: [
        {
          assertion = config.systemd.services ? sinnix-sentinel;
          message = "sinnix-sentinel oneshot service must exist";
        }
        {
          assertion = config.systemd.timers ? sinnix-sentinel;
          message = "sinnix-sentinel timer must exist";
        }
        {
          assertion = config.environment.etc ? "sinnix/health-policy.json";
          message = "health-policy.json must be generated (from introspection.nix)";
        }
        {
          assertion = config.environment.etc ? "sinnix/config.json";
          message = "config.json must be generated (from introspection.nix)";
        }
        {
          assertion = builtins.any (
            rule: builtins.match ".*sinnix-sentinel.*" rule != null
          ) config.systemd.tmpfiles.rules;
          message = "sentinel event log directory must be created via tmpfiles";
        }
      ];
    })

    # Note: sinex service test omitted — sinex requires PostgreSQL, TLS certs,
    # and agenix secrets which are too heavyweight for config-only assertion tests.
    # The sinex service is verified via the full sinnix-prime build.

    # === Bundle Tests (using DSL) ===
    (mkBundleTest {
      name = "bundle-dev";
      bundle = "dev";
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = hm.programs.zsh.enable;
            message = "Dev bundle must enable zsh";
          }
          {
            assertion = hm.programs.git.enable;
            message = "Dev bundle must enable git";
          }
          {
            assertion = hm.programs.tmux.enable;
            message = "Dev bundle must enable tmux";
          }
        ];
    })

    (mkBundleTest {
      name = "bundle-desktop";
      bundle = "desktop";
      extraModules = [
        (
          { lib, pkgs, ... }:
          {
            hardware.graphics.enable = lib.mkForce false;
            # Provide dummy graphics package for headless test evaluation
            hardware.graphics.package = lib.mkForce pkgs.mesa;
            hardware.graphics.package32 = lib.mkForce pkgs.pkgsi686Linux.mesa;
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.programs.hyprland.enable or false;
          message = "Desktop must enable hyprland";
        }
        {
          assertion = config.services.pipewire.enable or false;
          message = "Desktop must enable audio";
        }
      ];
    })

    # === Manual Tests (need custom module logic) ===
    {
      name = "minimal-no-features";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "minimal";
            sinnix.bundles.dev.enable = false;
          }
        )
      ];
      assertions =
        config:
        let
          hm = hmFor config;
        in
        [
          {
            assertion = !(hm.programs.starship.enable or false);
            message = "Starship should not be enabled in minimal";
          }
          {
            assertion = !(config.services.transmission.enable or false);
            message = "Transmission should not be enabled in minimal";
          }
        ];
    }

    {
      name = "desktop-bluetooth-persistence";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "desktop-bluetooth-persistence";
            sinnix.machine.isDesktop = true;
            sinnix.persistence.enable = true;
          }
        )
      ];
      assertions =
        config:
        let
          isBluetoothDir =
            entry:
            if builtins.isAttrs entry then
              (entry.directory or null) == "/var/lib/bluetooth"
            else
              entry == "/var/lib/bluetooth";
        in
        [
          {
            assertion = config.hardware.bluetooth.enable or false;
            message = "Desktop hosts must enable Bluetooth support";
          }
          {
            assertion = builtins.any isBluetoothDir config.sinnix.persistence.system.directories;
            message = "Bluetooth state must be persisted under /var/lib/bluetooth";
          }
        ];
    }

    {
      name = "paths-configured";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "paths-test";
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.sinnix.paths.realmRoot == "/realm";
          message = "realmRoot must be /realm";
        }
        {
          assertion = config.sinnix.paths.dataRoot == "/realm/data";
          message = "dataRoot must be /realm/data";
        }
        {
          assertion = config.sinnix.paths.capturesRoot == "/realm/data/captures";
          message = "capturesRoot must be correct";
        }
        {
          assertion = config.sinnix.user.name == "sinity";
          message = "Default user must be sinity";
        }
      ];
    }

    # === Password/Secrets Safety Tests ===
    {
      name = "password-secrets-wiring";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "password-test";
          }
        )
      ];
      assertions = config: [
        {
          assertion = config.users.mutableUsers == false;
          message = "mutableUsers must be false (declarative passwords)";
        }
        {
          assertion = config.users.users.${config.sinnix.user.name} ? hashedPasswordFile;
          message = "User must have hashedPasswordFile set (not inline hash)";
        }
        {
          assertion = config.users.users.root ? hashedPasswordFile;
          message = "Root must have hashedPasswordFile set (not inline hash)";
        }
        {
          assertion =
            config.users.users.${config.sinnix.user.name}.hashedPasswordFile
            == config.sinnix.secrets.paths."${config.sinnix.user.name}-password";
          message = "User password file must point to agenix secret path";
        }
        {
          assertion = config.users.users.root.hashedPasswordFile == config.sinnix.secrets.paths.root-password;
          message = "Root password file must point to agenix secret path";
        }
        {
          assertion = config.system.activationScripts ? passwordSafetyNet;
          message = "Password safety net activation script must exist";
        }
        {
          assertion = config.age.secrets ? "${config.sinnix.user.name}-password";
          message = "Agenix must have user password secret configured";
        }
        {
          assertion = config.age.secrets ? "root-password";
          message = "Agenix must have root password secret configured";
        }
      ];
    }

    # === Router Config Tests ===
    # Verify sinnix-gw OpenWrt config evaluates without errors
    # (no NixOS VM needed — just checks the Nix expressions)
    {
      name = "router-config-evaluates";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "router-test";
          }
        )
      ];
      assertions =
        _config:
        let
          routerCfg = import ../hosts/sinnix-gw/default.nix { inherit lib; };
          openwrtLib = import ../modules/lib/openwrt.nix { inherit lib; };
          uciScript = openwrtLib.mkUciScript routerCfg.uci;
          pkgScript = openwrtLib.mkOpkgScript routerCfg.packages;

          # Helper: check if string contains a substring
          contains = haystack: needle: builtins.match ".*${lib.escapeRegex needle}.*" haystack != null;
          # Helper: check if string matches regex (multiline via [\s\S])
          matchesRegex = haystack: regex: builtins.match regex haystack != null;
        in
        [
          # ── Basic metadata ──
          {
            assertion = routerCfg.hostname == "sinnix-gw";
            message = "Router hostname must be sinnix-gw";
          }
          {
            assertion = routerCfg.address == "192.168.1.1";
            message = "Router address must be 192.168.1.1";
          }
          {
            assertion = builtins.length routerCfg.packages > 0;
            message = "Router must have packages to install";
          }
          {
            assertion = builtins.stringLength uciScript > 100;
            message = "UCI script must generate non-trivial output";
          }
          {
            assertion = builtins.stringLength pkgScript > 10;
            message = "Package script must generate output";
          }
          {
            assertion = builtins.stringLength routerCfg.postCommands > 100;
            message = "Post-commands must be non-empty";
          }

          # ── Ash compatibility (no pipefail) ──
          {
            assertion = !(contains uciScript "pipefail");
            message = "UCI script must not contain pipefail (ash incompatible)";
          }
          {
            assertion = !(contains pkgScript "pipefail");
            message = "Package script must not contain pipefail (ash incompatible)";
          }

          # ── UCI script is a fragment (no embedded shebang) ──
          {
            assertion = !(contains uciScript "#!/bin/sh");
            message = "UCI script must not contain shebang (it's a fragment, not standalone)";
          }

          # ── Critical UCI sections exist ──
          {
            assertion = contains uciScript "network.lan=";
            message = "UCI script must configure LAN interface";
          }
          {
            assertion = contains uciScript "network.wan=";
            message = "UCI script must configure WAN interface";
          }
          {
            assertion = contains uciScript "wireless.radio0=";
            message = "UCI script must configure radio0 (2.4GHz)";
          }
          {
            assertion = contains uciScript "wireless.radio1=";
            message = "UCI script must configure radio1 (5GHz)";
          }
          {
            assertion = contains uciScript "sqm.wan_qos=";
            message = "UCI script must configure SQM";
          }
          {
            assertion = contains uciScript "firewall.defaults=";
            message = "UCI script must configure firewall defaults";
          }
          {
            assertion = contains uciScript "dhcp.dnsmasq=";
            message = "UCI script must configure dnsmasq";
          }

          # ── UCI commit commands present ──
          {
            assertion = contains uciScript "uci commit network";
            message = "UCI script must commit network package";
          }
          {
            assertion = contains uciScript "uci commit wireless";
            message = "UCI script must commit wireless package";
          }
          {
            assertion = contains uciScript "uci commit firewall";
            message = "UCI script must commit firewall package";
          }

          # ── postCommands content ──
          {
            assertion = contains routerCfg.postCommands "authorized_keys";
            message = "Post-commands must deploy SSH authorized key";
          }
          {
            assertion = contains routerCfg.postCommands "https-dns-proxy";
            message = "Post-commands must configure https-dns-proxy (DoH)";
          }
          {
            assertion = contains routerCfg.postCommands "network reload";
            message = "Post-commands must reload network";
          }
          {
            assertion = contains routerCfg.postCommands "nf_conntrack_max";
            message = "Post-commands must tune conntrack table";
          }
        ];
    }

    # === Backup Tests ===
    {
      name = "backup-btrbk";
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = "backup-test";
          }
        )
      ];
      assertions =
        config:
        let
          hasConf = config.environment.etc ? "btrbk/btrbk.conf";
          conf = if hasConf then config.environment.etc."btrbk/btrbk.conf".text else "";
          realmJob = config.services.borgbackup.jobs.realm;
          varJob = config.services.borgbackup.jobs.var;
          subvolumeGuard =
            config.systemd.services.sinnix-realm-sinex-target-subvolume.script or "";
          hasTmpfilesRule =
            pattern:
            builtins.any (rule: builtins.match ".*${pattern}.*" rule != null) config.systemd.tmpfiles.rules;
        in
        [
          # Core service
          {
            assertion = config.systemd.services ? btrbk;
            message = "btrbk service must exist";
          }
          {
            assertion = config.systemd.timers ? btrbk;
            message = "btrbk timer must exist";
          }
          {
            assertion = builtins.match ".*btrfs subvolume show.*" subvolumeGuard != null;
            message = "sinex target guard must detect an existing Btrfs subvolume rather than requiring a mountpoint";
          }
          # Config deployed
          {
            assertion = hasConf;
            message = "btrbk config must be deployed to /etc";
          }
          # Config contains correct paths (guarded — conf is "" if etc file missing)
          {
            assertion = hasConf && builtins.match ".*volume /realm.*" conf != null;
            message = "btrbk config must include /realm volume";
          }
          {
            assertion = hasConf && builtins.match ".*volume /neo-outer-realm.*" conf != null;
            message = "btrbk config must include neo-outer-realm volume";
          }
          {
            assertion = hasConf && builtins.match ".*volume /\n.*" conf != null;
            message = "btrbk config must include root volume for rollback snapshots";
          }
          # Retention policy present
          {
            assertion = hasConf && builtins.match ".*volume /realm\n      snapshot_dir   \.snapshot\n      subvolume \.\n        snapshot_preserve       3d.*" conf != null;
            message = "btrbk config must keep /realm at 3d retention";
          }
          {
            assertion = hasConf && builtins.match ".*volume /persist\n      snapshot_dir   \.snapshot\n      subvolume \.\n        snapshot_preserve       14d 52w.*" conf != null;
            message = "btrbk config must preserve long-horizon /persist snapshots";
          }
          {
            assertion = realmJob.repo == "file:///outer-realm/backup/borg-realm-v2";
            message = "Realm Borg job must target the v2 encrypted repository via file URI";
          }
          {
            assertion = varJob.repo == "file:///outer-realm/backup/borg-var-v2";
            message = "System Borg job must target the v2 encrypted repository via file URI";
          }
          {
            assertion = realmJob.paths == [ "/run/borgbackup-snapshot-inputs/realm/./" ];
            message = "Realm Borg job must archive the bind-mounted snapshot contents";
          }
          {
            assertion = varJob.paths == [ "/run/borgbackup-snapshot-inputs/var/./" ];
            message = "System Borg job must archive the bind-mounted snapshot contents";
          }
          {
            assertion = builtins.match ".*mount --bind.*" realmJob.preHook != null;
            message = "Realm Borg job must bind-mount the latest snapshot before backup";
          }
          {
            assertion = builtins.match ".*mount --bind.*" varJob.preHook != null;
            message = "System Borg job must bind-mount the latest snapshot before backup";
          }
          # Snapshot dirs created by tmpfiles
          {
            assertion = builtins.any (
              rule: builtins.match ".*\\.snapshot.*" rule != null
            ) config.systemd.tmpfiles.rules;
            message = "Snapshot directories must be created via tmpfiles";
          }
          {
            assertion = hasTmpfilesRule "/run/borgbackup-snapshot-inputs";
            message = "Borg snapshot bind-mount staging directories must be created via tmpfiles";
          }
          {
            assertion = config.system.activationScripts ? borgRepositoryDirectories;
            message = "Borg repository directories must be created during activation";
          }
        ];
    }

      ];
    in
    mkSystemChecks system testSpecs;
in
{
  perSystem =
    { system, ... }:
    let
      pkgs = pkgsFor system;
      terminalCaptureRuntime =
        pkgs.runCommand "sinnix-terminal-capture-runtime-check"
          {
            nativeBuildInputs = [
              pkgs.asciinema_3
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.util-linux
              pkgs.zsh
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            export PATH="${
              lib.makeBinPath [
                pkgs.asciinema_3
                pkgs.coreutils
                pkgs.findutils
                pkgs.gnugrep
                pkgs.jq
                pkgs.util-linux
                pkgs.zsh
              ]
            }:$PATH"
            mkdir -p "$HOME" "$TMPDIR/captures"

            cat > "$TMPDIR/fake-shell.zsh" <<'EOF'
            #!${pkgs.zsh}/bin/zsh
            set -eu
            source ${../scripts/sinnix-terminal-capture-hooks.zsh}
            print -r -- "terminal-capture-ready"
            true
            exit 0
            EOF
            chmod +x "$TMPDIR/fake-shell.zsh"

            transcript="$TMPDIR/terminal-capture-runtime.typescript"

            script -qfec "env \
              EPOCHREALTIME='1773285652,647035000' \
              HOME='$HOME' \
              HOSTNAME='terminal-capture-test' \
              KITTY_PID='4242' \
              SHELL='$TMPDIR/fake-shell.zsh' \
              SINNIX_CAPTURE_CAST_FILE='$TMPDIR/poison.cast' \
              SINNIX_CAPTURE_EVENTS_FILE='$TMPDIR/poison.events.jsonl' \
              SINNIX_CAPTURE_ROOT='$TMPDIR/captures' \
              SINNIX_CAPTURE_SESSION_ID='poison-session' \
              TERM='xterm-kitty' \
              USER='tester' \
              ${pkgs.bash}/bin/bash ${../scripts/sinnix-captured-shell}" "$transcript"

            grep -q "terminal-capture-ready" "$transcript"

            session_json="$(find "$TMPDIR/captures" -type f -name session.json | sed -n '1p')"
            events_json="$(find "$TMPDIR/captures" -type f -name events.jsonl | sed -n '1p')"
            cast_file="$(find "$TMPDIR/captures" -type f -name session.cast | sed -n '1p')"

            test -n "$session_json"
            test -n "$events_json"
            test -n "$cast_file"

            session_dir="$(dirname "$session_json")"
            session_id="$(basename "$session_dir")"
            month_dir="$(dirname "$session_dir")"
            day_dir="$(basename "$month_dir")"
            year_month_dir="$(dirname "$month_dir")"
            month_name="$(basename "$year_month_dir")"
            year_name="$(basename "$(dirname "$year_month_dir")")"

            test "$day_dir" != "$session_id"
            [[ "$year_name" =~ ^[0-9]{4}$ ]]
            [[ "$month_name" =~ ^[0-9]{2}$ ]]
            [[ "$day_dir" =~ ^[0-9]{2}$ ]]
            test "$cast_file" = "$session_dir/session.cast"
            test "$events_json" = "$session_dir/events.jsonl"
            test -z "$(find "$TMPDIR/captures" -maxdepth 1 -type f | sed -n '1p')"
            test -z "$(find "$TMPDIR/captures" -type f -name '*.cast.meta' | sed -n '1p')"

            jq -e '
              .schema == "terminal-session-v1" and
              .session_id == $session_id and
              (.started_at_ms | type) == "number" and
              (.command_count | type) == "number" and
              .command_count >= 1 and
              .event_count >= 4 and
              .cast_path == $cast_path and
              .events_path == $events_path and
              .host == "terminal-capture-test" and
              .terminal == "kitty" and
              .exit_reason == "shell_exit" and
              .cleanup_escalated == false and
              .recorder_exit_code == 0 and
              (.session_id | test(",") | not) and
              .session_id != "poison-session" and
              .cast_path != $poison_cast and
              .events_path != $poison_events
            ' \
              --arg session_id "$session_id" \
              --arg cast_path "$cast_file" \
              --arg events_path "$events_json" \
              --arg poison_cast "$TMPDIR/poison.cast" \
              --arg poison_events "$TMPDIR/poison.events.jsonl" \
              "$session_json" >/dev/null

            jq -s -e '
              length >= 4 and
              .[0].type == "session_start" and
              .[-1].type == "session_end" and
              ([.[] | select(.type == "command_start")] | length) >= 1 and
              all(.[]; .session_id != "poison-session")
            ' "$events_json" >/dev/null

            touch "$out"
          '';
      terminalCaptureRuntimeFailure =
        pkgs.runCommand "sinnix-terminal-capture-runtime-failure-check"
          {
            nativeBuildInputs = [
              pkgs.asciinema_3
              pkgs.coreutils
              pkgs.findutils
              pkgs.gnugrep
              pkgs.jq
              pkgs.util-linux
              pkgs.zsh
            ];
          }
          ''
            export HOME="$TMPDIR/home"
            mkdir -p "$HOME" "$TMPDIR/captures" "$TMPDIR/bin"

            cat > "$TMPDIR/bin/asciinema" <<'EOF'
            #!${pkgs.bash}/bin/bash
            set -euo pipefail

            command_path=""
            output_path=""

            while (($#)); do
              case "$1" in
                rec)
                  shift
                  ;;
                --command)
                  command_path="$2"
                  shift 2
                  ;;
                --*)
                  if (($# >= 2)) && [[ "$2" != --* ]]; then
                    shift 2
                  else
                    shift
                  fi
                  ;;
                *)
                  output_path="$1"
                  shift
                  ;;
              esac
            done

            test -n "$command_path"
            test -n "$output_path"
            mkdir -p "$(dirname "$output_path")"
            printf '{"version": 3, "width": 80, "height": 24, "timestamp": 0}\n' > "$output_path"
            "$command_path"
            exit 42
            EOF
            chmod +x "$TMPDIR/bin/asciinema"

            cat > "$TMPDIR/fake-shell.zsh" <<'EOF'
            #!${pkgs.zsh}/bin/zsh
            set -eu
            source ${../scripts/sinnix-terminal-capture-hooks.zsh}
            print -r -- "terminal-capture-ready"
            true
            exit 0
            EOF
            chmod +x "$TMPDIR/fake-shell.zsh"

            export PATH="$TMPDIR/bin:${
              lib.makeBinPath [
                pkgs.coreutils
                pkgs.findutils
                pkgs.gnugrep
                pkgs.jq
                pkgs.util-linux
                pkgs.zsh
              ]
            }:$PATH"

            transcript="$TMPDIR/terminal-capture-runtime-failure.typescript"

            set +e
            script -qfec "env \
              EPOCHREALTIME='1773285652,647035000' \
              HOME='$HOME' \
              HOSTNAME='terminal-capture-test' \
              KITTY_PID='4242' \
              SHELL='$TMPDIR/fake-shell.zsh' \
              SINNIX_CAPTURE_ROOT='$TMPDIR/captures' \
              TERM='xterm-kitty' \
              USER='tester' \
              ${pkgs.bash}/bin/bash ${../scripts/sinnix-captured-shell}" "$transcript"
            status=$?
            set -e

            test "$status" -eq 42
            grep -q "terminal-capture-ready" "$transcript"

            session_json="$(find "$TMPDIR/captures" -type f -name session.json | sed -n '1p')"
            events_json="$(find "$TMPDIR/captures" -type f -name events.jsonl | sed -n '1p')"
            cast_file="$(find "$TMPDIR/captures" -type f -name session.cast | sed -n '1p')"

            test -n "$session_json"
            test -n "$events_json"
            test -n "$cast_file"
            test -z "$(find "$TMPDIR/captures" -maxdepth 1 -type f | sed -n '1p')"
            test -z "$(find "$TMPDIR/captures" -type f -name '*.cast.meta' | sed -n '1p')"

            jq -e '
              .schema == "terminal-session-v1" and
              (.started_at_ms | type) == "number" and
              .exit_reason == "shell_exit" and
              .exit_code == 0 and
              .recorder_exit_code == 42 and
              .cleanup_escalated == false and
              .command_count >= 1 and
              .event_count >= 4 and
              (.session_id | test(",") | not)
            ' "$session_json" >/dev/null

            jq -s -e '
              length >= 4 and
              .[0].type == "session_start" and
              .[-1].type == "session_end"
            ' "$events_json" >/dev/null

            touch "$out"
          '';
    in
    {
      checks = (mkSpecChecks system) // {
        terminal-capture-runtime = terminalCaptureRuntime;
        terminal-capture-runtime-failure = terminalCaptureRuntimeFailure;
      };
    };
}
