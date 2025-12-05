{ pkgs, lib, sinnix, ... }:
let
  dataDir = "/monero";
  moneroConfig = ''
    data-dir=${dataDir}
    p2p-bind-ip=0.0.0.0
    p2p-bind-port=18080
    db-sync-mode=fast:async:10000
    out-peers=32
    in-peers=8
    limit-rate-up=10240
    limit-rate-down=0
    confirm-external-bind=1
    rpc-bind-ip=127.0.0.1
    rpc-restricted-bind-ip=127.0.0.1
    log-file=${dataDir}/monerod.log
  '';
  importRaw = pkgs.writeShellScriptBin "monero-import-raw" ''
    #!/usr/bin/env bash
    set -euo pipefail

    RAW=''${1:-${dataDir}/blockchain.raw}

    if [ ! -f "$RAW" ]; then
      echo "blockchain.raw not found at $RAW" >&2
      exit 1
    fi

    mkdir -p "${dataDir}"

    exec ${pkgs.monero-cli}/bin/monero-blockchain-import \
      --data-dir "${dataDir}" \
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
in
{
  home.packages = with pkgs; [
    monero-cli
    monero-gui
    importRaw
    moneroDaemon
  ];

  home.activation.ensureMoneroDataDir = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    mkdir -p ${dataDir}
  '';

  home.file.".bitmonero/bitmonero.conf".text = moneroConfig;

  home.sessionVariables.MONERO_DATA_DIR = dataDir;
}
