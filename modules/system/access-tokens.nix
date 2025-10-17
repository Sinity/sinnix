{
  lib,
  config,
  ...
}:
let
  githubTokenPath = config.age.secrets.github-token.path or "";
  nixTokenEntry = lib.optionalString (githubTokenPath != "")
    "github.com=$(builtins.readFile githubTokenPath)";
in
{
  assertions = [
    {
      assertion = githubTokenPath != "";
      message = "GitHub token secret not available at runtime.";
    }
  ];

  nix.settings.access-tokens =
    lib.mkMerge [
      (lib.mkIf (githubTokenPath != "") [
        "github.com=@${githubTokenPath}"
        "api.github.com=@${githubTokenPath}"
      ])
    ];
}
