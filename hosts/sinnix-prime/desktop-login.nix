{
  pkgs,
  lib,
  user,
  hyprland,
  noctalia,
  sessionEnvironment,
}:
let
  requestLock = pkgs.writeShellApplication {
    name = "noctalia-startup-lock";
    runtimeInputs = [
      pkgs.coreutils
      pkgs.systemd
      noctalia
    ];
    text = ''
      # Noctalia starts as a graphical-session service after UWSM finalizes.
      for ((i = 0; i < 60; i++)); do
        if response=$(timeout --kill-after=1s 1s noctalia msg session lock 2>/dev/null) && [[ "$response" == ok ]]; then
          exit 0
        fi
        sleep 0.25
      done
      systemd-cat -t noctalia-startup-lock -p err echo \
        "Noctalia did not accept the startup lock. The compositor remains locked."
      exit 1
    '';
  };
  startDesktop = pkgs.writeShellScript "start-sinnix-desktop" ''
    # greetd runs a command directly, outside the user's zsh login profile.
    . ${sessionEnvironment}
    # Keep the mutable Home Manager symlink as the reload path.
    export HYPRLAND_CONFIG="$HOME/.config/hypr/hyprland.lua"
    exec ${pkgs.uwsm}/bin/uwsm start -e -D Hyprland -- ${hyprland}/bin/start-hyprland "$@"
  '';
in
{
  services.greetd = {
    enable = true;
    useTextGreeter = true;
    settings = {
      # Hyprland force-locks before enabling outputs, then invokes the
      # command. A failed command leaves the compositor's own lock in place.
      initial_session = {
        inherit user;
        command = "${startDesktop} -- --locked-cmd ${lib.getExe requestLock}";
      };
      default_session.command = "${pkgs.greetd}/bin/agreety --cmd ${startDesktop}";
    };
  };

  # Starting greetd conflicts with getty@tty1 and would end the current
  # console session during the first activation. Let boot start it instead.
  systemd.services.greetd.unitConfig.X-OnlyManualStart = true;
}
