{
  lib,
  python3Packages,
  sinnix-capture-lib,
}:
python3Packages.buildPythonApplication {
  pname = "sinnix-capture-a11y";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  # pyatspi is nixpkgs' packaged Python client binding for AT-SPI2 (built on
  # gi.repository.Atspi / pygobject3 under the hood) -- see the module doc
  # comment in modules/services/capture-a11y.nix for why pygobject3 has to
  # be listed explicitly (pyatspi does not propagate it as a runtime dep).
  dependencies = [
    python3Packages.pyatspi
    python3Packages.pygobject3
    sinnix-capture-lib
  ];
  nativeCheckInputs = [ python3Packages.pytest ];
  checkPhase = ''
    runHook preCheck
    pytest -q
    runHook postCheck
  '';
  meta = {
    description = "AT-SPI2 accessibility-tree capture daemon: focus/text-changed events + bounded focused-window subtree dumps via the sinnix-capture lib";
    mainProgram = "sinnix-capture-a11y";
    license = lib.licenses.mit;
  };
}
