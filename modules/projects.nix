{
  lib,
  config,
  ...
}:
let
  inherit (lib) types mkOption;
  cfg = config.sinnix.projects;
in
{
  options.sinnix.projects = mkOption {
    type = types.submodule (
      { config, ... }:
      {
        options = {
          # Base directory for all ecosystem projects
          root = mkOption {
            type = types.str;
            default = "/realm/project";
            description = "Root directory containing all ecosystem projects.";
          };

          # Core data infrastructure
          lynchpin = mkOption {
            type = types.str;
            default = "${config.root}/sinity-lynchpin";
            description = ''
              Longitudinal activity analysis workspace. Central coordination layer
              that aggregates captures, exports, and libraries into warehouse views,
              dashboards, and narratives. The "alive" component of the ecosystem.
            '';
          };

          sinex = mkOption {
            type = types.str;
            default = "${config.root}/sinex";
            description = ''
              Event-driven data capture platform (the "sentient archive"). Satellite
              constellation architecture with NATS JetStream, PostgreSQL, TimescaleDB.
              Handles lossless universal capture with ULID keys and JSON schema.
            '';
          };

          polylogue = mkOption {
            type = types.str;
            default = "${config.root}/polylogue";
            description = ''
              AI chat export archiver (ChatGPT, Claude, Codex, Google AI Studio).
              Pure library for ingesting, normalizing, and querying conversation logs.
              No UI, no daemon—consumed by lynchpin.
            '';
          };

          # System configuration
          sinnix = mkOption {
            type = types.str;
            default = "${config.root}/sinnix";
            description = ''
              Declarative NixOS system configuration using flake-parts and devenv.
              Manages services, dotfiles, desktop environment (Hyprland + qutebrowser).
            '';
          };

          # Capture tools
          scribeTap = mkOption {
            type = types.str;
            default = "${config.root}/scribe-tap";
            description = ''
              Wayland-friendly keystroke mirror for Hyprland. Integrates with
              interception-tools pipeline, tags keystrokes with window context.
            '';
          };

          interceptBounce = mkOption {
            type = types.str;
            default = "${config.root}/intercept-bounce";
            description = ''
              Keyboard debouncing filter (removes switch bounce). Standalone
              Rust utility with detailed statistics on dropped events.
            '';
          };

          # Knowledge systems
          knowledgeExtract = mkOption {
            type = types.str;
            default = "${config.root}/knowledge-extract";
            description = ''
              Adaptive knowledge assessment engine for human-in-the-loop evaluation.
              Item generation via LLM, persistent store, FastAPI service + web UI.
            '';
          };

          knowledgebase = mkOption {
            type = types.str;
            default = "${config.root}/knowledgebase";
            description = ''
              Lifecycle-structured PKM vault (Obsidian-friendly). MOCs, projects,
              standardized frontmatter with CLI helpers for navigation/search.
            '';
          };

          # Supporting utilities
          pwrank = mkOption {
            type = types.str;
            default = "${config.root}/pwrank";
            description = ''
              Web-based ranking/preference elicitation tool. Flask + Vue frontend
              with Peewee ORM and JWT auth.
            '';
          };

          # Context bundles for LLM consumption
          contextBundles = mkOption {
            type = types.str;
            default = "${config.root}/_context-project-bundles";
            description = ''
              Pre-generated documentation bundles for each project (combined source,
              git logs, line-of-code analysis) for LLM context windows.
            '';
          };

          # Inactive/archived projects
          inactive = mkOption {
            type = types.str;
            default = "${config.root}/_inactive";
            description = "Directory containing archived or experimental projects.";
          };
        };
      }
    );
    default = { };
    description = ''
      Paths to ecosystem projects in the realm. These form a "monorepo-ish"
      constellation: separate Git repositories that are treated as a cohesive
      unit via standardized relative paths and unified NixOS configuration.
    '';
  };

  config = {
    # Export commonly-used project paths as environment variables
    # so scripts and services can reference them without hard-coding
    environment.variables = {
      LYNCHPIN_REPO_ROOT = cfg.lynchpin;
      SINEX_ROOT = cfg.sinex;
      POLYLOGUE_ROOT = cfg.polylogue;
      SINNIX_ROOT = cfg.sinnix;
      KNOWLEDGEBASE_ROOT = cfg.knowledgebase;
    };
  };
}
