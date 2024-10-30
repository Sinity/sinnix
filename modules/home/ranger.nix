{ config, pkgs, lib, ... }:
{
  programs.ranger = {
    enable = true;
    # package = pkgs.ranger;
    extraPackages = with pkgs; [
      ffmpegthumbnailer  # For video thumbnails
      ueberzugpp  # For image previews
      atool  # For archive previews
      libcaca  # For ASCII-art image previews
      highlight  # For syntax highlighting
      mediainfo  # For media file information
      poppler_utils  # For PDF previews
      w3m  # For HTML previews
      bat  # For syntax highlighting
    ];
    settings = {
      preview_images = true;
      preview_images_method = "ueberzug";
      vcs_aware = true;
      vcs_backend_git = "enabled";
      unicode_ellipsis = true;
      show_hidden = true;
      collapse_preview = false;
      sort_case_insensitive = true;
      sort_directories_first = true;
      sort_unicode = true;
      tilde_in_titlebar = true;
      padding_right = true;
      max_history_size = 20;
      max_console_history_size = 50;
      mouse_enabled = true;
      column_ratios = "1,3,4";
      hidden_filter = "^\\..*";
      confirm_on_delete = "multiple";
      use_preview_script = true;
      # preview_script = "${pkgs.ranger}/share/ranger/data/scope.sh";
      open_all_images = true;
    };
    aliases = {
      e = "edit";
      q = "quit";
      Q = "quitall";
      "!" = "shell";
      "/" = "search";
      "?" = "search";
    };
    mappings = {
      K = "move up=0.5 pages=True";
      J = "move down=0.5 pages=True";
      "<DELETE>" = "console delete";
      "<F7>" = "console mkdir ";
      "<F8>" = "console delete";
    };

    rifle = [
      { condition = "mime ^text,  label editor"; command = "nvim -- \"$@\""; }
      { condition = "mime ^text,  label pager"; command = "\"$PAGER\" -- \"$@\""; }
      { condition = "!mime ^text, label editor, ext xml|json|csv|tex|py|pl|rb|js|sh|php"; command = "nvim -- \"$@\""; }
      { condition = "!mime ^text, label pager,  ext xml|json|csv|tex|py|pl|rb|js|sh|php"; command = "\"$PAGER\" -- \"$@\""; }
      { condition = "mime ^image/svg, has inkscape, X, flag f"; command = "inkscape -- \"$@\""; }
      { condition = "mime ^image/svg, has display,  X, flag f"; command = "display -- \"$@\""; }
      { condition = "mime ^image, has imv,      X, flag f"; command = "imv -- \"$@\""; }
      { condition = "mime ^image, has feh,       X, flag f"; command = "feh -- \"$@\""; }
      { condition = "mime ^image, has gimp,      X, flag f"; command = "gimp -- \"$@\""; }
      { condition = "ext xcf,                    X, flag f"; command = "gimp -- \"$@\""; }
      { condition = "mime ^video,       has mpv,      X, flag f"; command = "mpv -- \"$@\""; }
      { condition = "mime ^video,       has mpv,      X, flag f"; command = "mpv --fs -- \"$@\""; }
      { condition = "mime ^video|audio, has vlc,      X, flag f"; command = "vlc -- \"$@\""; }
      { condition = "ext pdf, has zathura,  X, flag f"; command = "zathura -- \"$@\""; }
      { condition = "ext docx?, has libreoffice, X, flag f"; command = "libreoffice \"$@\""; }
      { condition = "ext xlsx?, has libreoffice, X, flag f"; command = "libreoffice \"$@\""; }
      { condition = "ext pptx?, has libreoffice, X, flag f"; command = "libreoffice \"$@\""; }
      { condition = "ext 7z, has 7z"; command = "7z -p l \"$@\" | \"$PAGER\""; }
      { condition = "ext tar|gz|bz2|xz, has tar"; command = "tar vvtf \"$1\" | \"$PAGER\""; }
      { condition = "ext tar|gz|bz2|xz, has tar"; command = "for file in \"$@\"; do tar vvxf \"$file\"; done"; }
      { condition = "ext bz2, has bzip2"; command = "for file in \"$@\"; do bzip2 -dk \"$file\"; done"; }
      { condition = "ext zip, has unzip"; command = "unzip -l \"$1\" | less"; }
      # { condition = "ext zip, has unzip"; command = "for file in \"$@\"; do unzip -d \"''${file%.*}\" \"$file\"; done"; }
      { condition = "ext ace, has unace"; command = "unace l \"$1\" | less"; }
      { condition = "ext ace, has unace"; command = "for file in \"$@\"; do unace e \"$file\"; done"; }
      { condition = "ext rar, has unrar"; command = "unrar l \"$1\" | less"; }
      { condition = "ext rar, has unrar"; command = "for file in \"$@\"; do unrar x \"$file\"; done"; }
    ];
  };

  # Custom scope.sh configuration
  home.file.".config/ranger/scope.sh" = {
    executable = true;
    text = ''
      #!/usr/bin/env bash

      set -o noclobber -o noglob -o nounset -o pipefail
      IFS=$'\n'

      # Script arguments
      FILE_PATH="''${1}"
      PV_WIDTH="''${2}"
      PV_HEIGHT="''${3}"
      IMAGE_CACHE_PATH="''${4}"
      PV_IMAGE_ENABLED="''${5}"

      # Settings
      HIGHLIGHT_SIZE_MAX=262143
      HIGHLIGHT_TABWIDTH=8
      HIGHLIGHT_STYLE='pablo'

      handle_extension() {
        case "''${FILE_EXTENSION_LOWER}" in
          # Archives
          a|ace|alz|arc|arj|bz|bz2|cab|cpio|deb|gz|jar|lha|lz|lzh|lzma|lzo|\
          rpm|rz|t7z|tar|tbz|tbz2|tgz|tlz|txz|tZ|tzo|war|xpi|xz|Z|zip)
            atool --list -- "''${FILE_PATH}" && exit 5
            bsdtar --list --file "''${FILE_PATH}" && exit 5
            exit 1;;
          rar)
            unrar lt -p- -- "''${FILE_PATH}" && exit 5
            exit 1;;
          7z)
            7z l -p -- "''${FILE_PATH}" && exit 5
            exit 1;;
          # PDF
          pdf)
            pdftotext -l 10 -nopgbrk -q -- "''${FILE_PATH}" - && exit 5
            exiftool "''${FILE_PATH}" && exit 5
            exit 1;;
          # HTML
          htm|html|xhtml)
            w3m -dump "''${FILE_PATH}" && exit 5
            lynx -dump -- "''${FILE_PATH}" && exit 5
            elinks -dump "''${FILE_PATH}" && exit 5
            ;;
        esac
      }

      handle_image() {
        local mimetype="''${1}"
        case "''${mimetype}" in
          image/svg+xml)
            convert "''${FILE_PATH}" "''${IMAGE_CACHE_PATH}" && exit 6
            exit 1;;
          image/*)
            local orientation
            orientation="$( identify -format '%[EXIF:Orientation]\n' -- "''${FILE_PATH}" )"
            if [[ -n "$orientation" && "$orientation" != 1 ]]; then
              convert -- "''${FILE_PATH}" -auto-orient "''${IMAGE_CACHE_PATH}" && exit 6
            fi
            exit 7;;
          video/*)
            ffmpegthumbnailer -i "''${FILE_PATH}" -o "''${IMAGE_CACHE_PATH}" -s 0 && exit 6
            exit 1;;
          application/pdf)
            pdftoppm -f 1 -l 1 \
                     -scale-to-x 1920 \
                     -scale-to-y -1 \
                     -singlefile \
                     -jpeg -tiffcompression jpeg \
                     -- "''${FILE_PATH}" "''${IMAGE_CACHE_PATH%.*}" \
                && exit 6 || exit 1;;
        esac
      }

      handle_mime() {
        local mimetype="''${1}"
        case "''${mimetype}" in
          text/* | */xml)
            if [[ "$( stat --printf='%s' -- "''${FILE_PATH}" )" -gt "''${HIGHLIGHT_SIZE_MAX}" ]]; then
              exit 2
            fi
            bat --color=always -- "''${FILE_PATH}" && exit 5
            exit 2;;
          image/*)
            exiftool "''${FILE_PATH}" && exit 5
            exit 1;;
          video/* | audio/*)
            mediainfo "''${FILE_PATH}" && exit 5
            exiftool "''${FILE_PATH}" && exit 5
            exit 1;;
        esac
      }

      handle_fallback() {
        echo '----- File Type Classification -----' && file --dereference --brief -- "''${FILE_PATH}" && exit 5
        exit 1
      }

      MIMETYPE="$( file --dereference --brief --mime-type -- "''${FILE_PATH}" )"
      if [[ "''${PV_IMAGE_ENABLED}" == 'True' ]]; then
        handle_image "''${MIMETYPE}"
      fi
      handle_extension
      handle_mime "''${MIMETYPE}"
      handle_fallback

      exit 1
    '';
  };

  # Ensure necessary packages are installed
  home.packages = with pkgs; [
    # ranger
    ueberzugpp
    ffmpegthumbnailer
    atool
    libcaca
    highlight
    mediainfo
    poppler_utils
    w3m
    bat
    kitty
    sxiv
    feh
    mpv
    zathura
    libreoffice
  ];
}
