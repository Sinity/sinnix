# Continuous audio capture with VAD + ASR.
#
# Runs two user services:
# - sinnix-asr-server:    exposes local faster-whisper or local Cohere Transcribe on port 7778
# - sinnix-audio-daemon:  captures the preferred PipeWire input and transcribes the Yeti mic
#
# Disabled by default (opt-in).
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
  description = "Continuous audio capture with VAD and automatic ASR";
  enableDefault = false;
  extraOptions = {
    archiveDir = lib.mkOption {
      type = lib.types.str;
      default = "/realm/data/captures/audio";
      description = "Directory for opus-compressed full-stream archives.";
    };
    transcriptDir = lib.mkOption {
      type = lib.types.str;
      default = "/realm/data/captures/audio/transcripts";
      description = "Directory for ASR transcript JSONL files.";
    };
    asrPort = lib.mkOption {
      type = lib.types.port;
      default = 7778;
      description = "Port the ASR server listens on.";
    };
    asrModel = lib.mkOption {
      type = lib.types.str;
      default = "small";
      description = "faster-whisper model name used by the local ASR server.";
    };
    asrProvider = lib.mkOption {
      type = lib.types.enum [
        "local"
        "cohere"
        "cohere-api"
      ];
      default = "local";
      description = "ASR backend used by the local HTTP service. Cohere uses local open weights.";
    };
    cohereModel = lib.mkOption {
      type = lib.types.str;
      default = "CohereLabs/cohere-transcribe-03-2026";
      description = "Cohere Transcribe model repo or model name.";
    };
    cohereRevision = lib.mkOption {
      type = lib.types.str;
      default = "refs/pr/6";
      description = "Cohere Transcribe model revision used for the working Transformers implementation.";
    };
    cohereApiModel = lib.mkOption {
      type = lib.types.str;
      default = "cohere-transcribe-03-2026";
      description = "Cohere Transcribe API model name.";
    };
    cohereLanguage = lib.mkOption {
      type = lib.types.str;
      default = "en";
      description = "Single language code passed to Cohere Transcribe.";
    };
    cohereApiKeyFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = lib.attrByPath [
        "sinnix"
        "secrets"
        "paths"
        "cohere-api-key"
      ] null config;
      description = "Path to a file containing the Cohere API key.";
    };
    cohereMaxNewTokens = lib.mkOption {
      type = lib.types.ints.positive;
      default = 256;
      description = "Maximum generated tokens for each Cohere Transcribe chunk.";
    };
    preferredSourcePattern = lib.mkOption {
      type = lib.types.str;
      default = "(?i)(blue.*yeti|yeti)";
      description = "Regex for the input source that should be transcribed.";
    };
    captureOutputs = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Also record output/sink monitor streams.";
    };
    captureAllInputs = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Record every input source instead of only the preferred source.";
    };
    chunkSeconds = lib.mkOption {
      type = lib.types.ints.positive;
      default = 30;
      description = "Length of each captured audio chunk.";
    };
    enableAsrServer = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run the persistent local ASR server.";
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
      description = "Extra args passed to sinnix-audio-daemon.";
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
      pythonEnv = pkgs.python313.withPackages (ps: [
        ps.accelerate
        ps.fastapi
        ps.uvicorn
        ps.python-multipart
        ps.faster-whisper
        ps.huggingface-hub
        ps.librosa
        ps.protobuf
        ps.requests
        ps.sentencepiece
        ps.setuptools
        ps.soundfile
        ps.torch
        ps.transformers
        ps.webrtcvad
      ]);
      scriptsRoot = "${config.sinnix.paths.projectRoot}/scripts";
      # Wrapper scripts — avoid needing a shebang bash inside systemd to cd around.
      asrWrapper = pkgs.writeShellScript "sinnix-asr-server-wrapper" ''
        set -euo pipefail
        export SINNIX_ASR_MODEL=${lib.escapeShellArg cfg.asrModel}
        export SINNIX_COHERE_TRANSCRIBE_MODEL=${lib.escapeShellArg cfg.cohereModel}
        export SINNIX_COHERE_TRANSCRIBE_REVISION=${lib.escapeShellArg cfg.cohereRevision}
        export SINNIX_COHERE_TRANSCRIBE_API_MODEL=${lib.escapeShellArg cfg.cohereApiModel}
        export SINNIX_COHERE_TRANSCRIBE_LANGUAGE=${lib.escapeShellArg cfg.cohereLanguage}
        export SINNIX_COHERE_TRANSCRIBE_MAX_NEW_TOKENS=${toString cfg.cohereMaxNewTokens}
        export OMP_NUM_THREADS=1
        export MKL_NUM_THREADS=1
        export OPENBLAS_NUM_THREADS=1
        export NUMEXPR_NUM_THREADS=1
        ${lib.optionalString (cfg.cohereApiKeyFile != null) ''
          export COHERE_API_KEY_FILE=${lib.escapeShellArg cfg.cohereApiKeyFile}
        ''}
        export PATH=${
          lib.makeBinPath [
            pythonEnv
            pkgs.ffmpeg
          ]
        }:$PATH
        export SINNIX_ASR_PROVIDER=${lib.escapeShellArg cfg.asrProvider}
        exec ${pythonEnv}/bin/python3 ${scriptsRoot}/sinnix-asr-server \
          --host 127.0.0.1 \
          --port ${toString cfg.asrPort}
      '';
      daemonWrapper = pkgs.writeShellScript "sinnix-audio-daemon-wrapper" ''
        set -euo pipefail
        export PATH=${
          lib.makeBinPath [
            pythonEnv
            pkgs.pipewire
            pkgs.jq
          ]
        }:$PATH
        mkdir -p ${cfg.archiveDir} ${cfg.transcriptDir}
        exec ${pythonEnv}/bin/python3 ${scriptsRoot}/sinnix-audio-daemon \
          --archive-dir ${lib.escapeShellArg cfg.archiveDir} \
          --transcript-dir ${lib.escapeShellArg cfg.transcriptDir} \
          --asr-url http://127.0.0.1:${toString cfg.asrPort} \
          --chunk-seconds ${toString cfg.chunkSeconds} \
          --preferred-source-pattern ${lib.escapeShellArg cfg.preferredSourcePattern} \
          ${lib.optionalString cfg.captureOutputs "--capture-outputs"} \
          ${lib.optionalString cfg.captureAllInputs "--capture-all-inputs"} \
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
              Description = "Sinnix persistent ASR server";
              After = [ "default.target" ];
            };
            Service = {
              Type = "simple";
              ExecStart = "${asrWrapper}";
              Restart = "on-failure";
              RestartSec = 10;
              Environment = [
                "HF_HOME=%h/.cache/huggingface"
              ];
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

          # Ensure capture dirs exist at activation.
          home.activation.audioCaptureArchiveDir = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
            run mkdir -p ${cfg.archiveDir}
            run mkdir -p ${cfg.transcriptDir}
          '';
        };
    };
} args
