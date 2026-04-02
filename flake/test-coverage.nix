{
  allowedLayers = [
    "build"
    "eval"
    "runtime"
    "pty"
    "vm"
    "host"
  ];

  features = {
    "cli.core" = {
      layers = [ "eval" ];
    };
    "cli.polylogue" = {
      layers = [
        "eval"
        "runtime"
      ];
    };
    "cli.task-tracking" = {
      layers = [
        "eval"
        "runtime"
      ];
    };
    "desktop.activitywatch" = {
      layers = [ "eval" ];
    };
    "desktop.audio" = {
      layers = [ "eval" ];
    };
    "desktop.base" = {
      layers = [ "eval" ];
    };
    "desktop.browser" = {
      layers = [ "eval" ];
    };
    "desktop.common-apps" = {
      layers = [ "eval" ];
    };
    "desktop.crypto" = {
      layers = [ "eval" ];
    };
    "desktop.gaming" = {
      layers = [ "eval" ];
    };
    "desktop.hyprland" = {
      layers = [ "eval" ];
    };
    "desktop.media" = {
      layers = [ "eval" ];
    };
    "desktop.mime" = {
      layers = [ "eval" ];
    };
    "desktop.storage" = {
      layers = [ "eval" ];
    };
    "desktop.terminal" = {
      layers = [
        "eval"
        "runtime"
        "pty"
        "host"
      ];
    };
    "desktop.theming" = {
      layers = [ "eval" ];
    };
    "desktop.ui" = {
      layers = [ "eval" ];
    };
    "desktop.vr" = {
      layers = [ "eval" ];
    };
    "desktop.waybar" = {
      layers = [ "eval" ];
    };
    "dev.agentRestore" = {
      layers = [
        "eval"
        "runtime"
      ];
    };
    "dev.editors" = {
      layers = [ "eval" ];
    };
    "dev.git" = {
      layers = [
        "eval"
        "runtime"
      ];
    };
    "dev.languages" = {
      layers = [
        "eval"
        "runtime"
      ];
    };
    "dev.mcp-servers" = {
      layers = [
        "eval"
        "runtime"
      ];
    };
    "dev.shell" = {
      layers = [
        "eval"
        "runtime"
        "pty"
        "host"
      ];
    };
    "system.nix-ld" = {
      layers = [ "eval" ];
    };
  };

  services = {
    "below" = {
      layers = [
        "eval"
        "vm"
      ];
    };
    "polylogue" = {
      layers = [
        "eval"
        "vm"
      ];
    };
    "power-watchdog" = {
      layers = [
        "eval"
        "host"
      ];
    };
    "sentinel" = {
      layers = [
        "eval"
        "vm"
      ];
    };
    "sinex" = {
      layers = [ "build" ];
    };
    "terminal-capture" = {
      layers = [
        "eval"
        "runtime"
        "pty"
      ];
    };
    "transmission" = {
      layers = [
        "eval"
        "vm"
      ];
    };
  };

  bundles = {
    "desktop" = {
      layers = [
        "eval"
        "build"
      ];
    };
    "dev" = {
      layers = [ "eval" ];
    };
  };

  hosts = {
    "sinnix-prime" = {
      layers = [
        "build"
        "host"
      ];
    };
    "sinnix-ethereal" = {
      layers = [ "build" ];
    };
  };

  outputs = {
    "router-config" = {
      layers = [
        "build"
        "eval"
      ];
    };
  };
}
