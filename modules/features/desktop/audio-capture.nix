# Always-on microphone capture with local VAD and cloud-first ASR.
#
# Runs two user services:
# - sinnix-asr-server:    normalizes cloud/local ASR providers behind localhost:7778
# - sinnix-audio-daemon:  segments the preferred PipeWire input into speech utterances
#
# The daemon uploads only locally detected speech, not 24/7 silence.
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
  description = "Always-on microphone capture with local VAD and cloud-first ASR";
  enableDefault = false;
  extraOptions = {
    archiveDir = lib.mkOption {
      type = lib.types.str;
      default = "/realm/data/captures/audio";
      description = "Directory for utterance WAV captures.";
    };
    transcriptDir = lib.mkOption {
      type = lib.types.str;
      default = "/realm/data/captures/audio/transcripts";
      description = "Directory for normalized transcript JSONL files.";
    };
    asrPort = lib.mkOption {
      type = lib.types.port;
      default = 7778;
      description = "Port the ASR router listens on.";
    };
    asrProvider = lib.mkOption {
      type = lib.types.enum [
        "openai"
        "deepgram"
        "assemblyai"
        "cohere-api"
        "local"
      ];
      default = "openai";
      description = "ASR backend used by the localhost router. Cloud providers are preferred for realtime quality/features.";
    };
    asrLanguage = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = "en";
      description = "Optional language code passed to ASR providers.";
    };
    asrDiarization = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Request speaker diarization where the selected provider supports it.";
    };
    asrModel = lib.mkOption {
      type = lib.types.str;
      default = "small";
      description = "faster-whisper model used by the local fallback provider.";
    };
    openaiModel = lib.mkOption {
      type = lib.types.str;
      default = "gpt-4o-mini-transcribe";
      description = "OpenAI transcription model.";
    };
    openaiApiKeyFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = lib.attrByPath [ "sinnix" "secrets" "paths" "openai-api-key" ] null config;
      description = "Path to a file containing the OpenAI API key.";
    };
    deepgramModel = lib.mkOption {
      type = lib.types.str;
      default = "nova-3";
      description = "Deepgram model name.";
    };
    deepgramApiKeyFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = lib.attrByPath [ "sinnix" "secrets" "paths" "deepgram-api-key" ] null config;
      description = "Path to a file containing the Deepgram API key.";
    };
    assemblyaiModel = lib.mkOption {
      type = lib.types.str;
      default = "universal-2";
      description = "AssemblyAI speech model.";
    };
    assemblyaiApiKeyFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = lib.attrByPath [ "sinnix" "secrets" "paths" "assemblyai-api-key" ] null config;
      description = "Path to a file containing the AssemblyAI API key.";
    };
    cohereApiModel = lib.mkOption {
      type = lib.types.str;
      default = "cohere-transcribe-03-2026";
      description = "Cohere Transcribe API model name.";
    };
    cohereApiKeyFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = lib.attrByPath [ "sinnix" "secrets" "paths" "cohere-api-key" ] null config;
      description = "Path to a file containing the Cohere API key.";
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
    archive = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Archive finalized utterance WAV files. Off keeps only transcript JSONL.";
    };
    transcribe = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Send finalized speech utterances to the ASR router.";
    };
    vadAggressiveness = lib.mkOption {
      type = lib.types.ints.between 0 3;
      default = 2;
      description = "WebRTC VAD aggressiveness: 0 least strict, 3 most strict.";
    };
    preRollMs = lib.mkOption {
      type = lib.types.ints.positive;
      default = 450;
      description = "Audio kept before speech trigger to avoid clipped first syllables.";
    };
    minSpeechMs = lib.mkOption {
      type = lib.types.ints.positive;
      default = 300;
      description = "Minimum voiced audio needed before an utterance is transcribed.";
    };
    silenceMs = lib.mkOption {
      type = lib.types.ints.positive;
      default = 900;
      description = "Trailing silence that finalizes an utterance.";
    };
    maxUtteranceSeconds = lib.mkOption {
      type = lib.types.ints.positive;
      default = 18;
      description = "Maximum utterance length before forced finalization.";
    };
    captureLatencyMs = lib.mkOption {
      type = lib.types.ints.positive;
      default = 80;
      description = "PipeWire recording latency hint.";
    };
    enableAsrServer = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run the localhost ASR router.";
    };
    enableAudioDaemon = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Run the capture daemon (PipeWire → local VAD → ASR).";
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
        ps.fastapi
        ps.uvicorn
        ps.python-multipart
        ps.faster-whisper
        ps.requests
        ps.setuptools
        ps.webrtcvad
      ]);
      scriptsRoot = "${config.sinnix.paths.projectRoot}/scripts";
      maybeSecret =
        envName: path:
        lib.optionalString (path != null) ''
          export ${envName}=${lib.escapeShellArg path}
        '';
      maybeLanguage = lib.optionalString (cfg.asrLanguage != null) ''
        export SINNIX_ASR_LANGUAGE=${lib.escapeShellArg cfg.asrLanguage}
      '';
      asrWrapper = pkgs.writeShellScript "sinnix-asr-server-wrapper" ''
        set -euo pipefail
        export SINNIX_ASR_PROVIDER=${lib.escapeShellArg cfg.asrProvider}
        export SINNIX_ASR_MODEL=${lib.escapeShellArg cfg.asrModel}
        export SINNIX_ASR_DIARIZATION=${if cfg.asrDiarization then "true" else "false"}
        ${maybeLanguage}
        export SINNIX_OPENAI_TRANSCRIBE_MODEL=${lib.escapeShellArg cfg.openaiModel}
        export SINNIX_DEEPGRAM_MODEL=${lib.escapeShellArg cfg.deepgramModel}
        export SINNIX_ASSEMBLYAI_MODEL=${lib.escapeShellArg cfg.assemblyaiModel}
        export SINNIX_COHERE_TRANSCRIBE_API_MODEL=${lib.escapeShellArg cfg.cohereApiModel}
        ${maybeSecret "OPENAI_API_KEY_FILE" cfg.openaiApiKeyFile}
        ${maybeSecret "DEEPGRAM_API_KEY_FILE" cfg.deepgramApiKeyFile}
        ${maybeSecret "ASSEMBLYAI_API_KEY_FILE" cfg.assemblyaiApiKeyFile}
        ${maybeSecret "COHERE_API_KEY_FILE" cfg.cohereApiKeyFile}
        export OMP_NUM_THREADS=1
        export MKL_NUM_THREADS=1
        export OPENBLAS_NUM_THREADS=1
        export NUMEXPR_NUM_THREADS=1
        export PATH=${
          lib.makeBinPath [
            pythonEnv
            pkgs.ffmpeg
          ]
        }:$PATH
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
          --preferred-source-pattern ${lib.escapeShellArg cfg.preferredSourcePattern} \
          --vad-aggressiveness ${toString cfg.vadAggressiveness} \
          --pre-roll-ms ${toString cfg.preRollMs} \
          --min-speech-ms ${toString cfg.minSpeechMs} \
          --silence-ms ${toString cfg.silenceMs} \
          --max-utterance-seconds ${toString cfg.maxUtteranceSeconds} \
          --latency-ms ${toString cfg.captureLatencyMs} \
          ${lib.optionalString cfg.captureOutputs "--capture-outputs"} \
          ${lib.optionalString cfg.captureAllInputs "--capture-all-inputs"} \
          ${lib.optionalString (!cfg.transcribe) "--no-transcribe"} \
          ${lib.optionalString (!cfg.archive) "--no-archive"} \
          ${lib.concatStringsSep " " cfg.extraArgs}
      '';
    in
    {
      assertions = [
        {
          assertion = !(cfg.asrProvider == "openai" && cfg.openaiApiKeyFile == null);
          message = "audioCapture.asrProvider=openai requires openaiApiKeyFile";
        }
        {
          assertion = !(cfg.asrProvider == "deepgram" && cfg.deepgramApiKeyFile == null);
          message = "audioCapture.asrProvider=deepgram requires deepgramApiKeyFile";
        }
        {
          assertion = !(cfg.asrProvider == "assemblyai" && cfg.assemblyaiApiKeyFile == null);
          message = "audioCapture.asrProvider=assemblyai requires assemblyaiApiKeyFile";
        }
        {
          assertion = !(cfg.asrProvider == "cohere-api" && cfg.cohereApiKeyFile == null);
          message = "audioCapture.asrProvider=cohere-api requires cohereApiKeyFile";
        }
      ];

      home-manager.users.${user} =
        { lib, ... }:
        {
          systemd.user.services.sinnix-asr-server = lib.mkIf cfg.enableAsrServer {
            Unit = {
              Description = "Sinnix ASR router";
              After = [ "default.target" ];
            };
            Service = {
              Type = "simple";
              ExecStart = "${asrWrapper}";
              Restart = "on-failure";
              RestartSec = 10;
              Environment = [ "HF_HOME=%h/.cache/huggingface" ];
            };
            Install.WantedBy = [ "default.target" ];
          };

          systemd.user.services.sinnix-audio-daemon = lib.mkIf cfg.enableAudioDaemon {
            Unit = {
              Description = "Sinnix always-on microphone capture + transcription";
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

          home.activation.audioCaptureDirs = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
            run mkdir -p ${cfg.archiveDir}
            run mkdir -p ${cfg.transcriptDir}
          '';
        };
    };
} args
