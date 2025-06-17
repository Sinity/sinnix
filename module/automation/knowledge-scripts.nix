# Knowledge Management Scripts
# Scripts for working with personal knowledge base and data

{ pkgs, ... }:
let
  log-to-knowledgebase = pkgs.writeShellScriptBin "log-to-knowledgebase" ''
    #!/usr/bin/env bash
    # Define file path
    log_file="$HOME/knowledgebase/10_inbox/daily-log-$(date +%Y-%m-%d).md"

    # Create file if it doesn't exist with proper header
    if [ ! -f "$log_file" ]; then
        echo "# Daily Log - $(date +%Y-%m-%d)" > "$log_file"
        echo "" >> "$log_file"
        echo "## Entries" >> "$log_file"
        echo "" >> "$log_file"
    fi

    # Add timestamp and entry
    echo "### $(date +%H:%M)" >> "$log_file"
    echo "" >> "$log_file"

    if [ $# -eq 0 ]; then
        # Interactive mode
        echo "Enter your log entry (Ctrl+D to finish):"
        cat >> "$log_file"
    else
        # Command line argument mode
        echo "$*" >> "$log_file"
    fi

    echo "" >> "$log_file"
    echo "Logged to: $log_file"
  '';

  kb-search = pkgs.writeShellScriptBin "kb-search" ''
    #!/usr/bin/env bash
    # Search through knowledge base using ripgrep

    KB_PATH="$HOME/knowledgebase"

    if [ $# -eq 0 ]; then
        echo "Usage: kb-search <search_term>"
        echo "Search through your knowledge base"
        exit 1
    fi

    search_term="$*"

    echo "Searching for: $search_term"
    echo "===================="

    ${pkgs.ripgrep}/bin/rg --color=always --heading --line-number "$search_term" "$KB_PATH" || {
        echo "No results found for: $search_term"
        exit 1
    }
  '';

  kb-new-note = pkgs.writeShellScriptBin "kb-new-note" ''
    #!/usr/bin/env bash
    # Create a new note in the knowledge base

    KB_INBOX="$HOME/knowledgebase/10_inbox"

    if [ $# -eq 0 ]; then
        echo "Usage: kb-new-note <note_title>"
        exit 1
    fi

    title="$*"
    filename=$(echo "$title" | ${pkgs.gnused}/bin/sed 's/[^a-zA-Z0-9 ]//g' | ${pkgs.gnused}/bin/sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')
    filepath="$KB_INBOX/$filename.md"

    if [ -f "$filepath" ]; then
        echo "Note already exists: $filepath"
        echo "Opening existing note..."
    else
        echo "# $title" > "$filepath"
        echo "" >> "$filepath"
        echo "Created: $(date)" >> "$filepath"
        echo "Tags: #inbox" >> "$filepath"
        echo "" >> "$filepath"
        echo "## Content" >> "$filepath"
        echo "" >> "$filepath"
        echo "Created new note: $filepath"
    fi

    # Open in default editor if available
    if command -v "$EDITOR" > /dev/null; then
        "$EDITOR" "$filepath"
    fi
  '';
in
{
  config = {
    environment.systemPackages = [
      log-to-knowledgebase
      kb-search
      kb-new-note
    ];
  };
}
