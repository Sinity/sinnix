# Capability index — /etc/sinnix/capability-index.json
#
# The discoverability half of introspection.nix's config dump: not what the
# machine is configured to be, but what it can DO and how to invoke it, merged
# from the declarations that already carry that information. The builder and
# its source map live in modules/lib/capability-index.nix.
#
# Consumers: the hub's /capabilities/ page and `sinnix cheatsheet`, both through
# `sinnix-ops-reducer capabilities`, which joins these rows with live unit state
# and the usage census. Nothing polls it and nothing regenerates it — it is a
# build product, current by definition for the running generation.
{
  lib,
  config,
  options,
  pkgs,
  inputs,
  helpers,
  ...
}:
let
  builder = import ./lib/capability-index.nix { inherit lib; };

  # The script registry, for names, descriptions and tiers. This is the same
  # `import ./scripts.nix { ... }` that ~30 modules already make through
  # helpers.mkSinnixPackagesFor; that helper returns only the package set, and
  # the frontmatter descriptions are the whole point here.
  scriptRegistry = (import (inputs.self + "/flake/scripts.nix") { inherit inputs pkgs; }).registry;

  # The devshell verbs. commandDocs is a pure list in that file, so nothing of
  # the command machinery it also defines is forced by reading it.
  commandDocs =
    (import (inputs.self + "/flake/command-registry.nix") {
      inherit inputs pkgs;
      inherit (pkgs.stdenv.hostPlatform) system;
    }).commandDocs;

  index = builder.mkCapabilityIndex {
    inherit config options;
    sourceRoot = toString inputs.self;
    inherit scriptRegistry commandDocs;
    inherit (helpers.data) mcpRegistry agentLanes;
    skillsRoot = "${inputs.self}/dots/_ai/skills";
    sharedSkills = import (inputs.self + "/flake/data/shared-agent-skills.nix");
  };
in
{
  environment.etc."sinnix/capability-index.json" = {
    text = builtins.toJSON index;
    mode = "0444";
  };
}
