{
  pkgs,
  inputs,
  ...
}:
let
  quickshellConfigFile = pkgs.writeText "shell.qml" ''
    import QtQuick
    import Quickshell
    import Quickshell.Io

    ShellRoot {
      QuickshellSettings {
        watchFiles: true
      }

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

      component CpuWidget: Text {
        id: cpuText
        font.family: "SauceCodePro Nerd Font Mono"
        font.pointSize: 14
        font.weight: Font.DemiBold
        color: "#d5c4a1"
        text: "CPU --%"

        Process {
          id: cpuSampler
          command: [
            "bash",
            "-lc",
            "prev_total=0; prev_idle=0; while true; do read cpu user nice system idle iowait irq softirq steal guest guest_nice < /proc/stat; total=$((user+nice+system+idle+iowait+irq+softirq+steal)); idle_all=$((idle+iowait)); if [ $prev_total -ne 0 ]; then totald=$((total-prev_total)); idled=$((idle_all-prev_idle)); if [ $totald -gt 0 ]; then usage=$((1000*(totald-idled)/totald)); printf '%s\\n' $usage; fi; fi; prev_total=$total; prev_idle=$idle_all; sleep 2; done"
          ]
          running: true
          stdout: SplitParser {
            splitMarker: "\n"
            onRead: function(line) {
              var raw = parseInt(line)
              if (!isNaN(raw)) {
                var value = Math.max(0, Math.min(100, Math.round(raw / 10)))
                cpuText.text = "CPU " + value + "%"
                cpuText.color = value > 90 ? "#fb4934" : (value > 70 ? "#fabd2f" : "#d5c4a1")
              }
            }
          }
          onRunningChanged: if (!running) restartTimer.restart()
          Timer {
            id: restartTimer
            interval: 2000
            repeat: false
            running: false
            onTriggered: cpuSampler.running = true
          }
        }
      }

      component MemoryWidget: Text {
        id: memText
        font.family: "SauceCodePro Nerd Font Mono"
        font.pointSize: 14
        font.weight: Font.DemiBold
        color: "#d5c4a1"
        text: "RAM --%"

        Process {
          id: memSampler
          command: [
            "bash",
            "-lc",
            "while true; do eval $(awk '/MemTotal/ {printf \"total=%d;\", $2} /MemAvailable/ {printf \"avail=%d;\", $2}' /proc/meminfo); used=$((total-avail)); if [ $total -gt 0 ]; then pct=$((1000*used/total)); printf '%s\\n' $pct; fi; sleep 3; done"
          ]
          running: true
          stdout: SplitParser {
            splitMarker: "\n"
            onRead: function(line) {
              var raw = parseInt(line)
              if (!isNaN(raw)) {
                var value = Math.max(0, Math.min(100, Math.round(raw / 10)))
                memText.text = "RAM " + value + "%"
                memText.color = value > 90 ? "#fb4934" : (value > 75 ? "#fabd2f" : "#d5c4a1")
              }
            }
          }
          onRunningChanged: if (!running) restartTimer.restart()
          Timer {
            id: restartTimer
            interval: 2000
            repeat: false
            running: false
            onTriggered: memSampler.running = true
          }
        }
      }

      component VolumeWidget: Text {
        id: volText
        font.family: "SauceCodePro Nerd Font Mono"
        font.pointSize: 14
        font.weight: Font.DemiBold
        color: "#d5c4a1"
        text: "VOL --%"

        Process {
          id: volumeWatcher
          command: [
            "bash",
            "-lc",
            "print_vol(){ if command -v pamixer >/dev/null 2>&1; then pamixer --get-volume; else wpctl get-volume @DEFAULT_AUDIO_SINK@ | awk '{print int(($2)*100 + 0.5)}'; fi; }\nprint_vol\npactl subscribe | while read -r line; do case $line in *'on sink'*|*'on server'* ) print_vol;; esac; done"
          ]
          running: true
          stdout: SplitParser {
            splitMarker: "\n"
            onRead: function(line) {
              var raw = parseInt(line)
              if (!isNaN(raw)) {
                var value = Math.max(0, Math.min(100, raw))
                volText.text = "VOL " + value + "%"
                volText.color = value === 0 ? "#665c54" : "#d5c4a1"
              }
            }
          }
          onRunningChanged: if (!running) restartTimer.restart()
          Timer {
            id: restartTimer
            interval: 2000
            repeat: false
            running: false
            onTriggered: volumeWatcher.running = true
          }
        }

        Process {
          id: toggleProcess
          command: ["pamixer", "-t"]
        }

        MouseArea {
          anchors.fill: parent
          onClicked: toggleProcess.running = true
        }
      }
    }
  '';
in
{
  systemd.user.services.quickshell = {
    Unit = {
      Description = "Quickshell status bar";
      After = [ "graphical-session.target" ];
      PartOf = [ "graphical-session.target" ];
      Wants = [ "graphical-session.target" ];
    };
    Service = {
      Type = "simple";
      ExecStart = "${
        inputs.quickshell.packages.${pkgs.stdenv.hostPlatform.system}.default
      }/bin/quickshell";
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

  xdg.configFile."quickshell/shell.qml".source = quickshellConfigFile;

  home.shellAliases = {
    qs-edit = "$EDITOR ~/.config/quickshell/shell.qml";
    qs-reload = "systemctl --user restart quickshell";
  };
}
