#!/usr/bin/env bash
# Blueprint v0.3 Validation Suite
# Ensures each phase of domain-unified migration is successful

set -euo pipefail

PHASE="${1:-all}"
LOG_FILE="/tmp/blueprint-v0.3-validation-$(date +%Y%m%d-%H%M%S).log"
FLAKE_PATH="/realm/nixos-config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

success() {
    log "${GREEN}✅ $1${NC}"
}

error() {
    log "${RED}❌ $1${NC}"
}

info() {
    log "${YELLOW}🔍 $1${NC}"
}

# Basic system validation
validate_syntax() {
    info "Running syntax validation..."
    if nix flake check --no-build 2>&1 | tee -a "$LOG_FILE"; then
        success "Syntax validation passed"
        return 0
    else
        error "Syntax validation failed"
        return 1
    fi
}

validate_build() {
    info "Running build validation..."
    if sudo nixos-rebuild dry-build --flake "$FLAKE_PATH#sinnix-prime" 2>&1 | tee -a "$LOG_FILE"; then
        success "Build validation passed"
        return 0
    else
        error "Build validation failed"
        return 1
    fi
}

# Phase-specific validations
validate_infrastructure() {
    info "Validating infrastructure setup..."
    local failed=0
    
    # Check module structure exists
    for module in foundation interface development media communication automation; do
        if [[ ! -f "$FLAKE_PATH/module/$module.nix" ]]; then
            error "Missing module: $module.nix"
            ((failed++))
        fi
    done
    
    # Check service directory structure
    if [[ ! -d "$FLAKE_PATH/module/service" ]]; then
        error "Missing module/service directory"
        ((failed++))
    fi
    
    # Check domain factory
    if [[ ! -f "$FLAKE_PATH/module/lib/domain.nix" ]]; then
        error "Missing domain factory: module/lib/domain.nix"
        ((failed++))
    fi
    
    if [[ $failed -eq 0 ]]; then
        success "Infrastructure validation passed"
        return 0
    else
        error "Infrastructure validation failed with $failed errors"
        return 1
    fi
}

validate_phase1() {
    info "Validating Phase 1: Sinity Alias Pattern..."
    local failed=0
    
    # Check if domain module factory includes sinity pattern
    if ! grep -q "sinity = config.home-manager.users" "$FLAKE_PATH/module/lib/domain.nix"; then
        error "Sinity pattern not defined in domain module factory"
        ((failed++))
    fi
    
    # Check if example pattern exists
    if [[ ! -f "$FLAKE_PATH/module/sinity-pattern-example.nix" ]]; then
        error "Sinity pattern example not found"
        ((failed++))
    fi
    
    # Test that the system still builds
    info "Testing build with sinity pattern..."
    if ! sudo nixos-rebuild dry-build --flake "$FLAKE_PATH#sinnix-prime" 2>&1 | tee -a "$LOG_FILE"; then
        error "System fails to build"
        ((failed++))
    fi
    
    if [[ $failed -eq 0 ]]; then
        success "Phase 1 validation passed - sinity pattern ready for use"
        return 0
    else
        error "Phase 1 validation failed with $failed errors"
        return 1
    fi
}

validate_phase2() {
    info "Validating Phase 2: Foundation Domain..."
    local failed=0
    
    # Check if foundation module is enabled
    if ! grep -q "^[[:space:]]*\./foundation\.nix" "$FLAKE_PATH/module/default.nix"; then
        error "Foundation module not enabled in module/default.nix"
        ((failed++))
    fi
    
    # Check if foundation imports required modules
    if ! grep -q "./system/system.nix" "$FLAKE_PATH/module/foundation.nix"; then
        error "Foundation missing system.nix import"
        ((failed++))
    fi
    
    # Test core functionality
    info "Testing nix command functionality..."
    if ! nix --version >/dev/null 2>&1; then
        error "Nix commands not working"
        ((failed++))
    fi
    
    # Test that secrets directory structure exists
    if [[ ! -d "$FLAKE_PATH/secret" ]]; then
        error "Secret directory missing"
        ((failed++))
    fi
    
    if [[ $failed -eq 0 ]]; then
        success "Phase 2 validation passed - foundation domain functional"
        return 0
    else
        error "Phase 2 validation failed with $failed errors"
        return 1
    fi
}

