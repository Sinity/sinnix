"""claudia-kit: the method behind the lip-synced Claudia music videos, as small command-line stages.

  lyric      score lyric lines on a 4/4 grid and rank rewrites
  songmap    beat map, hits, voiced phrases and the line table from the song and its stems
  frames     stills for first and last frames (GPT Image 2.6 Sunburst on Replicate), with the same ledger and cap
  shotbook   the shot book -> gated vocal windows, prompts (Seedance 2.5, or a first-frame model) and job files; lint
  run        submit jobs: Seedance 2.5 (Replicate or Higgsfield) or a first-frame model such as Grok Imagine Video
             1.5 (OpenRouter), with a ledger and a spending cap
  sync       place each take on the song: DTW on its soundtrack, or her lips when it has none or never heard the song
  cut        render the film, review sheets, the flash check and an audit

Run any stage as `python -m claudia_kit <stage> --help`.
"""
__version__ = "0.2.0"
STAGES = ("lyric", "songmap", "frames", "shotbook", "run", "sync", "cut")
