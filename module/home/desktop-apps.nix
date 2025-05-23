{
  pkgs,
  ...
}:
{
  # Desktop applications
  home.packages = with pkgs; [
    # Web browsers - moved to communication domain

    # Document and office applications
    libreoffice
    # audacity # Moved to media domain
    # gimp # Moved to media domain

    # Gaming
    mangohud
    steam-run
    # steam-tui
    # protonup
    # bottles
    # Factorio with authentication token
    # (factorio.override {
    #   username = "Sinityy";
    #   token = "$FACTORIO_TOKEN";
    # })
    # (pkgs.writeShellScriptBin "factorio-steam" ''
    #   exec ${steam-run}/bin/steam-run ${factorio}/bin/factorio "$@"
    # '')

    # File management
    nautilus
    transmission_3-gtk

    # Productivity
    obsidian
    taskwarrior3
    timewarrior

    # System maintenance
    bleachbit # cache cleaner

    # Utility applications
    ddcutil # Query and change Linux monitor settings using DDC/CI and USB
    evtest # Input device event monitor and query tool
    meld # Compare files, directories and working copies
    piper # GTK application to configure gaming mice

    # Android tools
    android-tools
    android-file-transfer

    # Fonts
    fira-code
    hack-font

    # Miscellaneous utilities
    hledger # Accounting system
    llm # Run inference for Large Language Models on CPU
    mosh # Mobile shell
    single-file-cli # Save web pages as single HTML file
    programmer-calculator
    bc
    calc
  ];
}