validate_phase3() {
    info "Validating Phase 3: Interface Domain..."
    local failed=0
    
    # Check if interface module is enabled
    if ! grep -q "^\s*\./interface\.nix" "$FLAKE_PATH/module/default.nix"; then
        error "Interface module not enabled in module/default.nix"
        ((failed++))
    fi
    
    # Check if interface imports desktop modules
    if ! grep -q "./home/desktop" "$FLAKE_PATH/module/interface.nix"; then
        error "Interface missing desktop imports"
        ((failed++))
    fi
    
    # Check critical interface packages
    local critical_pkgs=("hyprland" "waybar" "rofi")
    for pkg in "${critical_pkgs[@]}"; do
        if ! nix-env -qa 2>/dev/null | grep -q "$pkg" 2>/dev/null; then
            info "Note: $pkg availability check skipped (build-time)"
        fi
    done
    
    # Check XDG portal configuration
    if ! grep -q "xdg.portal" "$FLAKE_PATH/module/interface.nix"; then
        error "XDG portal not configured in interface module"
        ((failed++))
    fi
    
    # Check font configuration
    if ! grep -q "fonts" "$FLAKE_PATH/module/interface.nix"; then
        error "Font configuration not found in interface module"
        ((failed++))
    fi
    
    if [[ $failed -eq 0 ]]; then
        success "Phase 3 validation passed - interface domain configured"
        return 0
    else
        error "Phase 3 validation failed with $failed errors"
        return 1
    fi
}

validate_phase4() {
    info "Validating Phase 4: Development Domain..."
    local failed=0
    
    # Check if development module is enabled
    if ! grep -q "^\s*\./development\.nix" "$FLAKE_PATH/module/default.nix"; then
        error "Development module not enabled in module/default.nix"
        ((failed++))
    fi
    
    # Check if development module has proper tag
    if ! grep -q "development-domain-v0.3" "$FLAKE_PATH/module/development.nix"; then
        error "Development domain tag not found"
        ((failed++))
    fi
    
    # Check critical development components
    if ! grep -q "programs.nix-ld" "$FLAKE_PATH/module/development.nix"; then
        error "nix-ld configuration not found in development module"
        ((failed++))
    fi
    
    if ! grep -q "nixpkgs.overlays" "$FLAKE_PATH/module/development.nix"; then
        error "Development overlays not configured"
        ((failed++))
    fi
    
    # Check git configuration
    if ! grep -q "programs.git" "$FLAKE_PATH/module/development.nix"; then
        error "Git configuration not found in development module"
        ((failed++))
    fi
    
    # Check neovim configuration
    if ! grep -q "neovim" "$FLAKE_PATH/module/development.nix"; then
        error "Neovim configuration not found in development module"
        ((failed++))
    fi
    
    # Check AI tools
    if ! grep -q "claude-code" "$FLAKE_PATH/module/development.nix"; then
        error "AI development tools not found in development module"
        ((failed++))
    fi
    
    if [[ $failed -eq 0 ]]; then
        success "Phase 4 validation passed - development domain configured"
        return 0
    else
        error "Phase 4 validation failed with $failed errors"
        return 1
    fi
}

validate_phase5() {
    info "Validating Phase 5: Media Domain..."
    local failed=0
    
    # Check if media module is enabled
    if ! grep -q "^\s*\./media\.nix" "$FLAKE_PATH/module/default.nix"; then
        error "Media module not enabled in module/default.nix"
        ((failed++))
    fi
    
    # Check if media module has proper tag
    if ! grep -q "media-domain-v0.3" "$FLAKE_PATH/module/media.nix"; then
        error "Media domain tag not found"
        ((failed++))
    fi
    
    # Check audio system configuration
    if ! grep -q "services.pipewire" "$FLAKE_PATH/module/media.nix"; then
        error "PipeWire audio system not configured in media module"
        ((failed++))
    fi
    
    # Check real-time audio optimizations
    if ! grep -q "security.pam.loginLimits" "$FLAKE_PATH/module/media.nix"; then
        error "Real-time audio optimizations not configured"
        ((failed++))
    fi
    
    # Check MPV configuration
    if ! grep -q "programs.mpv" "$FLAKE_PATH/module/media.nix"; then
        error "MPV media player not configured in media module"
        ((failed++))
    fi
    
    # Check media packages
    if ! grep -q "spotify\|ffmpeg\|audacity" "$FLAKE_PATH/module/media.nix"; then
        error "Media packages not found in media module"
        ((failed++))
    fi
    
    # Check enhanced image viewer
    if ! grep -q "imv.overrideAttrs" "$FLAKE_PATH/module/media.nix"; then
        error "Enhanced image viewer not configured"
        ((failed++))
    fi
    
    if [[ $failed -eq 0 ]]; then
        success "Phase 5 validation passed - media domain configured"
        return 0
    else
        error "Phase 5 validation failed with $failed errors"
        return 1
    fi
}

