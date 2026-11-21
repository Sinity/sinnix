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
    signal preferred

    property color panel: "#191e26"
    property color borderColor: "#313947"
    property color mutedText: "#aebccc"
    property color accent: "#87cfb4"
    property bool videoVisible: false
    property bool previewOnly: false
    property real pendingFraction: -1
    property url playbackSource: ""
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
            video.stop();
            video.recenter();
            video.original = false;
        }
        videoVisible = false;
        playbackSource = "";
        pendingFraction = -1;
        imageZoom = 1;
        imageX = 0;
        imageY = 0;
    }

    function jump(fraction) {
        pane.activated();
        pendingFraction = fraction;
        videoVisible = true;
        playbackSource = info.media;
        if (video.duration > 0) {
            video.seek(pendingFraction * video.duration);
            pendingFraction = -1;
        }
        video.play();
    }

    function toggle() {
        if (info.kind !== "video")
            return;
        if (!videoVisible)
            jump(0);
        else if (video.playing)
            video.pause();
        else
            video.play();
    }

    property string identity: info.key || ""
    onIdentityChanged: reset()

    radius: 12
    color: panel
    border.color: active ? accent : borderColor
    border.width: 1

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
        anchors.margins: 14
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Label {
                text: pane.side === "left" ? "1" : "2"
                color: pane.accent
                font.pixelSize: 18
                font.bold: true
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                Label {
                    Layout.fillWidth: true
                    text: pane.info.label || "No item"
                    font.pixelSize: 19
                    font.bold: true
                    elide: Text.ElideRight
                    ToolTip.visible: hovered.hovered && truncated
                    ToolTip.text: text
                    HoverHandler { id: hovered }
                }
                Label {
                    Layout.fillWidth: true
                    visible: !!text
                    text: pane.info.details || ""
                    color: pane.mutedText
                    font.pixelSize: 13
                    elide: Text.ElideRight
                }
            }
            ToolButton {
                text: pane.focused ? "Restore" : "Focus"
                visible: !pane.previewOnly
                enabled: !!pane.info.key
                onClicked: pane.focusRequested()
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

            GridLayout {
                anchors.fill: parent
                anchors.margins: 8
                visible: pane.info.kind === "video" && !pane.videoVisible
                columns: content.width >= content.height * 16 / 9 ? 3 : 2
                columnSpacing: 7
                rowSpacing: 7
                Repeater {
                    model: pane.info.frames || []
                    delegate: Rectangle {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        Layout.preferredHeight: 1
                        color: "#263140"
                        radius: 5
                        clip: true

                        Image {
                            anchors.fill: parent
                            source: modelData.url || ""
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                            opacity: thumb.hovered ? 0.85 : 1
                        }
                        Label {
                            anchors.left: parent.left
                            anchors.bottom: parent.bottom
                            anchors.margins: 5
                            padding: 5
                            text: modelData.label
                            color: "#ffffff"
                            background: Rectangle { color: "#cc10141a"; radius: 4 }
                        }
                        Label {
                            anchors.centerIn: parent
                            visible: !modelData.url || thumb.hovered
                            text: "▶"
                            color: "#ffffff"
                            font.pixelSize: 24
                        }
                        HoverHandler { id: thumb }
                        TapHandler { onTapped: pane.jump(modelData.fraction) }
                    }
                }
            }

            VideoPane {
                id: video
                anchors.fill: parent
                visible: pane.videoVisible
                source: pane.playbackSource
                projection: pane.info.projection || ({})
                muted: pane.muted
                volume: 0.75
                onDurationChanged: {
                    if (duration > 0 && pane.pendingFraction >= 0) {
                        seek(pane.pendingFraction * duration);
                        pane.pendingFraction = -1;
                    }
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            visible: pane.info.kind === "video"
            columns: width >= 540 ? 2 : 1
            rowSpacing: 3
            RowLayout {
                Layout.fillWidth: true
                ToolButton {
                    text: video.playing ? "Pause" : "Play"
                    onClicked: { pane.activated(); pane.toggle(); }
                }
                Slider {
                    id: timeline
                    Layout.fillWidth: true
                    enabled: pane.videoVisible && video.duration > 0
                    from: 0
                    to: Math.max(video.duration, 1)
                    value: video.position
                    onMoved: video.seek(value)
                }
                Label {
                    text: pane.clock(pane.videoVisible ? video.position : 0) + " / "
                          + pane.clock((pane.videoVisible ? video.duration : 0) || pane.info.duration || 0)
                    color: pane.mutedText
                }
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                ToolButton {
                    text: "Frames"
                    visible: pane.videoVisible
                    onClicked: { video.pause(); pane.videoVisible = false; }
                }
                ToolButton {
                    text: video.original ? "Flatten" : "Original"
                    visible: pane.videoVisible && ["equirect", "fisheye"].includes(pane.info.projection?.projection)
                    onClicked: video.original = !video.original
                }
                ToolButton {
                    text: "Projection"
                    enabled: !!pane.info.path && !pane.rankController.busy
                    onClicked: {
                        const projection = pane.info.projection || {};
                        projectionMode.currentIndex = Math.max(0, projectionMode.indexOfValue(projection.projection));
                        stereoMode.currentIndex = Math.max(0, stereoMode.indexOfValue(projection.layout));
                        inputFov.value = projection.hfov || 180;
                        swap.checked = !!projection.swap;
                        correction.open();
                    }
                }
                ToolButton {
                    text: "Recenter"
                    visible: pane.videoVisible && ["equirect", "fisheye"].includes(pane.info.projection?.projection) && !video.original
                    onClicked: video.recenter()
                }
            }
        }

        Label {
            Layout.fillWidth: true
            visible: pane.videoVisible && !!video.playbackError
            text: video.playbackError
            color: "#fca1a9"
            wrapMode: Text.Wrap
        }

        RowLayout {
            Layout.fillWidth: true
            Button {
                objectName: pane.side + "Prefer"
                visible: !pane.previewOnly
                text: pane.side === "left" ? "Prefer left" : "Prefer right"
                enabled: pane.rankController.can_compare && !pane.rankController.busy
                highlighted: pane.active
                onClicked: pane.preferred()
            }
            ToolButton {
                text: "Reset zoom"
                visible: pane.info.kind === "image" && pane.imageZoom > 1
                onClicked: { pane.imageZoom = 1; pane.imageX = 0; pane.imageY = 0; }
            }
            Item { Layout.fillWidth: true }
            ToolButton {
                text: "Other versions (" + (pane.info.versions?.length || 0) + ")"
                visible: (pane.info.versions?.length || 0) > 0
                onClicked: pane.versionsRequested()
            }
        }
    }
}
