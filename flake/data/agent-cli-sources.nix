# Pinned recovery tarballs for the npm agent CLIs; the CLIs' own updaters
# still manage the live installs. Pi keeps its publisher shrinkwrap with
# missing integrity hashes repaired. Every other entry is locked by
# flake/data/agent-cli-locks.json, rendered only by
# `nix run .#sinnix-agent-cli-locks` (agentctl operation agent_cli_locks).
# To bump one: `nix run .#sinnix-agent-cli-locks -- --set @openai/codex=0.163.0`
# rewrites its URL and hash here and re-locks every entry.
{ pkgs }:
{
  "@anthropic-ai/claude-code" = import ../../pkgs/agent-cli-sources/dependency-source.nix {
    inherit pkgs;
    name = "@anthropic-ai/claude-code";
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/@anthropic-ai/claude-code/-/claude-code-2.1.292.tgz";
      hash = "sha512-ptT9UcOsyR2VLNgfHgF87To8B7tCrZktIpYC4dEGt+9MG42NAWsljEGBZ3spdHcJ2akednszESVNti7hWxZrJg==";
    };
  };
  "@openai/codex" = import ../../pkgs/agent-cli-sources/dependency-source.nix {
    inherit pkgs;
    name = "@openai/codex";
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/@openai/codex/-/codex-0.162.1.tgz";
      hash = "sha512-NWZdi/kxyjv/8EUGFupziGU38YyleugZRM4JXgY5XFH7FUmaFA33NZS2Bmq0HPazf7S3jJQQWsZ/jAK9jsrV3Q==";
    };
  };
  "@earendil-works/pi-coding-agent" = import ../../pkgs/agent-cli-sources/pi-source.nix {
    inherit pkgs;
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/@earendil-works/pi-coding-agent/-/pi-coding-agent-0.87.1.tgz";
      hash = "sha512-m8ArJUtVcQMSe1lLE/Ei7vX/JV7O39sWmWBsXV2NOU70F0qCp8GubA24pT3LnwTmM6LL2xV80/h6sQg85n69ew==";
    };
  };
  "@google/gemini-cli" = import ../../pkgs/agent-cli-sources/dependency-source.nix {
    inherit pkgs;
    name = "@google/gemini-cli";
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/@google/gemini-cli/-/gemini-cli-0.45.2.tgz";
      hash = "sha512-Gm9UrodMu8Tw0hk2ncz1b8po5zhjA8tyED6SpDbkuJ91NjwzoYJ0s7sHlnJ1RpFUYuK6I+zMQMgtRqCcd+FbnA==";
    };
  };
}
