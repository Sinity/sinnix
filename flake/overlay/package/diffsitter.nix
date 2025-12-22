{ inputs }: final: prev:
let
  inherit (final) lib linkFarm rustPlatform fetchFromGitHub makeWrapper tree-sitter gitUpdater versionCheckHook;

  # Filter out grammars that are marked as broken upstream so we never try to
  # build them (tree-sitter-razor fails against modern toolchains).
  filterBroken = lib.filter (drv: lib.strings.getName drv != "tree-sitter-razor");

  withPlugins = grammarFn:
    let
      grammars = filterBroken (grammarFn tree-sitter.builtGrammars);
    in
    linkFarm "grammars" (
      map (
        drv:
          let
            name = lib.strings.getName drv;
          in
          {
            name = "lib" + (lib.strings.removeSuffix "-grammar" name) + ".so";
            path = "${drv}/parser";
          }
      ) grammars
    );

  libPath = withPlugins (_: tree-sitter.allGrammars);
in
{
  diffsitter = rustPlatform.buildRustPackage rec {
    pname = "diffsitter";
    version = "0.8.4";

    src = fetchFromGitHub {
      owner = "afnanenayet";
      repo = "diffsitter";
      rev = "v${version}";
      hash = "sha256-ta7JcSPEgpJwieYvtZnNMFvsYvz4FuxthhmKMYe2XUE=";
      fetchSubmodules = false;
    };

    cargoHash = "sha256-YgVsWiINzEsmUMAi6ttEtXutwNDJA2viXnV5rGdSSxU=";

    buildNoDefaultFeatures = true;
    buildFeatures = [ "dynamic-grammar-libs" ];

    nativeBuildInputs = [ makeWrapper ];

    nativeInstallCheckInputs = [ versionCheckHook ];
    doInstallCheck = true;

    postInstall = ''
      rm $out/bin/diffsitter_completions

      wrapProgram "$out/bin/diffsitter" \
        --prefix LD_LIBRARY_PATH : "${libPath}"
    '';

    doCheck = false;

    passthru.updateScript = gitUpdater { rev-prefix = "v"; };

    meta = {
      homepage = "https://github.com/afnanenayet/diffsitter";
      description = "Tree-sitter based AST difftool to get meaningful semantic diffs";
      license = lib.licenses.mit;
      maintainers = with lib.maintainers; [ bbigras ];
    };
  };
}
