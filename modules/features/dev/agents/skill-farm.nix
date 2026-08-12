# Shared/Codex agent skill farms — the single builder for every client's
# skill tree (claude, codex, gemini, hermes). Plain helper (not a NixOS
# module) — imported by clis.nix and client-profiles.nix, not auto-imported.
#
# Out-of-store by construction: the farm is a store directory, but every
# entry symlinks into the live dots checkout rather than a copied source.
# Editing a skill's SKILL.md/template therefore takes effect immediately
# for every client, matching every other dots file. Only ADDING or
# REMOVING a skill name still needs a rebuild.
{
  lib,
  pkgs,
  dotsRoot,
}:
let
  sharedSkillNames = import ../../../../flake/data/shared-agent-skills.nix;
  mkSkillFarm =
    farmName: entries:
    pkgs.runCommand farmName { } ''
      mkdir -p "$out"
      ${lib.concatMapStringsSep "\n" (e: ''
        ln -s ${lib.escapeShellArg e.path} "$out/${e.name}"
      '') entries}
    '';
  sharedSkillLinks = map (name: {
    inherit name;
    path = "${dotsRoot}/_ai/skills/${name}";
  }) sharedSkillNames;
in
{
  sharedSkillFarm = mkSkillFarm "sinnix-shared-agent-skills" sharedSkillLinks;
  codexSkillFarm = mkSkillFarm "sinnix-codex-agent-skills" (
    sharedSkillLinks
    ++ [
      {
        name = ".system";
        path = "${dotsRoot}/codex/skills/.system";
      }
    ]
  );
}
