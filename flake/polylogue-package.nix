{
  inputs,
  pkgs,
  package,
}:

package.overrideAttrs (old: {
  # Polylogue's runtime contract requires nh3 for every free-threaded
  # consumer, including the generated agent hook.
  propagatedBuildInputs = (old.propagatedBuildInputs or [ ]) ++ [
    pkgs.python314FreeThreading.pkgs.nh3
  ];
})
