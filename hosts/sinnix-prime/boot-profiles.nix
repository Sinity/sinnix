{
  config,
  lib,
  pkgs,
  ...
}:
let
  bootProfileTag =
    {
      gpuMode,
      recorderEnabled,
      launchCaptureEnabled,
      diagnosisEnabled,
    }:
    if gpuMode == "igpu" then
      "prime.igpu-rescue"
    else if gpuMode == "dual" then
      "prime.dual-gpu"
    else if recorderEnabled && launchCaptureEnabled then
      "prime.nvidia-investigation"
    else if recorderEnabled then
      "prime.nvidia-recorder"
    else if diagnosisEnabled then
      "prime.nvidia-diagnostics"
    else
      "prime.nvidia-operational";

  mkProfileConfig =
    {
      gpuMode,
      recorderEnabled,
      launchCaptureEnabled,
      diagnosisEnabled,
    }:
    {
      system.nixos.tags = lib.mkForce [
        (bootProfileTag {
          inherit
            gpuMode
            recorderEnabled
            launchCaptureEnabled
            diagnosisEnabled
            ;
        })
      ];

      sinnix.gpu.mode = lib.mkForce gpuMode;
      sinnix.services.reboot-no-more.enable = lib.mkForce recorderEnabled;
      sinnix.services.reboot-no-more.launchCapture.enable = lib.mkForce launchCaptureEnabled;
      sinnix.services.reboot-no-more.diagnosisMode = lib.mkForce diagnosisEnabled;
    };

  stagedGenerationScript = ''
    staged_link="$(readlink /nix/var/nix/profiles/system || true)"
    if [[ -z "$staged_link" ]]; then
      echo "Cannot resolve /nix/var/nix/profiles/system" >&2
      exit 1
    fi

    if [[ "$staged_link" =~ (^|/)system-([0-9]+)-link$ ]]; then
      staged_generation="''${BASH_REMATCH[2]}"
    else
      echo "Unrecognized staged system link: $staged_link" >&2
      exit 1
    fi
  '';

  bootProfileTool = pkgs.writeShellApplication {
    name = "sinnix-boot-profile";
    runtimeInputs = with pkgs; [
      gnugrep
      gnused
      coreutils
      systemd
      sudo
    ];
    text = ''
      set -euo pipefail

      profile_names=(nvidia-operational nvidia-recorder nvidia-investigation igpu-rescue dual-gpu)

      profile_description() {
        case "$1" in
          nvidia-operational) echo "Daily dGPU profile via NVIDIA open kernel module: recorder off, wrappers off" ;;
          nvidia-recorder) echo "dGPU via NVIDIA open kernel module with reboot-no-more on, Chrome/Hyprland wrappers off" ;;
          nvidia-investigation) echo "dGPU via NVIDIA open kernel module with reboot-no-more on plus Chrome/Hyprland capture wrappers" ;;
          igpu-rescue) echo "Intel iGPU rescue boot; display cable must be on the motherboard outputs" ;;
          dual-gpu) echo "Both i915 + NVIDIA active; plug cable into mobo or dGPU port, either works" ;;
          *)
            echo "Unknown profile: $1" >&2
            return 1
            ;;
        esac
      }

      entry_id_for() {
        local generation="$1"
        local profile="$2"
        case "$profile" in
          nvidia-operational) printf 'nixos-generation-%s.conf\n' "$generation" ;;
          nvidia-recorder|nvidia-investigation|igpu-rescue|dual-gpu)
            printf 'nixos-generation-%s-specialisation-%s.conf\n' "$generation" "$profile"
            ;;
          *)
            echo "Unknown profile: $profile" >&2
            return 1
            ;;
        esac
      }

      entry_path_for() {
        printf '/boot/loader/entries/%s\n' "$1"
      }

      entry_title_for() {
        local path="$1"
        sed -n 's/^title //p' "$path" | head -n 1
      }

      require_root() {
        if [[ "''${EUID:-$(id -u)}" -ne 0 ]]; then
          exec sudo "$0" "$@"
        fi
      }

      list_profiles() {
        ${stagedGenerationScript}
        printf 'Staged generation: %s\n' "$staged_generation"
        printf '\n'
        for profile in "''${profile_names[@]}"; do
          entry_id="$(entry_id_for "$staged_generation" "$profile")"
          entry_path="$(entry_path_for "$entry_id")"
          description="$(profile_description "$profile")"
          if [[ -e "$entry_path" ]]; then
            title="$(entry_title_for "$entry_path")"
            printf '%-22s  %-48s  %s\n' "$profile" "$title" "$description"
          else
            printf '%-22s  %-48s  %s [missing entry]\n' "$profile" "(not built in staged generation)" "$description"
          fi
        done
      }

      cmd="''${1:-status}"
      case "$cmd" in
        list)
          require_root "$cmd"
          list_profiles
          ;;
        status)
          require_root "$cmd"
          ${stagedGenerationScript}
          printf 'Running system: %s\n' "$(readlink -f /run/current-system)"
          printf 'Staged system:  %s\n' "$(readlink -f /nix/var/nix/profiles/system)"
          printf 'Staged generation: %s\n' "$staged_generation"
          printf '\n'
          bootctl status
          printf '\n'
          list_profiles
          ;;
        oneshot|default)
          profile="''${2:-}"
          if [[ -z "$profile" ]]; then
            echo "Usage: $0 $cmd <nvidia-operational|nvidia-recorder|nvidia-investigation|igpu-rescue|dual-gpu>" >&2
            exit 1
          fi
          ${stagedGenerationScript}
          entry_id="$(entry_id_for "$staged_generation" "$profile")"
          entry_path="$(entry_path_for "$entry_id")"
          if [[ ! -e "$entry_path" ]]; then
            echo "Missing boot entry: $entry_path" >&2
            exit 1
          fi
          require_root "$cmd" "$profile"
          if [[ "$cmd" == "oneshot" ]]; then
            bootctl set-oneshot "$entry_id"
          else
            bootctl set-default "$entry_id"
          fi
          printf 'Selected %s -> %s\n' "$profile" "$entry_id"
          ;;
        help|-h|--help)
          cat <<'EOF'
      Usage: sinnix-boot-profile [status|list|oneshot|default] [profile]

        status                     Show current/staged systems, bootctl status, and available profiles
        list                       List available profiles in the staged generation
        oneshot <profile>          Boot the selected profile once on the next reboot
        default <profile>          Make the selected profile the persistent boot default

      Profiles:
        nvidia-operational
        nvidia-recorder
        nvidia-investigation
        igpu-rescue
        dual-gpu
      EOF
          ;;
        *)
          echo "Unknown command: $cmd" >&2
          exit 1
          ;;
      esac
    '';
  };
