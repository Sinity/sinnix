# modules/home/hydrus.nix
{ config, pkgs, lib, ... }: 
let 
 hydrus-wrapped = pkgs.hydrus.overrideAttrs (oldAttrs: {
   postInstall = ''
     ${oldAttrs.postInstall or ""}
     # Link the db directory in site-packages to our desired location
     rm -rf $out/lib/python3.12/site-packages/db
     ln -s /mnt/ssd_storage/hydrus/db $out/lib/python3.12/site-packages/db
   '';
 });
in {
 home.packages = [
   hydrus-wrapped
 ];
}
