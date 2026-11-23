import QtQuick
import QtQuick.Controls

// A keyboard key shown next to the control it triggers.
Label {
    property real u: 1
    property bool dark: false
    font.pixelSize: Math.round(11 * u)
    font.weight: Font.DemiBold
    color: dark ? "#0f2621" : "#c3ccd7"
    leftPadding: Math.round(6 * u)
    rightPadding: Math.round(6 * u)
    topPadding: Math.round(2 * u)
    bottomPadding: Math.round(2 * u)
    background: Rectangle {
        radius: Math.round(4 * parent.u)
        color: parent.dark ? "#22000000" : "#12ffffff"
        border.width: 1
        border.color: parent.dark ? "#440f2621" : "#22ffffff"
    }
}
