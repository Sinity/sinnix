{
  lib,
  stdenv,
  fetchFromGitHub,
  nodejs,
}:
stdenv.mkDerivation rec {
  pname = "claude-code-logger";
  version = "1.1.0";

  src = fetchFromGitHub {
    owner = "arsenyinfo";
    repo = "claude-code-logger";
    rev = "f572de0552716ae51a6090026f9cba9424f0f02e";
    sha256 = "sha256-pPyjYczcjtmC4j7c/+nkZQLeBzN+8WHp5x2LPIT1E7g=";
  };

  nativeBuildInputs = [nodejs];

  installPhase = ''
    runHook preInstall

    # Set npm cache and tmp directories to writable paths
    export npm_config_cache=$TMPDIR/npm-cache
    export npm_config_tmp=$TMPDIR/npm-tmp
    mkdir -p $npm_config_cache $npm_config_tmp

    # Create directories in the Nix store
    mkdir -p $out/bin $out/libexec/${pname}

    # Pack the source code into a tarball
    npm pack

    # Install the package into the private libexec directory
    npm install --global --prefix $out/libexec/${pname} claude-logger-*.tgz

    # Create a wrapper script for claude-log
    cat > $out/bin/claude-log <<EOF
    #!${stdenv.shell}
    # Wrapper for claude-log to use the local Claude CLI.

    CLAUDE_CLI="\$HOME/.claude/local/node_modules/.bin/claude"

    if [ ! -x "\$CLAUDE_CLI" ]; then
      echo "Error: Claude Code not found at \$CLAUDE_CLI or is not executable." >&2
      echo "Please ensure it is installed at that location and is executable." >&2
      exit 1
    fi

    # Export CLAUDE_CLI for the logger script
    export CLAUDE_CLI="\$CLAUDE_CLI"

    # Execute the claude-log script installed by npm
    exec "$out/libexec/${pname}/bin/claude-log" --log_dir=/realm/observability/claude_code_api_log "\$@"
    EOF
    chmod +x $out/bin/claude-log

    runHook postInstall
  '';

  meta = with lib; {
    description = "Log Anthropic API calls made through the Claude CLI, installed locally alongside Claude";
    homepage = "https://github.com/arsenyinfo/claude-code-logger";
    license = licenses.mit;
    maintainers = [maintainers.sinity];
    platforms = platforms.linux;
  };
}
