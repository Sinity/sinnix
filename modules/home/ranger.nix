{ config, pkgs, lib, ... }:
let
  # Helper for path construction
  homeDir = config.home.homeDirectory;
  
  # Common directory paths
  cachePath = "${homeDir}/.cache/ranger";
  thumbsPath = "${cachePath}/thumbs";
  trashPath = "${homeDir}/.local/share/Trash/files";
in
{
  programs.ranger = {
    enable = true;
    
    extraPackages = with pkgs; [
      # Core dependencies
      ueberzugpp ffmpeg ffmpegthumbnailer

      # Media handling
      imagemagick poppler_utils mpv
      
      # Preview utilities
      atool libcaca highlight mediainfo w3m bat
      
      # Enhanced format support
      librsvg
      
      # Tools
      parallel bc file exiftool
    ];

    settings = {
      # Preview settings
      preview_images = true;
      preview_images_method = "ueberzug";
      use_preview_script = true;
      preview_max_size = 40000000;  # ~40MB limit for previews
      
      # UI preferences
      column_ratios = "1,3,4";
      unicode_ellipsis = true;
      draw_borders = "both";
      tilde_in_titlebar = true;
      padding_right = true;
      
      # Behavior settings
      vcs_aware = true;
      vcs_backend_git = "enabled";
      show_hidden = true;
      collapse_preview = false;
      
      # Sorting preferences
      sort_case_insensitive = true;
      sort_directories_first = true;
      sort_unicode = true;
      
      # History settings
      max_history_size = 20;
      max_console_history_size = 50;
      
      # Other settings
      mouse_enabled = true;
      hidden_filter = "^\\..*";
      confirm_on_delete = "multiple";
      open_all_images = true;
    };

    mappings = {
      K = "move up=0.5 pages=True";
      J = "move down=0.5 pages=True";
      "<DELETE>" = "console delete";
      "<F7>" = "console mkdir ";
      "<F8>" = "console delete";
    };

    aliases = {
      e = "edit";
      q = "quit";
      Q = "quitall";
      "!" = "shell";
      "/" = "search";
      "?" = "search";
    };

    # File associations
    rifle = [
      # Text files
      { condition = "mime ^text, label editor"; command = "nvim -- \"$1\""; }
      { condition = "mime ^text, label pager"; command = "$PAGER -- \"$1\""; }
      { condition = "!mime ^text, label editor, ext xml|json|csv|tex|py|pl|rb|js|sh|php"; command = "nvim -- \"$1\""; }
      { condition = "!mime ^text, label pager, ext xml|json|csv|tex|py|pl|rb|js|sh|php"; command = "$PAGER -- \"$1\""; }
      
      # Images
      { condition = "mime ^image/svg, has inkscape, X, flag f"; command = "inkscape -- \"$1\""; }
      { condition = "mime ^image/svg, has display, X, flag f"; command = "display -- \"$1\""; }
      { condition = "mime ^image, has imv, X, flag f"; command = "imv -- \"$1\""; }
      { condition = "mime ^image, has feh, X, flag f"; command = "feh -- \"$1\""; }
      { condition = "mime ^image, has gimp, X, flag f"; command = "gimp -- \"$1\""; }
      { condition = "ext xcf, X, flag f"; command = "gimp -- \"$1\""; }
      
      # Video/Audio
      { condition = "mime ^video, has mpv, X, flag f"; command = "mpv -- \"$1\""; }
      { condition = "mime ^video, has mpv, X, flag f"; command = "mpv --fs -- \"$1\""; }
      { condition = "mime ^video|audio, has vlc, X, flag f"; command = "vlc -- \"$1\""; }
      
      # Documents
      { condition = "ext pdf, has zathura, X, flag f"; command = "zathura -- \"$1\""; }
      { condition = "ext docx?, has libreoffice, X, flag f"; command = "libreoffice \"$1\""; }
      { condition = "ext xlsx?, has libreoffice, X, flag f"; command = "libreoffice \"$1\""; }
      { condition = "ext pptx?, has libreoffice, X, flag f"; command = "libreoffice \"$1\""; }
      
      # Archives
      { condition = "ext 7z, has 7z"; command = "7z -p l \"$1\" | \"$PAGER\""; }
      { condition = "ext tar|gz|bz2|xz, has tar"; command = "tar vvtf \"$1\" | \"$PAGER\""; }
      { condition = "ext tar|gz|bz2|xz, has tar"; command = "for file in \"$@\"; do tar vvxf \"$file\"; done"; }
      { condition = "ext bz2, has bzip2"; command = "for file in \"$@\"; do bzip2 -dk \"$file\"; done"; }
      { condition = "ext zip, has unzip"; command = "unzip -l \"$1\" | less"; }
      { condition = "ext ace, has unace"; command = "unace l \"$1\" | less"; }
      { condition = "ext ace, has unace"; command = "for file in \"$@\"; do unace e \"$file\"; done"; }
      { condition = "ext rar, has unrar"; command = "unrar l \"$1\" | less"; }
      { condition = "ext rar, has unrar"; command = "for file in \"$@\"; do unrar x \"$file\"; done"; }
    ];

    extraConfig = ''
      # File operations
      map DD shell mv %s ~/.local/share/Trash/files/
      map ex shell atool -x %f
      map cc shell zip -r %f.zip %s
      
      # Media playback
      map V chain shell mpv --vo=kitty --profile=sw-fast %s; reload_dir
      
      # Toggle metadata display in preview
      map M chain set preview_metadata!; reload_cwd
    '';

    settings.preview_script = toString (pkgs.writeShellScript "ranger-scope.sh" ''
      #!/usr/bin/env bash
      set -o noclobber -o noglob -o nounset -o pipefail
      IFS=$'\n'

      FILE_PATH="''${1}"
      PV_WIDTH="''${2}"
      PV_HEIGHT="''${3}"
      PV_X="''${4}"
      PV_Y="''${5}"
      IMAGE_CACHE_PATH="''${6}"
      PV_IMAGE_ENABLED="''${7}"

      CACHE_DIR="''${XDG_CACHE_HOME:-''${HOME}/.cache}/ranger/thumbs"
      mkdir -p "''${CACHE_DIR}"

      # Use file for better MIME detection
      MIME_TYPE="$(file --mime-type -b --uncompress -- "''${FILE_PATH}")"
      FILE_EXTENSION_LOWER="$(echo "''${FILE_PATH##*.}" | tr '[:upper:]' '[:lower:]')"

      have() { command -v "''${1}" &>/dev/null; }

      # Enhanced JSON output for ueberzug++
      show_image() {
          local path="$1"
          local identifier="''${2:-preview}"
          printf '{"action":"add","identifier":"%s","x":%d,"y":%d,"width":%d,"height":%d,"scaler":"contain","path":"%s","alpha":1.0}\n' \
              "$identifier" "''${PV_X}" "''${PV_Y}" "''${PV_WIDTH}" "''${PV_HEIGHT}" "$path"
      }

      # Get metadata string for media files
      get_metadata() {
          local file="$1"
          local meta=""
          
          if have mediainfo; then
              # Get basic metadata
              meta="$(mediainfo --Output="General;%Duration/String%\n%FileSize/String%" "$file")"
              
              # Add format-specific metadata
              case "''${MIME_TYPE}" in
                  video/*)
                      meta="$meta\n$(mediainfo --Output="Video;%Width%x%Height% %BitRate/String% %FrameRate% FPS" "$file")"
                      ;;
                  audio/*)
                      meta="$(mediainfo --Output="Audio;%Album% - %Title%\n%Artist%\n%BitRate/String% %Channels%" "$file")"
                      ;;
                  image/*)
                      if have exiftool; then
                          meta="$(exiftool -s3 -ImageSize -ColorSpace -FileType "$file" | paste -sd '\n')"
                      fi
                      ;;
              esac
          fi
          echo -e "''${meta:-No metadata available}"
      }

      handle_extension() {
          case "''${FILE_EXTENSION_LOWER}" in
              # Archive preview with better error handling
              a|ace|alz|arc|arj|bz|bz2|cab|cpio|deb|gz|jar|lha|lz|lzh|lzma|lzo|\
              rpm|rz|t7z|tar|tbz|tbz2|tgz|tlz|txz|tZ|tzo|war|xpi|xz|Z|zip)
                  if have atool; then
                      atool --list -- "''${FILE_PATH}" && exit 5
                  elif have bsdtar; then
                      bsdtar --list --file "''${FILE_PATH}" && exit 5
                  fi
                  echo "No archive previewer available." && exit 1
                  ;;
              rar)
                  have unrar && unrar lt -p- -- "''${FILE_PATH}" && exit 5
                  echo "unrar not available." && exit 1
                  ;;
              7z)
                  have 7z && 7z l -p -- "''${FILE_PATH}" && exit 5
                  echo "7z not available." && exit 1
                  ;;
              # PDF preview with metadata
              pdf)
                  local cache_key="$(echo "''${FILE_PATH}" | sha256sum | cut -d' ' -f1)"
                  local cached_thumb="''${CACHE_DIR}/''${cache_key}.png"
                  
                  if [[ ! -f "''${cached_thumb}" || "''${FILE_PATH}" -nt "''${cached_thumb}" ]]; then
                      pdftoppm -png -singlefile -f 1 "''${FILE_PATH}" "''${cached_thumb%.png}" || exit 1
                  fi
                  
                  if [[ -f "''${cached_thumb}" ]]; then
                      show_image "''${cached_thumb}"
                      if have pdfinfo; then
                          pdfinfo "''${FILE_PATH}"
                      fi
                      exit 6
                  fi
                  exit 1
                  ;;
          esac
      }

      handle_video() {
          local video_path="''${1}"
          local cache_key="$(echo "''${video_path}" | sha256sum | cut -d' ' -f1)"
          local cached_thumb="''${CACHE_DIR}/''${cache_key}.jpg"
          local meta="$(get_metadata "''${video_path}")"

          # Regenerate if cache missing or outdated
          if [[ ! -f "''${cached_thumb}" || "''${video_path}" -nt "''${cached_thumb}" ]]; then
              local temp_dir="$(mktemp -d)"
              trap 'rm -rf "''${temp_dir}"' EXIT

              local duration="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "''${video_path}")"
              [[ -z "''${duration}" ]] && { echo "Could not determine video duration."; return 1; }

              local interval="$(bc <<< "scale=2; ''${duration}/4")"
              
              # Extract frames with progress feedback
              echo "Generating video preview..."
              for i in {0..3}; do
                  ffmpegthumbnailer -i "''${video_path}" -o "''${temp_dir}/thumb_''${i}.jpg" \
                      -t "$(bc <<< "scale=2; ''${i} * ''${interval}")" -s 0 -q 8 || \
                      { echo "Failed to extract video frame $i"; return 1; }
                  echo -n "."
              done
              echo "done"

              montage "''${temp_dir}"/thumb_*.jpg -geometry 512x288+2+2 -tile 2x2 "''${cached_thumb}" || return 1
              
              # Add metadata overlay
              convert "''${cached_thumb}" \
                  -gravity northwest -pointsize 12 \
                  -fill white -stroke black -strokewidth 2 \
                  -annotate +5+5 "''${meta}" \
                  "''${cached_thumb}" || true
          fi

          [[ -f "''${cached_thumb}" ]] && show_image "''${cached_thumb}" && exit 6
          echo "''${meta}" && exit 5
          return 1
      }

      handle_audio() {
          local audio_path="''${1}"
          local cache_key="$(echo "''${audio_path}" | sha256sum | cut -d' ' -f1)"
          local cached_thumb="''${CACHE_DIR}/''${cache_key}.jpg"
          local meta="$(get_metadata "''${audio_path}")"

          if [[ -f "''${cached_thumb}" && ! "''${audio_path}" -nt "''${cached_thumb}" ]]; then
              show_image "''${cached_thumb}"
              echo "''${meta}" && exit 6
          fi

          if ! have ffmpeg || ! have convert; then
              echo "''${meta}" && exit 5
              exit 1
          fi

          local temp_art="$(mktemp)"
          local temp_wave="$(mktemp)"
          trap 'rm -f "''${temp_art}" "''${temp_wave}"' EXIT

          # Try to extract embedded cover art
          if timeout 10s ffmpeg -i "''${audio_path}" -an -vcodec copy "''${temp_art}" 2>/dev/null; then
              timeout 20s ffmpeg -i "''${audio_path}" \
                  -filter_complex 'showwavespic=s=512x128:colors=lime' \
                  "''${temp_wave}" || true

              convert "''${temp_art}" -resize 512x384 \
                  -gravity north \
                  -gravity northwest -pointsize 12 \
                  -fill white -stroke black -strokewidth 2 \
                  -annotate +5+5 "''${meta}" \
                  "''${temp_wave}" -gravity south \
                  -append \
                  -quality 80 \
                  "''${cached_thumb}" || true
          else
              # No embedded art -> just waveform with metadata
              timeout 20s ffmpeg -i "''${audio_path}" \
                  -filter_complex 'showwavespic=s=512x512:colors=lime' \
                  "''${cached_thumb}" && \
              convert "''${cached_thumb}" \
                  -gravity northwest -pointsize 12 \
                  -fill white -stroke black -strokewidth 2 \
                  -annotate +5+5 "''${meta}" \
                  "''${cached_thumb}" || true
          fi

          [[ -f "''${cached_thumb}" ]] && show_image "''${cached_thumb}" && exit 6
          echo "''${meta}" && exit 5
          exit 1
      }

      handle_image() {
          local mimetype="''${1}"
          local meta="$(get_metadata "''${FILE_PATH}")"
          
          # Direct display for GIFs (ueberzug++ handles animation)
          if [[ "''${mimetype}" == "image/gif" ]]; then
              show_image "''${FILE_PATH}"
              echo "''${meta}" && exit 6
          fi

          case "''${mimetype}" in
              image/svg+xml|image/heic|image/heif)
                  local cache_key="$(echo "''${FILE_PATH}" | sha256sum | cut -d' ' -f1)"
                  local cached_thumb="''${CACHE_DIR}/''${cache_key}.jpg"

                  if [[ ! -f "''${cached_thumb}" || "''${FILE_PATH}" -nt "''${cached_thumb}" ]]; then
                      if have convert; then
                          timeout 20s convert "''${FILE_PATH}" \
                              -quality 80 \
                              -resize 1024x1024\> \
                              "''${cached_thumb}" || true
                      fi
                      # Add metadata
                      convert "''${cached_thumb}" \
                          -gravity northwest -pointsize 12 \
                          -fill white -stroke black -strokewidth 2 \
                          -annotate +5+5 "''${meta}" \
                          "''${cached_thumb}" || true
                  fi
                  [[ -f "''${cached_thumb}" ]] && show_image "''${cached_thumb}" && exit 6
                  exit 1;;
              *)
                  # Handle EXIF orientation
                  local orientation
                  if have identify; then
                      orientation="$(identify -format '%[EXIF:Orientation]\n' -- "''${FILE_PATH}" 2>/dev/null || echo "")"
                  fi

                  if [[ -n "''${orientation}" && "''${orientation}" != "1" ]]; then
                      local cache_key="$(echo "''${FILE_PATH}" | sha256sum | cut -d' ' -f1)"
                      local cached_thumb="''${CACHE_DIR}/''${cache_key}.jpg"

                      if [[ ! -f "''${cached_thumb}" || "''${FILE_PATH}" -nt "''${cached_thumb}" ]]; then
                          convert "''${FILE_PATH}" -auto-orient -quality 80 "''${cached_thumb}" || exit 1
                          convert "''${cached_thumb}" \
                              -gravity northwest -pointsize 12 \
                              -fill white -stroke black -strokewidth 2 \
                              -annotate +5+5 "''${meta}" \
                              "''${cached_thumb}" || true
                      fi
                      show_image "''${cached_thumb}" && exit 6
                  fi

                  # Direct display with metadata overlay
                  local temp_file="$(mktemp).jpg"
                  trap 'rm -f "''${temp_file}"' EXIT
                  
                  cp "''${FILE_PATH}" "''${temp_file}" && \
                  convert "''${temp_file}" \
                      -gravity northwest -pointsize 12 \
                      -fill white -stroke black -strokewidth 2 \
                      -annotate +5+5 "''${meta}" \
                      "''${temp_file}" && \
                  show_image "''${temp_file}" && exit 6

                  # Fallback to direct display without metadata
                  show_image "''${FILE_PATH}" && exit 6
                  ;;
          esac
      }

      case "''${MIME_TYPE}" in
          image/*) handle_image "''${MIME_TYPE}" ;;
          video/*) handle_video "''${FILE_PATH}" ;;
          audio/*) handle_audio "''${FILE_PATH}" ;;
          text/*)  bat --color=always "''${FILE_PATH}" && exit 5 ;;
      esac

      handle_extension || handle_fallback

      exit 1
    '');
  };

  # Ensure required directories exist
  home.activation.rangerSetup = lib.hm.dag.entryAfter ["writeBoundary"] ''
    $DRY_RUN_CMD mkdir -p ${thumbsPath}
    $DRY_RUN_CMD mkdir -p ${trashPath}
  '';
}
