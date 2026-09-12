# Materialize optional private XDG links from the encrypted runtime catalog.
# The public module owns validation and mechanics; names and targets stay in
# the deployed catalog beside private project identities.
{
  mkServiceModule,
  lib,
  pkgs,
  ...
}@args:
mkServiceModule {
  name = "private-state-links";
  description = "private state links from the encrypted runtime catalog";
  defaultOnDesktop = true;
  surface = {
    unit = "sinnix-private-state-links.service";
    resourceClass = "ordinary";
  };
  configFn =
    { config, ... }:
    let
      user = config.sinnix.user.name;
      catalog = config.sinnix.projects.privateCatalogFile;
      render = pkgs.writeShellApplication {
        name = "sinnix-private-state-links";
        runtimeInputs = [
          pkgs.coreutils
          pkgs.jq
        ];
        text = ''
          set -eu
          catalog=${lib.escapeShellArg catalog}
          [ -r "$catalog" ] || exit 0
          jq -e '(.links // {}) | type == "object"' "$catalog" >/dev/null
          jq -r '(.links // {}) | to_entries[] | [.key, .value] | @tsv' "$catalog" |
            while IFS=$'\t' read -r link target; do
              case "$link" in
                /home/${user}/.local/share/*) ;;
                *) echo "private state link outside the user data directory: $link" >&2; exit 1 ;;
              esac
              case "$target" in
                /realm/state/*) ;;
                *) echo "private state target outside /realm/state: $target" >&2; exit 1 ;;
              esac
              mkdir -p "$(dirname "$link")" "$target"
              chown ${user}:users "$target"
              ln -sfnT "$target" "$link"
              chown -h ${user}:users "$link"
            done
        '';
      };
    in
    {
      systemd.services.sinnix-private-state-links = {
        wantedBy = [ "multi-user.target" ];
        after = [ "realm.mount" ];
        unitConfig.ConditionPathExists = catalog;
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          ExecStart = "${render}/bin/sinnix-private-state-links";
        };
      };
    };
} args
