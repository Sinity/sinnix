import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts

ApplicationWindow {
    id: window
    objectName: "rankWindow"
    width: 1440
    height: 870
    minimumWidth: 790
    minimumHeight: 540
    visible: true
    color: "#0b0e12"
    font.family: "Inter"
    font.pixelSize: Math.round(14 * u)
    title: controller.window_title

    // Everything is sized in units of `u`, so a 4K output at scale 1 gets the
    // same proportions as a 1080p one.
    readonly property real u: Math.max(1, Math.min(width / 1700, height / 1000))
    readonly property color mutedText: "#9aa7b6"
    readonly property color strongText: "#eef2f6"
    readonly property color accent: "#8fd9c2"

    property var rankController: controller
    property string activeSide: "left"
    property string focusedSide: ""
    property bool leftMuted: false
    property bool rightMuted: true
    property string versionSide: "left"
    property var deleteKeys: []

    readonly property var scopes: [
        { title: "VR", value: "vr" },
        { title: "Non-VR", value: "flat" },
        { title: "Needs review", value: "unknown" },
        { title: "All files", value: "all" }
    ]
    readonly property var orders: [
        { title: "Largest first", value: "largest", help: "Biggest files first. The preferred file stays for the next pair." },
        { title: "Most informative", value: "informative", help: "Each pair is chosen from the comparisons so far." }
    ]
    function titleOf(list, value) {
        const found = list.find(entry => entry.value === value);
        return found ? found.title : "";
    }

    function selectSide(side) {
        if (activeSide === side)
            return;
        activeSide = side;
        leftMuted = side !== "left";
        rightMuted = side !== "right";
    }

    function focusSide(side) {
        if (focusedSide === side) {
            focusedSide = "";
        } else {
            focusedSide = side;
            selectSide(side);
        }
    }

    function activePane() { return activeSide === "left" ? left : right }

    readonly property bool dialogsOpen: sources.visible || versions.visible || versionPreview.visible
        || left.dialogOpen || right.dialogOpen || sessionMenu.visible || keysHelp.visible

    function pairAction(action, keys, ids) {
        controller.decide(keys[0], keys[1], keys[2], action, ids || [])
    }
    function pairKeys() { return [controller.epoch, left.identity, right.identity] }

    Timer { id: secondClick; interval: Qt.styleHints.mouseDoubleClickInterval }
    component Decision: CompareButton {
        required property string decision
        property var keys: []
        property var files: []
        property var pressedFiles: []
        u: window.u
        enabled: !controller.busy
        onPressed: { keys = window.pairKeys(); pressedFiles = files.slice() }
        onClicked: {
            if (!secondClick.running) {
                secondClick.start()
                window.pairAction(decision, keys, pressedFiles)
            }
        }
    }

    // The choice, in the rail between the two items: a large target per side,
    // labelled with its keys, that flashes when it records.
    component Choice: AbstractButton {
        id: choice
        required property string decision
        property var keys: []
        function pulse() { flashAnimation.restart() }
        hoverEnabled: true
        enabled: controller.can_compare && !controller.busy
        implicitHeight: Math.round(112 * window.u)
        onPressed: keys = window.pairKeys()
        onClicked: {
            if (!secondClick.running) {
                secondClick.start()
                pulse()
                window.pairAction(decision, keys)
            }
        }
        background: Rectangle {
            radius: Math.round(12 * window.u)
            color: !choice.enabled ? "#141920"
                   : choice.down ? "#5fae9a" : choice.hovered ? "#2b5b50" : "#1d3a34"
            border.width: 1
            border.color: choice.enabled ? (choice.hovered ? "#8fd9c2" : "#2f5d53") : "#20262e"
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                color: "#8fd9c2"
                opacity: 0
                SequentialAnimation on opacity {
                    id: flashAnimation
                    running: false
                    NumberAnimation { to: 0.55; duration: 60 }
                    NumberAnimation { to: 0; duration: 380; easing.type: Easing.OutCubic }
                }
            }
        }
        contentItem: ColumnLayout {
            spacing: Math.round(4 * window.u)
            Label {
                Layout.alignment: Qt.AlignHCenter
                text: choice.decision === "left" ? "←" : "→"
                font.pixelSize: Math.round(30 * window.u)
                color: choice.enabled ? "#dff7ef" : "#4f5864"
            }
            Label {
                Layout.alignment: Qt.AlignHCenter
                text: choice.decision === "left" ? "Prefer left" : "Prefer right"
                font.pixelSize: Math.round(15 * window.u)
                font.weight: Font.DemiBold
                color: choice.enabled ? "#dff7ef" : "#4f5864"
            }
            KeyCap {
                Layout.alignment: Qt.AlignHCenter
                text: choice.decision === "left" ? "← or 1" : "→ or 2"
                u: window.u
            }
        }
    }

    component Card: Rectangle {
        default property alias content: inner.data
        property alias spacing: inner.spacing
        Layout.fillWidth: true
        implicitHeight: inner.implicitHeight + Math.round(24 * window.u)
        radius: Math.round(10 * window.u)
        color: "#10141a"
        ColumnLayout {
            id: inner
            anchors.fill: parent
            anchors.margins: Math.round(12 * window.u)
            spacing: Math.round(8 * window.u)
        }
    }
    component Heading: Label {
        color: window.mutedText
        font.pixelSize: Math.round(11 * window.u)
        font.weight: Font.DemiBold
        font.capitalization: Font.AllUppercase
        font.letterSpacing: 0.6
    }

    function choose(side) {
        const target = side === "left" ? leftChoice : rightChoice;
        if (!controller.can_compare || controller.busy)
            return;
        target.pulse();
        pairAction(side, pairKeys());
    }

    palette.window: "#10141a"
    palette.windowText: "#eef2f6"
    palette.base: "#151b22"
    palette.alternateBase: "#1e252e"
    palette.text: "#eef2f6"
    palette.button: "#1e252e"
    palette.buttonText: "#eef2f6"
    palette.highlight: "#8fd9c2"
    palette.highlightedText: "#10141a"
    palette.mid: "#2f3843"
    palette.dark: "#0b0e12"
    palette.light: "#2c3440"
    palette.disabled.text: "#5f6875"
    palette.disabled.buttonText: "#5f6875"

    Popup {
        id: sessionMenu
        objectName: "sessionMenu"
        parent: sessionCard
        x: Math.round((sessionCard.width - width) / 2)
        y: sessionCard.height + Math.round(6 * window.u)
        padding: Math.round(14 * window.u)
        width: Math.round(460 * window.u)
        background: Rectangle { color: "#161b22"; radius: Math.round(10 * window.u); border.color: "#2f3843" }

        component Segment: CompareButton {
            required property var entry
            required property bool chosen
            u: window.u
            Layout.fillWidth: true
            tone: chosen ? "primary" : "neutral"
            text: entry.title
        }
        contentItem: ColumnLayout {
            spacing: Math.round(10 * window.u)
            Heading { text: "Collection" }
            RowLayout {
                Layout.fillWidth: true
                Label {
                    Layout.fillWidth: true
                    text: controller.title
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                CompareButton { u: window.u; text: "Refresh"; enabled: !controller.busy; onClicked: { sessionMenu.close(); controller.refresh() } }
                CompareButton { u: window.u; text: "Open…"; keyHint: "Ctrl O"; onClicked: { sessionMenu.close(); sources.open() } }
            }
            Heading { text: "Show"; visible: controller.can_scope }
            RowLayout {
                visible: controller.can_scope
                Layout.fillWidth: true
                spacing: Math.round(6 * window.u)
                Repeater {
                    model: window.scopes
                    Segment {
                        required property var modelData
                        entry: modelData
                        chosen: controller.scope === modelData.value
                        enabled: !controller.busy
                        onClicked: controller.set_scope(modelData.value)
                    }
                }
            }
            Heading { text: "Order" }
            Repeater {
                model: window.orders
                ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: Math.round(3 * window.u)
                    Segment {
                        entry: modelData
                        chosen: controller.order === modelData.value
                        enabled: !controller.busy
                        onClicked: controller.set_order(modelData.value)
                    }
                    Label {
                        Layout.fillWidth: true
                        text: modelData.help
                        wrapMode: Text.Wrap
                        color: window.mutedText
                        font.pixelSize: Math.round(12 * window.u)
                    }
                }
            }
        }
    }

    Popup {
        id: keysHelp
        objectName: "keysHelp"
        anchors.centerIn: Overlay.overlay
        modal: true
        padding: Math.round(20 * window.u)
        background: Rectangle { color: "#161b22"; radius: Math.round(10 * window.u); border.color: "#2f3843" }
        contentItem: GridLayout {
            columns: 2
            columnSpacing: Math.round(24 * window.u)
            rowSpacing: Math.round(8 * window.u)
            Repeater {
                model: [
                    ["← or 1", "Prefer left"], ["→ or 2", "Prefer right"], ["T", "Tie"], ["S", "Skip"],
                    ["U", "Undo"], ["Tab", "Switch sound and keys to the other side"],
                    ["Space", "Play or pause"], ["J / L", "Back or forward 10 seconds"],
                    ["F", "Expand the side, or show both"], ["Esc", "Back to frames"],
                    ["Ctrl O", "Open a collection"], ["Drag along the strip", "Scrub through the video"]
                ]
                delegate: RowLayout {
                    required property var modelData
                    Layout.columnSpan: 2
                    spacing: Math.round(16 * window.u)
                    KeyCap { text: modelData[0]; u: window.u; Layout.preferredWidth: Math.round(150 * window.u) }
                    Label { text: modelData[1] }
                }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Math.round(8 * window.u)
        spacing: Math.round(8 * window.u)

        ItemPane {
            id: left
            objectName: "leftPane"
            Layout.fillHeight: true
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            visible: window.focusedSide !== "right"
            u: window.u
            rankController: window.rankController
            canDelete: controller.can_delete
            info: controller.left
            side: "left"
            active: window.activeSide === side
            focused: window.focusedSide === side
            muted: window.leftMuted
            onActivated: window.selectSide(side)
            onFocusRequested: window.focusSide(side)
            onVersionsRequested: { window.versionSide = side; versions.open() }
            onDeletePressed: window.deleteKeys = window.pairKeys()
            onDeleteHeld: window.pairAction("delete", window.deleteKeys, [controller.left.id])
        }
        // The rail: the session, the pair's facts side by side, the choice,
        // what comes next and what this sitting has done.
        ColumnLayout {
            id: rail
            Layout.fillHeight: true
            Layout.preferredWidth: Math.round(300 * window.u)
            Layout.maximumWidth: Math.round(300 * window.u)
            spacing: Math.round(8 * window.u)

            Card {
                id: sessionCard
                spacing: Math.round(6 * window.u)
                // Source, filter and order change once per sitting, so they
                // share one control that opens one menu.
                AbstractButton {
                    id: sessionButton
                    Layout.fillWidth: true
                    hoverEnabled: true
                    implicitHeight: sessionText.implicitHeight + Math.round(8 * window.u)
                    onClicked: controller.title ? sessionMenu.open() : sources.open()
                    background: Rectangle {
                        radius: Math.round(6 * window.u)
                        color: sessionButton.hovered ? "#1b2129" : "transparent"
                    }
                    contentItem: ColumnLayout {
                        id: sessionText
                        spacing: Math.round(2 * window.u)
                        Label {
                            Layout.fillWidth: true
                            text: (controller.title || "Open a collection") + "  ▾"
                            font.pixelSize: Math.round(15 * window.u)
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: !!controller.title
                            text: [controller.can_scope ? window.titleOf(window.scopes, controller.scope) : "",
                                   window.titleOf(window.orders, controller.order)].filter(t => t).join(" · ")
                            color: window.mutedText
                            font.pixelSize: Math.round(13 * window.u)
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    visible: controller.progress_fraction >= 0
                    implicitHeight: Math.max(3, Math.round(4 * window.u))
                    radius: height / 2
                    color: "#1e252e"
                    Rectangle {
                        width: parent.width * Math.max(0, controller.progress_fraction)
                        height: parent.height
                        radius: parent.radius
                        color: window.accent
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        Layout.fillWidth: true
                        text: controller.progress_label
                        color: window.mutedText
                        font.pixelSize: Math.round(12 * window.u)
                        elide: Text.ElideRight
                    }
                    BusyIndicator {
                        running: controller.busy
                        visible: running
                        implicitWidth: Math.round(20 * window.u)
                        implicitHeight: implicitWidth
                    }
                    CompareButton { u: window.u; flat: true; text: "Keys"; keyHint: "?"; onClicked: keysHelp.open() }
                }
                Label {
                    Layout.fillWidth: true
                    visible: controller.tally.compared > 0 || controller.tally.deleted > 0
                    text: [controller.tally.compared ? controller.tally.compared + " compared" : "",
                           controller.tally.deleted ? controller.tally.deleted + " deleted" : "",
                           controller.tally.freed_label ? controller.tally.freed_label + " freed" : ""]
                          .filter(t => t).join(" · ")
                    color: window.strongText
                    font.pixelSize: Math.round(13 * window.u)
                    wrapMode: Text.Wrap
                }
            }

            Card {
                visible: controller.comparison.length > 0
                spacing: Math.round(2 * window.u)
                Repeater {
                    model: controller.comparison
                    delegate: ColumnLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 0
                        Heading {
                            Layout.alignment: Qt.AlignHCenter
                            Layout.topMargin: Math.round(4 * window.u)
                            text: modelData.label
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                text: modelData.left
                                elide: Text.ElideRight
                                color: modelData.winner === "left" ? window.accent
                                       : modelData.winner ? window.mutedText : window.strongText
                                font.weight: modelData.winner === "left" ? Font.DemiBold : Font.Normal
                                font.pixelSize: Math.round(14 * window.u)
                            }
                            Label {
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                horizontalAlignment: Text.AlignRight
                                text: modelData.right
                                elide: Text.ElideLeft
                                color: modelData.winner === "right" ? window.accent
                                       : modelData.winner ? window.mutedText : window.strongText
                                font.weight: modelData.winner === "right" ? Font.DemiBold : Font.Normal
                                font.pixelSize: Math.round(14 * window.u)
                            }
                        }
                    }
                }
            }

            Card {
                visible: controller.failed
                color: "#3a1f25"
                Label {
                    Layout.fillWidth: true
                    text: controller.message
                    color: "#fcc3c8"
                    wrapMode: Text.Wrap
                    font.pixelSize: Math.round(13 * window.u)
                }
            }

            Item { Layout.fillHeight: true }

            Card {
                visible: !!controller.upcoming.label
                spacing: Math.round(6 * window.u)
                Heading { text: "Next up" }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: width * 9 / 16
                    radius: Math.round(6 * window.u)
                    color: "#0b0e12"
                    clip: true
                    Image {
                        anchors.fill: parent
                        source: controller.upcoming.frame || ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize.width: Math.ceil(parent.width)
                    }
                }
                Label {
                    Layout.fillWidth: true
                    text: controller.upcoming.label || ""
                    elide: Text.ElideMiddle
                    font.pixelSize: Math.round(13 * window.u)
                }
                Label {
                    text: controller.upcoming.size_label || ""
                    color: window.mutedText
                    font.pixelSize: Math.round(12 * window.u)
                }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: Math.round(8 * window.u)
                rowSpacing: Math.round(8 * window.u)
                Choice { id: leftChoice; objectName: "leftPrefer"; decision: "left"; Layout.fillWidth: true; Layout.preferredWidth: 1 }
                Choice { id: rightChoice; objectName: "rightPrefer"; decision: "right"; Layout.fillWidth: true; Layout.preferredWidth: 1 }
                Decision { decision: "tie"; text: "Tie"; keyHint: "T"; Layout.fillWidth: true; Layout.preferredWidth: 1; enabled: controller.can_compare && !controller.busy }
                Decision { decision: "skip"; text: "Skip"; keyHint: "S"; Layout.fillWidth: true; Layout.preferredWidth: 1; enabled: !!(left.identity || right.identity) && !controller.busy }
            }

            Card {
                visible: controller.recent.length > 0
                spacing: Math.round(4 * window.u)
                Heading { text: "This sitting" }
                Repeater {
                    model: controller.recent.slice(0, 5)
                    delegate: RowLayout {
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        Label {
                            Layout.fillWidth: true
                            text: modelData.text
                            elide: Text.ElideMiddle
                            color: index === 0 ? window.strongText : window.mutedText
                            font.pixelSize: Math.round(13 * window.u)
                        }
                        Decision {
                            visible: index === 0 && controller.can_undo
                            decision: "undo"
                            text: "Undo"
                            keyHint: "U"
                            flat: true
                            enabled: controller.can_undo && !controller.busy
                        }
                    }
                }
            }
        }

        ItemPane {
            id: right
            objectName: "rightPane"
            Layout.fillHeight: true
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            visible: window.focusedSide !== "left"
            u: window.u
            rankController: window.rankController
            canDelete: controller.can_delete
            info: controller.right
            side: "right"
            active: window.activeSide === side
            focused: window.focusedSide === side
            muted: window.rightMuted
            onActivated: window.selectSide(side)
            onFocusRequested: window.focusSide(side)
            onVersionsRequested: { window.versionSide = side; versions.open() }
            onDeletePressed: window.deleteKeys = window.pairKeys()
            onDeleteHeld: window.pairAction("delete", window.deleteKeys, [controller.right.id])
        }
    }

    Shortcut { autoRepeat: false; sequences: ["Left", "1"]; enabled: !window.dialogsOpen; onActivated: window.choose("left") }
    Shortcut { autoRepeat: false; sequences: ["Right", "2"]; enabled: !window.dialogsOpen; onActivated: window.choose("right") }
    Shortcut { autoRepeat: false; sequence: "T"; enabled: !window.dialogsOpen; onActivated: window.pairAction("tie", window.pairKeys()) }
    Shortcut { autoRepeat: false; sequence: "S"; enabled: !window.dialogsOpen; onActivated: window.pairAction("skip", window.pairKeys()) }
    Shortcut { autoRepeat: false; sequence: "U"; enabled: !window.dialogsOpen; onActivated: window.pairAction("undo", window.pairKeys()) }
    Shortcut { autoRepeat: false; sequence: "Tab"; enabled: !window.dialogsOpen && !window.focusedSide; onActivated: window.selectSide(window.activeSide === "left" ? "right" : "left") }
    Shortcut { autoRepeat: false; sequences: ["Space", "K"]; enabled: !window.dialogsOpen; onActivated: window.activePane().toggle() }
    Shortcut { sequence: "J"; enabled: !window.dialogsOpen; onActivated: window.activePane().nudge(-10) }
    Shortcut { sequence: "L"; enabled: !window.dialogsOpen; onActivated: window.activePane().nudge(10) }
    Shortcut { autoRepeat: false; sequence: "F"; enabled: !window.dialogsOpen; onActivated: window.focusSide(window.activeSide) }
    Shortcut { autoRepeat: false; sequence: "?"; enabled: !window.dialogsOpen; onActivated: keysHelp.open() }
    Shortcut { autoRepeat: false; sequence: "Escape"; enabled: !window.dialogsOpen; onActivated: { if (window.focusedSide) window.focusedSide = ""; else window.activePane().reset() } }
    Shortcut { autoRepeat: false; sequence: "Ctrl+O"; enabled: !window.dialogsOpen && !controller.busy; onActivated: sources.open() }

    Dialog {
        id: sources
        objectName: "sourcesDialog"
        anchors.centerIn: parent
        modal: true
        width: Math.min(window.width - 48, Math.round(560 * window.u))
        title: "Open a ranking collection"

        ColumnLayout {
            anchors.fill: parent
            spacing: Math.round(12 * window.u)
            Label {
                text: "Ranking domain"
                font.bold: true
            }
            RowLayout {
                Layout.fillWidth: true
                TextField {
                    id: domain
                    Layout.fillWidth: true
                    placeholderText: "Domain name"
                    onAccepted: if (text.trim()) { sources.close(); controller.open_domain(text.trim()); }
                }
                CompareButton {
                    u: window.u
                    text: "Open domain"
                    enabled: !!domain.text.trim() && !controller.busy
                    onClicked: { sources.close(); controller.open_domain(domain.text.trim()); }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                CompareButton { u: window.u; text: "Select files"; onClicked: fileDialog.open() }
                CompareButton { u: window.u; text: "Select folder"; onClicked: folderDialog.open() }
                CompareButton { u: window.u; text: "Open Stash"; onClicked: { sources.close(); controller.open_stash(); } }
            }
            Label {
                visible: recents.count > 0
                text: "Recent collections"
                font.bold: true
            }
            ListView {
                id: recents
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(Math.round(210 * window.u), contentHeight)
                clip: true
                model: controller.recents
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    width: ListView.view.width
                    text: modelData.label
                    onClicked: { sources.close(); controller.open_recent(index); }
                }
            }
        }
    }

    FileDialog {
        id: fileDialog
        title: "Select files to compare"
        fileMode: FileDialog.OpenFiles
        onAccepted: { sources.close(); controller.open_files(selectedFiles.map(file => String(file))); }
    }

    FolderDialog {
        id: folderDialog
        title: "Select a folder to compare"
        onAccepted: { sources.close(); controller.open_files([String(selectedFolder)]); }
    }

    Drawer {
        id: versions
        edge: window.versionSide === "left" ? Qt.LeftEdge : Qt.RightEdge
        width: Math.min(Math.round(640 * window.u), window.width * 0.6)
        height: window.height
        background: Rectangle { color: "#161b22" }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Math.round(16 * window.u)
            spacing: Math.round(12 * window.u)
            Label {
                text: "Versions of this scene"
                font.pixelSize: Math.round(20 * window.u)
                font.bold: true
            }
            ListView {
                Layout.fillHeight: true
                Layout.fillWidth: true
                clip: true
                spacing: Math.round(10 * window.u)
                model: (window.versionSide === "left" ? controller.left.versions : controller.right.versions) || []
                delegate: ColumnLayout {
                    required property var modelData
                    width: ListView.view.width
                    spacing: Math.round(5 * window.u)
                    Label { Layout.fillWidth: true; text: modelData.label; wrapMode: Text.Wrap; font.bold: true }
                    Label { Layout.fillWidth: true; text: modelData.details; wrapMode: Text.Wrap; color: window.mutedText }
                    Label { Layout.fillWidth: true; text: modelData.path; wrapMode: Text.WrapAnywhere; color: window.mutedText; font.pixelSize: Math.round(12 * window.u) }
                    RowLayout {
                        CompareButton {
                            u: window.u
                            text: "Play version"
                            onClicked: { controller.preview_version(modelData); versionPreview.open(); }
                        }
                        Item { Layout.fillWidth: true }
                        HoldButton {
                            id: versionDelete
                            property var keys: []
                            u: window.u
                            text: "Delete version · " + modelData.size_label
                            enabled: !controller.busy
                            onHoldStarted: keys = window.pairKeys()
                            onHeld: window.pairAction("delete", keys, [modelData.id])
                        }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: "#2a323d" }
                }
            }
        }
    }

    Dialog {
        id: versionPreview
        anchors.centerIn: parent
        width: window.width * 0.8
        height: window.height * 0.8
        title: "File version"
        modal: true
        onClosed: controller.close_preview()
        standardButtons: Dialog.Close
        ItemPane {
            anchors.fill: parent
            u: window.u
            rankController: window.rankController
            info: controller.preview
            side: "left"
            active: true
            focused: true
            previewOnly: true
            muted: false
            onIdentityChanged: if (identity) Qt.callLater(() => jump(0))
        }
    }

    DropArea {
        anchors.fill: parent
        onDropped: drop => {
            if (drop.hasUrls && !controller.busy)
                controller.open_files(drop.urls.map(url => String(url)));
        }
    }

    onClosing: (event) => { if (controller.busy) event.accepted = false; }
    Component.onCompleted: if (!controller.busy && !controller.title) sources.open()
}
