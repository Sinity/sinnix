# Observability and Monitoring Module
# Prometheus, Grafana, and system monitoring for Sinex/Sinnix

{
  config,
  lib,
  pkgs,
  ...
}:
{
  config = {
    system.nixos.tags = [ "observability-v0.1" ];

    # Prometheus for metrics collection
    services.prometheus = {
      enable = true;
      listenAddress = "127.0.0.1";
      port = 9090;
      retentionTime = "30d";

      scrapeConfigs = [
        {
          job_name = "prometheus";
          static_configs = [ { targets = [ "localhost:9090" ]; } ];
        }
        {
          job_name = "node_exporter";
          static_configs = [ { targets = [ "localhost:9100" ]; } ];
        }
        {
          job_name = "postgres_exporter";
          static_configs = [ { targets = [ "localhost:9187" ]; } ];
        }
        # Sinex services - these ports match the TIM documentation
        {
          job_name = "sinex_unified_collector";
          metrics_path = "/metrics";
          static_configs = [ { targets = [ "localhost:2112" ]; } ];
          scrape_interval = "15s";
        }
        {
          job_name = "sinex_promo_worker";
          metrics_path = "/metrics";
          static_configs = [ { targets = [ "localhost:2113" ]; } ];
          scrape_interval = "15s";
        }
      ];

      exporters = {
        node = {
          enable = true;
          listenAddress = "127.0.0.1";
          port = 9100;
          enabledCollectors = [
            "systemd"
            "processes"
          ];
        };

        postgres = {
          enable = true;
          listenAddress = "127.0.0.1";
          port = 9187;
          # Uses default PostgreSQL connection via peer authentication
          runAsLocalSuperUser = true;
        };
      };
    };

    # Grafana for visualization and dashboards
    services.grafana = {
      enable = true;
      settings = {
        server = {
          http_addr = "127.0.0.1";
          http_port = 3000;
          domain = "localhost";
        };
        "auth.anonymous" = {
          enabled = true;
          org_name = "Sinex Exocortex";
          org_role = "Admin"; # For local development
        };
        # Disable user signup and use anonymous access for simplicity
        users = {
          allow_sign_up = false;
          auto_assign_org = true;
          auto_assign_org_role = "Viewer";
        };
      };

      provision = {
        enable = true;
        datasources.settings.datasources = [
          {
            name = "Prometheus-Sinex";
            type = "prometheus";
            access = "proxy";
            url = "http://localhost:${toString config.services.prometheus.port}";
            isDefault = true;
            jsonData = {
              httpMethod = "POST";
              prometheusType = "Prometheus";
              prometheusVersion = "2.40.0";
            };
          }
        ];

        dashboards.settings.providers = [
          {
            name = "Sinex Dashboards";
            orgId = 1;
            folder = "Sinex";
            type = "file";
            disableDeletion = false;
            updateIntervalSeconds = 10;
            allowUiUpdates = true;
            options.path = "/var/lib/grafana/dashboards";
          }
        ];
      };
    };

    # System packages for monitoring tools
    environment.systemPackages = with pkgs; [
      prometheus
      grafana
      # Command line tools for debugging
      prometheus-alertmanager # For future alerting
    ];

    # Deploy dashboard files
    environment.etc."grafana/dashboards/sinex-dashboard.json".source = ./sinex-dashboard.json;

    # Ensure Grafana can access the dashboard
    systemd.tmpfiles.rules = [
      "d /var/lib/grafana/dashboards 0755 grafana grafana"
      "L+ /var/lib/grafana/dashboards/sinex-dashboard.json - - - - /etc/grafana/dashboards/sinex-dashboard.json"
    ];

    # Enable PostgreSQL for the exporters to work
    # Note: This assumes PostgreSQL is already configured elsewhere
    assertions = [
      {
        assertion = config.services.postgresql.enable;
        message = "PostgreSQL must be enabled for postgres_exporter to work";
      }
    ];

    # User configuration for convenient access
    home-manager.users.sinity = {
      # Add monitoring shortcuts to shell aliases
      home.activation.createMonitoringAliases =
        config.home-manager.users.sinity.lib.dag.entryAfter [ "writeBoundary" ]
          ''
            mkdir -p $HOME/.local/bin

            # Create monitoring convenience scripts
            cat > $HOME/.local/bin/sinex-metrics << 'EOF'
            #!/usr/bin/env bash
            echo "🔍 Sinex Observability Stack"
            echo "Prometheus: http://localhost:9090"
            echo "Grafana: http://localhost:3000"
            echo ""
            echo "📊 Current Metrics Status:"
            curl -s http://localhost:9090/api/v1/targets | jq -r '.data.activeTargets[] | "\(.scrapePool): \(.health)"' 2>/dev/null || echo "Prometheus not accessible"
            EOF
            chmod +x $HOME/.local/bin/sinex-metrics

            cat > $HOME/.local/bin/sinex-logs << 'EOF'
            #!/usr/bin/env bash
            echo "📋 Sinex Service Logs"
            echo "Press Ctrl+C to exit, or choose a specific service:"
            echo "1) Unified Collector"
            echo "2) Promo Worker" 
            echo "3) Prometheus"
            echo "4) Grafana"
            echo "5) All services"
            read -p "Choice (1-5): " choice

            case $choice in
              1) journalctl -u sinex-unified-collector -f ;;
              2) journalctl -u sinex-promo-worker -f ;;
              3) journalctl -u prometheus -f ;;
              4) journalctl -u grafana -f ;;
              5) journalctl -u prometheus -u grafana -u sinex-unified-collector -u sinex-promo-worker -f ;;
              *) echo "Invalid choice" ;;
            esac
            EOF
            chmod +x $HOME/.local/bin/sinex-logs
          '';

      home.sessionVariables = {
        # Make monitoring tools easily accessible
        PROMETHEUS_URL = "http://localhost:9090";
        GRAFANA_URL = "http://localhost:3000";
      };
    };

    # Firewall configuration for local access
    networking.firewall = {
      # Only allow local access to monitoring services
      allowedTCPPorts = [ ];
      interfaces.lo.allowedTCPPorts = [
        3000
        9090
        9100
        9187
      ];
    };

    # Optional: Systemd services configuration for Sinex monitoring
    systemd.services = {
      # Example service health monitoring
      prometheus.serviceConfig = {
        # Restart policy for reliability
        Restart = lib.mkForce "always";
        RestartSec = "10s";
      };

      grafana.serviceConfig = {
        Restart = lib.mkForce "always";
        RestartSec = "10s";
      };
    };
  };
}
