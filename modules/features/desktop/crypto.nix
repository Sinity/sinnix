{ mkFeatureModule, pkgs, ... }@args:
mkFeatureModule {
  path = [
    "desktop"
    "crypto"
  ];
  description = "Crypto daemon/wallet tooling";
  configFn =
    {
      config,
      lib,
      pkgs,
      user,
      ...
    }:
    let
      userGroup = config.users.users.${user}.group or user;
      moneroDataDir = config.sinnix.paths.cryptoRoot;
      # P2P bound to localhost (no external peers). For public node, change p2p-bind-ip
      # to 0.0.0.0 and add firewall rule: networking.firewall.allowedTCPPorts = [ 18080 ]
      moneroConfig = ''
        data-dir=${moneroDataDir}
        p2p-bind-ip=127.0.0.1
        p2p-bind-port=18080
        db-sync-mode=fast:async:10000
        out-peers=32
        in-peers=8
        limit-rate-up=10240
        limit-rate-down=0
        rpc-bind-ip=127.0.0.1
        rpc-restricted-bind-ip=127.0.0.1
        log-file=${moneroDataDir}/monerod.log
      '';
      moneroImportRaw = pkgs.writeShellScriptBin "monero-import-raw" ''
        #!/usr/bin/env bash
        set -euo pipefail

        RAW=''${1:-${moneroDataDir}/blockchain.raw}

        if [ ! -f "$RAW" ]; then
          echo "blockchain.raw not found at $RAW" >&2
          exit 1
        fi

        mkdir -p "${moneroDataDir}"

        exec ${pkgs.monero-cli}/bin/monero-blockchain-import \
          --data-dir "${moneroDataDir}" \
          --input-file "$RAW" \
          --batch-size 200000 \
          --batch 1 \
          --prep-blocks-threads 8 \
          --dangerous-unverified-import 1 \
          --resume 1
      '';
      moneroDaemon = pkgs.writeShellScriptBin "monero-daemon" ''
        #!/usr/bin/env bash
        set -euo pipefail

        exec ${pkgs.monero-cli}/bin/monerod --config-file "$HOME/.bitmonero/bitmonero.conf" "$@"
      '';
      bitcoinDataDir = "${moneroDataDir}/bitcoin";
      bitcoinWalletDir = "${bitcoinDataDir}/wallets";
      bitcoinMainWallet = "${bitcoinWalletDir}/main_wallet";
      btcWallet = pkgs.writeShellScriptBin "btc-wallet" ''
        #!/usr/bin/env bash
        set -euo pipefail

        mkdir -p "${bitcoinWalletDir}"

        exec ${pkgs.electrum}/bin/electrum \
          --dir "${bitcoinDataDir}" \
          --wallet "${bitcoinMainWallet}" \
          "$@"
      '';
    in
    {
      home-manager.users.${user} =
        { pkgs, lib, ... }:
        {
          home = {
            packages = with pkgs; [
              monero-cli
              monero-gui
              moneroImportRaw
              moneroDaemon
              electrum
              btcWallet
            ];

            file.".bitmonero/bitmonero.conf".text = moneroConfig;
            sessionVariables.MONERO_DATA_DIR = moneroDataDir;
          };
        };

      systemd.tmpfiles.rules = lib.mkAfter [
        "d ${moneroDataDir} 0700 ${user} ${userGroup} -"
        "d ${bitcoinDataDir} 0700 ${user} ${userGroup} -"
        "d ${bitcoinWalletDir} 0700 ${user} ${userGroup} -"
      ];
    };
} args
