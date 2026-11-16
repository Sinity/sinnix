"""What is going on across all agent work, computed once for every view.

``engine.compute`` turns collected facts into one state document. The desktop
bar, the desktop panel, the hub page and ``sinnix state`` all read that
document; none of them computes its own.
"""

SCHEMA = "sinnix-operator-state-v1"
