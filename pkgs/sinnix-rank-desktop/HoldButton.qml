import QtQuick
import QtQuick.Controls

// Permanent actions run only after the button is held for `holdTime`; the
// fill shows how far along the hold is and releasing early cancels it.
CompareButton {
    id: control
    property int holdTime: 600
    property real progress: 0
    signal held
    signal holdStarted

    tone: "danger"
    autoRepeat: false
    ToolTip.visible: hovered && !down
    ToolTip.delay: 400
    ToolTip.text: "Hold to delete permanently"

    onPressedChanged: {
        if (pressed) {
            holdStarted();
            fill.restart();
        } else {
            fill.stop();
            progress = 0;
        }
    }

    NumberAnimation on progress {
        id: fill
        running: false
        from: 0
        to: 1
        duration: control.holdTime
        onFinished: if (control.pressed) { control.progress = 0; control.held(); }
    }

    Rectangle {
        parent: control.background
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: parent.width * control.progress
        radius: parent.radius
        color: "#88d9535f"
    }
}
