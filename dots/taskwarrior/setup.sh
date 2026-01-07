#!/usr/bin/env bash
# Setup script for advanced Taskwarrior & Timewarrior configuration

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTS_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Taskwarrior & Timewarrior Advanced Setup ==="
echo ""

# Backup existing configurations
if [ -f ~/.taskrc ]; then
    echo "Backing up existing ~/.taskrc to ~/.taskrc.backup"
    mv ~/.taskrc ~/.taskrc.backup
fi

if [ -f ~/.config/timewarrior/timewarrior.cfg ]; then
    echo "Backing up existing timewarrior config"
    mv ~/.config/timewarrior/timewarrior.cfg ~/.config/timewarrior/timewarrior.cfg.backup
fi

# Create necessary directories
mkdir -p ~/.config/timewarrior/extensions
mkdir -p ~/.local/share/timewarrior

# Symlink Taskwarrior configuration
echo "Symlinking Taskwarrior configuration..."
ln -sf "$SCRIPT_DIR/taskrc" ~/.taskrc

# Symlink Timewarrior configuration
echo "Symlinking Timewarrior configuration..."
ln -sf "$DOTS_DIR/timewarrior/timewarrior.cfg" ~/.config/timewarrior/timewarrior.cfg

# Copy Timewarrior extensions (can't symlink directory contents easily)
echo "Installing Timewarrior extensions..."
cp "$DOTS_DIR/timewarrior/extensions/"*.py ~/.config/timewarrior/extensions/
chmod +x ~/.config/timewarrior/extensions/*.py

# Copy Taskwarrior-Timewarrior integration hook
if [ -f "$DOTS_DIR/timewarrior/extensions/on-modify.timewarrior" ]; then
    echo "Installing Taskwarrior-Timewarrior integration hook..."
    mkdir -p "$SCRIPT_DIR/hooks"
    cp "$DOTS_DIR/timewarrior/extensions/on-modify.timewarrior" "$SCRIPT_DIR/hooks/"
    chmod +x "$SCRIPT_DIR/hooks/on-modify.timewarrior"
fi

# Make hooks executable
chmod +x "$SCRIPT_DIR/hooks/"*.py 2>/dev/null || true

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Configuration installed:"
echo "  Taskwarrior config: ~/.taskrc -> $SCRIPT_DIR/taskrc"
echo "  Timewarrior config: ~/.config/timewarrior/timewarrior.cfg"
echo "  Extensions: ~/.config/timewarrior/extensions/"
echo ""
echo "To use shell aliases and functions, add to your ~/.bashrc or ~/.zshrc:"
echo "  source $SCRIPT_DIR/shell-aliases.sh"
echo ""
echo "Test the setup:"
echo "  task diagnostics"
echo "  timew extensions"
echo "  task add 'Test task' priority:H +test"
echo "  task next"
echo ""
echo "View documentation:"
echo "  cat $DOTS_DIR/README-taskwarrior-timewarrior.md"
