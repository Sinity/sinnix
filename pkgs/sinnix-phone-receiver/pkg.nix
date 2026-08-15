{
  lib,
  python3Packages,
  sinnix-capture-lib,
}:

python3Packages.buildPythonApplication {
  pname = "sinnix-phone-receiver";
  version = "0.1.0";
  pyproject = true;
  src = ./.;
  build-system = [ python3Packages.setuptools ];
  dependencies = [ sinnix-capture-lib ];
  meta = {
    description = "Persistent TCP receiver for the phone's always-on telemetry push (tailscale0 only), demuxed into sinnix-capture-v1 envelopes";
    mainProgram = "sinnix-phone-receiver";
    license = lib.licenses.mit;
  };
}