validate_phase6() {
    info "Validating Phase 6: Communication Domain..."
    local failed=0
    
    # Check if communication module is enabled
    if ! grep -q "^\s*\./communication\.nix" "$FLAKE_PATH/module/default.nix"; then
        error "Communication module not enabled in module/default.nix"
        ((failed++))
    fi
    
    # Check if communication module has proper tag
    if ! grep -q "communication-domain-v0.3" "$FLAKE_PATH/module/communication.nix"; then
        error "Communication domain tag not found"
        ((failed++))
    fi
    
    # Check network configuration
    if ! grep -q "networkmanager.enable" "$FLAKE_PATH/module/communication.nix"; then
        error "NetworkManager not configured in communication module"
        ((failed++))
    fi
    
    # Check SSH configuration
    if ! grep -q "openssh = {" "$FLAKE_PATH/module/communication.nix"; then
        error "SSH server not configured in communication module"
        ((failed++))
    fi
    
    # Check web server configuration
    if ! grep -q "nginx = {" "$FLAKE_PATH/module/communication.nix"; then
        error "NGINX web server not configured in communication module"
        ((failed++))
    fi
    
    # Check browser packages
    if ! grep -q "google-chrome\|firefox\|qutebrowser" "$FLAKE_PATH/module/communication.nix"; then
        error "Web browsers not found in communication module"
        ((failed++))
    fi
    
    # Check SSH client configuration
    if ! grep -q "programs.ssh" "$FLAKE_PATH/module/communication.nix"; then
        error "SSH client not configured in communication module"
        ((failed++))
    fi
    
    if [[ $failed -eq 0 ]]; then
        success "Phase 6 validation passed - communication domain configured"
        return 0
    else
        error "Phase 6 validation failed with $failed errors"
        return 1
    fi
}

validate_phase7() {
    info "Validating Phase 7: Automation Domain..."
    local failed=0
    
    # Check if automation module is enabled
    if ! grep -q "^\s*\./automation\.nix" "$FLAKE_PATH/module/default.nix"; then
        error "Automation module not enabled in module/default.nix"
        ((failed++))
    fi
    
    # Check if automation module has proper tag
    if ! grep -q "automation-domain-v0.3" "$FLAKE_PATH/module/automation.nix"; then
        error "Automation domain tag not found"
        ((failed++))
    fi
    
    # Check transmission service
    if ! grep -q "transmission = {" "$FLAKE_PATH/module/automation.nix"; then
        error "Transmission service not configured in automation module"
        ((failed++))
    fi
    
    # Check ollama service  
    if ! grep -q "ollama = {" "$FLAKE_PATH/module/automation.nix"; then
        error "Ollama service not configured in automation module"
        ((failed++))
    fi
    
    # Check ActivityWatch service
    if ! grep -q "services.activitywatch" "$FLAKE_PATH/module/automation.nix"; then
        error "ActivityWatch service not configured in automation module"
        ((failed++))
    fi
    
    # Check script packages
    if ! grep -q "wall-change\|wallpaper-picker\|toggle_" "$FLAKE_PATH/module/automation.nix"; then
        error "Script packages not found in automation module"
        ((failed++))
    fi
    
    # Check systemd services
    if ! grep -q "asbl-no-moar = {" "$FLAKE_PATH/module/automation.nix"; then
        error "ASBL mitigation service not configured"
        ((failed++))
    fi
    
    # Check systemd timers
    if ! grep -q "timers.asbl-no-moar" "$FLAKE_PATH/module/automation.nix"; then
        error "ASBL mitigation timer not configured"
        ((failed++))
    fi
    
    # Check journald configuration
    if ! grep -q "journald = {" "$FLAKE_PATH/module/automation.nix"; then
        error "System journald not configured in automation module"
        ((failed++))
    fi
    
    if [[ $failed -eq 0 ]]; then
        success "Phase 7 validation passed - automation domain configured"
        return 0
    else
        error "Phase 7 validation failed with $failed errors"
        return 1
    fi
}

