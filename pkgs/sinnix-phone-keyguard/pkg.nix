{
  lib,
  stdenvNoCC,
  jdk,
  buildTools,
  python3,
  android-tools,
  makeWrapper,
}:
stdenvNoCC.mkDerivation {
  pname = "sinnix-phone-keyguard";
  version = "0.1.0";
  src = ./.;
  nativeBuildInputs = [
    jdk
    makeWrapper
  ];
  buildPhase = ''
    javac --release 11 PhoneKeyguard.java
    mkdir dex
    JAVA_HOME=${jdk} ${buildTools}/d8 --output dex PhoneKeyguard.class
  '';
  installPhase = ''
    mkdir -p $out/share $out/bin
    cp dex/classes.dex $out/share/keyguard.dex
    cp unlock.py $out/share/unlock.py
    makeWrapper ${python3}/bin/python3 $out/bin/sinnix-phone-keyguard \
      --add-flags $out/share/unlock.py \
      --prefix PATH : ${lib.makeBinPath [ android-tools ]}
  '';
  meta.description = "Bounded root-authorized native phone keyguard maintenance";
}
