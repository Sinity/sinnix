# Continuous audio capture with VAD + ASR.
#
# Runs two user services:
# - sinnix-asr-server:    keeps Cohere Transcribe 2B in VRAM on port 7778
#
# Disabled by default (opt-in).
#
{
  mkFeatureModule,
  pkgs,
  lib,
  config,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "audioCapture"
  ];
  description = "Continuous audio capture (mic + monitor) with VAD and automatic Cohere Transcribe ASR";
  enableDefault = false;
  extraOptions = {
    archiveDir = lib.mkOption {
      type = lib.types.str;
      default = "/realm/data/captures/audio";
      description = "Directory for opus-compressed full-stream archives.";
    };
    asrPort = lib.mkOption {
      type = lib.types.port;
      default = 7778;
      description = "Port the ASR server listens on.";
    };
    enableAsrServer = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run the persistent ASR server (Cohere Transcribe 2B).";
    };
    enableAudioDaemon = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run the capture daemon (pipewire → VAD → transcribe).";
    };
    transcribe = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Auto-transcribe detected speech segments. Requires ASR server.";
    };
    archive = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Archive full audio streams as opus. Off = VAD + transcribe only, no archival.";
    };
    extraArgs = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = "Extra args passed to audio-daemon (e.g. --input-only, --output-only).";
    };
  };
  configFn =
    {
      config,
      pkgs,
      lib,
      user,
      cfg,
      ...
    }:
    let
      # Unstable transformers 5.5 has CohereAsrForConditionalGeneration; torch CPU is cached
      pythonEnv = pkgs.python313.withPackages (ps: [
        ps.fastapi
        ps.uvicorn
        ps.python-multipart
        ps.torch
        ps.torchaudio
        ps.transformers
        ps.accelerate
        ps.huggingface-hub
        ps.soundfile
        ps.librosa
        ps.sentencepiece
        ps.protobuf
        ps.numpy
        ps.click
        ps.pyyaml
      ]);
      # System NVIDIA driver provides libcudart, libcudnn etc.
      # torch-bin is a pre-compiled CUDA wheel — needs these at runtime only.
      cudaLibPath = "/run/opengl-driver/lib";
      # Wrapper scripts — avoid needing a shebang bash inside systemd to cd around.
      asrWrapper = pkgs.writeShellScript "sinnix-asr-server-wrapper" ''
        set -euo pipefail
        export LD_LIBRARY_PATH=${cudaLibPath}''${LD_LIBRARY_PATH:+:}$LD_LIBRARY_PATH
        export PATH=${
          lib.makeBinPath [
            pythonEnv
            pkgs.ffmpeg
            pkgs.libsndfile
          ]
        }:$PATH
      '';
      daemonWrapper = pkgs.writeShellScript "sinnix-audio-daemon-wrapper" ''
        set -euo pipefail
        export ASR_URL=http://127.0.0.1:${toString cfg.asrPort}
        export PATH=${
          lib.makeBinPath [
            pythonEnv
            pkgs.pipewire
            pkgs.ffmpeg
            pkgs.libsndfile
          ]
        }:$PATH
        mkdir -p ${cfg.archiveDir}
          ${lib.optionalString (!cfg.transcribe) "--no-transcribe"} \
          ${lib.optionalString (!cfg.archive) "--no-archive"} \
          ${lib.concatStringsSep " " cfg.extraArgs}
      '';
    in
    {
      home-manager.users.${user} =
        { pkgs, lib, ... }:
        {
          systemd.user.services.sinnix-asr-server = lib.mkIf cfg.enableAsrServer {
            Unit = {
              Description = "Sinnix persistent ASR server (Cohere Transcribe 2B)";
              After = [ "default.target" ];
            };
            Service = {
              Type = "simple";
              ExecStart = "${asrWrapper}";
              Restart = "on-failure";
              RestartSec = 10;
              # Allow HuggingFace model cache (~4-6GB) to persist.
              # First run downloads; subsequent runs are instant.
            };
            Install.WantedBy = [ "default.target" ];
          };

          systemd.user.services.sinnix-audio-daemon = lib.mkIf cfg.enableAudioDaemon {
            Unit = {
              Description = "Sinnix continuous audio capture + auto-transcribe";
              After = [
                "graphical-session.target"
                "pipewire.service"
              ]
              ++ lib.optional cfg.enableAsrServer "sinnix-asr-server.service";
              Wants = lib.optional cfg.enableAsrServer "sinnix-asr-server.service";
              PartOf = [ "graphical-session.target" ];
              Requisite = [ "graphical-session.target" ];
            };
            Service = {
              Type = "simple";
              ExecStart = "${daemonWrapper}";
              Restart = "on-failure";
              RestartSec = 10;
            };
            Install.WantedBy = [ "graphical-session.target" ];
          };

          # Ensure archive dir exists at activation.
          home.activation.audioCaptureArchiveDir = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
            run mkdir -p ${cfg.archiveDir}
          '';
        };
    };
} args
