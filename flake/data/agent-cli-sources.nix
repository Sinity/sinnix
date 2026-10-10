# Top-level recovery tarballs. Native CLI updates retain their own ownership.
# Pi retains its publisher shrinkwrap with missing integrity hashes repaired.
# Claude and Codex platform packages have reviewed recovery shrinkwraps.
# Gemini and Clodex dependency trees remain outside this registry.
{ pkgs }:
{
  "@anthropic-ai/claude-code" = import ../../pkgs/agent-cli-recovery/platform-source.nix {
    inherit pkgs;
    name = "@anthropic-ai/claude-code";
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/@anthropic-ai/claude-code/-/claude-code-2.1.292.tgz";
      hash = "sha512-ptT9UcOsyR2VLNgfHgF87To8B7tCrZktIpYC4dEGt+9MG42NAWsljEGBZ3spdHcJ2akednszESVNti7hWxZrJg==";
    };
  };
  "@openai/codex" = import ../../pkgs/agent-cli-recovery/platform-source.nix {
    inherit pkgs;
    name = "@openai/codex";
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/@openai/codex/-/codex-0.162.1.tgz";
      hash = "sha512-NWZdi/kxyjv/8EUGFupziGU38YyleugZRM4JXgY5XFH7FUmaFA33NZS2Bmq0HPazf7S3jJQQWsZ/jAK9jsrV3Q==";
    };
  };
  "@earendil-works/pi-coding-agent" = import ../../pkgs/agent-cli-recovery/pi-source.nix {
    inherit pkgs;
    src = pkgs.fetchurl {
      url = "https://registry.npmjs.org/@earendil-works/pi-coding-agent/-/pi-coding-agent-0.87.1.tgz";
      hash = "sha512-m8ArJUtVcQMSe1lLE/Ei7vX/JV7O39sWmWBsXV2NOU70F0qCp8GubA24pT3LnwTmM6LL2xV80/h6sQg85n69ew==";
    };
  };
  "@bman654/clodex" = pkgs.fetchurl {
    url = "https://registry.npmjs.org/@bman654/clodex/-/clodex-2.18.10.tgz";
    hash = "sha512-8BA+8mzerSl6DDP0nkswZjQZSGsFR2ev9uyIWTKCvkc+jjTrgzF8ZN2/+Wmu7j28zw0XRg4O7hTYkGJGihIj/A==";
  };
  "@google/gemini-cli" = pkgs.fetchurl {
    url = "https://registry.npmjs.org/@google/gemini-cli/-/gemini-cli-0.45.2.tgz";
    hash = "sha512-Gm9UrodMu8Tw0hk2ncz1b8po5zhjA8tyED6SpDbkuJ91NjwzoYJ0s7sHlnJ1RpFUYuK6I+zMQMgtRqCcd+FbnA==";
  };
}
