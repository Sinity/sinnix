import QtQuick
import QtQuick.Controls

Button {
    id: control
    property string tone: "neutral"
    readonly property bool primary: tone === "primary"
    readonly property bool danger: tone === "danger"

    hoverEnabled: true
    leftPadding: 13
    rightPadding: 13
    topPadding: 7
    bottomPadding: 7
    implicitHeight: Math.max(34, implicitContentHeight + topPadding + bottomPadding)
    font.pixelSize: 13
    font.weight: primary ? Font.DemiBold : Font.Medium

    contentItem: Text {
        text: control.text
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        color: !control.enabled ? "#69717e" : control.primary ? "#102623"
               : control.danger ? "#ffb9bb" : "#e1e7ef"
    }
    background: Rectangle {
        radius: 8
        color: control.enabled && control.primary
               ? (control.down ? "#64b5a1" : control.hovered ? "#aff4df" : "#91ddc7")
               : control.down ? "#151920"
               : control.danger && control.hovered ? "#503038"
               : control.hovered ? "#323b48" : "#232a34"
        border.color: control.visualFocus ? "#b6e8da"
                      : control.danger ? "#603940" : control.primary && control.enabled ? color : "#353e4a"
    }
}