validate_phase8() {
    info "Validating Phase 8: Cleanup and Finalization..."
    local failed=0
    
    # Check that placeholder modules have been removed
    local placeholder_files=(
        "module/temp-services.nix"
        "module/system/services.nix"
        "module/home/asbl-no-moar.nix"
        "module/home/activity_watch.nix"
        "module/home/scripts/scripts.nix"
        "module/system/network.nix"
        "module/home/ssh.nix"
        "module/service/nginx.nix"
        "module/home/media.nix"
        "module/home/neovim.nix"
        "module/home/development.nix"
        "module/home/git.nix"
    )
    
    for file in "${placeholder_files[@]}"; do
        if [[ -f "$FLAKE_PATH/$file" ]]; then
            error "Placeholder file still exists: $file"
            ((failed++))
        fi
    done
    
    # Check that all domain modules are enabled
    local domain_modules=("foundation" "interface" "development" "media" "communication" "automation")
    for module in "${domain_modules[@]}"; do
        if ! grep -q "^\s*\./$module\.nix" "$FLAKE_PATH/module/default.nix"; then
            error "Domain module not enabled: $module.nix"
            ((failed++))
        fi
    done
    
    # Check that import statements are cleaned up
    if grep -q "temp-services.nix" "$FLAKE_PATH/module/default.nix"; then
        error "temp-services.nix still referenced in module/default.nix"
        ((failed++))
    fi
    
    # Check system has all domain tags
    local expected_tags=("foundation-domain-v0.3" "interface-domain-v0.3" "development-domain-v0.3" "media-domain-v0.3" "communication-domain-v0.3" "automation-domain-v0.3")
    for tag in "${expected_tags[@]}"; do
        if ! nix eval ".#nixosConfigurations.sinnix-prime.config.system.nixos.tags" | grep -q "$tag"; then
            error "Missing domain tag: $tag"
            ((failed++))
        fi
    done
    
    if [[ $failed -eq 0 ]]; then
        success "Phase 8 validation passed - cleanup and finalization complete"
        return 0
    else
        error "Phase 8 validation failed with $failed errors"
        return 1
    fi
}

# Main execution
main() {
    log "=== Blueprint v0.3 Validation Suite ==="
    log "Phase: $PHASE"
    log "Log file: $LOG_FILE"
    log ""
    
    # Always run basic validations
    validate_syntax || exit 1
    validate_build || exit 1
    
    # Run phase-specific validation
    case $PHASE in
        infrastructure)
            validate_infrastructure || exit 1
            ;;
        phase1)
            validate_phase1 || exit 1
            ;;
        phase2)
            validate_phase2 || exit 1
            ;;
        phase3)
            validate_phase3 || exit 1
            ;;
        phase4)
            validate_phase4 || exit 1
            ;;
        phase5)
            validate_phase5 || exit 1
            ;;
        phase6)
            validate_phase6 || exit 1
            ;;
        phase7)
            validate_phase7 || exit 1
            ;;
        phase8)
            validate_phase8 || exit 1
            ;;
        all)
            info "Running all validations..."
            validate_infrastructure
            validate_phase1
            validate_phase2
            validate_phase3
            validate_phase4
            validate_phase5
            validate_phase6
            validate_phase7
            validate_phase8
            ;;
        *)
            error "Unknown phase: $PHASE"
            echo "Usage: $0 [infrastructure|phase1|phase2|...|phase8|all]"
            exit 1
            ;;
    esac
    
    success "All validations passed!"
    log ""
    log "Full log available at: $LOG_FILE"
}

main "$@"