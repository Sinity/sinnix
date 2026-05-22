{
  lib,
  python3,
}:
# sinnix-sentinel (Python port) — Phase G.
#
# Ships as a separate binary (`sinnix-sentinel-py`) so it can be installed
# alongside the bash `sinnix-sentinel` during the 24h observation window.
# modules/services/sentinel.nix is intentionally NOT updated; promoting to
# the systemd unit is a separate operational step.
python3.pkgs.buildPythonApplication {
  pname = "sinnix-sentinel-py";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3.pkgs.setuptools ];
  doCheck = false; # tests are run via the flake checks tree
  meta = with lib; {
    description = "Python port of sinnix-sentinel (observe-only by default)";
    mainProgram = "sinnix-sentinel-py";
    license = licenses.mit;
    platforms = platforms.linux;
  };
}
