# module/home/ssh.nix
{ pkgs, ... }:
{
  programs.ssh = {
    enable = true;
    addKeysToAgent = "yes";
    package = pkgs.openssh;

    # # Translates ~/.ssh/config entries
    # matchBlocks = {
    #   # Host * settings
    #   "*" = {
    #     ForwardAgent = "no";
    #     # AddKeysToAgent = "yes";
    #     # Compression = "no";
    #     ServerAliveInterval = 0; # Note: 0 usually means disable keepalive
    #     ServerAliveCountMax = 3;
    #     HashKnownHosts = "no";
    #     UserKnownHostsFile = "~/.ssh/known_hosts";
    #     ControlMaster = "no"; # 'auto' or 'yes' might be needed for ControlPath
    #     ControlPath = "~/.ssh/master-%r@%n:%p";
    #     ControlPersist = "no"; # Or a time value like "10m" if ControlMaster is enabled
    #     IdentitiesOnly = "yes";
    #     # Add specific Host blocks here if needed
    #     # "github.com" = {
    #     #   User = "git";
    #     #   IdentityFile = "~/.ssh/id_ed25519_github";
    #     # };
    #   };
    #   # Add other specific Host blocks as needed
    #   # "my-server" = {
    #   #   HostName = "192.168.1.100";
    #   #   User = "myuser";
    #   #   Port = 2222;
    #   #   IdentityFile = "~/.ssh/id_rsa_myserver";
    #   # };
    # };
    #
    # If you use an SSH agent like gnome-keyring or KeePassXC
    # addKeysToAgent = "yes"; # Already set in '*' block

    # ForwardAgent = false; # Already set in '*' block
  };
}
