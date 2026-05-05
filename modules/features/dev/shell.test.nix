{
  lib,
  mkFeatureTest,
  expect,
  hmFor,
  ...
}:
mkFeatureTest {
  name = "dev-shell";
  feature = "sinnix.features.dev.shell.enable";
  assertions =
    config:
    let
      hm = hmFor config;
      packageNames = map (pkg: pkg.name or "") hm.home.packages;
    in
    [
      {
        assertion = hm.programs.zsh.enable;
        message = "Zsh must be enabled";
      }
      {
        assertion = hm.programs.starship.enable;
        message = "Starship must be enabled";
      }
      {
        assertion = hm.programs.atuin.enable;
        message = "Atuin must be enabled";
      }
      {
        assertion = hm.programs.fzf.enable;
        message = "FZF must be enabled";
      }
      {
        assertion = hm.programs.zoxide.enable;
        message = "Zoxide must be enabled";
      }
      (expect.sessionVariableMatches hm "LYNCHPIN_PYTHON" ".*/bin/lynchpin-python"
        "Dev shell must export the system-wide Lynchpin API interpreter path"
      )
      (expect.sessionVariableMatches hm "POLYLOGUE_PYTHON" ".*/bin/polylogue-python"
        "Dev shell must export the system-wide Polylogue API interpreter path"
      )
      {
        assertion = hm.programs.zsh.shellAliases.ccusage == "ccusage";
        message = "ccusage alias must resolve to the packaged CLI";
      }
      {
        assertion = builtins.any (name: lib.hasPrefix "lynchpin-python" name) packageNames;
        message = "Dev shell must install the Lynchpin API interpreter wrapper";
      }
      {
        assertion = builtins.any (name: lib.hasPrefix "polylogue-python" name) packageNames;
        message = "Dev shell must install the Polylogue API interpreter wrapper";
      }
      {
        assertion = !(builtins.any (name: lib.hasPrefix "pytest-" name || name == "pytest") packageNames);
        message = "Dev shell must not install the transparent pytest resource-scope wrapper";
      }
      {
        assertion = lib.hasInfix "unsetopt prompt_sp" hm.programs.zsh.initContent;
        message = "Zsh init must disable PROMPT_SP to avoid stray partial-line prompt markers";
      }
    ];
}
