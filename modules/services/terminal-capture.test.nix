{
  lib,
  mkServiceTest,
  hmFor,
  inputs,
  ...
}:
mkServiceTest {
  name = "services-terminal-capture";
  service = "terminal-capture";
  assertions = config: [
    {
      assertion = builtins.any (
        rule: builtins.match ".*captures/asciinema.*" rule != null
      ) config.systemd.tmpfiles.rules;
      message = "Asciinema captures directory tmpfiles entry must exist";
    }
    {
      assertion = (hmFor config).home.file ? ".local/bin/sinnix-captured-shell";
      message = "The terminal capture launcher must be linked into ~/.local/bin";
    }
    {
      assertion =
        (hmFor config).home.sessionVariables.SINNIX_CAPTURE_ROOT == "/realm/data/captures/asciinema";
      message = "The capture root session variable must point at the canonical asciinema directory";
    }
    {
      assertion = (hmFor config).home.sessionVariables.SINNIX_CAPTURE_TERMINAL == "kitty";
      message = "The capture terminal session variable must identify Kitty";
    }
    {
      assertion = lib.hasInfix "sinnix-terminal-capture-hooks.zsh" (hmFor config)
      .programs.zsh.initContent;
      message = "The zsh init path must source the terminal capture hooks";
    }
    {
      assertion =
        builtins.match ".*SUCCESS_BACKOFF_SECONDS.*sleep.*" (
          builtins.readFile (inputs.self + "/scripts/rawlog-loop")
        ) != null;
      message = "rawlog-loop must back off after fast success exits";
    }
  ];
}
