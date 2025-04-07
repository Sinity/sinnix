# mpv Configuration

This directory contains configuration for mpv, a free, open-source, and cross-platform media player.

## Installation

Use the manage-dots.sh script to deploy this configuration:

```bash
./manage-dots.sh deploy mpv
```

## Configuration Files

- `mpv.conf`: Main configuration file with video/audio settings and profiles
- `input.conf`: Key bindings configuration file

## Features

- Custom keybindings for intuitive navigation and control
- Multiple profiles for different use cases (normal, wallpaper, benchmarking)
- High-quality video scaling settings
- Language preferences for subtitles and audio tracks
- Optimized playback settings

## Dependencies

The configuration assumes the following packages are installed:

- mpv (core package)
- mediainfo
- vapoursynth
- aria2
- svpflow (custom package)
- ffmpeg