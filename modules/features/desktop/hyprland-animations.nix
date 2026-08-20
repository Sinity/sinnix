# Sole authority for Hyprland Lua animations.
#
# Hyprland 0.56 exposes curves and animation leaves as semantic Lua calls;
# these values are rendered as hl.curve(name, table) and hl.animation(table).
{
  mkFeatureModule,
  ...
}@args:
mkFeatureModule {
  path = [
    "desktop"
    "hyprlandAnimations"
  ];
  description = "Polished Hyprland animations ported from end-4/dots-hyprland";
  configFn =
    { user, ... }:
    {
      home-manager.users.${user} = _: {
        wayland.windowManager.hyprland.settings = {
          curve = [
            {
              _args = [
                "expressiveFastSpatial"
                {
                  type = "bezier";
                  points = [
                    [
                      0.42
                      1.67
                    ]
                    [
                      0.21
                      0.90
                    ]
                  ];
                }
              ];
            }
            {
              _args = [
                "expressiveSlowSpatial"
                {
                  type = "bezier";
                  points = [
                    [
                      0.39
                      1.29
                    ]
                    [
                      0.35
                      0.98
                    ]
                  ];
                }
              ];
            }
            {
              _args = [
                "expressiveDefaultSpatial"
                {
                  type = "bezier";
                  points = [
                    [
                      0.38
                      1.21
                    ]
                    [
                      0.22
                      1.00
                    ]
                  ];
                }
              ];
            }
            {
              _args = [
                "emphasizedDecel"
                {
                  type = "bezier";
                  points = [
                    [
                      0.05
                      0.7
                    ]
                    [
                      0.1
                      1
                    ]
                  ];
                }
              ];
            }
            {
              _args = [
                "emphasizedAccel"
                {
                  type = "bezier";
                  points = [
                    [
                      0.3
                      0
                    ]
                    [
                      0.8
                      0.15
                    ]
                  ];
                }
              ];
            }
            {
              _args = [
                "standardDecel"
                {
                  type = "bezier";
                  points = [
                    [
                      0
                      0
                    ]
                    [
                      0
                      1
                    ]
                  ];
                }
              ];
            }
            {
              _args = [
                "menu_decel"
                {
                  type = "bezier";
                  points = [
                    [
                      0.1
                      1
                    ]
                    [
                      0
                      1
                    ]
                  ];
                }
              ];
            }
            {
              _args = [
                "menu_accel"
                {
                  type = "bezier";
                  points = [
                    [
                      0.52
                      0.03
                    ]
                    [
                      0.72
                      0.08
                    ]
                  ];
                }
              ];
            }
            {
              _args = [
                "stall"
                {
                  type = "bezier";
                  points = [
                    [
                      1
                      (-0.1)
                    ]
                    [
                      0.7
                      0.85
                    ]
                  ];
                }
              ];
            }
            {
              _args = [
                "linear"
                {
                  type = "bezier";
                  points = [
                    [
                      0
                      0
                    ]
                    [
                      1
                      1
                    ]
                  ];
                }
              ];
            }
          ];
          animation = [
            {
              leaf = "global";
              enabled = true;
              speed = 10;
              bezier = "expressiveDefaultSpatial";
            }
            {
              leaf = "windowsIn";
              enabled = true;
              speed = 3;
              bezier = "emphasizedDecel";
              style = "popin 80%";
            }
            {
              leaf = "fadeIn";
              enabled = true;
              speed = 3;
              bezier = "emphasizedDecel";
            }
            {
              leaf = "windowsOut";
              enabled = true;
              speed = 2;
              bezier = "emphasizedDecel";
              style = "popin 90%";
            }
            {
              leaf = "fadeOut";
              enabled = true;
              speed = 2;
              bezier = "emphasizedDecel";
            }
            {
              leaf = "windowsMove";
              enabled = true;
              speed = 3;
              bezier = "emphasizedDecel";
              style = "slide";
            }
            {
              leaf = "border";
              enabled = true;
              speed = 10;
              bezier = "emphasizedDecel";
            }
            {
              leaf = "layersIn";
              enabled = true;
              speed = 2.7;
              bezier = "emphasizedDecel";
              style = "popin 93%";
            }
            {
              leaf = "layersOut";
              enabled = true;
              speed = 2.4;
              bezier = "menu_accel";
              style = "popin 94%";
            }
            {
              leaf = "fadeLayersIn";
              enabled = true;
              speed = 0.5;
              bezier = "menu_decel";
            }
            {
              leaf = "fadeLayersOut";
              enabled = true;
              speed = 2.7;
              bezier = "stall";
            }
            {
              leaf = "workspaces";
              enabled = true;
              speed = 7;
              bezier = "menu_decel";
              style = "slide";
            }
            {
              leaf = "specialWorkspaceIn";
              enabled = true;
              speed = 2.8;
              bezier = "emphasizedDecel";
              style = "slidevert";
            }
            {
              leaf = "specialWorkspaceOut";
              enabled = true;
              speed = 1.2;
              bezier = "emphasizedAccel";
              style = "slidevert";
            }
            {
              leaf = "zoomFactor";
              enabled = true;
              speed = 3;
              bezier = "standardDecel";
            }
            {
              leaf = "borderangle";
              enabled = true;
              speed = 100;
              bezier = "linear";
              style = "loop";
            }
          ];
        };
      };
    };
} args