in
{
  system.nixos.tags = [
    (bootProfileTag {
      gpuMode = config.sinnix.gpu.mode;
      recorderEnabled = config.sinnix.services.reboot-no-more.enable;
      launchCaptureEnabled = config.sinnix.services.reboot-no-more.launchCapture.enable;
      diagnosisEnabled = config.sinnix.services.reboot-no-more.diagnosisMode;
    })
  ];

  environment.systemPackages = [ bootProfileTool ];

  specialisation = {
    nvidia-recorder.configuration = mkProfileConfig {
      gpuMode = "nvidia-open";
      recorderEnabled = true;
      launchCaptureEnabled = false;
      diagnosisEnabled = true;
    };

    nvidia-investigation.configuration = mkProfileConfig {
      gpuMode = "nvidia-open";
      recorderEnabled = true;
      launchCaptureEnabled = true;
      diagnosisEnabled = true;
    };

    igpu-rescue.configuration = {
      imports = [
        (mkProfileConfig {
          gpuMode = "igpu";
          recorderEnabled = false;
          launchCaptureEnabled = false;
          diagnosisEnabled = false;
        })
        { sinnix.gpu.nvidiaTuning.enable = lib.mkForce false; }
        {
          # Hypothesis test: i915 PSR + DC power-gating wake failures cause silent
          # hard resets under Hyprland + browser load + thermal pressure.
          #
          # PSR (Panel Self Refresh): lets display cache a frame and powers down
          # the display link. Wake on new frames (browser launch) can fail on
          # Raptor Lake a780 — display pipeline freezes, compositor starves, DRM
          # scheduler timeout → hard reset with no kernel log.
          #
          # DC5/DC6: display engine C-states, similar wake hazard.
          # FBC: frame buffer compression, interacts with PSR timing.
          #
          # If resets stop here, move i915.enable_psr=0 to the permanent igpu config.
          # If they don't, the next tier is i915.enable_guc=0 (disables GuC RC6,
          # falls back to execlists — more invasive, loses GuC scheduling).
          boot.kernelParams = [
            "i915.enable_psr=0"
            "i915.enable_dc=0"
            "i915.enable_fbc=0"
          ];
        }
      ];
    };

    dual-gpu.configuration = {
      imports = [
        (mkProfileConfig {
          gpuMode = "dual";
          recorderEnabled = false;
          launchCaptureEnabled = false;
          diagnosisEnabled = false;
        })
        { sinnix.gpu.nvidiaTuning.enable = lib.mkForce false; }
      ];
    };
  };
}
