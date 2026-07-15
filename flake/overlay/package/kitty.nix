# Kitty 0.47.4 predates three upstream fixes merged on 2026-07-12:
#
# - bounded TextCache retention for unique multi-codepoint cell text;
# - clean Wayland window failure when EGL context creation fails;
# - mmap-backed scrollback segments that return memory directly to the OS.
#
# Keep this package-wide rather than wrapping Home Manager's kitty executable:
# scratchpads and other launchers reference pkgs.kitty directly and must receive
# the same fixes.
#
# recheck: when nixpkgs bumps kitty past 0.47.4 — drop every patch already
# included in the new release, then re-run the live memory-slope A/B.
_: _final: prev: {
  kitty = prev.kitty.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      (prev.fetchurl {
        url = "https://github.com/kovidgoyal/kitty/commit/7ab90de16651fef89b1ecea6924d40638edd6fc7.patch";
        hash = "sha256-mD1uhiw8FtoCBirKzWhW31J9UsHSB6O7RPWjJ6L0oo8=";
      })
      (prev.fetchurl {
        url = "https://github.com/kovidgoyal/kitty/commit/95ded6817b11330ad05a7bd16dbd96bb9526dfd6.patch";
        hash = "sha256-ZE0rVtu+VOentFfjyZZgTULZqFqyOnyrumhMNFFI8vU=";
      })
      (prev.fetchurl {
        url = "https://github.com/kovidgoyal/kitty/commit/e71c49a17e157a23c80fc3cf313321d15e901afe.patch";
        hash = "sha256-rlLYDf7HA2HlyOXT8ZCJcNASeVajcL1dBlkGGuv8gAg=";
      })
    ];
    passthru = (old.passthru or { }) // {
      sinnixUpstreamFixes = [
        "7ab90de16651fef89b1ecea6924d40638edd6fc7"
        "95ded6817b11330ad05a7bd16dbd96bb9526dfd6"
        "e71c49a17e157a23c80fc3cf313321d15e901afe"
      ];
    };
  });
}
