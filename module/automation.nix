# Automation Domain Module
# Complete orchestration (services + scripts)
# Consolidates: scripts, services, monitoring, scheduling

{ pkgs, ... }:
let
  runbg = pkgs.writeShellScriptBin "runbg" ''
    #!/usr/bin/env bash

    [ $# -eq 0 ] && {  # $# is number of args
        echo "$(${pkgs.coreutils}/bin/basename $0): missing command" >&2
        exit 1
    }
    prog="$(${pkgs.which}/bin/which "$1")"  # Validate command exists
    [ -z "$prog" ] && {
        echo "$(${pkgs.coreutils}/bin/basename $0): unknown command: $1" >&2
        exit 1
    }
    shift  # remove $1, now $prog, from args
    ${pkgs.coreutils}/bin/tty -s && exec </dev/null      # if stdin is a terminal, redirect from null
    ${pkgs.coreutils}/bin/tty -s <&1 && exec >/dev/null  # if stdout is a terminal, redirect to null
    ${pkgs.coreutils}/bin/tty -s <&2 && exec 2>&1        # stderr to stdout (which might not be null)
    "$prog" "$@" &  # $@ is all args
  '';

  lofi = pkgs.writeScriptBin "lofi" ''
    #!/usr/bin/env bash
    ${pkgs.libnotify}/bin/notify-send "起動 Lofi Music" "Enjoy!"
    ${pkgs.mpv}/bin/mpv "https://www.youtube.com/watch?v=jfKfPfyJRdk" --no-video --loop-playlist=inf
  '';

  toggle_blur = pkgs.writeScriptBin "toggle_blur" ''
    #!/usr/bin/env bash
    STATE=$(${pkgs.hyprland}/bin/hyprctl getoption decoration:blur:enabled | ${pkgs.gawk}/bin/awk 'NR==1{print $2}')
    if [ "$STATE" = "1" ]; then
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:blur:enabled false
    else
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:blur:enabled true
    fi
  '';

  toggle_opacity = pkgs.writeScriptBin "toggle_opacity" ''
    #!/usr/bin/env bash
    STATE=$(${pkgs.hyprland}/bin/hyprctl getoption decoration:inactive_opacity | ${pkgs.gawk}/bin/awk 'NR==1{print $2}')
    if [ "$STATE" = "0.900000" ]; then
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:inactive_opacity 1.0
    else
        ${pkgs.hyprland}/bin/hyprctl keyword decoration:inactive_opacity 0.9
    fi
  '';

  toggle_waybar = pkgs.writeScriptBin "toggle_waybar" ''
    #!/usr/bin/env bash
    if ${pkgs.procps}/bin/pgrep -x "waybar" > /dev/null; then
        ${pkgs.procps}/bin/pkill waybar
    else
        ${pkgs.waybar}/bin/waybar &
    fi
  '';

  compress = pkgs.writeScriptBin "compress" ''
    #!/usr/bin/env bash
    if [ $# -eq 0 ]; then
        echo "Usage: compress <file_or_directory> [output_name]"
        exit 1
    fi

    INPUT="$1"
    OUTPUT="$2"

    if [ -z "$OUTPUT" ]; then
        OUTPUT="$(${pkgs.coreutils}/bin/basename "$INPUT").tar.gz"
    fi

    ${pkgs.gnutar}/bin/tar -czf "$OUTPUT" "$INPUT"
    echo "Compressed $INPUT to $OUTPUT"
  '';

  extract = pkgs.writeScriptBin "extract" ''
    #!/usr/bin/env bash
    if [ $# -eq 0 ]; then
        echo "Usage: extract <file>"
        exit 1
    fi

    case "$1" in
        *.tar.gz|*.tgz) ${pkgs.gnutar}/bin/tar -xzf "$1" ;;
        *.tar.bz2|*.tbz2) ${pkgs.gnutar}/bin/tar -xjf "$1" ;;
        *.tar) ${pkgs.gnutar}/bin/tar -xf "$1" ;;
        *.zip) ${pkgs.unzip}/bin/unzip "$1" ;;
        *.rar) ${pkgs.unrar}/bin/unrar x "$1" ;;
        *.7z) ${pkgs.p7zip}/bin/7z x "$1" ;;
        *) echo "Unsupported format: $1" ;;
    esac
  '';

  show-keybinds = pkgs.writeScriptBin "show-keybinds" ''
    #!/usr/bin/env bash
    config_file=~/.config/hypr/hyprland.conf
    keybinds=$(${pkgs.gnugrep}/bin/grep -oP '(?<=bind=).*' $config_file)
    keybinds=$(echo "$keybinds" | ${pkgs.gnused}/bin/sed 's/,\([^,]*\)$/ = \1/' | ${pkgs.gnused}/bin/sed 's/, exec//g' | ${pkgs.gnused}/bin/sed 's/^,//g')
    ${pkgs.tofi}/bin/tofi --width=50% <<< "$keybinds"
  '';

  vm-start = pkgs.writeShellScriptBin "vm-start" ''
    # VM name
    vm_name="win10"
    export LIBVIRT_DEFAULT_URI="qemu:///system"

    # change workspace
    ${pkgs.hyprland}/bin/hyprctl dispatch workspace 6

    ${pkgs.libvirt}/bin/virsh start "$vm_name"
    ${pkgs.virt-viewer}/bin/virt-viewer -f -w -a "$vm_name"
  '';

  # ASBL mitigation script
  asbl-fooler = pkgs.writeShellApplication {
    name = "asbl-no-moar";
    runtimeInputs = [
      pkgs.wl-gammactl
      pkgs.coreutils
    ];
    text = ''
      #!/usr/bin/env bash

      echo "Setting gamma to 1.2"
      timeout -p 3500ms ${pkgs.wl-gammactl}/bin/wl-gammactl -g 1.2 || true
      echo "Gamma is back to 1.0"
    '';
  };

  # Powerful shader effects controller
  hyperfx = pkgs.writeShellApplication {
    name = "hyperfx";
    runtimeInputs = [
      pkgs.hyprland
      pkgs.libnotify
      pkgs.coreutils
    ];
    text = ''
      #!/usr/bin/env bash

      SHADER_DIR="/realm/project/sinnix/module"

      case "$1" in
        matrix)
          hyprctl keyword decoration:screen_shader "$SHADER_DIR/shader-matrix.glsl"
          notify-send "HyperFX" "Matrix rain activated" -t 2000
          ;;
        cyberpunk)
          hyprctl keyword decoration:screen_shader "$SHADER_DIR/shader-cyberpunk.glsl"
          notify-send "HyperFX" "Cyberpunk mode activated" -t 2000
          ;;
        warp|reality)
          hyprctl keyword decoration:screen_shader "$SHADER_DIR/shader-reality-warp.glsl"
          notify-send "HyperFX" "Reality warp activated" -t 2000
          ;;
        oled)
          # Use the hyproled shader for OLED protection
          temp_shader="/dev/shm/hyproled_shader.glsl"
          cat > "$temp_shader" <<'EOF'
      precision highp float;
      varying vec2 v_texcoord;
      uniform sampler2D tex;

      void main() {
          vec4 originalColor = texture2D(tex, v_texcoord);
          vec2 fragCoord = gl_FragCoord.xy;
          bool isEvenPixel = mod(fragCoord.x + fragCoord.y, 2.0) == 0.0;
          vec4 color = isEvenPixel ? originalColor : vec4(0.0, 0.0, 0.0, 1.0);
          gl_FragColor = color;
      }
      EOF
          hyprctl keyword decoration:screen_shader "$temp_shader"
          notify-send "HyperFX" "OLED protection activated" -t 2000
          ;;
        retro)
          # CRT TV effect
          temp_shader="/dev/shm/retro_shader.glsl"
          cat > "$temp_shader" <<'EOF'
      precision highp float;
      varying vec2 v_texcoord;
      uniform sampler2D tex;
      uniform float time;

      void main() {
          vec2 uv = v_texcoord;
          
          // CRT curvature
          vec2 crtUV = uv * 2.0 - 1.0;
          float curvature = 0.1;
          crtUV += crtUV * curvature * dot(crtUV, crtUV);
          crtUV = crtUV * 0.5 + 0.5;
          
          if (crtUV.x < 0.0 || crtUV.x > 1.0 || crtUV.y < 0.0 || crtUV.y > 1.0) {
              gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0);
              return;
          }
          
          vec4 color = texture2D(tex, crtUV);
          
          // Scanlines
          float scanline = sin(crtUV.y * 800.0) * 0.04;
          color.rgb -= scanline;
          
          // Phosphor RGB strips
          float strip = mod(gl_FragCoord.x, 3.0);
          if (strip < 1.0) color.gb *= 0.7;
          else if (strip < 2.0) color.rb *= 0.7;
          else color.rg *= 0.7;
          
          // Vignette
          float vignette = 1.0 - length(uv - 0.5) * 1.0;
          color.rgb *= vignette;
          
          gl_FragColor = color;
      }
      EOF
          hyprctl keyword decoration:screen_shader "$temp_shader"
          notify-send "HyperFX" "Retro CRT mode activated" -t 2000
          ;;
        off|clear|reset)
          hyprctl keyword decoration:screen_shader ""
          notify-send "HyperFX" "Shaders disabled" -t 2000
          ;;
        *)
          echo "Usage: hyperfx [matrix|cyberpunk|warp|oled|retro|off]"
          echo ""
          echo "Effects:"
          echo "  matrix     - Matrix digital rain"
          echo "  cyberpunk  - Glitch and neon effects"  
          echo "  warp       - Reality warping fractals"
          echo "  oled       - OLED burn-in protection"
          echo "  retro      - CRT TV simulation"
          echo "  off        - Disable all effects"
          ;;
      esac
    '';
  };

  # Scripts from ~/scripts
  combine-files = pkgs.writeShellScriptBin "combine-files" ''
    #!/usr/bin/env bash
    #
    # combine-files.sh — Combine multiple text files into a single structured document
    # Usage: ./combine-files.sh [options]

    set -euo pipefail
    IFS=$'\n\t'

    # ------------------------
    #  Dependencies check
    # ------------------------
    for cmd in fd fzf bat file stat date getopt; do
      command -v "$cmd" &>/dev/null || {
        echo "❌  '$cmd' is required but not installed." >&2
        exit 1
      }
    done

    # ------------------------
    #  Defaults & help
    # ------------------------
    directory="."
    output_file="combined.md"
    output_format="markdown"

    print_help() {
      cat <<EOF
    Usage: $(${pkgs.coreutils}/bin/basename "$0") [options]

    Combine multiple text files into a single structured document.

    Options:
      -d, --directory DIR   Directory to scan (default: current directory)
      -o, --output FILE     Output file (default: combined_configs.txt)
      -f, --format FORMAT   Output format: text, markdown (default: markdown)
      -h, --help            Show this help message
    EOF
      exit 0
    }

    # ------------------------
    #  Parse arguments
    # ------------------------
    OPTIONS=d:o:f:h
    LONGOPTS=directory:,output:,format:,help

    ! PARSED=$(${pkgs.util-linux}/bin/getopt --options=$OPTIONS --longoptions=$LONGOPTS --name "$0" -- "$@") && exit 2
    eval set -- "$PARSED"

    while true; do
      case "$1" in
      -d | --directory)
        directory="$2"
        shift 2
        ;;
      -o | --output)
        output_file="$2"
        shift 2
        ;;
      -f | --format)
        output_format="$2"
        shift 2
        ;;
      -h | --help) print_help ;;
      --)
        shift
        break
        ;;
      *) break ;;
      esac
    done

    # ------------------------
    #  Validate directory
    # ------------------------
    if [[ ! -d "$directory" ]]; then
      echo "Error: Directory '$directory' does not exist." >&2
      exit 1
    fi

    # ------------------------
    #  Gather & filter files
    # ------------------------
    # fd will respect .gitignore and skip hidden by default; we re‑include hidden but then
    # explicitly exclude a few infra dirs:
    mapfile -t all_files < <(
      ${pkgs.fd}/bin/fd --type f --hidden \
        --exclude .git --exclude .obsidian --exclude node_modules --exclude vendor --exclude build \
        . "$directory"
    )

    # remove non-text files
    files=()
    for f in "''${all_files[@]}"; do
      if ${pkgs.file}/bin/file --mime-type -b "$f" | ${pkgs.gnugrep}/bin/grep -q '^text/'; then
        files+=("$f")
      fi
    done

    if [[ ''${#files[@]} -eq 0 ]]; then
      echo "No suitable text files found in '$directory'." >&2
      exit 1
    fi

    # ------------------------
    #  fzf selection
    # ------------------------
    echo "Select files to include:"
    mapfile -t selected_files < <(
      printf '%s\n' "''${files[@]}" |
        ${pkgs.fzf}/bin/fzf --multi --layout=reverse \
          --preview 'sz=$(${pkgs.coreutils}/bin/stat -c%s {}); tk=$((sz/4)); \
                       printf "Size: %d bytes | Tokens: %d\n\n" "$sz" "$tk"; \
                       ${pkgs.bat}/bin/bat --style=numbers --color=always {}' \
          --preview-window=right:60%:wrap \
          --prompt="› "
    )

    if [[ ''${#selected_files[@]} -eq 0 ]]; then
      echo "No files selected. Exiting."
      exit 0
    fi

    # ------------------------
    #  Compute totals & header
    # ------------------------
    current_date=$(${pkgs.coreutils}/bin/date -u +"%Y-%m-%dT%H:%M:%SZ")
    total_files=''${#selected_files[@]}
    total_tokens=0

    # precompute size & token per file
    declare -A size_map token_map
    for f in "''${selected_files[@]}"; do
      sz=$(${pkgs.coreutils}/bin/stat -c%s "$f")
      tk=$((sz / 4))
      size_map["$f"]=$sz
      token_map["$f"]=$tk
      total_tokens=$((total_tokens + tk))
    done

    # ------------------------
    #  Write output
    # ------------------------
    : >"$output_file"

    if [[ "$output_format" == "markdown" ]]; then
      {
        echo '---'
        echo "generated: $current_date"
        echo "base_directory: $directory"
        echo "total_files: $total_files"
        echo "total_tokens_est: $total_tokens"
        echo '---'
        echo
        echo "## Table of Contents"
        echo
        i=1
        for f in "''${selected_files[@]}"; do
          rel=''${f#"$directory"/}
          echo "$i. [$rel](#file-$i)"
          i=$((i + 1))
        done
        echo
      } >>"$output_file"
    else
      # plain‑text header
      {
        echo "COMBINED FILES"
        echo "Generated: $current_date"
        echo "Directory: $directory"
        echo
      } >>"$output_file"
    fi

    # ------------------------
    #  Append each file
    # ------------------------
    i=1
    for f in "''${selected_files[@]}"; do
      rel=''${f#"$directory"/}
      sz=''${size_map["$f"]}
      tk=''${token_map["$f"]}
      typ=$(${pkgs.file}/bin/file -b "$f" | ${pkgs.coreutils}/bin/cut -d, -f1)

      if [[ "$output_format" == "markdown" ]]; then
        echo "<a id=\"file-$i\"></a>" >>"$output_file"
        echo "## File: $rel" >>"$output_file"
        echo >>"$output_file"
        echo "- Size: $sz bytes" >>"$output_file"
        echo "- Tokens: $tk" >>"$output_file"
        echo "- Type: $typ" >>"$output_file"
        echo >>"$output_file"
        # code‑block language detection (unchanged)
        ext=''${f##*.}
        case "$ext" in
        js | ts) lang=javascript ;;
        py) lang=python ;;
        rb) lang=ruby ;;
        sh | bash) lang=bash ;;
        nix) lang=nix ;;
        md) lang=markdown ;;
        html) lang=html ;;
        css) lang=css ;;
        json) lang=json ;;
        xml) lang=xml ;;
        lua) lang=lua ;;
        *) lang="" ;;
        esac
        echo '```'"$lang" >>"$output_file"
        ${pkgs.coreutils}/bin/cat "$f" >>"$output_file"
        echo '```' >>"$output_file"
        echo >>"$output_file"
      else
        # plain‑text
        echo "========================================" >>"$output_file"
        echo "FILE: $rel" >>"$output_file"
        echo "Size: $sz bytes | Tokens: $tk | Type: $typ" >>"$output_file"
        echo "========================================" >>"$output_file"
        echo >>"$output_file"
        ${pkgs.coreutils}/bin/cat "$f" >>"$output_file"
        echo -e "\n" >>"$output_file"
      fi

      i=$((i + 1))
    done

    echo "Done! Combined configuration saved to '$output_file'."
  '';

  log-to-knowledgebase = pkgs.writeShellScriptBin "log-to-knowledgebase" ''
    #!/usr/bin/env bash

    # Define file path
    LOG_FILE=/realm/knowledgebase/50_logs/raw-log.md
    DATETIME=$(${pkgs.coreutils}/bin/date "+%Y-%m-%d %H:%M:%S")

    # Extract recent entries (up to 1000) from the log file
    RECENT_ENTRIES=$(${pkgs.coreutils}/bin/tac "$LOG_FILE" | ${pkgs.coreutils}/bin/head -1000)

    # Get user input using tofi with recent entries as suggestions
    # --require-match=false allows entering custom text not in the list
    SELECTED=$(echo -e "$RECENT_ENTRIES" | ${pkgs.tofi}/bin/tofi --prompt-text="Log entry: " --width=80% --height=600 --require-match=false)

    # Exit if canceled
    if [ -z "$SELECTED" ]; then
      exit 0
    fi

    # Check if user selected an existing entry or typed a new one
    if echo "$RECENT_ENTRIES" | ${pkgs.gnugrep}/bin/grep -q "^$SELECTED$"; then
      # User selected an existing entry - extract just the content part
      ENTRY=$(echo "$SELECTED" | ${pkgs.gnused}/bin/sed -E 's/^- \*\*[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\*\* //')
    else
      # User typed a new entry
      ENTRY="$SELECTED"
    fi

    # Format the log entry with bolded timestamp
    FORMATTED_ENTRY="- **$DATETIME** $ENTRY"

    # Add the log entry at the end of the log file
    echo -e "$FORMATTED_ENTRY" >>"$LOG_FILE"

    # Create a more informative notification
    TRUNCATED_ENTRY=$(echo "$ENTRY" | ${pkgs.coreutils}/bin/cut -c 1-50)
    if [ ''${#ENTRY} -gt 50 ]; then
      TRUNCATED_ENTRY="$TRUNCATED_ENTRY..."
    fi

    ${pkgs.libnotify}/bin/notify-send "Log Entry Added" "Time: $DATETIME\nEntry: $TRUNCATED_ENTRY\nFile: $LOG_FILE" -t 3000
  '';
in
{
  system.nixos.tags = [ "automation-domain-v0.3" ];

  services = {
    transmission = {
      enable = true;
      settings = {
        script-torrent-done-enabled = false;
        ratio-limit-enabled = false;
        umask = 18; # 002
        download-dir = "/outer-realm/inbox";
        incomplete-dir-enabled = false;
        rpc-port = 9091;
      };
    };

    ollama = {
      enable = true;
      acceleration = "cuda";
    };

    # Monero service (commented out for easy enablement)
    # monero = {
    #   enable = true;
    #   dataDir = "/var/lib/monero";
    # };.
    postgresql = {
      enable = true;
      package = pkgs.postgresql_16;
      extensions =
        ps: with ps; [
          timescaledb
          pgvector
          pgx_ulid # This is a custom package built from source
        ];
      settings = {
        shared_preload_libraries = "timescaledb";
      };
    };
    sinex = {
      enable = true;
      systemUser = "sinity";

      autoConfigureSystem = true;

      ingestors = {
        hyprland = {
          enable = true;
          interval = 1;
        };

        filesystem = {
          enable = true;
          watchDirectories = [
            "~"
            "/realm"
          ];
          excludePatterns = [
            "*.tmp"
            "*.log"
            "*.cache"
            ".git/**"
            "node_modules/**"
            "__pycache__/**"
            "*.swp"
            "*.swo"
            "target/**"
            ".direnv/**"
          ];
          debounceMs = 200;
        };

        kitty = {
          enable = true;
          captureCommands = true;
          captureOutput = true; # Maximalist approach - capture everything
          shellIntegration = true; # Automatic shell markers for command tracking
        };
      };
    };
  };

  home-manager.users.sinity = {
    home.packages = with pkgs; [
      vm-start

      runbg
      lofi

      toggle_blur
      toggle_opacity
      toggle_waybar

      # File management automation
      compress
      extract
      combine-files

      # Documentation and help
      show-keybinds

      # Knowledge management
      log-to-knowledgebase

      # ASBL mitigation and gamma control
      asbl-fooler
      hyperfx

      # From home/system.nix - system monitoring
      btop
      ncdu # disk space
      nitch # system fetch util

      # Modern file utilities
      dua # Disk usage analyzer (like ncdu but faster)
      yazi # Terminal file manager
      fselect # SQL-like file search

      # From home/system.nix - CLI utilities
      toipe # typing test in the terminal
      ttyper # cli typing test

      # From home/system.nix - Terminal toys
      cbonsai
      pipes
      tty-clock

      # From home/system.nix - Graphics tools
      mesa-demos
      vulkan-tools
      vulkan-validation-layers
      wayland-utils
      libva-utils
      glxinfo
      drm_info

      # Script dependencies
      unzip # For extract.sh
      unrar # For extract.sh
      p7zip # For extract.sh
      zenity # For dialogs
      tofi # For various scripts (show-keybinds, log-to-knowledgebase)

      # VM management dependencies (for vm-start)
      virt-viewer
      libvirt

      # ActivityWatch watchers
      aw-watcher-window-wayland
      aw-watcher-afk
    ];

    # Activity monitoring and tracking

    # From home/system.nix - btop configuration
    programs.btop = {
      enable = true;
      settings = {
        vim_keys = true;
        update_ms = 2000;
        show_cpu_freq = true;
        show_gpu = true;
        mem_graphs = true;
        proc_sorting = "cpu direct";
        proc_filter = false;
        tree_view = false;
        proc_per_core = true;
        proc_mem_bytes = true;
        cpu_graph_upper = "total";
        cpu_graph_lower = "user";
        cpu_invert_lower = true;
      };
    };

    services.activitywatch = {
      enable = true;
      package = pkgs.aw-server-rust;

      watchers = {
        awatcher = {
          package = pkgs.awatcher;
          settings = {
            idle-timeout-seconds = 60;
            poll-time-idle-seconds = 1;
            poll-time-window-seconds = 1;
          };
        };
      };
    };

    systemd.user = {
      services = {
        asbl-no-moar = {
          Unit = {
            Description = "Wayland gamma poke to mitigate ASBL";
            After = [ "graphical-session.target" ];
          };
          Service = {
            Type = "simple";
            ExecStart = "${asbl-fooler}/bin/asbl-no-moar";
            Restart = "no";
          };
          Install = {
            WantedBy = [ "default.target" ];
          };
        };

        activitywatch-watcher-awatcher =
          let
            target = "graphical-session.target";
          in
          {
            Unit = {
              After = [ target ];
              Requisite = [ target ];
              PartOf = [ target ];
            };
            Install = {
              WantedBy = [ target ];
            };
          };
      };

      timers.asbl-no-moar = {
        Unit = {
          Description = "Timer for asbl-no-moar service";
        };
        Timer = {
          OnBootSec = "2min";
          OnUnitActiveSec = "150s";
          AccuracySec = "1s";
          Persistent = true;
        };
        Install = {
          WantedBy = [ "timers.target" ];
        };
      };
    };
  };
}
