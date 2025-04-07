# Ranger Configuration

This directory contains configuration for Ranger, a terminal file manager with VI key bindings.

## Installation

Use the manage-dots.sh script to deploy this configuration:

```bash
./manage-dots.sh deploy ranger
```

## Configuration Files

- `rc.conf`: Main configuration file with UI settings and key bindings
- `rifle.conf`: File associations for opening different file types
- `scope.sh`: Preview script for generating previews of various file types

## Features

- Image previews using ueberzug++
- Video thumbnails with ffmpegthumbnailer
- Audio visualization with waveforms
- PDF thumbnails
- Archive content previews
- Custom key bindings for efficient navigation
- File operations including trash support

## Dependencies

The configuration assumes the following packages are installed:

- ranger (core package)
- ueberzugpp
- ffmpeg and ffmpegthumbnailer
- imagemagick
- poppler-utils
- mpv
- atool
- libcaca
- highlight
- mediainfo
- w3m
- bat
- parallel
- bc
- file
- exiftool