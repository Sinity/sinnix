# Sinnix — the estate's phone-side member, built as a normal Android app.
#
# This used to be a Gradle-free build (aapt2 + javac + d8 by hand) because the
# app had nothing to resolve. That stopped being true when the app grew a UI
# worth the name: Compose, Glance and an HTTP client are not "a plain JAR on
# the javac classpath", and hand-rolling framework views to avoid a dependency
# lock was paying a permanent interface cost to avoid a one-time build cost.
#
# So this is Gradle, made reproducible the way nixpkgs supports: the Gradle
# setup hook drives the build, and `gradle.fetchDeps` records every artifact
# fetch through mitm-cache into the committed deps.json. Regenerate that
# lockfile after any dependency change with:
#
#   $(nix-build /realm/project/sinnix -A packages.x86_64-linux.sinnix-phone-app.mitmCache.updateScript)
#
# The APK is still emitted UNSIGNED, and that is still load-bearing: signing
# happens in sinnix-phone-app-install against a keystore outside the store, so
# `adb install -r` stays an upgrade rather than a forced uninstall — which on
# Android also discards the app's runtime grants.
{
  lib,
  stdenv,
  pkgs,
  writeShellApplication,
  android-tools,
  gradle,
  fetchurl,
}:

let
  # Silero VAD, shipped as an app asset.
  #
  # Fetched here rather than committed: 2 MB of weights is not source, and a
  # binary in a public repo is a thing that has to be explained forever. But it
  # must be IN the APK rather than downloaded on the device, because the speech
  # lane deliberately has no network gate — a model that needed one download
  # first would have made "always on" mean "always on once you have been home".
  sileroVad = fetchurl {
    url = "https://github.com/snakers4/silero-vad/raw/76e3dc408eb2a5c655c34e230d2d5459b4439daa/src/silero_vad/data/silero_vad.onnx";
    hash = "sha256-GhU6IvRQnikqlOZ9b5uF6N6yW0mIaCt+F0xlJ52HiOM=";
  };

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

  # compileSdk. targetSdk stays at 33 (app/build.gradle.kts explains why); the
  # compile platform is free to be newer, and current AndroidX requires 35.
  platformVersion = "36";
  buildToolsVersion = "36.0.0";

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

  jdk = androidPkgs.jdk17_headless;

  apk = stdenv.mkDerivation (finalAttrs: {
    pname = "sinnix-phone-app";
    version = "0.2.0";
    src = lib.cleanSourceWith {
      src = ./.;
      # pkg.nix and deps.json are build inputs of the derivation, not sources
      # of the app; including them would rebuild the APK whenever a comment in
      # this file moved.
      filter =
        path: type:
        let
          base = baseNameOf path;
        in
        !(builtins.elem base [
          "pkg.nix"
          "deps.json"
          ".gradle"
          "build"
        ]);
    };

    nativeBuildInputs = [
      gradle
      jdk
    ];

    mitmCache = gradle.fetchDeps {
      pkg = finalAttrs.finalPackage;
      data = ./deps.json;
    };

    dontConfigure = false;

    # AGP resolves the SDK from the environment; there is no local.properties
    # in the source tree because that file is a per-developer artifact and this
    # build has exactly one "developer".
    env = {
      ANDROID_HOME = sdkRoot;
      ANDROID_SDK_ROOT = sdkRoot;
      JAVA_HOME = jdk;
    };

    # AGP insists on a writable analytics/preferences directory before it will
    # even apply its plugin, and neither the build sandbox nor the mitm-cache
    # update sandbox has a HOME. Runs in both, because both need it.
    preBuild = ''
      export HOME="''${TMPDIR:-/tmp}/android-home"
      export ANDROID_USER_HOME="$HOME/.android"
      mkdir -p "$ANDROID_USER_HOME"

      # The VAD model, into the asset tree the app reads it from.
      mkdir -p app/src/main/assets
      cp ${sileroVad} app/src/main/assets/silero_vad.onnx
    '';

    gradleFlags = [
      "-Dorg.gradle.java.home=${jdk}"
      # AGP otherwise pulls a prebuilt aapt2 from Maven, which is a dynamically
      # linked binary against a libc that does not exist here. The SDK's copy is
      # already patched by androidenv.
      "-Pandroid.aapt2FromMavenOverride=${buildTools}/aapt2"
    ];

    gradleBuildTask = ":app:assembleRelease";

    # The default (nixDownloadDeps) resolves declared configurations, which is
    # not the same set as "what an Android build actually fetches" — AGP pulls
    # r8, the lint model and several tool jars during task execution. Running
    # the real build under the recording proxy is the only way to capture them.
    gradleUpdateTask = ":app:assembleRelease";

    # Compose's compiler plugin and AGP both dislike being run in parallel
    # inside the sandbox for a single-module project, and there is nothing to
    # gain: one module, one variant.
    enableParallelBuilding = false;
    enableParallelUpdating = false;

    doCheck = false;

    installPhase = ''
      runHook preInstall
      mkdir -p "$out"
      cp app/build/outputs/apk/release/app-release-unsigned.apk \
        "$out/sinnix-capture-unsigned.apk"
      runHook postInstall
    '';

    passthru = {
      inherit buildTools jdk;
      applicationId = "dev.sinnix.phone";
    };

    meta = {
      description = "Sinnix: the estate's phone-side app — ambient capture, instruments, ingress and the estate remote";
      platforms = lib.platforms.linux;
      sourceProvenance = with lib.sourceTypes; [
        fromSource
        binaryBytecode # mitm cache
      ];
    };
  });

  install = writeShellApplication {
    name = "sinnix-phone-app-install";
    runtimeInputs = [
      android-tools
      jdk
    ];
    text = ''
      # Sign and sideload Sinnix.
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
