{ lib, mountTmpfsRoots, baseTestConfig, inputs, ... }:
{
  name = "router-config-evaluates";
  modules = [
    mountTmpfsRoots
    baseTestConfig
    (
      { ... }:
      {
        networking.hostName = "router-test";
      }
    )
  ];
  assertions =
    _config:
    let
      routerCfg = import (inputs.self + "/hosts/sinnix-gw/default.nix") { inherit lib; };
      openwrtLib = import (inputs.self + "/modules/lib/openwrt.nix") { inherit lib; };
      uciScript = openwrtLib.mkUciScript routerCfg.uci;
      pkgScript = openwrtLib.mkOpkgScript routerCfg.packages;

      contains = haystack: needle: builtins.match ".*${lib.escapeRegex needle}.*" haystack != null;
    in
    [
      # ── Basic metadata ──
      {
        assertion = routerCfg.hostname == "sinnix-gw";
        message = "Router hostname must be sinnix-gw";
      }
      {
        assertion = routerCfg.address == "192.168.1.1";
        message = "Router address must be 192.168.1.1";
      }
      {
        assertion = builtins.length routerCfg.packages > 0;
        message = "Router must have packages to install";
      }
      {
        assertion = builtins.stringLength uciScript > 100;
        message = "UCI script must generate non-trivial output";
      }
      {
        assertion = builtins.stringLength pkgScript > 10;
        message = "Package script must generate output";
      }
      {
        assertion = builtins.stringLength routerCfg.postCommands > 100;
        message = "Post-commands must be non-empty";
      }

      # ── Ash compatibility (no pipefail) ──
      {
        assertion = !(contains uciScript "pipefail");
        message = "UCI script must not contain pipefail (ash incompatible)";
      }
      {
        assertion = !(contains pkgScript "pipefail");
        message = "Package script must not contain pipefail (ash incompatible)";
      }

      # ── UCI script is a fragment (no embedded shebang) ──
      {
        assertion = !(contains uciScript "#!/bin/sh");
        message = "UCI script must not contain shebang (it's a fragment, not standalone)";
      }

      # ── Critical UCI sections exist ──
      {
        assertion = contains uciScript "network.lan=";
        message = "UCI script must configure LAN interface";
      }
      {
        assertion = contains uciScript "network.wan=";
        message = "UCI script must configure WAN interface";
      }
      {
        assertion = contains uciScript "wireless.radio0=";
        message = "UCI script must configure radio0 (2.4GHz)";
      }
      {
        assertion = contains uciScript "wireless.radio1=";
        message = "UCI script must configure radio1 (5GHz)";
      }
      {
        assertion = contains uciScript "sqm.wan_qos=";
        message = "UCI script must configure SQM";
      }
      {
        assertion = contains uciScript "firewall.defaults=";
        message = "UCI script must configure firewall defaults";
      }
      {
        assertion = contains uciScript "dhcp.dnsmasq=";
        message = "UCI script must configure dnsmasq";
      }

      # ── UCI commit commands present ──
      {
        assertion = contains uciScript "uci commit network";
        message = "UCI script must commit network package";
      }
      {
        assertion = contains uciScript "uci commit wireless";
        message = "UCI script must commit wireless package";
      }
      {
        assertion = contains uciScript "uci commit firewall";
        message = "UCI script must commit firewall package";
      }

      # ── postCommands content ──
      {
        assertion = contains routerCfg.postCommands "authorized_keys";
        message = "Post-commands must deploy SSH authorized key";
      }
      {
        assertion = contains routerCfg.postCommands "https-dns-proxy";
        message = "Post-commands must configure https-dns-proxy (DoH)";
      }
      {
        assertion = contains routerCfg.postCommands "network reload";
        message = "Post-commands must reload network";
      }
      {
        assertion = contains routerCfg.postCommands "nf_conntrack_max";
        message = "Post-commands must tune conntrack table";
      }
    ];
}
