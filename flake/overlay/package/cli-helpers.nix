# cli-helpers 2.10.0 ships tests that hardcode pre-upgrade Pygments ANSI
# escape sequences (48;5;7 vs 48;5;255). The library itself works; only
# the assertions are stale. Skip them so pgcli (a downstream consumer)
# can build until upstream refreshes the fixtures.
_: _final: prev: {
  pythonPackagesExtensions = (prev.pythonPackagesExtensions or [ ]) ++ [
    (pyFinal: pyPrev: {
      cli-helpers = pyPrev.cli-helpers.overrideAttrs (old: {
        disabledTests = (old.disabledTests or [ ]) ++ [
          "test_style_output"
          "test_style_output_with_newlines"
          "test_style_output_custom_tokens"
        ];
      });
    })
  ];
}
