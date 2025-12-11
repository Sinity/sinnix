_:
final: prev: {
  yt-dlp = prev.yt-dlp.overrideAttrs (_old: {
    version = "2025.12.08";
    src = final.fetchFromGitHub {
      owner = "yt-dlp";
      repo = "yt-dlp";
      rev = "2025.12.08";
      hash = "sha256-y06MDP+CrlHGrell9hcLOGlHp/gU2OOxs7can4hbj+g=";
    };
  });
}
