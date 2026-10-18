# Repair the publisher shrinkwrap while preserving the hash-locked source archive.
{ pkgs, src }:
let
  declarations = {
    "node_modules/@earendil-works/chord" = {
      url = "https://registry.npmjs.org/@earendil-works/chord/-/chord-0.87.1.tgz";
      hash = "sha512-bg7IkJGFcEaMqqYgOGUiq5Ky9RghpRfrlZ8I/v/1b4bBZ02A7t3E+6uhPRbadwWb/kWsnVFbZsqOKRN4a3LLCg==";
    };
    "node_modules/@earendil-works/pi-agent-core" = {
      url = "https://registry.npmjs.org/@earendil-works/pi-agent-core/-/pi-agent-core-0.87.1.tgz";
      hash = "sha512-Zev3B0HK7YS5A4EZQ2XnEqiJuirx6QBiltJ+LpmjV5a/+2IU0cfKtIfnkNkORK707XOvKBY2WRtk7cAwHpbh2Q==";
    };
    "node_modules/@earendil-works/pi-ai" = {
      url = "https://registry.npmjs.org/@earendil-works/pi-ai/-/pi-ai-0.87.1.tgz";
      hash = "sha512-X/3PfQBnnoeVdO9Cv8zHghUMglzlgNZYGNzoPnbRoGnHl3Rw3TlA2UKSUB7BRHUOxMryHXYa8dnjWZlbRheDZA==";
    };
    "node_modules/@earendil-works/pi-telemetry" = {
      url = "https://registry.npmjs.org/@earendil-works/pi-telemetry/-/pi-telemetry-0.87.1.tgz";
      hash = "sha512-MC6TRQH5lgMXpcN+Vku2WMI2T8BsiUPzMQHGo81uqFZD3/9O79WWJAysEDGuzduP6R4tvtgwMLwmqIxynM10JQ==";
    };
    "node_modules/@earendil-works/pi-tui" = {
      url = "https://registry.npmjs.org/@earendil-works/pi-tui/-/pi-tui-0.87.1.tgz";
      hash = "sha512-YEH2vRyOeiO7hhN6j6AE6YwKSq2Kz2f3XR8bj1TbR+aGE/JsnY1hLPMI2pvaZfRM1n9Y00tejxFQ4zbzvF7nkQ==";
    };
  };
  verified = pkgs.writeText "pi-recovery-integrities.json" (
    builtins.toJSON (
      builtins.mapAttrs (_: spec: {
        inherit (spec) url hash;
        archive = toString (pkgs.fetchurl spec);
      }) declarations
    )
  );
in
pkgs.runCommand "pi-coding-agent-0.87.1-integrity-locked.tgz"
  {
    nativeBuildInputs = [ pkgs.python3 ];
    passthru.original = src;
  }
  ''
    python3 ${./repair-pi.py} ${src} ${verified} "$out"
  ''
