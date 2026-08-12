"""sinnix-capture-screen: Hyprland-triggered per-window screen frame capture.

See daemon.py's module docstring for the frame-grab mechanism decision
(why grim over Noctalia's own screenshot IPC, and the live black-frame
regression discovered while authoring this lane).
"""

from __future__ import annotations
