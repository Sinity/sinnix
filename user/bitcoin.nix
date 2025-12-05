{ pkgs, lib, ... }:
let
  dataDir = "/monero/bitcoin";
  walletDir = "${dataDir}/wallets";
  mainWallet = "${walletDir}/main_wallet";
  btcWallet = pkgs.writeShellScriptBin "btc-wallet" ''
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p "${walletDir}"
    exec ${pkgs.electrum}/bin/electrum \
      --dir "${dataDir}" \
      --wallet "${mainWallet}" \
      "$@"
  '';
in
{
  home.packages = [
    pkgs.electrum
    btcWallet
  ];

  home.activation.ensureBitcoinDir = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    mkdir -p ${walletDir}
  '';
}
