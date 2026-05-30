DEFAULT_RUNTIME_INVENTORY_JSON = r"""{
  "schema": "sinnix-runtime-inventory-v1",
  "classes": {
    "interactive-agent": {
      "description": "Interactive AI agent shells and frontends",
      "serviceConfig": {}
    },
    "interactive-access": {
      "description": "Login, SSH, and input services needed to regain control",
      "serviceConfig": {
        "Slice": "system-critical.slice"
      }
    },
    "developer-build": {
      "description": "User-initiated builds, tests, and Nix work",
      "serviceConfig": {}
    },
    "background-maintenance": {
      "description": "Bulk maintenance that should yield to interaction",
      "serviceConfig": {}
    },
    "backup-maintenance": {
      "description": "Snapshot and backup jobs",
      "serviceConfig": {}
    },
    "capture-runtime": {
      "description": "Long-running capture daemons",
      "serviceConfig": {}
    },
    "capture-substrate": {
      "description": "Databases and queues backing capture daemons",
      "serviceConfig": {}
    },
    "observability": {
      "description": "Monitoring that should remain responsive during contention",
      "serviceConfig": {
        "Slice": "system-critical.slice"
      }
    },
    "system": {
      "description": "Ordinary system services without Sinnix-specific placement",
      "serviceConfig": {}
    }
  },
  "commandClasses": {
    "agent": {
      "resourceClass": "interactive-agent",
      "slice": "agent.slice"
    },
    "build": {
      "resourceClass": "developer-build",
      "slice": "build.slice"
    },
    "background": {
      "resourceClass": "background-maintenance",
      "slice": "background.slice"
    },
    "nix-build": {
      "resourceClass": "developer-build",
      "slice": "nix-build.slice"
    }
  },
  "environmentAllowList": [],
  "slices": {
    "system": {
      "background": {},
      "nix-build": {},
      "system-critical": {}
    },
    "user": {
      "agent": {},
      "background": {},
      "build": {},
      "nix-build": {}
    }
  },
  "surfaces": {
    "sshd": {
      "unit": "sshd.service",
      "manager": "system",
      "kind": "service",
      "resourceClass": "interactive-access"
    },
    "sshd-socket": {
      "unit": "sshd.socket",
      "manager": "system",
      "kind": "socket",
      "resourceClass": "interactive-access"
    },
    "nix-gc": {
      "unit": "nix-gc.service",
      "manager": "system",
      "kind": "service",
      "resourceClass": "background-maintenance"
    },
    "nix-optimise": {
      "unit": "nix-optimise.service",
      "manager": "system",
      "kind": "service",
      "resourceClass": "background-maintenance"
    }
  },
  "observedServices": [],
  "captures": [],
  "mounts": [],
  "backups": {}
}"""
