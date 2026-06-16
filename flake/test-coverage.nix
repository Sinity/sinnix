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
    "cli.yt-polisher" = {
      layers = [ "eval" ];
    };
    "desktop.activitywatch" = {
      layers = [ "eval" ];
    };
    "desktop.agentVerifyTimer" = {
      layers = [ "eval" ];
    };
    "desktop.audio" = {
      layers = [ "eval" ];
    };
    "desktop.audioCapture" = {
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
    "desktop.gaming" = {
      layers = [ "eval" ];
    };
    "desktop.hyprland" = {
      layers = [ "eval" ];
    };
    "desktop.hyprlandAnimations" = {
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
    "desktop.noctalia" = {
      layers = [ "eval" ];
    };
    "dev.agentTools" = {
      layers = [
        "eval"
        "runtime"
        "pty"
        "host"
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
      layers = [ "eval" ];
    };
    "dev.workbench" = {
      layers = [ "eval" ];
    };
    "system.nix-ld" = {
      layers = [ "eval" ];
    };
  };
  services = {
    "agent-gateway" = {
      layers = [ "eval" ];
    };
    "airvpn-seed" = {
      layers = [ "eval" ];
    };
    "below" = {
      layers = [
        "eval"
        "vm"
      ];
    };
    "borg" = {
      layers = [ "eval" ];
    };
    "lynchpin" = {
      layers = [ "eval" ];
    };
    "machine-telemetry" = {
      layers = [
        "eval"
        "host"
      ];
    };
    "oracle" = {
      layers = [ "eval" ];
    };
    "polylogue" = {
      layers = [
        "eval"
        "vm"
      ];
    };
    "sinex" = {
      layers = [ "build" ];
    };
    "tailscale" = {
      layers = [ "eval" ];
    };
    "weechat-log-sealer" = {
      layers = [ "eval" ];
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
