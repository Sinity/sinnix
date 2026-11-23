import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One button style for the window. `u` scales it with the window, `keyHint`
// shows the keyboard shortcut beside the label, and `flat` drops the fill for
// controls that sit on top of media or in a header.
Button {
    id: control
    property string tone: "neutral"
    property real u: 1
    property string keyHint: ""
    readonly property bool primary: tone === "primary"
    readonly property bool danger: tone === "danger"

    hoverEnabled: true
    leftPadding: Math.round(12 * u)
    rightPadding: Math.round(12 * u)
    topPadding: Math.round(6 * u)
    bottomPadding: Math.round(6 * u)
    implicitHeight: Math.max(Math.round(32 * u), implicitContentHeight + topPadding + bottomPadding)
    font.pixelSize: Math.round(13 * u)
    font.weight: primary ? Font.DemiBold : Font.Medium

    readonly property color foreground: !enabled ? "#5f6875" : primary ? "#0f2621"
                                        : danger ? "#ffb9bb" : "#dfe6ee"

    contentItem: RowLayout {
        spacing: Math.round(8 * control.u)
        Text {
            Layout.fillWidth: true
            text: control.text
            font: control.font
            color: control.foreground
            horizontalAlignment: control.keyHint ? Text.AlignLeft : Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        KeyCap { visible: !!control.keyHint; text: control.keyHint; u: control.u; dark: control.primary }
    }
    background: Rectangle {
        radius: Math.round(7 * control.u)
        color: control.flat && !control.hovered && !control.down ? "transparent"
               : control.enabled && control.primary
               ? (control.down ? "#64b5a1" : control.hovered ? "#aff4df" : "#8fd9c2")
               : control.down ? "#12161c"
               : control.danger && control.hovered ? "#4a2a31"
               : control.hovered ? "#2c3440" : "#1e252e"
        border.width: control.flat && !control.visualFocus ? 0 : 1
        border.color: control.visualFocus ? "#b6e8da"
                      : control.danger ? "#5a363d" : control.primary && control.enabled ? color : "#2f3843"
    }
}
