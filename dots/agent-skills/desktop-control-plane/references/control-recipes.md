# Control Recipes

## 1) Run a Command in an Existing Kitty Window and Wait for Completion
```bash
scripts/kitty-remote-control.sh send-await \
  --match 'title:Codex' \
  --text 'python3 main.py analysis-validate && printf "__DONE__\\n"' \
  --enter \
  --pattern '^__DONE__$' \
  --timeout-sec 600
```

## 2) Capture Full Scrollback as Artifact
```bash
scripts/kitty-remote-control.sh capture \
  --match 'title:Codex' \
  --extent all \
  --out /realm/data/captures/logs/codex-session.txt
```

## 3) Inspect Hyprland Context Before Automation
```bash
scripts/hypr-control.sh status
scripts/hypr-control.sh binds --grep 'Print|grimblast|workspace'
```

## 4) HDR Screenshot Workflow (Raw + Corrected Sidecars)
```bash
scripts/screenshot-color-lab.sh probe
scripts/screenshot-color-lab.sh capture-output --fix-hdr
```

## 5) Arrange Kitty Windows as Grid (System Script)
```bash
/realm/project/sinnix/scripts/kitty-grid --workspace 3 --grid 3x2
```
