# Hyprland semantic Lua rules DSL.
#
# Hyprland 0.56 consumes rule tables through hl.window_rule and hl.layer_rule.
# Keep the DSL independent of the renderer so rules remain inspectable Nix
# values and Home Manager can emit valid Lua tables.
{ lib }:
let
  formatSize = size: [
    (if size.w < 1 then "(monitor_w*${toString size.w})" else toString size.w)
    (if size.h < 1 then "(monitor_h*${toString size.h})" else toString size.h)
  ];
  formatPos = pos: [
    (if builtins.isString pos.x then pos.x else toString pos.x)
    (if builtins.isString pos.y then pos.y else toString pos.y)
  ];
  mkMatch =
    rule:
    (lib.optionalAttrs (rule ? class) { class = rule.class; })
    // (lib.optionalAttrs (rule ? title) { title = rule.title; })
    // (lib.optionalAttrs (rule ? initialTitle) { initial_title = rule.initialTitle; })
    // (lib.optionalAttrs (rule ? floating) { float = rule.floating; });
  formatOpacity =
    opacity:
    if builtins.isAttrs opacity then
      "${toString opacity.active} override ${toString opacity.inactive} override"
    else
      opacity;
  mkEffects =
    rule:
    (lib.optionalAttrs (rule.float or false) { float = true; })
    // (lib.optionalAttrs (rule.center or false) { center = true; })
    // (lib.optionalAttrs (rule.pin or false) { pin = true; })
    // (lib.optionalAttrs (rule.tile or false) { tile = true; })
    // (lib.optionalAttrs (rule.fullscreen or false) { fullscreen = true; })
    // (lib.optionalAttrs (rule.immediate or false) { immediate = true; })
    // (lib.optionalAttrs (rule.noBlur or false) { no_blur = true; })
    // (lib.optionalAttrs (rule ? size) { size = formatSize rule.size; })
    // (lib.optionalAttrs (rule ? move) { move = formatPos rule.move; })
    // (lib.optionalAttrs (rule ? workspace) { workspace = rule.workspace; })
    // (lib.optionalAttrs (rule ? opacity) { opacity = formatOpacity rule.opacity; })
    // (lib.optionalAttrs (rule ? group) { group = rule.group; })
    // (lib.optionalAttrs (rule ? idleInhibit) { idle_inhibit = rule.idleInhibit; })
    // (lib.optionalAttrs (rule.noInitialFocus or false) { no_initial_focus = true; })
    // (lib.optionalAttrs (rule ? focusOnActivate) { focus_on_activate = rule.focusOnActivate; })
    // (lib.optionalAttrs (rule ? suppressEvent) { suppress_event = rule.suppressEvent; });
  mkRule =
    name: rule:
    {
      inherit name;
      match = mkMatch rule;
    }
    // mkEffects rule;
  mkLayerRule =
    name: rule:
    {
      inherit name;
      match = lib.optionalAttrs (rule ? namespace) { namespace = rule.namespace; };
    }
    // (lib.optionalAttrs (rule.blur or false) { blur = true; })
    // (lib.optionalAttrs (rule ? ignoreAlpha) { ignore_alpha = rule.ignoreAlpha; })
    // (lib.optionalAttrs (rule.noAnim or false) { no_anim = true; })
    // (lib.optionalAttrs (rule.xray or false) { xray = true; })
    // (lib.optionalAttrs (rule.dimAround or false) { dim_around = true; });
  mkScratchpad =
    name:
    {
      class,
      size,
      workspace ? "special:scratch_${name}",
      silent ? true,
    }:
    mkRule "scratchpad-${name}" {
      inherit class size;
      float = true;
      center = true;
      workspace = "${workspace}${if silent then " silent" else ""}";
    };
  mkDialog =
    name:
    {
      title ? null,
      class ? null,
    }:
    mkRule "dialog-${name}" (
      {
        float = true;
      }
      // (lib.optionalAttrs (title != null) { inherit title; })
      // (lib.optionalAttrs (class != null) { inherit class; })
    );
  mkIdleInhibit =
    index:
    {
      mode,
      class ? null,
      title ? null,
    }:
    mkRule "idle-${mode}-${toString index}" (
      {
        idleInhibit = mode;
      }
      // (lib.optionalAttrs (class != null) { inherit class; })
      // (lib.optionalAttrs (title != null) { inherit title; })
    );
in
{
  inherit
    mkRule
    mkScratchpad
    mkDialog
    mkIdleInhibit
    mkLayerRule
    ;
}
