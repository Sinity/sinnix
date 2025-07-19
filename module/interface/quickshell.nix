# Quickshell Configuration
# Modern Qt/QML based status bar and widgets
# Structured for rapid development with modular components

{ pkgs, ... }:
let
  quickshellConfigFile = pkgs.writeText "shell.qml" ''
    import QtQuick
    import Quickshell
    import Quickshell.Io

    ShellRoot {
      QuickshellSettings {
        watchFiles: true  // Enable live config reloading
      }
      
      // Launcher Component
      component Launcher: Text {
        text: ""
        font.family: "SauceCodePro Nerd Font Mono"
        font.pointSize: 18
        font.weight: Font.DemiBold
        color: "#d5c4a1"
        
        MouseArea {
          anchors.fill: parent
          onClicked: launcherProcess.running = true
        }
        
        Process {
          id: launcherProcess
          command: ["tofi-drun", "--drun-launch=true"]
        }
      }

      // Clock Component
      component ClockWidget: Text {
        id: clockText
        font.family: "SauceCodePro Nerd Font Mono"
        font.pointSize: 16
        font.weight: Font.DemiBold
        color: "#d5c4a1"
        
        property bool showDate: false
        
        Timer {
          interval: 1000
          running: true
          repeat: true
          onTriggered: updateTime()
        }
        
        MouseArea {
          anchors.fill: parent
          onClicked: {
            showDate = !showDate
            updateTime()
          }
        }
        
        function updateTime() {
          var now = new Date()
          if (showDate) {
            text = "  " + now.toLocaleDateString(Qt.locale(), "dd/MM")
          } else {
            text = "  " + now.toLocaleTimeString(Qt.locale(), "HH:mm")
          }
        }
        
        Component.onCompleted: updateTime()
      }

      // System Monitor Component  
      component SystemMonitor: Text {
        id: monitorText
        
        property string monitorType: "cpu"
        property string displayText: monitorType.toUpperCase() + " --"
        
        text: displayText
        font.family: "SauceCodePro Nerd Font Mono"
        font.pointSize: 14
        font.weight: Font.DemiBold
        color: "#d5c4a1"
        
        Timer {
          interval: 2000
          running: true
          repeat: true
          onTriggered: updateMonitor()
        }
        
        Process {
          id: monitorProcess
          command: getCommand()
          
          Component.onCompleted: {
            finished.connect(function() {
              if (exitCode === 0) {
                var value = parseInt(stdout.trim())
                displayText = monitorType.toUpperCase() + " " + value + "%"
                
                // Color coding based on thresholds
                if (monitorType === "cpu") {
                  if (value > 90) monitorText.color = "#fb4934"      // Red
                  else if (value > 70) monitorText.color = "#fabd2f" // Yellow  
                  else monitorText.color = "#d5c4a1"                 // Normal
                } else if (monitorType === "memory") {
                  if (value > 85) monitorText.color = "#fb4934"      // Red
                  else if (value > 70) monitorText.color = "#fabd2f" // Yellow
                  else monitorText.color = "#d5c4a1"                 // Normal
                }
              }
            })
          }
        }
        
        function getCommand() {
          if (monitorType === "cpu") {
            return ["sh", "-c", "top -bn1 | grep 'Cpu(s)' | awk '{print int(100-$8)}'"]
          } else if (monitorType === "memory") {
            return ["sh", "-c", "free | grep Mem | awk '{printf \"%.0f\", $3/$2 * 100.0}'"]
          }
          return ["echo", "0"]
        }
        
        function updateMonitor() {
          monitorProcess.running = true
        }
      }

      // Volume Control Component
      component VolumeControl: Text {
        id: volText
        text: "VOL --"
        font.family: "SauceCodePro Nerd Font Mono"
        font.pointSize: 14
        font.weight: Font.DemiBold
        color: "#d5c4a1"
        
        Timer {
          interval: 1000
          running: true
          repeat: true
          onTriggered: volumeProcess.running = true
        }
        
        Process {
          id: volumeProcess
          command: ["pamixer", "--get-volume"]
          
          Component.onCompleted: {
            finished.connect(function() {
              if (exitCode === 0) {
                var vol = parseInt(stdout.trim())
                volText.text = "VOL " + vol + "%"
                volText.color = vol === 0 ? "#665c54" : "#d5c4a1"
              }
            })
          }
        }
        
        Process {
          id: toggleProcess
          command: ["pamixer", "-t"]
        }
        
        MouseArea {
          anchors.fill: parent
          onClicked: {
            toggleProcess.running = true
            // Refresh volume display after toggle
            volumeProcess.running = true
          }
        }
      }

      // Main Panel - Using internal components for rapid development
      PanelWindow {
        id: panel
        anchors {
          bottom: true
          left: true
          right: true
        }
        
        implicitHeight: 32
        color: "#282828"
        
        // Left section - launcher 
        Launcher {
          anchors.left: parent.left
          anchors.verticalCenter: parent.verticalCenter
          anchors.leftMargin: 12
        }
        
        // Center - clock
        ClockWidget {
          anchors.centerIn: parent
        }
        
        // Right section - system monitors
        Row {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          anchors.rightMargin: 12
          spacing: 16
          
          SystemMonitor { monitorType: "cpu" }
          SystemMonitor { monitorType: "memory" }
          VolumeControl {}
        }
      }
    }
  '';
in
{
  config = {
    home-manager.users.sinity = {
      # Quickshell systemd service
      systemd.user.services.quickshell = {
        Unit = {
          Description = "Quickshell status bar";
          After = [ "graphical-session.target" ];
          PartOf = [ "graphical-session.target" ];
          Wants = [ "graphical-session.target" ];
        };
        Service = {
          Type = "simple";
          ExecStart = "/etc/profiles/per-user/sinity/bin/quickshell";
          Restart = "on-failure";
          RestartSec = 2;
          Environment = [
            "QT_QPA_PLATFORM=wayland"
            "QML2_IMPORT_PATH=\${QML2_IMPORT_PATH:-}"
          ];
        };
        Install = {
          WantedBy = [ "graphical-session.target" ];
        };
      };
      
      # Create initial quickshell config for live development  
      xdg.configFile."quickshell/shell.qml".source = quickshellConfigFile;
      
      # Development convenience: alias for quick config editing
      home.shellAliases = {
        qs-edit = "$EDITOR ~/.config/quickshell/shell.qml";
        qs-reload = "systemctl --user restart quickshell";
      };
    };
  };
}