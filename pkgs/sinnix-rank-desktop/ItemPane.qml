import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: pane
    required property var rankController
    required property var info
    required property string side
    required property bool active
    required property bool focused
    required property bool muted
    signal activated
    signal focusRequested
    signal versionsRequested
    readonly property bool dialogOpen: correction.visible || options.visible
    readonly property var video: player.item
    TapHandler { onPressedChanged: if (pressed) pane.activated() }

    property color panel: "#1a2029"
    property color borderColor: "#303944"
    property color mutedText: "#aab6c5"
    property color accent: "#91ddc7"
    property bool videoVisible: false
    property bool previewOnly: false
    property real pendingFraction: -1

    property real imageZoom: 1
    property real imageX: 0
    property real imageY: 0

    function clock(milliseconds) {
        const seconds = Math.max(0, Math.floor(milliseconds / 1000));
        const minutes = Math.floor(seconds / 60);
        const fraction = seconds % 60;
        return minutes + ":" + (fraction < 10 ? "0" : "") + fraction;
    }

    function reset() {
        if (video) {
            seekTimer.stop();
            video.stop();
            video.recenter();
            video.original = false;
        }
        videoVisible = false;

        pendingFraction = -1;
        imageZoom = 1;
        imageX = 0;
        imageY = 0;
    }

    function jump(fraction) {
        pane.activated();
        pendingFraction = fraction;
        videoVisible = true;

        if (video && video.duration > 0) {
            video.seek(pendingFraction * video.duration);
            pendingFraction = -1;
        }
        if (video) video.play();
    }

    function toggle() {
        if (info.kind !== "video")
            return;
        if (!videoVisible)
            jump(0);
        else if (video && video.playing)
            video.pause();
        else
            video.play();
    }

    property string identity: info.key || ""
    onIdentityChanged: reset()

    radius: 0
    color: "#16191d"
    border.color: active ? accent : borderColor
    border.width: 0

    function setProjection() {
        pane.activated()
        const value = pane.info.projection || {}
        projectionMode.currentIndex = Math.max(0, projectionMode.indexOfValue(value.projection))
        stereoMode.currentIndex = Math.max(0, stereoMode.indexOfValue(value.layout))
        inputFov.value = value.hfov || 180
        swap.checked = !!value.swap
        correction.open()
    }

    Dialog {
        id: correction
        anchors.centerIn: Overlay.overlay
        width: 390
        modal: true
        title: "Video projection"
        standardButtons: Dialog.Save | Dialog.Cancel
        onAccepted: pane.rankController.correct_projection(pane.info.path, projectionMode.currentValue, stereoMode.currentValue,
                                                   inputFov.value, swap.checked)
        ColumnLayout {
            anchors.fill: parent
            RowLayout {
                Label { text: "Projection"; Layout.fillWidth: true }
                ComboBox {
                    id: projectionMode
                    textRole: "text"
                    valueRole: "value"
                    model: [
                        { text: "Automatic detection", value: "automatic" },
                        { text: "Flat", value: "flat" },
                        { text: "Equirectangular", value: "equirect" },
                        { text: "Fisheye", value: "fisheye" }
                    ]
                }
            }
            RowLayout {
                enabled: projectionMode.currentValue !== "automatic"
                Label { text: "Eyes"; Layout.fillWidth: true }
                ComboBox {
                    id: stereoMode
                    textRole: "text"
                    valueRole: "value"
                    model: [
                        { text: "Mono", value: "mono" },
                        { text: "Side by side", value: "sbs" },
                        { text: "Top and bottom", value: "tb" }
                    ]
                }
            }
            RowLayout {
                enabled: ["equirect", "fisheye"].includes(projectionMode.currentValue)
                Label { text: "Input field of view"; Layout.fillWidth: true }
                SpinBox { id: inputFov; from: 30; to: 360; editable: true }
            }
            CheckBox {
                id: swap
                text: "Swap eyes"
                enabled: stereoMode.currentValue !== "mono" && projectionMode.currentValue !== "automatic"
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 6
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                Label {
                    Layout.fillWidth: true
                    text: pane.info.label || "No item"
                    font.pixelSize: 15
                    font.bold: true
                    elide: Text.ElideRight
                    ToolTip.visible: hovered.hovered && truncated
                    ToolTip.text: text
                    HoverHandler { id: hovered }
                }
                Label {
                    Layout.fillWidth: true
                    visible: !!text
                    text: pane.info.size_label || ""
                    font.bold: true
                    color: pane.mutedText
                    font.pixelSize: 17
                    elide: Text.ElideRight
                }
            }
            CompareButton {
                visible: pane.info.kind === "video" && pane.info.projection?.projection === "unknown"
                text: "Set projection"
                onClicked: pane.setProjection()
            }
            CompareButton {
                text: "Options"
                onClicked: { pane.activated(); options.open() }
                Menu {
                    id: options
                    MenuItem { text: pane.focused ? "Show both" : "Expand"; onTriggered: pane.focusRequested() }
                    MenuItem { text: "Projection and eyes"; enabled: pane.info.kind === "video"; onTriggered: pane.setProjection() }
                    MenuItem { text: "Other versions"; enabled: !!pane.info.versions?.length; onTriggered: pane.versionsRequested() }
                    MenuItem { text: "Original view"; checkable: true; enabled: !!pane.video; checked: pane.video?.original || false; onTriggered: pane.video.original = checked }
                    MenuItem { text: "Recenter"; enabled: !!pane.video; onTriggered: pane.video.recenter() }
                    MenuItem { text: "Reset zoom"; enabled: pane.imageZoom > 1; onTriggered: { pane.imageZoom = 1; pane.imageX = 0; pane.imageY = 0 } }
                }
            }
        }

        Rectangle {
            id: content
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#10141a"
            radius: 8
            clip: true

            Label {
                anchors.centerIn: parent
                visible: !pane.info.key
                text: "Waiting for an item"
                color: pane.mutedText
            }

            Image {
                id: still
                anchors.centerIn: parent
                width: content.width * pane.imageZoom
                height: content.height * pane.imageZoom
                transform: Translate { x: pane.imageX; y: pane.imageY }
                visible: pane.info.kind === "image"
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                source: visible ? pane.info.media : ""
                DragHandler {
                    target: null
                    enabled: still.visible && pane.imageZoom > 1
                    property vector2d last: Qt.vector2d(0, 0)
                    onActiveChanged: last = activeTranslation
                    onActiveTranslationChanged: {
                        if (active) {
                            const xLimit = Math.max(0, (still.width - content.width) / 2);
                            const yLimit = Math.max(0, (still.height - content.height) / 2);
                            pane.imageX = Math.max(-xLimit, Math.min(xLimit, pane.imageX + activeTranslation.x - last.x));
                            pane.imageY = Math.max(-yLimit, Math.min(yLimit, pane.imageY + activeTranslation.y - last.y));
                        }
                        last = activeTranslation;
                    }
                }
                WheelHandler {
                    enabled: still.visible
                    target: null
                    onWheel: event => {
                        pane.activated();
                        pane.imageZoom = Math.max(1, Math.min(6, pane.imageZoom * Math.pow(1.15, event.angleDelta.y / 120)));
                        if (pane.imageZoom === 1) {
                            pane.imageX = 0;
                            pane.imageY = 0;
                        }
                    }
                }
            }

            ScrollView {
                anchors.fill: parent
                anchors.margins: 18
                visible: pane.info.kind === "text"
                clip: true
                contentWidth: availableWidth
                TextArea {
                    text: pane.info.text || ""
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.Wrap
                    readOnly: true
                    selectByMouse: true
                    color: "#edf1f5"
                    font.pixelSize: 18
                    background: null
                }
            }

            Loader {
                id: player
                active: pane.videoVisible
                anchors.fill: parent
                anchors.bottomMargin: active ? Math.min(content.height / 4, 75) : 0
                sourceComponent: VideoPane {
                    source: pane.info.media || ""
                    projection: pane.info.projection || ({})
                    muted: pane.muted
                    volume: 0.75
                    onDurationChanged: {
                        if (duration > 0 && pane.pendingFraction >= 0) {
                            seek(pane.pendingFraction * duration)
                            pane.pendingFraction = -1
                        }
                    }
                    Component.onCompleted: play()
                }
            }

            Grid {
                id: grid
                function tile(c) {
                    return Math.min((content.width - (c - 1) * spacing) / c,
                        (content.height - (6/c - 1) * spacing) / (6/c) * 16/9)
                }
                columns: pane.videoVisible ? 6 : [1,2,3,6].reduce((best,c) => tile(c) > tile(best) ? c : best, 1)
                spacing: 3
                property real cellWidth: Math.max(1,pane.videoVisible ? (content.width-5*spacing)/6 : tile(columns))
                property real cellHeight: pane.videoVisible ? Math.min(player.anchors.bottomMargin - spacing,cellWidth*9/16) : cellWidth*9/16
                anchors.horizontalCenter: parent.horizontalCenter
                y: pane.videoVisible ? content.height-height : (content.height-height)/2
                visible: pane.info.kind === "video"
                Repeater {
                    model: pane.info.kind === "video" ? 6 : 0
                    delegate: Rectangle {
                        id: tile
                        required property int index
                        property var moment: pane.info.frames?.[index] || ({})
                        property var frame
                        function refresh() {
                            frame = moment.pct ? pane.rankController.frame(pane.info.path, moment.pct) : ({})
                        }
                        onMomentChanged: refresh()
                        Component.onCompleted: refresh()
                        Connections {
                            target: pane.rankController
                            function onFrame_changed(path, pct) {
                                if (path === pane.info.path && pct === tile.moment.pct) tile.refresh()
                            }
                        }
                        width: grid.cellWidth
                        height: grid.cellHeight
                        color: "#24282d"
                        Image {
                            id: image
                            anchors.fill: parent
                            source: tile.frame?.url || ""
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                        }
                        Rectangle { anchors.fill: parent; color: "transparent"; border.width: hover.hovered ? 2 : 0; border.color: pane.accent }
                        HoverHandler { id: hover }
                        Label {
                            anchors.left: parent.left
                            anchors.bottom: parent.bottom
                            padding: 3
                            font.family: "monospace"
                            font.pixelSize: 12
                            text: tile.moment.label || ""
                            background: Rectangle { color: "#cb121518" }
                        }
                        TapHandler { onTapped: pane.jump(tile.moment.fraction) }
                        Button {
                            anchors.centerIn: parent
                            visible: tile.frame?.failed || image.status === Image.Error
                            text: "Retry"
                            onClicked: pane.rankController.retry_frames(pane.info.path)
                        }
                    }
                }
            }
        }
        RowLayout {
            visible: pane.videoVisible
            Layout.fillWidth: true
            CompareButton { text: "Back to frames"; onClicked: pane.reset() }
            CompareButton { text: pane.video?.playing ? "Pause" : "Play"; onClicked: pane.toggle() }
            Slider {
                id: timeline
                Layout.fillWidth: true
                to: Math.max(1,pane.video?.duration || 0)
                value: pane.video?.position || 0
                onMoved: { pane.activated(); seekTimer.targetTime = value; if (!seekTimer.running) seekTimer.start() }
                Timer {
                    id: seekTimer
                    interval: 40
                    property real targetTime
                    onTriggered: if (pane.video) pane.video.seek(targetTime)
                }
            }
            Label { text: pane.clock(timeline.pressed || seekTimer.running ? timeline.value : (pane.video?.position || 0)); font.family: "monospace" }
        }
        Label { visible: !!pane.video?.playbackError; text: pane.video?.playbackError || ""; color: "#fca1a9" }
    }
}
