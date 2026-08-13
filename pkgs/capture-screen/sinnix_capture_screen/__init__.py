"""sinnix-capture-screen: Hyprland-triggered per-window screen frame capture.

See daemon.py's module docstring for the frame-grab mechanism: why grim
rather than Noctalia's own screenshot IPC, and the compositor-side
black-frame failure this lane guards against.
"""

from __future__ import annotations
