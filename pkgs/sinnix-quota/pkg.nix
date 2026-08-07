{
  lib,
  stdenv,
  fetchurl,
  gnutar,
  gzip,
  autoPatchelfHook,
  curl,
  sqlite,
  python3Packages,
}:

let
  codexbar = stdenv.mkDerivation {
    pname = "codexbar-cli";
    version = "0.47.0";
    src = fetchurl {
      url = "https://github.com/steipete/CodexBar/releases/download/v0.47.0/CodexBarCLI-v0.47.0-linux-x86_64.tar.gz";
      hash = "sha256-Qv+L/3kDUHjJHIWdC9n3uvWCF8qYj6o9sHG/DICjAtU=";
    };
    dontUnpack = true;
    nativeBuildInputs = [
      autoPatchelfHook
      gnutar
      gzip
    ];
    buildInputs = [
      curl
      sqlite
      stdenv.cc.cc
    ];
    installPhase = ''
      mkdir -p $out/bin
      tar -xzf $src -C $TMPDIR
      if [ -x $TMPDIR/codexbar ]; then
        install -Dm755 $TMPDIR/codexbar $out/bin/codexbar
      else
        install -Dm755 $TMPDIR/CodexBarCLI $out/bin/codexbar
      fi
    '';
    meta = {
      description = "Pinned CodexBar Linux CLI provider usage adapter";
      homepage = "https://github.com/steipete/CodexBar";
      license = lib.licenses.mit;
      mainProgram = "codexbar";
    };
  };
in
python3Packages.buildPythonApplication {
  pname = "sinnix-quota";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  nativeCheckInputs = [ python3Packages.pytest ];
  checkPhase = ''
    runHook preCheck
    pytest -q
    runHook postCheck
  '';
  passthru = { inherit codexbar; };
  meta = {
    description = "Versioned provider quota normalization and redaction adapters";
    mainProgram = "sinnix-quota";
    license = lib.licenses.mit;
  };
}
