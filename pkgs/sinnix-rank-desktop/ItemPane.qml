import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One side of the comparison: a header with the item's facts and its own
// actions, then the media. The choice itself lives in Main.qml.
Rectangle {
    id: pane
    required property var rankController
    required property var info
    required property string side
    required property bool active
    required property bool focused
    required property bool muted
    property real u: 1
    property bool canDelete: false
    property bool previewOnly: false
    signal activated
    signal focusRequested
    signal versionsRequested
    signal deletePressed
    signal deleteHeld
    readonly property bool dialogOpen: correction.visible || options.visible || commentDialog.visible
    readonly property var video: player.item
    TapHandler { onPressedChanged: if (pressed) pane.activated() }

    readonly property color mutedText: "#9aa7b6"
    readonly property color strongText: "#eef2f6"
    readonly property color accent: "#8fd9c2"
    property bool videoVisible: false
    property real pendingFraction: -1

    property real imageZoom: 1
    property real imageX: 0
    property real imageY: 0

    function clock(milliseconds) {
        const seconds = Math.max(0, Math.floor(milliseconds / 1000));
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor(seconds / 60) % 60;
        const rest = seconds % 60;
        const two = n => (n < 10 ? "0" : "") + n;
        return (hours ? hours + ":" + two(minutes) : minutes) + ":" + two(rest);
    }

    // Filenames arrive with separators for spaces; show words, keep the raw
    // name in the tooltip.
    function readable(label) {
        return String(label || "").replace(/\.[A-Za-z0-9]{2,4}$/, "").replace(/[_]+/g, " ").replace(/\s+/g, " ").trim();
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
        else if (video)
            video.play();
    }

    function nudge(seconds) {
        if (info.kind !== "video")
            return;
        if (!videoVisible || !video || video.duration <= 0) {
            jump(0);
            return;
        }
        video.seek(Math.max(0, Math.min(video.duration - 500, video.position + seconds * 1000)));
    }

    property string identity: info.key || ""
    onIdentityChanged: { reset(); grid.frameAspect = 0 }

    color: "#12161b"
    radius: Math.round(8 * u)

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
        id: commentDialog
        objectName: pane.side + "CommentDialog"
        anchors.centerIn: Overlay.overlay
        width: Math.round(600 * pane.u)
        modal: true
        title: "Video comment"
        property string fileKey
        property string fileLabel
        property bool saving: false
        closePolicy: saving ? Popup.NoAutoClose : Popup.CloseOnEscape
        onOpened: commentText.forceActiveFocus()

        function edit() {
            fileKey = pane.identity
            fileLabel = pane.info.label
            commentText.text = pane.rankController.file_comment(fileKey)
            open()
        }

        Connections {
            target: pane.rankController
            function onComment_saved(key) {
                if (key === commentDialog.fileKey) commentDialog.close()
            }
            function onChanged() {
                if (commentDialog.saving && !pane.rankController.busy)
                    commentDialog.saving = false
            }
        }

        contentItem: ColumnLayout {
            Label {
                Layout.fillWidth: true
                text: commentDialog.fileLabel
                elide: Text.ElideMiddle
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 180
                contentWidth: availableWidth
                TextArea {
                    id: commentText
                    objectName: pane.side + "CommentText"
                    Accessible.name: "Video comment"
                    placeholderText: "Write a comment about this video"
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.Wrap
                    readOnly: commentDialog.saving
                }
            }
            Label {
                Layout.fillWidth: true
                visible: pane.rankController.failed
                text: pane.rankController.message
                wrapMode: Text.Wrap
            }
        }
        footer: DialogButtonBox {
            Button {
                objectName: pane.side + "SaveComment"
                text: "Save"
                enabled: !pane.rankController.busy && pane.identity === commentDialog.fileKey
                onClicked: {
                    commentDialog.saving = true
                    pane.rankController.save_file_comment(commentDialog.fileKey, commentText.text)
                }
            }
            Button {
                text: "Cancel"
                enabled: !commentDialog.saving
                onClicked: commentDialog.close()
            }
        }
    }
    Dialog {
        id: correction
        anchors.centerIn: Overlay.overlay
        width: Math.round(390 * pane.u)
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
        anchors.margins: Math.round(8 * pane.u)
        spacing: Math.round(8 * pane.u)

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: false
            spacing: Math.round(8 * pane.u)

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: false
                spacing: Math.round(2 * pane.u)
                Label {
                    id: titleLabel
                    Layout.fillWidth: true
                    text: pane.readable(pane.info.label) || "No item"
                    font.pixelSize: Math.round(16 * pane.u)
                    font.weight: Font.DemiBold
                    color: pane.strongText
                    elide: Text.ElideMiddle
                    ToolTip.visible: titleHover.hovered
                    ToolTip.delay: 500
                    ToolTip.text: pane.info.path || pane.info.label || ""
                    HoverHandler { id: titleHover }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Math.round(10 * pane.u)
                    Label {
                        visible: !!text
                        text: pane.info.size_label || ""
                        font.pixelSize: Math.round(13 * pane.u)
                        font.weight: Font.DemiBold
                        color: pane.strongText
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: !!text
                        text: pane.info.details || ""
                        font.pixelSize: Math.round(13 * pane.u)
                        color: pane.mutedText
                        elide: Text.ElideRight
                    }
                    Label {
                        visible: pane.active && pane.info.kind === "video" && !pane.previewOnly
                        text: "Sound and keys"
                        font.pixelSize: Math.round(12 * pane.u)
                        color: pane.accent
                    }
                }
            }
            CompareButton {
                u: pane.u
                visible: !pane.previewOnly && (pane.info.versions?.length || 0) > 1
                flat: true
                text: (pane.info.versions?.length || 0) + " versions"
                onClicked: { pane.activated(); pane.versionsRequested() }
            }
            CompareButton {
                u: pane.u
                visible: pane.info.kind === "video" && pane.info.projection?.projection === "unknown"
                text: "Set projection"
                onClicked: pane.setProjection()
            }
            CompareButton {
                u: pane.u
                visible: !pane.previewOnly && !!pane.info.key
                flat: true
                text: pane.focused ? "Show both" : "Expand"
                keyHint: "F"
                onClicked: pane.focusRequested()
            }
            CompareButton {
                u: pane.u
                visible: !!pane.info.key
                flat: true
                text: "More"
                onClicked: { pane.activated(); options.open() }
                Menu {
                    id: options
                    y: parent.height
                    MenuItem { text: "Projection and eyes…"; enabled: pane.info.kind === "video"; onTriggered: pane.setProjection() }
                    MenuItem {
                        text: "Comment…"
                        enabled: pane.info.kind === "video" && !pane.rankController.busy
                        onTriggered: commentDialog.edit()
                    }
                    MenuItem { text: "Other versions…"; enabled: !!pane.info.versions?.length; onTriggered: pane.versionsRequested() }
                    MenuSeparator {}
                    MenuItem { text: "Original view"; checkable: true; enabled: !!pane.video; checked: pane.video?.original || false; onTriggered: pane.video.original = checked }
                    MenuItem { text: "Recenter view"; enabled: !!pane.video; onTriggered: pane.video.recenter() }
                    MenuItem { text: "Reset zoom"; enabled: pane.imageZoom > 1; onTriggered: { pane.imageZoom = 1; pane.imageX = 0; pane.imageY = 0 } }
                }
            }
            HoldButton {
                objectName: pane.side + "Delete"
                u: pane.u
                visible: pane.canDelete && !!pane.info.key
                enabled: !pane.rankController.busy
                text: "Delete · " + (pane.info.size_label || "0 B")
                onHoldStarted: pane.deletePressed()
                onHeld: pane.deleteHeld()
            }
        }

        Rectangle {
            id: content
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#0b0e12"
            radius: Math.round(6 * pane.u)
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
                anchors.margins: Math.round(24 * pane.u)
                visible: pane.info.kind === "text"
                clip: true
                contentWidth: availableWidth
                TextArea {
                    text: pane.info.text || ""
                    textFormat: TextEdit.PlainText
                    wrapMode: TextEdit.Wrap
                    readOnly: true
                    selectByMouse: true
                    color: pane.strongText
                    font.pixelSize: Math.round(18 * pane.u)
                    background: null
                }
            }

            Loader {
                id: player
                asynchronous: true
                active: pane.videoVisible
                anchors.fill: parent
                anchors.bottomMargin: active ? strip.height + strip.anchors.bottomMargin + grid.spacing : 0
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

            // Before playback the six moments fill the pane as a contact
            // sheet; during playback they shrink into a strip under the video
            // that doubles as its timeline: drag across it to scrub.
            Item {
                id: strip
                visible: pane.info.kind === "video"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.bottomMargin: pane.videoVisible ? controls.height : 0
                height: pane.videoVisible ? grid.cellHeight : parent.height

                Grid {
                    id: grid
                    // Cached frames may be cropped to one eye, so the first
                    // decoded frame decides the cell shape.
                    property real frameAspect: 0
                    readonly property real aspect: Math.max(0.3, frameAspect || Number(pane.info.aspect) || 16 / 9)
                    function tile(c) {
                        const rows = 6 / c;
                        return Math.min((content.width - (c - 1) * spacing) / c,
                            (content.height - (rows - 1) * spacing) / rows * aspect)
                    }
                    columns: pane.videoVisible ? 6 : [1, 2, 3, 6].reduce((best, c) => tile(c) > tile(best) ? c : best, 1)
                    spacing: Math.max(2, Math.round(3 * pane.u))
                    property real stripWidth: Math.max(1, (content.width - 5 * spacing) / 6)
                    property real cellWidth: pane.videoVisible
                        ? Math.min(stripWidth, content.height * 0.16 * aspect) : Math.max(1, tile(columns))
                    property real cellHeight: cellWidth / aspect
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.verticalCenter: pane.videoVisible ? undefined : parent.verticalCenter
                    anchors.bottom: pane.videoVisible ? parent.bottom : undefined
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
                            color: "#1b2027"
                            radius: Math.round(3 * pane.u)
                            Image {
                                id: poster
                                objectName: "stashPoster"
                                anchors.fill: parent
                                source: tile.index === 0 && image.status !== Image.Ready
                                        ? (pane.info.poster || "") : ""
                                visible: status === Image.Ready
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                sourceSize.width: Math.ceil(grid.cellWidth)
                            }
                            Image {
                                id: image
                                anchors.fill: parent
                                source: tile.frame?.url || ""
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                                onStatusChanged: if (status === Image.Ready && implicitHeight > 0 && !grid.frameAspect)
                                    grid.frameAspect = implicitWidth / implicitHeight
                            }
                            Rectangle {
                                anchors.fill: parent
                                color: "transparent"
                                radius: parent.radius
                                border.width: hover.hovered && !pane.videoVisible ? Math.max(2, Math.round(2 * pane.u)) : 0
                                border.color: pane.accent
                            }
                            HoverHandler { id: hover; enabled: !pane.videoVisible }
                            Label {
                                anchors.left: parent.left
                                anchors.bottom: parent.bottom
                                anchors.margins: Math.round(4 * pane.u)
                                padding: Math.round(3 * pane.u)
                                font.family: "monospace"
                                font.pixelSize: Math.round(12 * pane.u)
                                text: tile.moment.label || ""
                                color: pane.strongText
                                background: Rectangle { color: "#cc0b0e12"; radius: 3 }
                            }
                            TapHandler { enabled: !pane.videoVisible; onTapped: pane.jump(tile.moment.fraction) }
                            Button {
                                anchors.centerIn: parent
                                visible: tile.frame?.failed || image.status === Image.Error
                                text: "Retry"
                                onClicked: pane.rankController.retry_frames(pane.info.path)
                            }
                        }
                    }
                }

                // Timeline over the strip: the playhead, a drag to scrub
                // (keyframe seeks so it keeps up), a click to jump exactly.
                Item {
                    visible: pane.videoVisible
                    anchors.fill: grid
                    readonly property real fraction: pane.video && pane.video.duration > 0
                        ? (scrubber.active ? scrubber.fraction : pane.video.position / pane.video.duration) : 0
                    Rectangle {
                        x: parent.fraction * parent.width - width / 2
                        width: Math.max(2, Math.round(3 * pane.u))
                        height: parent.height
                        color: pane.accent
                    }
                    MouseArea {
                        id: scrubber
                        anchors.fill: parent
                        property bool active: pressed
                        property real fraction: 0
                        cursorShape: Qt.SizeHorCursor
                        function at(x) { return Math.max(0, Math.min(1, x / width)) }
                        onPressed: mouse => { pane.activated(); fraction = at(mouse.x); if (pane.video) pane.video.scrub(fraction * pane.video.duration) }
                        onPositionChanged: mouse => {
                            if (!pressed) return;
                            fraction = at(mouse.x);
                            seekTimer.targetTime = fraction * (pane.video?.duration || 0);
                            if (!seekTimer.running) seekTimer.start();
                        }
                        onReleased: mouse => { if (pane.video) pane.video.seek(at(mouse.x) * pane.video.duration) }
                    }
                    Timer {
                        id: seekTimer
                        interval: 40
                        property real targetTime
                        onTriggered: if (pane.video) pane.video.scrub(targetTime)
                    }
                }
            }

            RowLayout {
                id: controls
                visible: pane.videoVisible
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: visible ? implicitHeight + Math.round(8 * pane.u) : 0
                spacing: Math.round(6 * pane.u)
                CompareButton { u: pane.u; flat: true; text: "Frames"; keyHint: "Esc"; onClicked: pane.reset() }
                CompareButton { u: pane.u; flat: true; text: pane.video?.playing ? "Pause" : "Play"; keyHint: "Space"; onClicked: pane.toggle() }
                CompareButton { u: pane.u; flat: true; visible: content.width > 620 * pane.u; text: "−10 s"; keyHint: "J"; onClicked: pane.nudge(-10) }
                CompareButton { u: pane.u; flat: true; visible: content.width > 620 * pane.u; text: "+10 s"; keyHint: "L"; onClicked: pane.nudge(10) }
                Item { Layout.fillWidth: true }
                Label {
                    visible: !!pane.video?.playbackError
                    text: pane.video?.playbackError || ""
                    color: "#f0939a"
                    elide: Text.ElideRight
                    Layout.maximumWidth: content.width / 2
                }
                Label {
                    text: pane.clock(pane.video?.position || 0) + " / " + pane.clock(pane.video?.duration || pane.info.duration || 0)
                    font.family: "monospace"
                    font.pixelSize: Math.round(13 * pane.u)
                    color: pane.mutedText
                    rightPadding: Math.round(6 * pane.u)
                }
            }

            // The selected pane gets keyboard controls and sound.
            Rectangle {
                anchors.fill: parent
                visible: pane.active && !pane.previewOnly
                color: "transparent"
                radius: parent.radius
                border.width: Math.max(2, Math.round(2 * pane.u))
                border.color: pane.accent
                z: 10
            }
        }
    }
}
