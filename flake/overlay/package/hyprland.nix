_:
_final: prev:
let
  hyprlandPatches = builtins.path {
    path = ../patch/hyprland;
    name = "sinnix-hyprland-patches";
  };
  hyprlandPatch = name: hyprlandPatches + "/${name}";
in
{
  hyprland = prev.hyprland.overrideAttrs (old: {
    patches = (old.patches or [ ]) ++ [
      (hyprlandPatch "suppress-color-warning.patch")
      (hyprlandPatch "check-monitor-null.patch")
      (hyprlandPatch "special-workspace-damage.patch")
      (hyprlandPatch "guard-last-monitor.patch")
    ];
    postPatch = (old.postPatch or "") + ''
          substituteInPlace src/Compositor.cpp \
            --replace '        if (pw->m_isMapped)
          g_pHyprRenderer->damageMonitor(pw->m_monitor.lock());

      };' '        if (pw->m_isMapped) {
              if (m_monitors.empty()) {
                  Debug::log(WARN, "[sinnix] skip z-order damage: no active monitors");
              } else if (const auto PMONITOR = pw->m_monitor.lock()) {
                  g_pHyprRenderer->damageMonitor(PMONITOR);
              } else {
                  Debug::log(WARN, "[sinnix] skip z-order damage: window monitor vanished");
              }
          }

      };'
    '';
  });
}
