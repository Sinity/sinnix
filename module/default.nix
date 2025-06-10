# Domain Modules Entry Point
# Imports all domain modules (now with split structure)

_: {
  imports = [
    ./foundation.nix # Phase 2: Core system bootstrap, users, security
    ./interface # Phase 3: Complete UI experience (system + desktop)
    ./development # Phase 4: Complete dev workflow (tools + environment)
    ./media.nix # Phase 5: Complete audio/video (system + applications)
    ./communication.nix # Phase 6: Complete connectivity (network + apps)
    ./automation # Phase 7: Complete orchestration (services + scripts)
  ];
}
