{
  inputs,
  ...
}:
let
  sinexOverlays =
    if builtins.getEnv "SINEX_DISABLE" == "1" then
      [ ]
    else if inputs ? sinex && inputs.sinex ? overlays && inputs.sinex.overlays ? default then
      [ inputs.sinex.overlays.default ]
    else
      [ ];
in
{
  nixpkgs.overlays = sinexOverlays ++ [
    # Community overlay providing large set of VSCode extensions
    inputs.nix-vscode-extensions.overlays.default

    (
      final: prev:
      let
        pythonOverrides = self: super: {
          spacy = super.spacy.overrideAttrs (old: rec {
            version = "3.8.4"; # last revision that still builds
            src = prev.fetchPypi {
              pname = "spacy";
              inherit version;
              sha256 = "sha256-G92R3l0MP2tqdnSX6uQyH3fF9qqoj4Tns5w8QAM3YCM";
            };
            meta = old.meta // {
              broken = false;
            };
          });

          questionary = super.questionary.overridePythonAttrs (old: {
            disabledTests = (old.disabledTests or [ ]) ++ [ "test_print_with_style" ];
          });
        };
        pgJsonschemaFor =
          postgresql:
          prev.buildPgrxExtension (
            finalAttrs:
            let
              version = "0.3.3";
            in
            {
              inherit postgresql;
              cargo-pgrx = prev.cargo-pgrx_0_12_6;

              pname = "pg_jsonschema";
              inherit version;

              src = final.fetchFromGitHub {
                owner = "supabase";
                repo = "pg_jsonschema";
                rev = "v${version}";
                hash = "sha256-Au1mqatoFKVq9EzJrpu1FVq5a1kBb510sfC980mDlsU=";
              };

              cargoHash = "sha256-FXqofhh89m6SFkOCdE4OCT/FgwzkM/ywyyv62mySODQ=";

              doCheck = false;

              meta = {
                description = "PostgreSQL extension for JSON Schema validation";
                homepage = "https://github.com/supabase/pg_jsonschema";
                license = final.lib.licenses.postgresql;
                platforms = postgresql.meta.platforms;
              };
            }
          );
      in
      {
        hyprland = prev.hyprland.overrideAttrs (old: {
          patches = (old.patches or [ ]) ++ [
            ../patches/hyprland/suppress-color-warning.patch
            ../patches/hyprland/check-monitor-null.patch
            ../patches/hyprland/special-workspace-damage.patch
            ../patches/hyprland/guard-last-monitor.patch
          ];
        });

        pwvucontrol = prev.pwvucontrol.overrideAttrs (old: {
          patches = (old.patches or [ ]) ++ [
            ../patches/pwvucontrol/graceful-format-missing-data.patch
          ];
        });

        uwsm = prev.uwsm.overrideAttrs (old: {
          patches = (old.patches or [ ]) ++ [
            ../patches/uwsm/fix-systemd-unit-escaping.patch
          ];
        });

        libutp = prev.libutp.overrideAttrs (old: {
          cmakeFlags = (old.cmakeFlags or [ ]) ++ [ "-DCMAKE_POLICY_VERSION=3.5" ];
          postPatch = (old.postPatch or "") + ''
            substituteInPlace CMakeLists.txt \
              --replace "cmake_minimum_required(VERSION 2.8" "cmake_minimum_required(VERSION 3.5"
          '';
        });

        pamixer = prev.pamixer.override {
          cxxopts = prev.cxxopts.override { enableUnicodeHelp = false; };
        };

        bpftrace = prev.bpftrace.override {
          llvmPackages = prev.llvmPackages_20;
        };

        ltrace = prev.ltrace.overrideAttrs (_old: {
          doCheck = false;
        });

        transmission_3 = prev.transmission_3.overrideAttrs (old: {
          postPatch = (old.postPatch or "") + ''
            substituteInPlace CMakeLists.txt \
              --replace "cmake_minimum_required(VERSION 2.8.12 FATAL_ERROR)" \
                       "cmake_minimum_required(VERSION 3.5 FATAL_ERROR)"
          '';
        });

        interception-tools = prev.interception-tools.overrideAttrs (old: {
          postPatch = (old.postPatch or "") + ''
            substituteInPlace CMakeLists.txt \
              --replace "cmake_minimum_required(VERSION 3.0)" \
                       "cmake_minimum_required(VERSION 3.5)"
          '';
        });

        autopanosiftc = prev.autopanosiftc.overrideAttrs (old: {
          cmakeFlags = (old.cmakeFlags or [ ]) ++ [ "-DCMAKE_POLICY_VERSION=3.5" ];
          postPatch = (old.postPatch or "") + ''
            substituteInPlace CMakeLists.txt \
              --replace "cmake_minimum_required(VERSION 2.8.12 FATAL_ERROR)" "cmake_minimum_required(VERSION 3.5 FATAL_ERROR)" \
              --replace "cmake_minimum_required(VERSION 2.8)" "cmake_minimum_required(VERSION 3.5)" \
              --replace "cmake_minimum_required(VERSION 2.6)" "cmake_minimum_required(VERSION 3.5)" \
              --replace "cmake_minimum_required(VERSION 2.4)" "cmake_minimum_required(VERSION 3.5)"
          '';
        });

        libsForQt5 = prev.libsForQt5 // {
          autopanosiftc = prev.libsForQt5.autopanosiftc.overrideAttrs (old: {
            cmakeFlags = (old.cmakeFlags or [ ]) ++ [ "-DCMAKE_POLICY_VERSION=3.5" ];
            postPatch = (old.postPatch or "") + ''
              substituteInPlace CMakeLists.txt \
                --replace "cmake_minimum_required(VERSION 2.8.12 FATAL_ERROR)" "cmake_minimum_required(VERSION 3.5 FATAL_ERROR)" \
                --replace "cmake_minimum_required(VERSION 2.8)" "cmake_minimum_required(VERSION 3.5)" \
                --replace "cmake_minimum_required(VERSION 2.6)" "cmake_minimum_required(VERSION 3.5)" \
                --replace "cmake_minimum_required(VERSION 2.4)" "cmake_minimum_required(VERSION 3.5)"
            '';
          });
        };

        interception-tools-plugins = prev.interception-tools-plugins // {
          caps2esc = prev.interception-tools-plugins.caps2esc.overrideAttrs (old: {
            postPatch = (old.postPatch or "") + ''
              substituteInPlace CMakeLists.txt \
                --replace "cmake_minimum_required(VERSION 3.0)" \
                         "cmake_minimum_required(VERSION 3.5)"
            '';
          });
        };

        # Override Codex CLI to a newer upstream tag
        codex = prev.codex.overrideAttrs (
          _old:
          let
            version = "0.47.0";
            newSrc = final.fetchFromGitHub {
              owner = "openai";
              repo = "codex";
              rev = "refs/tags/rust-v" + version;
              sha256 = "sha256-5AyatNXgHuia656OuSDozQzQv80bNHncgLN1X23bfM4=";
            };
            newCargo = final.rustPlatform.fetchCargoVendor {
              src = newSrc;
              sourceRoot = "source/codex-rs";
              hash = "sha256-PQ1NxwNBaI48gQ4GGoricA/j7vpsnaLlL6st5P+CTHk=";
            };
          in
          {
            inherit version;
            src = newSrc;
            cargoDeps = newCargo;
          }
        );
        python313Packages = prev.python313Packages.overrideScope pythonOverrides;

        python3 = prev.python3.override {
          packageOverrides = prev.lib.composeExtensions (prev.python3.packageOverrides or (_self: _super: { })
          ) pythonOverrides;
        };

        # Disable the package causing the issue until a fix is available
        aider-chat-full = prev.aider-chat-full.override {
          pythonPackages = final.python3Packages;
        };

        # claude-desktop-wayland = final.symlinkJoin {
        #   name = "claude-desktop-wayland";
        #   paths = [
        #     inputs.claude-desktop.packages.${pkgs.system}.claude-desktop-with-fhs
        #   ];
        #   buildInputs = [ final.makeWrapper ];
        #   postBuild = ''
        #     wrapProgram $out/bin/claude-desktop --add-flags "--enable-features=WaylandWindowDecorations --no-sandbox"
        #   '';
        # };

        claude-code-usage-monitor = final.python3Packages.buildPythonApplication {
          pname = "claude-code-usage-monitor";
          version = "unstable";
          src = inputs.claude-code-usage-monitor-src;

          pyproject = true;
          build-system = with final.python3Packages; [ setuptools ];

          propagatedBuildInputs = with final.python3Packages; [
            pytz
            requests
            beautifulsoup4
            lxml
            numpy
            pydantic
            pydantic-settings
            pyyaml
            rich
          ];

          # Use standard Python package installation instead of custom script install
          postInstall = ''
            # The package should install the console script via setuptools entry points
          '';

          meta = with final.lib; {
            description = "Real-time terminal monitoring tool for tracking Claude AI token usage";
            homepage = "https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor";
            license = licenses.mit;
          };
        };

        postgresqlPackages = prev.postgresqlPackages // {
          pg_jsonschema = pgJsonschemaFor prev.postgresql;
        };
        postgresql14Packages = prev.postgresql14Packages // {
          pg_jsonschema = pgJsonschemaFor prev.postgresql_14;
        };
        postgresql15Packages = prev.postgresql15Packages // {
          pg_jsonschema = pgJsonschemaFor prev.postgresql_15;
        };
        postgresql16Packages = prev.postgresql16Packages // {
          pg_jsonschema = pgJsonschemaFor prev.postgresql_16;
        };
        postgresql17Packages = prev.postgresql17Packages // {
          pg_jsonschema = pgJsonschemaFor prev.postgresql_17;
        };
        postgresql18Packages = prev.postgresql18Packages // {
          pg_jsonschema = pgJsonschemaFor prev.postgresql_18;
        };
      }
    )
  ];
}
