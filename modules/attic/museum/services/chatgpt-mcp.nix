# attic/museum: archived 2026-05-24.
# Revive by `git mv` back to modules/services/chatgpt-mcp.nix.
# Reason: Occasional-use ngrok bridge for exposing local MCP to ChatGPT;
# preserved as design reference; revival may need ngrok/mcpo updates.
# ChatGPT MCP Bridge - SSH transport to local machine
#
# Bridges ssh-mcp (stdio MCP server over SSH) to HTTP via mcpo,
# making it connectable as a ChatGPT Connector (Developer Mode).
# Expose port with ngrok: `ngrok http 3010`
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.sinnix.services.chatgpt-mcp;
  userName = config.sinnix.user.name;

  mcpBridge = pkgs.writeShellScriptBin "chatgpt-mcp-bridge" ''
    set -euo pipefail

    PORT="''${CHATGPT_MCP_PORT:-${toString cfg.port}}"
    HOST="''${CHATGPT_MCP_HOST:-${cfg.host}}"
    SSH_HOST="''${CHATGPT_MCP_SSH_HOST:-${cfg.sshHost}}"
    SSH_USER="''${CHATGPT_MCP_SSH_USER:-${cfg.sshUser}}"
    SSH_KEY="''${CHATGPT_MCP_SSH_KEY:-${cfg.sshKey}}"
    if [[ -z "''${CHATGPT_MCP_API_KEY:-}" && -n "''${CREDENTIALS_DIRECTORY:-}" && -r "$CREDENTIALS_DIRECTORY/api-key" ]]; then
      CHATGPT_MCP_API_KEY="$(< "$CREDENTIALS_DIRECTORY/api-key")"
    fi
    API_KEY_ARGS=()
    if [[ -n "''${CHATGPT_MCP_API_KEY:-}" ]]; then
      API_KEY_ARGS=(--api-key "$CHATGPT_MCP_API_KEY" --strict-auth)
    fi

    export UV_CACHE_DIR="''${STATE_DIRECTORY:-/tmp}/uv-cache"
    export npm_config_cache="''${STATE_DIRECTORY:-/tmp}/npm-cache"
    mkdir -p "$UV_CACHE_DIR" "$npm_config_cache"

    exec ${pkgs.uv}/bin/uvx mcpo \
      --host "$HOST" \
      --port "$PORT" \
      "''${API_KEY_ARGS[@]}" \
      -- \
      ${pkgs.nodejs}/bin/npx -y ssh-mcp@1.5.0 \
        -- \
        --host="$SSH_HOST" \
        --user="$SSH_USER" \
        --key="$SSH_KEY" \
        --timeout=120000 \
        --maxChars=none
  '';
in
{
  options.sinnix.services.chatgpt-mcp = {
    enable = lib.mkEnableOption "ChatGPT MCP bridge (SSH transport, exposed via mcpo)";

    port = lib.mkOption {
      type = lib.types.port;
      default = 3010;
      description = "Port for the HTTP MCP endpoint (expose via ngrok: `ngrok http <port>`)";
    };

    host = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = "Host address for mcpo to bind. Use a local tunnel for remote ChatGPT access.";
    };

    apiKeyFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Optional file containing the mcpo API key. When set, strict auth is enabled.";
    };

    sshHost = lib.mkOption {
      type = lib.types.str;
      default = "localhost";
      description = "SSH host for remote command execution";
    };

    sshUser = lib.mkOption {
      type = lib.types.str;
      default = userName;
      description = "SSH user for remote command execution";
    };

    sshKey = lib.mkOption {
      type = lib.types.str;
      default = "/home/${userName}/.ssh/id_ed25519";
      description = "Path to SSH private key for authentication";
    };
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ mcpBridge ];

    home-manager.users.${userName} = {
      systemd.user.services.chatgpt-mcp = {
        Unit = {
          Description = "ChatGPT MCP bridge - HTTP endpoint for ChatGPT Connector (Developer Mode)";
          After = [ "network.target" ];
        };

        Service = {
          ExecStart = "${mcpBridge}/bin/chatgpt-mcp-bridge";
          Restart = "on-failure";
          RestartSec = "5s";

          # Environment overrides (matching options above)
          Environment = [
            "CHATGPT_MCP_HOST=${cfg.host}"
            "CHATGPT_MCP_PORT=${toString cfg.port}"
            "CHATGPT_MCP_SSH_HOST=${cfg.sshHost}"
            "CHATGPT_MCP_SSH_USER=${cfg.sshUser}"
            "CHATGPT_MCP_SSH_KEY=${cfg.sshKey}"
          ];
          LoadCredential = lib.optional (cfg.apiKeyFile != null) "api-key:${cfg.apiKeyFile}";

          # Package caches persist across restarts
          StateDirectory = "chatgpt-mcp";
          StateDirectoryMode = "0700";

          # Hardening is conservative; this runs as the user and needs full home access.
          NoNewPrivileges = true;
          PrivateTmp = true;
        };

        Install.WantedBy = [ "default.target" ];
      };
    };
  };
}
