_:
final: _prev:
let
  promptSrc = final.fetchFromGitHub {
    owner = "simonw";
    repo = "codex";
    rev = "ae5f98a9248a8edb5d3c53261273a482fc0b5306";
    hash = "sha256-Epd6+CPB49VOVnH8ueQakgTwhla4Y1j7/elTr/2GNlU=";
  };
in
{
  codex = final.rustPlatform.buildRustPackage {
    pname = "codex";
    version = "0.71.0-simonw-prompt";
    cargoHash = "sha256-3cvIq/TGn6O7a0pg2lBWnSAgYVUCH+v8pBLVbWfGiVY=";

    src = promptSrc;
    sourceRoot = "source/codex-rs";

    cargoBuildFlags = [
      "--package"
      "codex-cli"
    ];

    nativeBuildInputs = [
      final.installShellFiles
      final.pkg-config
    ];

    buildInputs = [ final.openssl ];

    preBuild = ''
      # Remove LTO to speed up builds
      substituteInPlace Cargo.toml \
        --replace-fail 'lto = "fat"' 'lto = false'
    '';

    doCheck = false;

    postInstall =
      final.lib.optionalString (final.stdenv.buildPlatform.canExecute final.stdenv.hostPlatform) ''
        installShellCompletion --cmd codex \
          --bash <($out/bin/codex completion bash) \
          --fish <($out/bin/codex completion fish) \
          --zsh <($out/bin/codex completion zsh)
      '';

    doInstallCheck = false;

    meta = {
      description = "OpenAI Codex CLI - a coding agent that runs locally on your computer";
      homepage = "https://github.com/openai/codex";
      license = final.lib.licenses.asl20;
      mainProgram = "codex";
      platforms = final.lib.platforms.unix;
    };
  };
}
