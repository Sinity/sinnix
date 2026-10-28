{ inputs, ... }:
{
  perSystem =
    { pkgs, lib, ... }:
    let
      host = inputs.self.nixosConfigurations.sinnix-prime.config;
      service = host.systemd.services.realm-scratch-subvolumes;
      unit =
        pkgs.writeText "realm-scratch-subvolumes.service"
          host.systemd.units."realm-scratch-subvolumes.service".text;
      vm = pkgs.vmTools.override {
        rootModules = [
          "virtio_pci"
          "virtio_mmio"
          "virtio_blk"
          "virtio_balloon"
          "virtio_rng"
          "ext4"
          "virtiofs"
          "crc32c"
          "btrfs"
          "loop"
        ];
      };
    in
    {
      checks.realm-scratch-subvolumes =
        # Successful upstream assertions may have messages that only evaluate
        # on failure (for example, the filesystem cycle description).
        assert
          !lib.any (
            entry:
            !entry.assertion
            && entry.message == "Realm scratch subvolumes must name exact Borg-excluded regenerable roots."
          ) host.assertions;
        assert service.unitConfig.DefaultDependencies == false;
        assert service.unitConfig.RefuseManualStart;
        assert service.restartIfChanged == false;
        assert lib.all (path: lib.any (rule: lib.hasPrefix "v ${path} " rule) host.systemd.tmpfiles.rules) [
          "/realm/tmp"
          "/realm/worktree"
          "/realm/state/cache"
        ];
        assert service.wantedBy == [ "local-fs.target" ];
        assert service.requires == [ "realm.mount" ];
        assert service.after == [ "realm.mount" ];
        assert lib.all (name: builtins.elem name service.before) [
          "local-fs.target"
          "systemd-tmpfiles-setup.service"
          "realm-scaffold.service"
          "user@1000.service"
          "var-cache-sinex.mount"
          "realm-tmp-polylogue\\x2dpytest.mount"
        ];
        assert lib.hasInfix "--boot-only" service.serviceConfig.ExecStart;
        vm.runInLinuxVM (
          pkgs.runCommand "realm-scratch-subvolumes-check"
            {
              nativeBuildInputs = [
                pkgs.python3
                pkgs.btrfs-progs
                pkgs.coreutils
                pkgs.diffutils
                pkgs.util-linux
                pkgs.e2fsprogs
              ];
              memSize = 768;
            }
            ''
              python3 ${./scratch-subvolumes.py} ${../../modules/lib/storage/scratch-subvolumes.py}
              mkdir -p "$out"
              cp ${unit} "$out/realm-scratch-subvolumes.service"
            ''
        );
    };
}
