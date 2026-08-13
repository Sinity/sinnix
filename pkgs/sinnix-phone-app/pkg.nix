# Sinnix Capture — the on-device Android capture app.
#
# Built without Gradle, deliberately. Gradle wants to resolve dependencies
# from the network at build time, which a Nix derivation cannot do without a
# vendored dependency lock, and none of that machinery buys anything here: the
# app has no third-party dependencies at all, only platform APIs. So the build
# is the four tools underneath Gradle, invoked directly — aapt2 to link the
# manifest, javac to compile, d8 to dex, zipalign to align.
#
# The APK is emitted UNSIGNED. Signing happens in sinnix-phone-app-install
# against a keystore that lives outside the store (see that script for why):
# a key regenerated on every source change would make every `adb install -r`
# fail with a signature mismatch and force an uninstall, which on Android also
# throws away the app's runtime permission grants.
{
  lib,
  stdenv,
  pkgs,
  writeShellApplication,
  android-tools,
}:

let
  # The Android SDK is unfree and license-gated, so it needs its own nixpkgs
  # instantiation rather than the repo's shared one. pkgs.path keeps that
  # pinned to exactly the same nixpkgs revision the rest of the flake uses.
  androidPkgs = import pkgs.path {
    inherit (stdenv.hostPlatform) system;
    config = {
      android_sdk.accept_license = true;
      allowUnfree = true;
    };
  };

  platformVersion = "33";
  buildToolsVersion = "34.0.0";

  androidComposition = androidPkgs.androidenv.composeAndroidPackages {
    platformVersions = [ platformVersion ];
    buildToolsVersions = [ buildToolsVersion ];
    includeEmulator = false;
    includeSystemImages = false;
    includeNDK = false;
    includeSources = false;
  };

  sdkRoot = "${androidComposition.androidsdk}/libexec/android-sdk";
  buildTools = "${sdkRoot}/build-tools/${buildToolsVersion}";
  androidJar = "${sdkRoot}/platforms/android-${platformVersion}/android.jar";

  jdk = androidPkgs.jdk17_headless;

  apk = stdenv.mkDerivation {
    pname = "sinnix-phone-app";
    version = "0.1.0";
    src = ./app;

    nativeBuildInputs = [
      jdk
      androidPkgs.zip
    ];

    dontConfigure = true;

    buildPhase = ''
      runHook preBuild

      # Resources: none. Everything the UI needs is either built in code or a
      # framework resource (@android:drawable/...), so aapt2 only has to link
      # the manifest. That is what keeps this build Gradle-free.
      ${buildTools}/aapt2 link \
        -I ${androidJar} \
        --manifest AndroidManifest.xml \
        --min-sdk-version 29 \
        --target-sdk-version ${platformVersion} \
        -o base.apk

      mkdir -p classes dex
      find java -name '*.java' > sources.txt
      javac -nowarn -encoding UTF-8 --release 11 \
        -classpath ${androidJar} \
        -d classes @sources.txt

      find classes -name '*.class' > classes.txt
      ${buildTools}/d8 \
        --release \
        --lib ${androidJar} \
        --min-api 29 \
        --output dex \
        @classes.txt

      (cd dex && zip -q -X ../base.apk classes.dex)

      ${buildTools}/zipalign -p -f 4 base.apk sinnix-capture-unsigned.apk

      runHook postBuild
    '';

    installPhase = ''
      runHook preInstall
      mkdir -p "$out"
      cp sinnix-capture-unsigned.apk "$out/sinnix-capture-unsigned.apk"
      runHook postInstall
    '';

    passthru = {
      inherit androidJar buildTools jdk;
      applicationId = "dev.sinnix.phone";
    };

    meta = {
      description = "Sinnix Capture: Android foreground-service ambient audio capture for the operator's phone";
      platforms = lib.platforms.linux;
    };
  };

  install = writeShellApplication {
    name = "sinnix-phone-app-install";
    runtimeInputs = [
      android-tools
      jdk
    ];
    text = ''
      # Sign and sideload Sinnix Capture.
      #
      # The signing key is generated once, outside the Nix store, and reused
      # forever. That is the point: Android identifies an app by its signing
      # certificate, so a stable key is what makes `adb install -r` an upgrade
      # (permissions and app data preserved) instead of a forced uninstall.
      set -euo pipefail

      keystore_dir="''${SINNIX_PHONE_APP_KEYSTORE_DIR:-$HOME/.local/share/sinnix-phone-app}"
      keystore="$keystore_dir/keystore.jks"
      storepass="''${SINNIX_PHONE_APP_KEYSTORE_PASS:-sinnix-phone-app}"
      apk_src="${apk}/sinnix-capture-unsigned.apk"

      mkdir -p "$keystore_dir"
      chmod 700 "$keystore_dir"

      if [ ! -f "$keystore" ]; then
        echo "creating signing keystore at $keystore"
        keytool -genkeypair -v \
          -keystore "$keystore" \
          -storepass "$storepass" \
          -keypass "$storepass" \
          -alias sinnix \
          -keyalg RSA -keysize 4096 \
          -validity 36500 \
          -dname "CN=sinnix-phone-app, OU=sinnix, O=sinnix, C=US" >/dev/null
      fi

      workdir="$(mktemp -d)"
      trap 'rm -rf "$workdir"' EXIT
      signed="$workdir/sinnix-capture.apk"
      cp "$apk_src" "$signed"

      ${buildTools}/apksigner sign \
        --ks "$keystore" \
        --ks-pass "pass:$storepass" \
        --key-pass "pass:$storepass" \
        --v1-signing-enabled true \
        --v2-signing-enabled true \
        "$signed"

      ${buildTools}/apksigner verify --print-certs "$signed" | head -4

      if [ "''${1:-install}" = "build-only" ]; then
        out="''${2:-./sinnix-capture.apk}"
        cp "$signed" "$out"
        echo "wrote $out"
        exit 0
      fi

      echo "installing to ''${ANDROID_SERIAL:-<default device>}"
      adb install -r -g "$signed"
      echo "installed ${apk.passthru.applicationId}"
    '';
  };
in
apk // { inherit install; }
