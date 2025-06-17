# System Utility Scripts
# General purpose utilities and system management scripts

{ pkgs, ... }:
let
  runbg = pkgs.writeShellScriptBin "runbg" ''
    #!/usr/bin/env bash

    [ $# -eq 0 ] && {  # $# is number of args
        echo "$(${pkgs.coreutils}/bin/basename $0): missing command" >&2
        exit 1
    }
    prog="$(${pkgs.which}/bin/which "$1")"  # Validate command exists
    [ -z "$prog" ] && {
        echo "$(${pkgs.coreutils}/bin/basename $0): unknown command: $1" >&2
        exit 1
    }
    shift  # remove $1, now $prog, from args
    ${pkgs.coreutils}/bin/tty -s && exec </dev/null      # if stdin is a terminal, redirect from null
    ${pkgs.coreutils}/bin/tty -s <&1 && exec >/dev/null  # if stdout is a terminal, redirect to null
    ${pkgs.coreutils}/bin/tty -s <&2 && exec 2>&1        # stderr to stdout (which might not be null)
    "$prog" "$@" &  # $@ is all args
  '';

  compress = pkgs.writeScriptBin "compress" ''
    #!/usr/bin/env bash
    if [ $# -eq 0 ]; then
        echo "Usage: compress <file_or_folder> [output_name]"
        exit 1
    fi

    input="$1"
    output="''${2:-$1.tar.gz}"

    if [ -d "$input" ]; then
        ${pkgs.gnutar}/bin/tar -czf "$output" "$input"
    elif [ -f "$input" ]; then
        ${pkgs.gnutar}/bin/tar -czf "$output" "$input"
    else
        echo "Error: '$input' is not a valid file or directory"
        exit 1
    fi

    echo "Compressed '$input' to '$output'"
  '';

  extract = pkgs.writeScriptBin "extract" ''
    #!/usr/bin/env bash
    if [ $# -eq 0 ]; then
        echo "Usage: extract <archive_file>"
        exit 1
    fi

    archive="$1"

    if [ ! -f "$archive" ]; then
        echo "Error: '$archive' is not a valid file"
        exit 1
    fi

    case "$archive" in
        *.tar.gz|*.tgz)
            ${pkgs.gnutar}/bin/tar -xzf "$archive"
            ;;
        *.tar.bz2|*.tbz2)
            ${pkgs.gnutar}/bin/tar -xjf "$archive"
            ;;
        *.tar.xz|*.txz)
            ${pkgs.gnutar}/bin/tar -xJf "$archive"
            ;;
        *.zip)
            ${pkgs.unzip}/bin/unzip "$archive"
            ;;
        *.rar)
            ${pkgs.unrar}/bin/unrar x "$archive"
            ;;
        *.7z)
            ${pkgs.p7zip}/bin/7z x "$archive"
            ;;
        *)
            echo "Error: Unsupported archive format for '$archive'"
            exit 1
            ;;
    esac

    echo "Extracted '$archive'"
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
in
{
  config = {
    environment.systemPackages = [
      runbg
      compress
      extract
      combine-files
    ];
  };
}
