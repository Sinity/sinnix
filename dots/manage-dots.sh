#!/bin/sh
# Dotfiles management script using GNU Stow

# Simple path configuration
DOTS_DIR="$(dirname "$(readlink -f "$0")")"
TARGET_DIR="$HOME"

display_help() {
  echo "Dotfiles Manager"
  echo "Usage: $0 [command] [package]"
  echo
  echo "Commands:"
  echo "  deploy [package]   - Deploy dotfiles (create symlinks)"
  echo "  remove [package]   - Remove dotfiles (delete symlinks)"
  echo "  collect [package]  - Collect actual configs into dots repo"
  echo "  list               - List available dotfile packages"
  echo
  echo "Examples:"
  echo "  $0 deploy nvim     - Deploy neovim config"
  echo "  $0 deploy          - Deploy all packages"
  echo "  $0 collect git     - Collect git config from home to dots"
}

list_packages() {
  echo "Available dotfile packages:"
  # Use fd if available, otherwise fall back to find
  if command -v fd >/dev/null 2>&1; then
    fd --max-depth 1 --type d --exec basename {} \; . "$DOTS_DIR" | grep -v "^\\." | while read -r dir; do
      echo "  $dir"
    done
  else
    find "$DOTS_DIR" -maxdepth 1 -mindepth 1 -type d | while read -r dir; do
      echo "  $(basename "$dir")"
    done
  fi
}

deploy_package() {
  package="$1"
  echo "Deploying $package dotfiles..."
  cd "$DOTS_DIR" || exit 1
  stow -v -t "$TARGET_DIR" "$package"
}

remove_package() {
  package="$1"
  echo "Removing $package dotfiles..."
  cd "$DOTS_DIR" || exit 1
  stow -v -D -t "$TARGET_DIR" "$package"
}

deploy_all() {
  echo "Deploying all dotfiles packages..."
  cd "$DOTS_DIR" || exit 1
  
  # Use fd if available, otherwise fall back to find
  if command -v fd >/dev/null 2>&1; then
    fd --max-depth 1 --type d --exec basename {} \; . | grep -v "^\\." | while read -r dir; do
      echo "Deploying $dir..."
      stow -v -t "$TARGET_DIR" "$dir"
    done
  else
    find . -maxdepth 1 -mindepth 1 -type d | while read -r dir; do
      dir=$(basename "$dir")
      echo "Deploying $dir..."
      stow -v -t "$TARGET_DIR" "$dir"
    done
  fi
}

collect_package() {
  package="$1"
  echo "Collecting $package configuration..."
  
  case "$package" in
    nvim)
      mkdir -p "$DOTS_DIR/nvim/.config"
      rsync -av --delete "$HOME/.config/nvim/" "$DOTS_DIR/nvim/.config/nvim/"
      ;;
    git)
      mkdir -p "$DOTS_DIR/git/.config/git"
      if [ -f "$HOME/.gitconfig" ]; then
        rsync -av --delete "$HOME/.gitconfig" "$DOTS_DIR/git/"
      fi
      if [ -d "$HOME/.config/git" ]; then
        rsync -av --delete "$HOME/.config/git/" "$DOTS_DIR/git/.config/git/"
      fi
      ;;
    ssh)
      mkdir -p "$DOTS_DIR/ssh/.ssh"
      
      # Only collect configuration files, not keys
      if [ -f "$HOME/.ssh/config" ]; then
        rsync -av "$HOME/.ssh/config" "$DOTS_DIR/ssh/.ssh/"
      fi
      ;;
    *)
      echo "Error: Collection for $package is not yet configured"
      echo "Add your package to the collect_package function in this script"
      exit 1
      ;;
  esac
  
  echo "Collection complete!"
}

# Main execution
case "$1" in
  deploy)
    if [ -z "$2" ]; then
      deploy_all
    else
      deploy_package "$2"
    fi
    ;;
  remove)
    if [ -z "$2" ]; then
      echo "Error: Please specify a package to remove"
      exit 1
    else
      remove_package "$2"
    fi
    ;;
  collect)
    if [ -z "$2" ]; then
      echo "Error: Please specify a package to collect"
      exit 1
    else
      collect_package "$2"
    fi
    ;;
  list)
    list_packages
    ;;
  *)
    display_help
    ;;
esac