# Nushell Environment (env.nu)
# Managed by dotfiles / home-manager

# Basic environment variables
$env.EDITOR = "nvim"
$env.VISUAL = "nvim"
$env.PAGER = "less"
$env.BROWSER = "google-chrome-stable"
$env.TERM = "kitty"
$env.TERMINAL = "kitty"
$env.NU_FLAKE = "/mnt/ssd_storage/home/nixos-config"
$env.PYTHONDONTWRITEBYTECODE = "1"
$env.SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS = "0"
$env.MICRO_TRUECOLOR = "1"

$env.AIDER_OPENAI_API_KEY = $env.OPENAI_API_KEY
$env.AIDER_ANTHROPIC_API_KEY = $env.ANTHROPIC_API_KEY
# $env.AIDER_API_KEY = gemini?
# $env.AIDER_MODEL = "gemini/gemini-2.5-pro-exp-03-25"
$env.AIDER_MODEL = "gemini/gemini-2.5-flash-preview-04-17"

# Ensure your local scripts/bin directories exist in PATH
let custom_paths = [
  ($env.HOME | path join ".local" "bin"),
  ($env.HOME | path join "scripts"),
  ($env.HOME | path join "scripts" "yeelight"),
]

for p in $custom_paths {
  if ($p | path exists) and ($p not-in $env.PATH) {
    $env.PATH = ($env.PATH | prepend $p)
  }
}

# FZF Configuration (safe handling of filenames)
$env.FZF_DEFAULT_OPTS = "--preview 'bat --color=always --style=numbers -- {}' --preview-window=right:60%:wrap"
$env.FZF_DEFAULT_COMMAND = "fd --hidden --exclude .git ."

# Base Nushell configuration
$env.config = {
  show_banner: false
  edit_mode: "vi"
  completions: {
    case_sensitive: false
    quick: true
    partial: true
  }
}

