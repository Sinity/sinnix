# Domain Modules Entry Point
# Imports all domain modules (commented out until implemented)

_: {
  imports = [
    ./foundation.nix # Phase 2: Core system bootstrap, users, security
    ./interface.nix # Phase 3: Complete UI experience (system + desktop)
    ./development.nix # Phase 4: Complete dev workflow (tools + environment)
    ./media.nix # Phase 5: Complete audio/video (system + applications)
    ./communication.nix # Phase 6: Complete connectivity (network + apps)
    ./automation.nix # Phase 7: Complete orchestration (services + scripts)
  ];
}
