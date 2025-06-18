# Scripts

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

  combine-files = pkgs.writeShellScriptBin "combine-files" ''
    #!/usr/bin/env bash
    #
    # combine-files.sh — Combine multiple text files into a single structured document
    # Usage: ./combine-files.sh [options]
    #
    # This script walks through directories and combines text files into a single
    # output with clear file boundaries and metadata.

    output_file="combined_output.txt"
    include_hidden=false
    verbose=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            -o|--output)
                output_file="$2"
                shift 2
                ;;
            -h|--hidden)
                include_hidden=true
                shift
                ;;
            -v|--verbose)
                verbose=true
                shift
                ;;
            --help)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  -o, --output FILE    Output file (default: combined_output.txt)"
                echo "  -h, --hidden        Include hidden files"
                echo "  -v, --verbose       Verbose output"
                echo "  --help              Show this help"
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    > "$output_file"  # Clear output file

    find_args=()
    if [ "$include_hidden" = false ]; then
        find_args+=(-not -path "*/.*")
    fi

    ${pkgs.findutils}/bin/find . -type f -name "*.txt" -o -name "*.md" -o -name "*.py" -o -name "*.sh" ''${find_args[@]} | sort | while read -r file; do
        if [ "$verbose" = true ]; then
            echo "Processing: $file"
        fi
        
        echo "=== FILE: $file ===" >> "$output_file"
        echo "" >> "$output_file"
        cat "$file" >> "$output_file"
        echo "" >> "$output_file"
        echo "=== END: $file ===" >> "$output_file"
        echo "" >> "$output_file"
    done

    echo "Combined files written to: $output_file"
  '';

  toggle_waybar = pkgs.writeScriptBin "toggle_waybar" ''
    #!/usr/bin/env bash
    if ${pkgs.procps}/bin/pgrep -x waybar > /dev/null; then
        ${pkgs.procps}/bin/pkill waybar
    else
        ${pkgs.waybar}/bin/waybar &
    fi
  '';
in
{
  config = {
    environment.systemPackages = [
      log-to-knowledgebase
      combine-files
      toggle_waybar
    ];
  };
}

