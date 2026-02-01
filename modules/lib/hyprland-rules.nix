# Hyprland Window Rules DSL
#
# Provides declarative helpers for window rules that transform to
# Hyprland's windowrule {} block syntax (0.53+).
#
# Usage:
#   mkRule "dialog-open-file" { title = "^(Open File)$"; float = true; }
#   mkScratchpad "terminal" { class = "scratchpad-terminal"; size = { w = 0.75; h = 0.55; }; }
{ lib }:
let
  # Convert size spec to Hyprland format
  # { w = 0.75; h = 0.55; } -> "(monitor_w*0.75) (monitor_h*0.55)"
  # { w = 480; h = 270; } -> "480 270"
  formatSize = size:
    let
      w = if size.w < 1 then "(monitor_w*${toString size.w})" else toString size.w;
      h = if size.h < 1 then "(monitor_h*${toString size.h})" else toString size.h;
    in "${w} ${h}";

  # Convert position spec to Hyprland format
  formatPos = pos:
    let
      x = if builtins.isString pos.x then pos.x else toString pos.x;
      y = if builtins.isString pos.y then pos.y else toString pos.y;
    in "${x} ${y}";

  # Build match conditions
  mkMatch = rule:
    (lib.optional (rule ? class) "match:class = ${rule.class}")
    ++ (lib.optional (rule ? title) "match:title = ${rule.title}")
    ++ (lib.optional (rule ? floating) "match:float = ${if rule.floating then "true" else "false"}");

  # Build effect conditions
  mkEffects = rule:
    (lib.optional (rule.float or false) "float = yes")
    ++ (lib.optional (rule.center or false) "center = yes")
    ++ (lib.optional (rule.pin or false) "pin = yes")
    ++ (lib.optional (rule.tile or false) "tile = yes")
    ++ (lib.optional (rule.fullscreen or false) "fullscreen = yes")
    ++ (lib.optional (rule.immediate or false) "immediate = yes")
    ++ (lib.optional (rule ? size) "size = ${formatSize rule.size}")
    ++ (lib.optional (rule ? move) "move = ${formatPos rule.move}")
    ++ (lib.optional (rule ? workspace) "workspace = ${rule.workspace}")
    ++ (lib.optional (rule ? opacity) "opacity = ${toString rule.opacity} ${toString rule.opacity}")
    ++ (lib.optional (rule ? group) "group = ${rule.group}")
    ++ (lib.optional (rule ? idleInhibit) "idle_inhibit = ${rule.idleInhibit}");

  # Create a rule block
  # mkRule "name" { class = "^(foo)$"; float = true; size = { w = 0.5; h = 0.5; }; }
  mkRule = name: rule: {
    inherit name;
    props = mkMatch rule;
    effects = mkEffects rule;
  };

  # Create a scratchpad rule with common defaults
  # mkScratchpad "terminal" { class = "scratchpad-terminal"; size = { w = 0.75; h = 0.55; }; }
  mkScratchpad = name: { class, size, workspace ? "special:scratch_${name}", silent ? true }:
    mkRule "scratchpad-${name}" {
      inherit class size;
      float = true;
      center = true;
      workspace = "${workspace}${if silent then " silent" else ""}";
    };

  # Create a browser scratchpad (common pattern)
  mkBrowserScratchpad = name:
    mkScratchpad "browser-${name}" {
      class = "^(browser-${name})$";
      workspace = "special:browser_${name}";
      size = { w = 0.80; h = 0.85; };
    };

  # Create a dialog rule (float by title or class)
  mkDialog = name: { title ? null, class ? null }:
    mkRule "dialog-${name}" ({
      float = true;
    } // (lib.optionalAttrs (title != null) { inherit title; })
      // (lib.optionalAttrs (class != null) { inherit class; }));

  # Create idle inhibit rule
  mkIdleInhibit = index: { mode, class ? null, title ? null }:
    mkRule "idle-${mode}-${toString index}" ({
      idleInhibit = mode;
    } // (lib.optionalAttrs (class != null) { inherit class; })
      // (lib.optionalAttrs (title != null) { inherit title; }));

  # Render a rule block to Hyprland config string
  renderBlock = { name, props, effects }:
    ''
      windowrule {
        name = ${name}
    ${lib.concatMapStringsSep "\n" (p: "    ${p}") props}
    ${lib.concatMapStringsSep "\n" (e: "    ${e}") effects}
      }
    '';

in {
  inherit mkRule mkScratchpad mkBrowserScratchpad mkDialog mkIdleInhibit renderBlock formatSize formatPos;

  # Render multiple rules to config string
  renderRules = rules: lib.concatMapStringsSep "\n\n" renderBlock rules;
}
