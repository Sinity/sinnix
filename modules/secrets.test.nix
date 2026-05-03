{ mountTmpfsRoots, baseTestConfig, ... }:
{
  name = "password-secrets-wiring";
  modules = [
    mountTmpfsRoots
    baseTestConfig
    (
      { ... }:
      {
        networking.hostName = "password-test";
      }
    )
  ];
  assertions = config: [
    {
      assertion = config.users.mutableUsers == false;
      message = "mutableUsers must be false (declarative passwords)";
    }
    {
      assertion = config.users.users.${config.sinnix.user.name} ? hashedPasswordFile;
      message = "User must have hashedPasswordFile set (not inline hash)";
    }
    {
      assertion = config.users.users.root ? hashedPasswordFile;
      message = "Root must have hashedPasswordFile set (not inline hash)";
    }
    {
      assertion =
        config.users.users.${config.sinnix.user.name}.hashedPasswordFile
        == config.sinnix.secrets.paths."${config.sinnix.user.name}-password";
      message = "User password file must point to agenix secret path";
    }
    {
      assertion = config.users.users.root.hashedPasswordFile == config.sinnix.secrets.paths.root-password;
      message = "Root password file must point to agenix secret path";
    }
    {
      assertion = config.age.secrets ? "${config.sinnix.user.name}-password";
      message = "Agenix must have user password secret configured";
    }
    {
      assertion = config.age.secrets ? "root-password";
      message = "Agenix must have root password secret configured";
    }
  ];
}
