/*
  Launch policy, rendered at evaluation time.

  `flake/data/runtime-defaults.nix` is the single source of truth for what a
  command class means: which slice it lands in, its nice/ionice placement, the
  systemd properties its transient scope carries, and the environment defaults
  it seeds. That table is evaluation-known, so the launcher has no business
  discovering it at runtime — the previous `scripts/sinnix-scope` reimplemented
  the table as a jq interpreter over /etc/sinnix/runtime-inventory.json, with a
  hand-maintained fallback ladder for the case where the inventory was missing
  or unparseable.

  This module renders those classes straight into the launcher instead: one
  `apply_class_policy` shell function whose branches are generated from
  `commandClasses`, prepended to the genuinely-runtime half in
  `flake/launch/scope-runtime.bash`. Consequences worth keeping in mind:

  - An unknown class is a usage error listing the classes that actually exist,
    not a silent fall-through to a guessed `<class>.slice`.
  - A misspelled class name in the table is an evaluation error (property key
    validation below), not a property systemd rejects at launch.
  - jq is no longer on the launch path at all.

  The inventory still carries `commandClasses` for observability (sinnix-observe
  and the hub's /work/ page read it to name and explain a scope); nothing reads
  it to *place* a process any more.
*/
{
  lib,
  pkgs,
  runtimeDefaults,
}:
let
  inherit (runtimeDefaults) commandClasses;

  classNames = lib.attrNames commandClasses;

  # systemd property values arrive as Nix bools/ints/strings and must reach
  # systemd-run in the same spelling the old jq path produced from the
  # serialized inventory (`true`, `300`, `8G`).
  renderValue =
    class: name: value:
    if lib.isBool value then
      lib.boolToString value
    else if lib.isInt value then
      toString value
    else if lib.isString value then
      value
    else
      throw "flake/launch.nix: commandClasses.${class}.systemdProperties.${name} has unsupported type ${builtins.typeOf value}";

  checkPropertyName =
    class: name:
    if builtins.match "[A-Za-z][A-Za-z0-9_]*" name != null then
      name
    else
      throw "flake/launch.nix: commandClasses.${class}.systemdProperties has a non-systemd property name: ${name}";

  # One `--property=Name=Value` per entry, list values repeated per element —
  # the shape systemd-run accepts for the properties it allows more than once.
  propertyArgs =
    class: properties:
    lib.concatLists (
      lib.mapAttrsToList (
        name: value:
        let
          checked = checkPropertyName class name;
        in
        map (v: "--property=${checked}=${renderValue class checked v}") (
          if lib.isList value then value else [ value ]
        )
      ) properties
    );

  envDefaultEntries =
    class: envDefaults:
    lib.mapAttrsToList (
      name: value:
      if builtins.match "[A-Za-z_][A-Za-z0-9_]*" name == null then
        throw "flake/launch.nix: commandClasses.${class}.envDefaults has an unusable variable name: ${name}"
      else
        "${name}=${toString value}"
    ) envDefaults;

  shellList = items: lib.concatStringsSep " " (map lib.escapeShellArg items);

  classBranch =
    name: class:
    let
      properties = class.systemdProperties or { };
      envDefaults = class.envDefaults or { };
    in
    lib.concatStringsSep "\n" [
      "    ${lib.escapeShellArg name})"
      "      slice=${lib.escapeShellArg class.slice}"
      "      nice_level=${
        lib.escapeShellArg (if (class.nice or null) == null then "" else toString class.nice)
      }"
      "      ionice_class=${
        lib.escapeShellArg (if (class.ioniceClass or null) == null then "" else class.ioniceClass)
      }"
      "      ionice_priority=${
        lib.escapeShellArg (
          if (class.ionicePriority or null) == null then "" else toString class.ionicePriority
        )
      }"
      "      class_property_args=(${shellList (propertyArgs name properties)})"
      "      class_env_defaults=(${shellList (envDefaultEntries name envDefaults)})"
      "      ;;"
    ];

  policyPrelude = ''
    # Generated from flake/data/runtime-defaults.nix `commandClasses` by
    # flake/launch.nix. Do not hand-edit a rendered launcher; edit the table.
    apply_class_policy() {
      case "$1" in
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList classBranch commandClasses)}
        *)
          echo "sinnix-scope: unknown class: $1" >&2
          echo "known classes: ${lib.concatStringsSep ", " classNames}" >&2
          exit 64
          ;;
      esac
    }
  '';

  scopeText = policyPrelude + "\n" + builtins.readFile ./launch/scope-runtime.bash;

  runtimeInputs = with pkgs; [
    bash
    coreutils
    gnugrep
    systemd
    util-linux
  ];

  dispatcher = pkgs.writeShellApplication {
    name = "sinnix-scope";
    inherit runtimeInputs;
    text = scopeText;
    meta.description = "Place commands in Sinnix resource-control scopes";
    # `harness` is the same rendered text with no PATH prelude in front of it.
    # writeShellApplication prepends runtimeInputs to PATH, which is correct
    # for production and fatal for a test that must shadow `systemd-run` with
    # a recorder: the real one would always win. Tests exercise this file;
    # production runs the wrapper around it. There is one text, so a test
    # cannot drift from what ships.
    passthru.harness = pkgs.writeTextFile {
      name = "sinnix-scope-harness";
      executable = true;
      text = ''
        #!${pkgs.bash}/bin/bash
        set -euo pipefail
        ${scopeText}
      '';
    };
  };
in
{
  inherit dispatcher scopeText;
}
