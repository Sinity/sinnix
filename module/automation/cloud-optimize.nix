# Cloud Storage Optimization - Proactive caching and indexing
{ pkgs, ... }:

{
  # Thumbnail generation service for cloud files
  systemd.user.services.cloud-thumbnailer = {
    description = "Generate thumbnails for cloud storage files";
    after = [ "graphical-session.target" ];
    wantedBy = [ "default.target" ];
    
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${pkgs.writeShellScript "cloud-thumbnailer" ''
        #!/usr/bin/env bash
        
        # Thumbnail cache directory
        THUMB_DIR="$HOME/.cache/thumbnails"
        mkdir -p "$THUMB_DIR/large" "$THUMB_DIR/normal"
        
        # Function to generate thumbnail
        gen_thumb() {
          local file="$1"
          local hash=$(echo -n "file://$file" | sha256sum | cut -d' ' -f1)
          local thumb_large="$THUMB_DIR/large/$hash.png"
          local thumb_normal="$THUMB_DIR/normal/$hash.png"
          
          # Skip if thumbnail exists and is newer than file
          if [[ -f "$thumb_large" ]] && [[ "$thumb_large" -nt "$file" ]]; then
            return
          fi
          
          # Generate thumbnails based on file type
          case "$(file -b --mime-type "$file")" in
            image/*)
              ${pkgs.imagemagick}/bin/convert "$file" -resize 256x256 "$thumb_large" 2>/dev/null
              ${pkgs.imagemagick}/bin/convert "$file" -resize 128x128 "$thumb_normal" 2>/dev/null
              ;;
            video/*)
              ${pkgs.ffmpegthumbnailer}/bin/ffmpegthumbnailer -i "$file" -o "$thumb_large" -s 256 2>/dev/null
              ${pkgs.ffmpegthumbnailer}/bin/ffmpegthumbnailer -i "$file" -o "$thumb_normal" -s 128 2>/dev/null
              ;;
            application/pdf)
              ${pkgs.poppler_utils}/bin/pdftoppm -png -f 1 -l 1 -scale-to 256 "$file" | ${pkgs.imagemagick}/bin/convert - "$thumb_large" 2>/dev/null
              ${pkgs.poppler_utils}/bin/pdftoppm -png -f 1 -l 1 -scale-to 128 "$file" | ${pkgs.imagemagick}/bin/convert - "$thumb_normal" 2>/dev/null
              ;;
          esac
        }
        
        # Process cloud storage directories
        for mount in /mnt/nextcloud /mnt/onedrive /mnt/gdrive; do
          if mountpoint -q "$mount"; then
            echo "Processing $mount..."
            # Find image/video files modified in last 7 days
            find "$mount" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \
              -o -iname "*.gif" -o -iname "*.webp" -o -iname "*.mp4" -o -iname "*.mkv" \
              -o -iname "*.avi" -o -iname "*.pdf" \) -mtime -7 -print0 | \
            while IFS= read -r -d "" file; do
              gen_thumb "$file"
            done
          fi
        done
      ''}";
    };
    
    # Run every hour
    startAt = "hourly";
  };

  # Metadata pre-caching service
  systemd.user.services.cloud-metadata-cache = {
    description = "Pre-cache cloud storage metadata";
    after = [ "network-online.target" ];
    
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${pkgs.writeShellScript "cloud-metadata-cache" ''
        #!/usr/bin/env bash
        
        # Pre-warm directory caches
        for mount in /mnt/nextcloud /mnt/onedrive /mnt/gdrive; do
          if mountpoint -q "$mount"; then
            echo "Pre-caching metadata for $mount..."
            # Recursive ls to populate directory cache
            find "$mount" -type d -print0 2>/dev/null | \
              xargs -0 -P 4 -I {} ls -la {} >/dev/null 2>&1
          fi
        done
      ''}";
    };
    
    # Run every 30 minutes
    startAt = "*:0/30";
  };

  # Enhanced yazi configuration for cloud storage
  home-manager.users.sinity = {
    programs.yazi = {
      enable = true;
      settings = {
        mgr = {
          # Show thumbnails
          show_hidden = false;
          sort_by = "mtime";
          sort_reverse = true;
          sort_dir_first = true;
          linemode = "size";
          show_symlink = true;
        };
        
        preview = {
          # Aggressive caching for cloud files
          max_width = 1000;
          max_height = 1000;
          cache_dir = "$HOME/.cache/yazi";
          # Use pre-generated thumbnails
          image_quality = 90;
        };
        
        tasks = {
          micro_workers = 10;
          macro_workers = 5;
          bizarre_retry = 3;
        };
      };
      
      # Custom previewer for cloud files
      plugins = {
        cloud-preview = pkgs.writeTextFile {
          name = "cloud-preview.yazi";
          destination = "/init.lua";
          text = ''
            -- Enhanced preview for cloud files
            local M = {}
            
            function M:peek()
              local path = tostring(self.file.url)
              
              -- Check if file is from cloud mount
              if path:match("^/mnt/") then
                -- Use cached thumbnail if available
                local hash = ya.hash("file://" .. path)
                local thumb = os.getenv("HOME") .. "/.cache/thumbnails/large/" .. hash .. ".png"
                
                if ya.fs.cha(thumb) then
                  ya.image_show(thumb, self.area)
                  return
                end
              end
              
              -- Fallback to default preview
              ya.preview_file(self)
            end
            
            return M
          '';
        };
      };
    };
    
    # Yazi wrapper with cloud optimizations
    home.packages = [
      (pkgs.writeShellScriptBin "yazi-cloud" ''
        # Pre-cache current directory
        ls -la >/dev/null 2>&1
        
        # Set environment for better cloud performance
        export YAZI_FILE_MAX_SIZE=$((100 * 1024 * 1024))  # 100MB max for preview
        export YAZI_PREVIEW_REMOTE=true
        
        exec ${pkgs.yazi}/bin/yazi "$@"
      '')
    ];
    
    home.shellAliases = {
      y = "yazi-cloud";
      yc = "yazi-cloud /mnt/nextcloud";
      yo = "yazi-cloud /mnt/onedrive";
      yg = "yazi-cloud /mnt/gdrive";
    };
  };

  # Cloud storage performance monitoring
  systemd.user.services.cloud-monitor = {
    description = "Monitor cloud storage performance and cache usage";
    after = [ "graphical-session.target" ];
    
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${pkgs.writeShellScript "cloud-monitor" ''
        #!/usr/bin/env bash
        
        LOG="$HOME/.cache/cloud-storage-stats.log"
        
        {
          echo "=== Cloud Storage Stats $(date) ==="
          
          # Cache sizes
          echo "Cache Usage:"
          echo "  davfs2: $(sudo du -sh /var/cache/davfs2 2>/dev/null | cut -f1)"
          echo "  rclone: $(du -sh ~/.cache/rclone 2>/dev/null | cut -f1)"
          echo "  thumbnails: $(du -sh ~/.cache/thumbnails 2>/dev/null | cut -f1)"
          echo "  yazi: $(du -sh ~/.cache/yazi 2>/dev/null | cut -f1)"
          
          # Mount status
          echo ""
          echo "Mount Status:"
          for mount in nextcloud onedrive gdrive; do
            if mountpoint -q "/mnt/$mount"; then
              files=$(find "/mnt/$mount" -type f 2>/dev/null | wc -l)
              echo "  $mount: Mounted ($files files)"
            else
              echo "  $mount: Not mounted"
            fi
          done
          
          echo ""
        } >> "$LOG"
        
        # Rotate log if too large
        if [[ $(stat -c%s "$LOG" 2>/dev/null || echo 0) -gt 10485760 ]]; then
          mv "$LOG" "$LOG.old"
        fi
      ''}";
    };
    
    startAt = "hourly";
  };

  # Install required packages
  environment.systemPackages = with pkgs; [
    imagemagick
    ffmpegthumbnailer
    poppler_utils
    file
  ];
}