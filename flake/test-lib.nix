# Test Infrastructure Library
#
# Reusable helpers for NixOS configuration tests. Provides:
# - sanitizedInputs: Hermetic input sanitization for reproducible tests
# - mountTmpfsRoots: Mock filesystem roots for test VMs
# - baseTestConfig: Minimal test configuration (no desktop, no secrets)
# - Test DSL helpers for common test patterns
#
# Usage:
#   let testLib = import ./test-lib.nix { inherit inputs lib; };
#   in testLib.mkFeatureTest { ... }
{ inputs, lib }:
let
  libContext = import ./lib-context.nix { inherit inputs; };
  inherit (libContext)
    extendedLib
    mkBaseModules
    mkSharedSpecialArgs
    ;

  # Use the repository tree directly for test-time path references.
  flakeSource = ../.;

  # Sanitized inputs replace self with pure path for reproducible tests
  sanitizedInputs = {
    inherit (inputs)
      agenix
      home-manager
      llm-agents
      lynchpin
      sinex
      polylogue
      ;
    inherit (inputs)
      scribe-tap
      intercept-bounce
      stylix
      ;
    inherit (inputs) nix-vscode-extensions disko nixpkgs;
    self = flakeSource;
  };

  # Base modules required for all tests
  baseModules = (mkBaseModules inputs) ++ [ ../modules/default.nix ];

  # Shared special args for test evaluation
  sharedSpecialArgs = mkSharedSpecialArgs sanitizedInputs;

  # Mock filesystem roots for test VMs (prevents real FS dependencies)
  mountTmpfsRoots =
    { ... }:
    {
      fileSystems."/" = {
        device = "tmpfs";
        fsType = "tmpfs";
      };
      fileSystems."/realm" = {
        device = "tmpfs";
        fsType = "tmpfs";
        neededForBoot = true;
      };
      fileSystems."/outer-realm" = {
        device = "tmpfs";
        fsType = "tmpfs";
        neededForBoot = true;
      };
      fileSystems."/persist" = {
        device = "tmpfs";
        fsType = "tmpfs";
        neededForBoot = true;
      };
      fileSystems."/neo-outer-realm" = {
        device = "tmpfs";
        fsType = "tmpfs";
        neededForBoot = true;
      };
    };

  # Base test configuration: minimal, no desktop
  baseTestConfig =
    { lib, ... }:
    {
      # Minimal NixOS requirements for evaluation
      boot.loader.grub.enable = false;
      programs.zsh.enable = true;

      sinnix = {
        machine.isDesktop = lib.mkDefault false;
        bundles.desktop.enable = lib.mkDefault false;
      };
    };

  vmTestConfig =
    { lib, ... }:
    {
      # The qemu-vm test harness disables timesyncd in its base module.
      # Keep the VM baseline aligned so sinnix's normal networking defaults
      # do not conflict with the test driver.
      services.timesyncd.enable = lib.mkForce false;
    };

  expect =
    let
      mkAssertion = assertion: message: {
        inherit assertion message;
      };
      hasPersistedDir =
        entries: dir:
        builtins.any (
          entry: if builtins.isAttrs entry then (entry.directory or null) == dir else entry == dir
        ) entries;
      anyMatches = regex: values: builtins.any (value: builtins.match regex value != null) values;
      managedEntryText =
        entry:
        if entry ? text && entry.text != null then
          entry.text
        else if entry ? source && entry.source != null then
          let
            maybeRead = builtins.tryEval (builtins.readFile entry.source);
          in
          if maybeRead.success then maybeRead.value else ""
        else
          "";
    in
    rec {
      inherit mkAssertion hasPersistedDir anyMatches;

      hmFileExists =
        hm: path: message:
        mkAssertion (builtins.hasAttr path hm.home.file) message;
      xdgConfigFileExists =
        hm: path: message:
        mkAssertion (builtins.hasAttr path hm.xdg.configFile) message;
      activationExists =
        hm: name: message:
        mkAssertion (builtins.hasAttr name hm.home.activation) message;

      systemdServiceExists =
        config: name: message:
        mkAssertion (builtins.hasAttr name config.systemd.services) message;
      systemdTimerExists =
        config: name: message:
        mkAssertion (builtins.hasAttr name config.systemd.timers) message;
      hmUserServiceExists =
        hm: name: message:
        mkAssertion (builtins.hasAttr name hm.systemd.user.services) message;
      hmUserTimerExists =
        hm: name: message:
        mkAssertion (builtins.hasAttr name hm.systemd.user.timers) message;

      persistedHomeDir =
        config: dir: message:
        mkAssertion (hasPersistedDir config.sinnix.persistence.home.directories dir) message;
      persistedSystemDir =
        config: dir: message:
        mkAssertion (hasPersistedDir config.sinnix.persistence.system.directories dir) message;

      tmpfilesRuleMatches =
        rules: regex: message:
        mkAssertion (anyMatches regex rules) message;

      textContains =
        text: needle: message:
        mkAssertion (lib.hasInfix needle text) message;
      textContainsAll =
        text: needles: message:
        mkAssertion (builtins.all (needle: lib.hasInfix needle text) needles) message;
      textMatches =
        text: regex: message:
        mkAssertion (builtins.match regex text != null) message;
      textNotMatches =
        text: regex: message:
        mkAssertion (builtins.match regex text == null) message;
      attrPathEq =
        attrs: path: expected: message:
        mkAssertion ((lib.attrByPath path null attrs) == expected) message;
      sessionVariableMatches =
        hm: name: regex: message:
        mkAssertion (builtins.match regex (hm.home.sessionVariables.${name} or "") != null) message;
      hmFileTextContains =
        hm: path: needle: message:
        textContains (managedEntryText hm.home.file.${path}) needle message;
      hmFileTextContainsAll =
        hm: path: needles: message:
        textContainsAll (managedEntryText hm.home.file.${path}) needles message;
      hmFileTextNotMatches =
        hm: path: regex: message:
        textNotMatches (managedEntryText hm.home.file.${path}) regex message;
      xdgConfigFileTextContains =
        hm: path: needle: message:
        textContains (managedEntryText hm.xdg.configFile.${path}) needle message;
      packagedWrapperText =
        text:
        {
          envVar ? null,
          binaryFragments ? [ ],
          forbidRegexes ? [ ],
        }:
        builtins.all (fragment: lib.hasInfix fragment text) binaryFragments
        && (envVar == null || lib.hasInfix "${envVar}=" text)
        && builtins.all (regex: builtins.match ".*${regex}.*" text == null) forbidRegexes;
      hmPackagedWrapper =
        hm:
        path:
        {
          envVar ? null,
          binaryFragments ? [ ],
          forbidRegexes ? [ ],
        }:
        message:
        mkAssertion (
          packagedWrapperText (managedEntryText hm.home.file.${path}) {
            inherit envVar binaryFragments forbidRegexes;
          }
        ) message;
    };

  coverageDiscoveryEval = extendedLib.nixosSystem {
    system = "x86_64-linux";
    modules = baseModules ++ [
      mountTmpfsRoots
      baseTestConfig
      {
        networking.hostName = "coverage-discovery";
      }
    ];
    specialArgs = sharedSpecialArgs // {
      lib = extendedLib;
    };
  };

  autoDiscoveredCoverageSurfaces = {
    features = lib.concatMap (
      domain:
      map (subject: "${domain}.${subject}") (
        builtins.attrNames coverageDiscoveryEval.config.sinnix.features.${domain}
      )
    ) (builtins.attrNames coverageDiscoveryEval.config.sinnix.features);
    services = builtins.attrNames coverageDiscoveryEval.config.sinnix.services;
    bundles = builtins.attrNames coverageDiscoveryEval.config.sinnix.bundles;
    hosts = builtins.attrNames ((import ./nixos.nix { inherit inputs; }).flake.nixosConfigurations);
    # Flake outputs do not live under the module tree; keep the public surface
    # list explicit until router outputs move behind the same discovery path.
    outputs = [ "router-config" ];
  };

  # Create a test for a single feature
  # Example: mkFeatureTest {
  #   name = "dev-shell";
  #   feature = "sinnix.features.dev.shell.enable";
  #   assertions = config: let hm = ... in [ { assertion = ...; message = ...; } ];
  # }
  mkFeatureTest =
    {
      name,
      feature,
      assertions,
      extraModules ? [ ],
    }:
    {
      inherit name;
      modules = [
        mountTmpfsRoots
        baseTestConfig
        (
          { ... }:
          {
            networking.hostName = name;
          }
          // lib.setAttrByPath (lib.splitString "." feature) true
        )
      ]
      ++ extraModules;
      inherit assertions;
    };

  # Create a test for a service
  mkServiceTest =
    {
      name,
      service,
      assertions,
      extraModules ? [ ],
    }:
    mkFeatureTest {
      inherit name assertions extraModules;
      feature = "sinnix.services.${service}.enable";
    };

  # Create a test for a bundle
  mkBundleTest =
    {
      name,
      bundle,
      assertions,
      extraModules ? [ ],
    }:
    mkFeatureTest {
      inherit name assertions extraModules;
      feature = "sinnix.bundles.${bundle}.enable";
    };

  # Evaluate a test spec without forcing a check derivation.
  evalTestSpec =
    system: spec:
    lib.nixosSystem {
      inherit system;
      modules =
        baseModules
        ++ spec.modules
        ++ [
          (
            { config, ... }:
            {
              assertions = spec.assertions config;
            }
          )
        ];
      specialArgs = sharedSpecialArgs // {
        lib = extendedLib;
      };
    };

  renderManagedEntry =
    {
      target,
      entry,
      rootExpr,
      rewriteHomeDir ? null,
    }:
    let
      hasText = entry ? text && entry.text != null;
      hasSource = entry ? source && entry.source != null;
      sourcePath = if hasSource then toString entry.source else null;
      sourceFileText =
        if hasSource && !(lib.hasPrefix "/nix/store/" sourcePath) then
          let
            maybeRead = builtins.tryEval (builtins.readFile entry.source);
          in
          if maybeRead.success then maybeRead.value else null
        else
          null;
      textValue =
        if hasText then
          if rewriteHomeDir == null then
            entry.text
          else
            builtins.replaceStrings [ rewriteHomeDir ] [ "__SINNIX_TEST_HOME__" ] entry.text
        else if sourceFileText != null then
          if rewriteHomeDir == null then
            sourceFileText
          else
            builtins.replaceStrings [ rewriteHomeDir ] [ "__SINNIX_TEST_HOME__" ] sourceFileText
        else
          null;
      sourceValue = sourcePath;
      executable = if entry ? executable && entry.executable != null then entry.executable else false;
    in
    ''
      root_dir=${rootExpr}
      target_rel=${lib.escapeShellArg target}
      dest="$root_dir/$target_rel"
      mkdir -p "$(dirname "$dest")"
      ${
        if textValue != null then
          ''
                      cat > "$dest" <<'EOF_SINNIX_TEST'
            ${textValue}
            EOF_SINNIX_TEST
                      ${lib.optionalString (rewriteHomeDir != null) ''
                        sed -i "s|__SINNIX_TEST_HOME__|$HOME|g" "$dest"
                      ''}
                      ${lib.optionalString executable ''
                        chmod +x "$dest"
                        patchShebangs "$dest" >/dev/null
                      ''}
          ''
        else if sourceValue != null then
          ''
            ln -s ${lib.escapeShellArg sourceValue} "$dest"
          ''
        else
          throw "Unsupported managed file entry for ${target}: expected text or source"
      }
      ${lib.optionalString executable ''chmod +x "$dest"''}
    '';

  exportSessionVariableScript =
    {
      name,
      value,
      rewriteHomeDir ? null,
    }:
    let
      textValue =
        if rewriteHomeDir == null then
          toString value
        else
          builtins.replaceStrings [ rewriteHomeDir ] [ "__SINNIX_TEST_HOME__" ] (toString value);
    in
    ''
      export_value=${lib.escapeShellArg textValue}
      export_value="''${export_value//__SINNIX_TEST_HOME__/$HOME}"
      export ${name}="$export_value"
    '';

  rewritePathScript =
    {
      target,
      rewrites,
    }:
    let
      rewriteCommands = lib.concatMapStrings (
        rewrite:
        ''
          sed -i ${lib.escapeShellArg "s|${rewrite.from}|${rewrite.to}|g"} "$rewrite_target"
        ''
      ) rewrites;
    in
    ''
      rewrite_target="$HOME/${target}"
      if [ -f "$rewrite_target" ]; then
        ${rewriteCommands}
      fi
    '';

  renderFixtureAsset =
    {
      target,
      source,
      recursive ? false,
      executable ? false,
      rewrites ? [ ],
    }:
    let
      sourcePath = toString source;
      rewriteCommands = lib.concatMapStrings (
        rewrite:
        ''
          sed -i ${lib.escapeShellArg "s|${rewrite.from}|${rewrite.to}|g"} "$rewrite_file"
        ''
      ) rewrites;
    in
    ''
      fixture_target="$HOME/${target}"
      mkdir -p "$(dirname "$fixture_target")"
      ${
        if recursive then
          ''
            mkdir -p "$fixture_target"
            cp -R ${lib.escapeShellArg sourcePath}/. "$fixture_target"
          ''
        else
          ''
            cp ${lib.escapeShellArg sourcePath} "$fixture_target"
          ''
      }
      ${
        if rewrites == [ ] then
          ""
        else if recursive then
          ''
            while IFS= read -r rewrite_file; do
              ${rewriteCommands}
            done < <(find "$fixture_target" -type f)
          ''
        else
          ''
            rewrite_file="$fixture_target"
            ${rewriteCommands}
          ''
      }
      ${lib.optionalString executable ''
        chmod +x "$fixture_target"
        patchShebangs "$fixture_target" >/dev/null
      ''}
    '';

  # Build a shell-based runtime validation check.
  mkRuntimeCheck =
    system:
    {
      name,
      nativeBuildInputs ? [ ],
      script,
      extraAttrs ? { },
    }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
    in
    pkgs.runCommand "sinnix-${name}"
      (
        {
          inherit nativeBuildInputs;
        }
        // extraAttrs
      )
      ''
        export HOME="$TMPDIR/home"
        mkdir -p "$HOME"

        ${script}

        touch "$out"
      '';

  mkHmRuntimeCheck =
    system:
    {
      name,
      spec,
      nativeBuildInputs ? [ ],
      homeFiles ? [ ],
      xdgConfigFiles ? [ ],
      xdgDataFiles ? [ ],
      fixtureAssets ? [ ],
      rewriteFiles ? [ ],
      sessionVariables ? [ ],
      includeHomePath ? true,
      useHmZshrc ? false,
      zshrcPreamble ? "",
      zshrcAppend ? "",
      setup ? "",
      script,
      extraAttrs ? { },
    }:
    let
      evaluated = evalTestSpec system spec;
      config = evaluated.config;
      userName = config.sinnix.user.name;
      hm = config.home-manager.users.${userName};
      homeDir = hm.home.homeDirectory;
      homePathPrelude =
        if !includeHomePath then
          ""
        else
          ''
            export PATH="${hm.home.path}/bin:$PATH"
          '';
      renderHomeFiles = lib.concatMapStrings (
        path:
        renderManagedEntry {
          target = path;
          entry = builtins.getAttr path hm.home.file;
          rootExpr = ''"$HOME"'';
          rewriteHomeDir = homeDir;
        }
      ) homeFiles;
      renderXdgConfigFiles = lib.concatMapStrings (
        path:
        renderManagedEntry {
          target = path;
          entry = builtins.getAttr path hm.xdg.configFile;
          rootExpr = ''"$XDG_CONFIG_HOME"'';
          rewriteHomeDir = homeDir;
        }
      ) xdgConfigFiles;
      renderXdgDataFiles = lib.concatMapStrings (
        path:
        renderManagedEntry {
          target = path;
          entry = builtins.getAttr path hm.xdg.dataFile;
          rootExpr = ''"$XDG_DATA_HOME"'';
          rewriteHomeDir = homeDir;
        }
      ) xdgDataFiles;
      renderFixtureAssets = lib.concatMapStrings renderFixtureAsset fixtureAssets;
      renderRewriteFiles = lib.concatMapStrings rewritePathScript rewriteFiles;
      exportSessionVariables = lib.concatMapStrings (
        name:
        exportSessionVariableScript {
          inherit name;
          value = builtins.getAttr name hm.home.sessionVariables;
          rewriteHomeDir = homeDir;
        }
      ) sessionVariables;
      hmZshrc =
        if !useHmZshrc then
          ""
        else
          let
            zshText = builtins.replaceStrings [ homeDir ] [ "__SINNIX_TEST_HOME__" ] (
              zshrcPreamble + (hm.programs.zsh.initContent or "") + zshrcAppend
            );
          in
          ''
                        cat > "$HOME/.zshrc" <<'EOF_SINNIX_TEST'
            ${zshText}
            EOF_SINNIX_TEST
                        sed -i "s|__SINNIX_TEST_HOME__|$HOME|g" "$HOME/.zshrc"
          '';
    in
    mkRuntimeCheck system {
      inherit name extraAttrs;
      nativeBuildInputs = nativeBuildInputs ++ [ inputs.nixpkgs.legacyPackages.${system}.gnused ];
      script = ''
        export XDG_CONFIG_HOME="$HOME/.config"
        export XDG_DATA_HOME="$HOME/.local/share"
        mkdir -p "$XDG_CONFIG_HOME"
        mkdir -p "$XDG_DATA_HOME"

        ${homePathPrelude}
        ${exportSessionVariables}
        ${renderHomeFiles}
        ${renderXdgConfigFiles}
        ${renderXdgDataFiles}
        ${renderFixtureAssets}
        ${hmZshrc}
        ${renderRewriteFiles}
        ${setup}
        ${script}
      '';
    };

  mkVmCheck =
    system:
    {
      name,
      testScript,
      nodes ? {
        machine = { };
      },
      defaultModules ? [ ],
      nodeSpecialArgs ? { },
      extraAttrs ? { },
    }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      sharedNodeSpecialArgs =
        sharedSpecialArgs
        // {
          lib = extendedLib;
        }
        // nodeSpecialArgs;
      baseNodeModules =
        baseModules
        ++ [
          mountTmpfsRoots
          baseTestConfig
          vmTestConfig
        ]
        ++ defaultModules;
      normalizeNode =
        nodeName: nodeModule:
        { ... }:
        {
          imports = baseNodeModules ++ [ nodeModule ];
        };
    in
    pkgs.testers.runNixOSTest (
      {
        inherit name testScript;
        node.pkgsReadOnly = false;
        node.specialArgs = sharedNodeSpecialArgs;
        nodes = lib.mapAttrs normalizeNode nodes;
      }
      // extraAttrs
    );

  validateCoverageManifest =
    {
      coverage,
      discovered ? autoDiscoveredCoverageSurfaces,
      evidence ? { },
      availableChecks ? [ ],
      availableCommands ? [ ],
    }:
    let
      ensure = condition: message: if condition then true else throw message;
      allowedLayers =
        coverage.allowedLayers or [
          "build"
          "eval"
          "runtime"
          "pty"
          "vm"
          "host"
        ];
      allowedLayerSet = lib.listToAttrs (
        map (layer: {
          name = layer;
          value = true;
        }) allowedLayers
      );
      availableEvidenceSet = lib.listToAttrs (
        map (name: {
          inherit name;
          value = true;
        }) (availableChecks ++ availableCommands)
      );
      categories = [
        "features"
        "services"
        "bundles"
        "hosts"
        "outputs"
      ];
      autoEvalCategories = [
        "features"
        "services"
        "bundles"
      ];
      attrNamesFor = set: category: builtins.attrNames (set.${category} or { });
      listFor = set: category: set.${category} or [ ];
      missingSubjects =
        category:
        builtins.filter (name: !(builtins.hasAttr name (coverage.${category} or { }))) (
          listFor discovered category
        );
      extraSubjects =
        category:
        builtins.filter (name: !(builtins.elem name (listFor discovered category))) (
          attrNamesFor coverage category
        );
      validateEntry =
        category: name: entry:
        ensure (builtins.isAttrs entry) "Coverage ${category}.${name} must be an attribute set"
        && ensure (entry ? layers) "Coverage ${category}.${name} must declare layers"
        && ensure (builtins.isList entry.layers) "Coverage ${category}.${name}.layers must be a list"
        && ensure (entry.layers != [ ]) "Coverage ${category}.${name}.layers must not be empty"
        && ensure (builtins.all (
          layer: builtins.hasAttr layer allowedLayerSet
        ) entry.layers) "Coverage ${category}.${name}.layers contains an unknown layer"
        && true;
      validateCategory =
        category:
        let
          items = coverage.${category} or { };
        in
        ensure (missingSubjects category == [ ])
          "Coverage ${category} is missing public surfaces: ${builtins.concatStringsSep ", " (missingSubjects category)}"
        &&
          ensure (extraSubjects category == [ ])
            "Coverage ${category} contains unknown surfaces: ${builtins.concatStringsSep ", " (extraSubjects category)}"
        && builtins.all (name: validateEntry category name items.${name}) (builtins.attrNames items);
      validateEvidenceEntry =
        category: subject: layer: names:
        ensure (builtins.hasAttr subject (
          coverage.${category} or { }
        )) "Coverage evidence references unknown ${category}.${subject}"
        && ensure (builtins.elem layer (
          coverage.${category}.${subject}.layers or [ ]
        )) "Coverage evidence references undeclared layer ${layer} for ${category}.${subject}"
        && ensure (
          builtins.isList names && names != [ ]
        ) "Coverage evidence for ${category}.${subject}.${layer} must be a non-empty list"
        && ensure (builtins.all (name: builtins.hasAttr name availableEvidenceSet)
          names
        ) "Coverage evidence for ${category}.${subject}.${layer} references unavailable checks or commands"
        && true;
      validateEvidenceCategory =
        category:
        let
          items = evidence.${category} or { };
        in
        builtins.all (
          subject:
          let
            subjectEvidence = items.${subject};
          in
          ensure (builtins.isAttrs subjectEvidence) "Coverage evidence for ${category}.${subject} must be an attribute set"
          && builtins.all (layer: validateEvidenceEntry category subject layer subjectEvidence.${layer}) (
            builtins.attrNames subjectEvidence
          )
        ) (builtins.attrNames items);
      layerNeedsEvidence =
        category: layer: !(layer == "eval" && builtins.elem category autoEvalCategories);
      validateRequiredEvidence =
        category:
        let
          items = coverage.${category} or { };
          categoryEvidence = evidence.${category} or { };
        in
        builtins.all (
          subject:
          builtins.all (
            layer:
            if layerNeedsEvidence category layer then
              ensure (
                lib.attrByPath [ subject layer ] null categoryEvidence != null
              ) "Coverage ${category}.${subject}.${layer} has no concrete evidence binding"
            else
              true
          ) items.${subject}.layers
        ) (builtins.attrNames items);
    in
    builtins.all validateCategory categories
    && builtins.all validateEvidenceCategory categories
    && builtins.all validateRequiredEvidence categories;

  mkCoverageManifestCheck =
    system:
    {
      name,
      coverage,
      discovered ? autoDiscoveredCoverageSurfaces,
      evidence ? { },
      availableChecks ? [ ],
      availableCommands ? [ ],
    }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      validatedJson =
        assert validateCoverageManifest {
          inherit
            coverage
            discovered
            evidence
            availableChecks
            availableCommands
            ;
        };
        builtins.toFile "${name}.json" (
          builtins.toJSON {
            inherit
              coverage
              discovered
              evidence
              availableChecks
              availableCommands
              ;
          }
        );
    in
    pkgs.runCommand "sinnix-${name}" { } ''
      cp ${validatedJson} "$out"
    '';

  mkHostBuildCheck =
    system:
    {
      name,
      modules,
    }:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      evaluated = extendedLib.nixosSystem {
        inherit system;
        modules = baseModules ++ modules;
        specialArgs = sharedSpecialArgs // {
          lib = extendedLib;
        };
      };
    in
    pkgs.runCommand "nixos-${name}-build-check"
      {
        systemDrv = evaluated.config.system.build.toplevel;
      }
      ''
        touch "$out"
      '';

  # Build an evaluation-only test check derivation from a spec.
  # This forces the NixOS module graph and assertion list without building the
  # full system toplevel. Build coverage lives in dedicated host/output checks.
  mkTestForSystem =
    system: spec:
    let
      pkgs = inputs.nixpkgs.legacyPackages.${system};
      evaluated = evalTestSpec system spec;
      assertionReport = builtins.toFile "${spec.name}-assertions.json" (
        builtins.toJSON {
          toplevelDrvPath = builtins.unsafeDiscardStringContext evaluated.config.system.build.toplevel.drvPath;
        }
      );
    in
    pkgs.runCommand "nixos-${spec.name}-config-check" { } ''
      cp ${assertionReport} "$out"
    '';

  # Generate checks for all systems from a list of test specs
  mkSystemChecks =
    system: testSpecs:
    lib.listToAttrs (
      map (spec: {
        name = "nixos-${spec.name}";
        value = mkTestForSystem system spec;
      }) testSpecs
    );

in
{
  inherit sanitizedInputs baseModules sharedSpecialArgs;
  inherit mountTmpfsRoots baseTestConfig vmTestConfig;
  inherit expect;
  inherit mkFeatureTest mkServiceTest mkBundleTest;
  inherit
    evalTestSpec
    mkRuntimeCheck
    mkHmRuntimeCheck
    mkVmCheck
    mkCoverageManifestCheck
    mkHostBuildCheck
    ;
  inherit autoDiscoveredCoverageSurfaces;
  inherit mkTestForSystem mkSystemChecks;
}
