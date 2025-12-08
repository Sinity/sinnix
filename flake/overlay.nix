{
  inputs,
  ...
}:
{
  nixpkgs.overlays = [
    inputs.sinex.overlays.default
    inputs.nix-vscode-extensions.overlays.default

    (
      final: prev:
      let
        inherit (final) lib;
        pythonOverrides = _self: super: {
          # Upstream aggdraw test suite flakes on Python 3.13; keep disabled to avoid eval/switch failures.
          aggdraw = super.aggdraw.overridePythonAttrs (_old: {
            doCheck = false;
          });
        };
        hyprlandPatches = builtins.path {
          path = ../patches/hyprland;
          name = "sinnix-hyprland-patches";
        };
        hyprlandPatch = name: hyprlandPatches + "/${name}";
      in
      {
        hyprland = prev.hyprland.overrideAttrs (old: {
          patches = (old.patches or [ ]) ++ [
            (hyprlandPatch "suppress-color-warning.patch")
            (hyprlandPatch "check-monitor-null.patch")
            (hyprlandPatch "special-workspace-damage.patch")
            (hyprlandPatch "guard-last-monitor.patch")
          ];
          postPatch = (old.postPatch or "") + ''
                    substituteInPlace src/Compositor.cpp \
                      --replace '        if (pw->m_isMapped)
                    g_pHyprRenderer->damageMonitor(pw->m_monitor.lock());

            };' '        if (pw->m_isMapped) {
                    if (m_monitors.empty()) {
                        Debug::log(WARN, "[sinnix] skip z-order damage: no active monitors");
                    } else if (const auto PMONITOR = pw->m_monitor.lock()) {
                        g_pHyprRenderer->damageMonitor(PMONITOR);
                    } else {
                        Debug::log(WARN, "[sinnix] skip z-order damage: window monitor vanished");
                    }
                }

            };'
          '';
        });

        uwsm = prev.uwsm.overrideAttrs (old: {
          patches = (old.patches or [ ]) ++ [
            ../patches/uwsm/fix-systemd-unit-escaping.patch
          ];
        });

        pwvucontrol = prev.pwvucontrol.overrideAttrs (old: {
          patches = (old.patches or [ ]) ++ [
            ../patches/pwvucontrol/graceful-format-missing-data.patch
          ];
        });

        polylogue = inputs.polylogue.packages.${final.stdenv.hostPlatform.system}.polylogue;


        aionui =
          let
            pname = "aionui";
            version = "1.4.2";
            src = final.fetchurl {
              url = "https://github.com/iOfficeAI/AionUi/releases/download/v${version}/AionUi-${version}-linux-x86_64.AppImage";
              hash = "sha256-7/eoVSyQoA9M3YUxlHRvvXBWeA0JelfHTupg98XzTus=";
            };
            appimageContents = final.appimageTools.extractType2 {
              inherit pname version src;
            };
          in
          final.appimageTools.wrapType2 {
            inherit pname version src;
            nativeBuildInputs = [ final.makeWrapper ];
            extraPkgs =
              pkgs: with pkgs; [
                alsa-lib
                at-spi2-atk
                at-spi2-core
                bash
                brotli
                cairo
                cups
                curl
                dbus
                expat
                fontconfig
                freetype
                gdk-pixbuf
                glib
                glibc
                gsettings-desktop-schemas
                gtk3
                krb5
                libdrm
                libglvnd
                libnotify
                libpulseaudio
                libsecret
                libuuid
                libxkbcommon
                mesa
                nspr
                nss
                pango
                systemd
                util-linux
                wayland
                xdg-utils
                zlib
                xorg.libX11
                xorg.libXcomposite
                xorg.libXcursor
                xorg.libXdamage
                xorg.libXext
                xorg.libXfixes
                xorg.libXi
                xorg.libXrandr
                xorg.libxcb
              ];

            extraInstallCommands = ''
              wrapProgram "$out/bin/${pname}" \
                --set-default QT_QPA_PLATFORM xcb \
                --run 'if [ -n ''${WAYLAND_DISPLAY:-} ]; then
                  set -- --ozone-platform-hint=auto --enable-features=WaylandWindowDecorations --enable-wayland-ime "$@"
                fi' \
                --set-default ELECTRON_FORCE_IS_PACKAGED 1

              install -m 444 -D ${appimageContents}/AionUi.desktop $out/share/applications/AionUi.desktop
              install -m 444 -D ${appimageContents}/AionUi.png $out/share/icons/hicolor/512x512/apps/AionUi.png
              substituteInPlace $out/share/applications/AionUi.desktop \
                --replace-fail 'Exec=AppRun' 'Exec=${pname}'

              if [ -d ${appimageContents}/usr/share/icons ]; then
                mkdir -p $out/share
                cp -R ${appimageContents}/usr/share/icons $out/share/
              fi
            '';

            meta = with final.lib; {
              description = "Desktop interface for managing Aion CLI coding agents";
              homepage = "https://github.com/iOfficeAI/AionUi";
              license = licenses.asl20;
              platforms = [ "x86_64-linux" ];
              mainProgram = pname;
            };
          };

        python313Packages = prev.python313Packages.overrideScope pythonOverrides;

        python3 = prev.python3.override {
          packageOverrides = prev.lib.composeExtensions (prev.python3.packageOverrides or (_self: _super: { })
          ) pythonOverrides;
        };

        postgresql16Packages = prev.postgresql16Packages // {
          timescaledb = prev.postgresql16Packages.timescaledb.overrideAttrs (_old: rec {
            version = "2.23.0";
            src = final.fetchFromGitHub {
              owner = "timescale";
              repo = "timescaledb";
              tag = version;
              hash = "sha256-wgRaWxGr48p8xMc+yOQEN196KAKyptMCk/UFKn23cos=";
            };
          });
        };

        bat = prev.bat.overrideAttrs (
          old:
          let
            updatedJsonSyntax = final.fetchurl {
              url = "https://raw.githubusercontent.com/sublimehq/Packages/0d07278457f43f56c0f2c95f883621ea6ed2d370/JSON/JSON.sublime-syntax";
              sha256 = "sha256-fit/TAmpFwyVi3oVvNq7f9Oia5BQ6qMU2tHlppyN9SQ=";
            };
          in
          {
            # bat 0.26.0 bundles a Dockerfile syntax referencing the newer JSON
            # grammar's `arrays` context (see sharkdp/bat#3446) while still
            # shipping the older JSON definition. Replace it here so cache builds
            # succeed without warnings until upstream releases a fix.
            postPatch = (old.postPatch or "") + ''
              mkdir -p assets/syntaxes/01_Packages/JSON
              cp ${updatedJsonSyntax} assets/syntaxes/01_Packages/JSON/JSON.sublime-syntax
            '';
          }
        );

        # Disable the package causing the issue until a fix is available
        aider-chat-full = prev.aider-chat-full.override {
          pythonPackages = final.python3Packages;
        };

        antigravity =
          let
            version = "1.11.5-1763627318";
            buildId = "8c0426ef5d23bfd70393626b41210e0b";
            src = final.fetchurl {
              url = "https://us-central1-apt.pkg.dev/projects/antigravity-auto-updater-dev/pool/antigravity-debian/antigravity_${version}_amd64_${buildId}.deb";
              sha256 = "1bak8hfhvgk183gcfvkl9rdkgkmcqwy3cqqym84k25bnlvnlpcq1";
            };

            xorgDeps = with final.xorg; [
              libX11
              libXcomposite
              libXcursor
              libXdamage
              libXext
              libXfixes
              libXi
              libXinerama
              libXrandr
              libXrender
              libXScrnSaver
              libXxf86vm
              libXtst
              libxkbfile
              libxcb
            ];

            commonDeps = [
              final.alsa-lib
              final.at-spi2-atk
              final.cairo
              final.cups
              final.expat
              final.fontconfig.lib
              final.gdk-pixbuf
              final.glib
              final.gtk3
              final.libappindicator-gtk3
              final.libdbusmenu
              final.libdrm
              final.libgbm
              final.libnotify
              final.libsecret
              final.libxkbcommon
              final.libxshmfence
              final.mesa
              final.nspr
              final.nss
              final.pango
              final.pulseaudio
              final.systemd
              final.util-linux
              final.zlib
              final.stdenv.cc.cc.lib
            ]
            ++ xorgDeps;

            libPath = final.lib.makeLibraryPath (
              commonDeps
              ++ [
                final.vulkan-loader
                final.libGL
                final.libglvnd
                final.openssl
              ]
            );
            binPath = final.lib.makeBinPath [
              final.coreutils
              final.findutils
              final.gnugrep
              final.glib
            ];
          in
          final.stdenv.mkDerivation {
            pname = "antigravity";
            inherit version src;

            nativeBuildInputs = [
              final.autoPatchelfHook
              final.dpkg
              final.makeBinaryWrapper
            ];

            buildInputs = commonDeps ++ [
              final.libGL
              final.libglvnd
              final.vulkan-loader
              final.openssl
            ];

            runtimeDependencies = [
              (final.lib.getLib final.systemd)
              final.libnotify
              final.libappindicator-gtk3
              final.libsecret
            ];

            dontConfigure = true;
            dontBuild = true;
            unpackPhase = ''
              runHook preUnpack
              dpkg-deb --fsys-tarfile $src | tar -x --no-same-owner --no-same-permissions
              runHook postUnpack
            '';

            installPhase = ''
              runHook preInstall

              mkdir -p $out
              cp -r usr/* $out/
              rm -rf $out/share/doc

              substituteInPlace $out/share/applications/antigravity.desktop \
                --replace-fail /usr/share/antigravity/antigravity $out/bin/antigravity
              substituteInPlace $out/share/applications/antigravity-url-handler.desktop \
                --replace-fail /usr/share/antigravity/antigravity $out/bin/antigravity

              sed -i "/ELECTRON=/iVSCODE_PATH='$out/share/antigravity'" \
                $out/share/antigravity/bin/antigravity

              mkdir -p $out/bin
              makeBinaryWrapper $out/share/antigravity/bin/antigravity $out/bin/antigravity \
                --prefix LD_LIBRARY_PATH : ${libPath} \
                --prefix PATH : ${binPath} \
                --add-flags "\''${NIXOS_OZONE_WL:+\''${WAYLAND_DISPLAY:+--ozone-platform-hint=auto --enable-features=WaylandWindowDecorations --enable-wayland-ime=true --wayland-text-input-version=3}}"

              runHook postInstall
            '';

            meta = with final.lib; {
              description = "Google's Antigravity IDE";
              homepage = "https://antigravity.google";
              sourceProvenance = with sourceTypes; [ binaryNativeCode ];
              license = licenses.unfree;
              platforms = [ "x86_64-linux" ];
              mainProgram = "antigravity";
            };
          };

      }
    )
  ];
}
