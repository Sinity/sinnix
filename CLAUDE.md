# CLAUDE WORKFLOW SYSTEM

## 🔄 SYSTEMATIC WORK PATTERN
1. **📋 Map Possibilities** - Use TodoWrite to outline all approaches before acting
2. **🎯 Plan Optimal Path** - Select best approach with clear rationale documented
3. **⚙️ Execute Incrementally** - Implement with validation at each step, mark todos complete immediately

## 🔗 GIT & GITHUB PRACTICES
- **🌿 Branching**: Create feature branches for non-trivial changes (`claude/feature-name`)
- **📝 Issues**: Track work via GitHub issues for complex features (break into sub-issues)
- **🔀 PRs**: Use pull requests for review-worthy changes with clear context
- **💫 Commits**: Atomic, descriptive commits with `Co-authored-by: Claude <noreply@anthropic.com>`
- **✅ Testing**: Validate with `nix run .#test` before switching, `nix flake check` always

## 👤 IDENTITY PATTERN
- **Commits**: Co-authorship trailers for attribution clarity
- **Branches**: `claude/feature-description` for Claude-initiated work
- **Issues**: Claude-authored with clear automation context
- **Communication**: Direct, technical, no artificial humanness masking

## 🏗️ DOMAIN-UNIFIED ARCHITECTURE PRINCIPLES
- **🎯 Domain Ownership**: Eliminate system/user cognitive splits via unified domain modules
- **🔗 Sinity Alias**: Use `sinity.programs.X` instead of `home-manager.users.sinity.programs.X`
- **🎨 Stylix Integration**: System-wide theming, no custom abstractions
- **📈 Incremental Migration**: Validate each phase, preserve functionality always
- **🧪 Bottom-up Design**: Solve real friction, avoid over-abstraction trap

## 📊 MULTI-TURN TASK MANAGEMENT
- **📝 TodoWrite Proactively**: Break complex requests into trackable sub-tasks immediately
- **✅ Complete Immediately**: Mark todos done as soon as finished, don't batch
- **🎯 Single Focus**: Only one todo `in_progress` at a time
- **📋 Context Preservation**: Use GitHub issues for work spanning multiple sessions

## 🔧 TECHNICAL VALIDATION STACK
```bash
nix flake check                                    # Syntax validation
sudo nixos-rebuild test --flake .#sinnix-prime   # Functional validation
# Test: login, desktop, audio, development, networking, automation
```

## 🏛️ ARCHITECTURE OVERVIEW

This repository implements domain-unified NixOS configuration:

1. `flake.nix` - Entry point and dependency declaration
2. `flake/*.nix` - Modular flake outputs (development, apps, system config)
3. `module/foundation.nix` - Core system bootstrap, users, security
4. `module/interface.nix` - Complete UI experience (system + desktop)
5. `module/development.nix` - Complete dev workflow (tools + environment)
6. `module/media.nix` - Complete audio/video (system + applications)
7. `module/communication.nix` - Complete connectivity (network + apps)
8. `module/automation.nix` - Complete orchestration (services + scripts)
9. `host/sinnix-prime/*.nix` - Hardware-specific configuration only

## 🔑 CRITICAL PATTERNS

**Secret Management**: 
- Secrets in `secret/*.age`, auto-discovered via `module/foundation.nix`
- Environment variables: `dash-case-name.age` → `DASH_CASE_NAME`
- Access: `config.age.secrets.<name>.path`

**Package Management**:
- System packages: `environment.systemPackages` in appropriate domain
- User packages: `sinity.home.packages` in appropriate domain

**Extension Points**:
- New functionality goes in appropriate domain module
- Host-specific config only in `host/sinnix-prime/`
- Cross-cutting concerns handled by stylix + domain extension points

## 🎯 SUCCESS CRITERIA
- Zero cognitive overhead asking "is this system or user config?"
- Single source of truth for each functional domain
- All changes follow domain boundaries, not implementation layers
- System ready for Blueprint 0.5+ extensions

---
*Domain-unified architecture eliminates implementation detail leakage via functional organization*