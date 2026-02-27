# Automated Btrfs Backup with btrbk
#
# === Storage topology ===
#
# Drive           Label            Size    Used    Mount            Contents
# ────────────────────────────────────────────────────────────────────────────
# /dev/sda2       root_btrfs       931G    652G    /,/nix,/var      System (subvols: @, @nix, @var)
# /dev/nvme0n1p3  SSD_4TB          3.7T    2.5T    /realm           Crown jewel: projects, home, data
# /dev/sdb1       old_hdd_btrfs    5.5T    ~0      /outer-realm     Empty (reformatted), future use
# /dev/sdc1       neo-outer-realm  13T     6.8T    /neo-outer-realm Big storage: archive, content, inbox
#
# === Backup strategy ===
#
# Source              → Target                             Frequency   Purpose
# ────────────────────────────────────────────────────────────────────────────
# /realm              → /neo-outer-realm/backups/realm     Hourly      Protect irreplaceable data
# / (root @)          → (snapshots only, no send)          Daily       System rollback
# /neo-outer-realm    → (snapshots only, no send)          Daily       Accidental deletion recovery
#
# /outer-realm is empty (144KB used) — no backup needed.
# /nix is reproducible from flake — no backup needed.
# /var/log/journal is bind-mounted from /realm — already covered.
#
# === Retention policy ===
#
# /realm:
#   Snapshots: 48 hourly, 14 daily, 8 weekly (local rollback)
#   Backups:   14 daily, 8 weekly, 6 monthly, 2 yearly (disaster recovery)
#
# Root SSD:
#   Snapshots: 7 daily, 4 weekly (rollback from bad nixos-rebuild)
#   No off-disk backup (fully reproducible from sinnix flake)
#
# /neo-outer-realm:
#   Snapshots: 7 daily, 4 weekly (protect against accidental rm -rf)
#   No off-disk backup (this IS the backup target)
#
# === What's in /realm (2.5 TB) ===
#
# /realm/project/     — Git repos: sinex, polylogue, sinnix, scribe-tap, etc.
# /realm/home/        — Home dir (bind → /home/sinity): SSH keys, configs, state
# /realm/data/
#   captures/         — Irreplaceable: syslog, shell recordings, screenshots,
#                       audio, keylog, activitywatch, asciinema, comms/irc
#   exports/          — Processed data exports
#   libraries/media/  — Media library
#   indices/          — Search indices (rebuildable but slow)
# /realm/inbox/       — Staging area
# /realm/knowledgebase/ — Knowledge base docs
#
# === What's in /neo-outer-realm (6.8 TB) ===
#
# archive/  — Long-term archival storage
# content/  — Large content files
# inbox/    — Torrent downloads (torrentInbox path)
{
  pkgs,
  lib,
  config,
  ...
}:
let
  inherit (config.sinnix.paths) realmRoot neoOuterRealm;
  username = config.sinnix.user.name;

  # Snapshot directories (created by tmpfiles)
  realmSnapshots = "${realmRoot}/.snapshots";
  rootSnapshots = "/.snapshots";
  neoSnapshots = "${neoOuterRealm}/.snapshots";

  # Backup target on the 14TB drive
  backupTarget = "${neoOuterRealm}/backups";

  btrbkConfig = ''
    # === Global settings ===
    timestamp_format        long-iso
    snapshot_create          onchange
    incremental             yes
    preserve_day_of_week    monday
    ssh_identity            /etc/ssh/ssh_host_ed25519_key

    # Transaction log for crash recovery and audit trail
    transaction_log         /var/log/btrbk.log
    lockfile                /var/lock/btrbk.lock

    # ─── Volume 1: /realm (CRITICAL — irreplaceable data) ─────────
    # Hourly snapshots + incremental send/receive to 14TB backup drive
    volume ${realmRoot}
      snapshot_dir   ${realmSnapshots}
      target         ${backupTarget}/realm

      # Local snapshots: fine-grained recent, thinning over time
      snapshot_preserve_min   latest
      snapshot_preserve       48h 14d 8w

      # Remote backups: keep longer history on the backup drive
      target_preserve_min     latest
      target_preserve         14d 8w 6m 2y

      subvolume .

    # ─── Volume 2: Root SSD (reproducible — snapshots only) ────────
    # No backup target: system is fully reproducible from nix flake.
    # Snapshots provide rollback from bad nixos-rebuild switch.
    volume /
      snapshot_dir   ${rootSnapshots}

      snapshot_preserve_min   latest
      snapshot_preserve       7d 4w

      subvolume .

    # ─── Volume 3: /neo-outer-realm (backup target — self-protect) ─
    # In-place snapshots only. Protects against accidental deletion
    # of archive/ content/ or the backups/ directory itself.
    volume ${neoOuterRealm}
      snapshot_dir   ${neoSnapshots}

      snapshot_preserve_min   latest
      snapshot_preserve       7d 4w

      subvolume .
  '';

  # Health check script: verifies backup integrity and recency
  backupHealthCheck = pkgs.writeShellApplication {
    name = "backup-health";
    runtimeInputs = with pkgs; [
      btrbk
      coreutils
      findutils
      gawk
      btrfs-progs
    ];
    # SC2015: A && B || C pattern used intentionally for terse result mapping
    excludeShellChecks = [ "SC2015" ];
    text = ''
      set -euo pipefail

      RED=$'\033[0;31m'
      GREEN=$'\033[0;32m'
      YELLOW=$'\033[1;33m'
      NC=$'\033[0m'
      BOLD=$'\033[1m'

      ok=0
      warn=0
      fail=0

      check() {
        local label="$1" result="$2"
        if [ "$result" = "ok" ]; then
          printf '  %s[ok]%s %s\n' "$GREEN" "$NC" "$label"
          ok=$((ok + 1))
        elif [ "$result" = "warn" ]; then
          printf '  %s[!]%s  %s\n' "$YELLOW" "$NC" "$label"
          warn=$((warn + 1))
        else
          printf '  %s[FAIL]%s %s\n' "$RED" "$NC" "$label"
          fail=$((fail + 1))
        fi
      }

      echo ""
      printf '%s=== sinnix backup health ===%s\n' "$BOLD" "$NC"
      echo ""

      # 1. Check backup target is mounted
      printf '%sStorage:%s\n' "$BOLD" "$NC"
      if mountpoint -q "${neoOuterRealm}" 2>/dev/null; then
        used=$(df -h "${neoOuterRealm}" | awk 'NR==2{print $3}')
        avail=$(df -h "${neoOuterRealm}" | awk 'NR==2{print $4}')
        pct=$(df "${neoOuterRealm}" | awk 'NR==2{print $5}')
        check "neo-outer-realm mounted ($used used, $avail free, $pct)" "ok"

        # Warn if >90% full
        pct_num=''${pct%\%}
        if [ "$pct_num" -gt 90 ]; then
          check "neo-outer-realm disk space critical ($pct)" "fail"
        elif [ "$pct_num" -gt 80 ]; then
          check "neo-outer-realm disk space warning ($pct)" "warn"
        fi
      else
        check "neo-outer-realm NOT MOUNTED -- backups disabled" "fail"
      fi

      if mountpoint -q "${realmRoot}" 2>/dev/null; then
        check "realm mounted" "ok"
      else
        check "realm NOT MOUNTED" "fail"
      fi

      # 2. Check snapshot recency
      printf '\n%sSnapshots:%s\n' "$BOLD" "$NC"
      for dir in "${realmSnapshots}" "${rootSnapshots}" "${neoSnapshots}"; do
        label="$dir"
        if [ -d "$dir" ]; then
          newest=$(find "$dir" -maxdepth 1 -mindepth 1 -type d -printf '%T@\t%f\n' 2>/dev/null | sort -rn | head -1 | cut -f2)
          if [ -n "$newest" ]; then
            newest_ts=$(stat -c %Y "$dir/$newest")
            now=$(date +%s)
            age_hours=$(( (now - newest_ts) / 3600 ))
            if [ "$age_hours" -lt 2 ]; then
              check "$label: latest=$newest (''${age_hours}h ago)" "ok"
            elif [ "$age_hours" -lt 24 ]; then
              check "$label: latest=$newest (''${age_hours}h ago -- stale)" "warn"
            else
              check "$label: latest=$newest (''${age_hours}h ago -- OLD)" "fail"
            fi
          else
            check "$label: no snapshots found" "warn"
          fi
        else
          check "$label: directory missing" "warn"
        fi
      done

      # 3. Check backup recency (realm -> neo-outer-realm)
      printf '\n%sBackups (realm -> neo-outer-realm):%s\n' "$BOLD" "$NC"
      backup_dir="${backupTarget}/realm"
      if [ -d "$backup_dir" ]; then
        count=$(find "$backup_dir" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
        newest=$(find "$backup_dir" -maxdepth 1 -mindepth 1 -type d -printf '%T@\t%f\n' 2>/dev/null | sort -rn | head -1 | cut -f2)
        if [ -n "$newest" ]; then
          newest_ts=$(stat -c %Y "$backup_dir/$newest")
          now=$(date +%s)
          age_hours=$(( (now - newest_ts) / 3600 ))
          check "$count backups, latest=$newest (''${age_hours}h ago)" \
            "$([ "$age_hours" -lt 2 ] && echo ok || ([ "$age_hours" -lt 24 ] && echo warn || echo fail))"
        else
          check "backup directory exists but empty" "warn"
        fi
      else
        check "no backups yet ($backup_dir missing)" "warn"
      fi

      # 4. Check btrbk service status
      printf '\n%sService:%s\n' "$BOLD" "$NC"
      if systemctl is-enabled btrbk.timer &>/dev/null; then
        check "btrbk.timer enabled" "ok"
      else
        check "btrbk.timer not enabled" "fail"
      fi

      next=$(systemctl show btrbk.timer --property=NextElapseUSecRealtime --value 2>/dev/null || echo "unknown")
      if [ "$next" != "unknown" ] && [ -n "$next" ]; then
        check "next run: $next" "ok"
      fi

      last_exit=$(systemctl show btrbk.service --property=ExecMainStatus --value 2>/dev/null || echo "unknown")
      if [ "$last_exit" = "0" ]; then
        check "last run: success" "ok"
      elif [ "$last_exit" = "unknown" ] || [ -z "$last_exit" ]; then
        check "last run: never executed" "warn"
      else
        check "last run: FAILED (exit=$last_exit)" "fail"
      fi

      # 5. BTRFS health
      printf '\n%sFilesystem health:%s\n' "$BOLD" "$NC"
      for dev in / "${realmRoot}" "${neoOuterRealm}"; do
        if mountpoint -q "$dev" 2>/dev/null; then
          errors=$(dmesg 2>/dev/null | grep -ci "btrfs.*error" || echo "0")
          if [ "$errors" -eq 0 ]; then
            check "btrfs $dev: no kernel errors" "ok"
          else
            check "btrfs $dev: $errors kernel errors found" "warn"
          fi
        fi
      done

      # Summary
      echo ""
      total=$((ok + warn + fail))
      if [ "$fail" -gt 0 ]; then
        printf '%s%sBACKUP HEALTH: %d/%d checks passed, %d FAILED, %d warnings%s\n' "$RED" "$BOLD" "$ok" "$total" "$fail" "$warn" "$NC"
        exit 1
      elif [ "$warn" -gt 0 ]; then
        printf '%s%sBACKUP HEALTH: %d/%d checks passed, %d warnings%s\n' "$YELLOW" "$BOLD" "$ok" "$total" "$warn" "$NC"
        exit 0
      else
        printf '%s%sBACKUP HEALTH: all %d checks passed%s\n' "$GREEN" "$BOLD" "$total" "$NC"
        exit 0
      fi
    '';
  };

in
{
  config = {
    environment.systemPackages = [
      pkgs.btrbk
      backupHealthCheck
    ];

    # btrbk configuration
    environment.etc."btrbk/btrbk.conf".text = btrbkConfig;

    # Ensure snapshot and backup directories exist
    systemd.tmpfiles.rules = lib.mkAfter [
      "d ${realmSnapshots} 0750 root root -"
      "d ${rootSnapshots} 0750 root root -"
      "d ${neoSnapshots} 0750 root root -"
      "d ${backupTarget} 0750 root root -"
      "d ${backupTarget}/realm 0750 root root -"
    ];

    # btrbk service: main backup execution
    systemd.services.btrbk = {
      description = "btrbk btrfs snapshot and backup";
      documentation = [ "https://digint.ch/btrbk/doc/btrbk.1.html" ];
      unitConfig = {
        RequiresMountsFor = lib.unique [
          realmRoot
          neoOuterRealm
        ];
        # Don't fail the whole system if backup can't run
        ConditionPathIsMountPoint = [
          realmRoot
          neoOuterRealm
        ];
      };
      after = [
        "local-fs.target"
      ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${pkgs.btrbk}/bin/btrbk run --quiet";
        # Backup should never compete with interactive work
        Nice = 19;
        IOSchedulingClass = "idle";
        IOSchedulingPriority = 7;
        # Security hardening
        PrivateTmp = true;
        ProtectHome = "no"; # Needs access to /realm which bind-mounts home
        NoNewPrivileges = false; # btrbk needs btrfs ioctls
        # Allow writes to snapshot dirs and backup target
        ReadWritePaths = [
          realmRoot
          realmSnapshots
          neoOuterRealm
          neoSnapshots
          backupTarget
          rootSnapshots
          "/var/log"
          "/var/lock"
        ];
        # Logging
        StandardOutput = "journal";
        StandardError = "journal";
        SyslogIdentifier = "btrbk";
      };
    };

    # Timer: run hourly (btrbk is idempotent and fast when nothing changed)
    systemd.timers.btrbk = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "hourly";
        Persistent = true; # Catch up on missed runs after boot/sleep
        RandomizedDelaySec = "5min"; # Don't thundering-herd with other timers
        AccuracySec = "5min";
      };
    };

    # Daily health check: logs warnings if backups are stale
    systemd.services.btrbk-health = {
      description = "btrbk backup health check";
      after = [ "btrbk.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${backupHealthCheck}/bin/backup-health";
        Nice = 19;
        IOSchedulingClass = "idle";
        StandardOutput = "journal";
        StandardError = "journal";
        SyslogIdentifier = "btrbk-health";
      };
    };

    systemd.timers.btrbk-health = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "daily";
        Persistent = true;
        RandomizedDelaySec = "30min";
      };
    };
  };
}
