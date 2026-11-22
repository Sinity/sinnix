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
    color: "#111419"
    font.family: "Inter"
    font.pixelSize: 14
    title: controller.title ? controller.title + " · Compare" : "Compare"

    property var rankController: controller
    property string activeSide: "left"
    property string focusedSide: ""
    property bool leftMuted: false
    property bool rightMuted: true
    property string versionSide: "left"

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

    readonly property bool dialogsOpen: sources.visible || versions.visible || versionPreview.visible
        || left.dialogOpen || right.dialogOpen || libraryMenu.visible || scope.popup.visible || order.popup.visible

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
        enabled: !controller.busy
        onPressed: { keys = window.pairKeys(); pressedFiles = files.slice() }
        onClicked: {
            if (!secondClick.running) {
                secondClick.start()
                window.pairAction(decision, keys, pressedFiles)
            }
        }
    }
    function versionDrawer(side) {
        window.versionSide = side;
        versions.open();
    }

    palette.window: "#10141a"
    palette.windowText: "#edf1f5"
    palette.base: "#151b22"
    palette.alternateBase: "#202832"
    palette.text: "#edf1f5"
    palette.button: "#263140"
    palette.buttonText: "#edf1f5"
    palette.highlight: "#87cfb4"
    palette.highlightedText: "#10141a"
    palette.disabled.text: "#7a8594"
    palette.disabled.buttonText: "#7a8594"

    header: ToolBar {
        id: appBar
        padding: 5
        implicitHeight: headerRow.implicitHeight + 2 * padding
        background: Rectangle {
            color: "#1a1f27"
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#394250" }
        }

        RowLayout {
            id: headerRow
            anchors.fill: parent
            anchors.margins: 0
            spacing: 12

            CompareButton {
                text: controller.can_scope ? "Library  ▾" : (controller.title || "Library") + "  ▾"
                enabled: !controller.busy
                onClicked: libraryMenu.open()
                Menu {
                    id: libraryMenu
                    MenuItem { text: "Open source"; onTriggered: sources.open() }
                    MenuItem { text: "Refresh"; enabled: !!controller.title; onTriggered: controller.refresh() }
                }
            }
            ComboBox {
                id: scope
                visible: controller.can_scope
                enabled: !controller.busy
                Accessible.name: "Video type"
                implicitHeight: 36
                textRole: "title"
                valueRole: "value"
                model: [
                    { title: "VR", value: "vr" },
                    { title: "Non-VR", value: "flat" },
                    { title: "Needs review", value: "unknown" },
                    { title: "All files", value: "all" }
                ]
                currentIndex: Math.max(0, indexOfValue(controller.scope))
                onActivated: controller.set_scope(currentValue)
            }
            ComboBox {
                id: order
                implicitContentWidthPolicy: ComboBox.WidestText
                enabled: !controller.busy && !!controller.title
                textRole: "title"
                valueRole: "value"
                Accessible.name: "Comparison order"
                implicitHeight: 36
                model: [
                    { title: "Largest first", value: "largest" },
                    { title: "Most informative", value: "informative" }
                ]
                currentIndex: Math.max(0, indexOfValue(controller.order))
                onActivated: controller.set_order(currentValue)
            }
            Item { Layout.fillWidth: true }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 5

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 1

            ItemPane {
                id: left
                objectName: "leftPane"
                Layout.fillHeight: true
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                visible: window.focusedSide !== "right"
                rankController: window.rankController
                info: controller.left
                side: "left"
                active: window.activeSide === side
                focused: window.focusedSide === side
                muted: window.leftMuted
                onActivated: window.selectSide(side)
                onFocusRequested: window.focusSide(side)
                onVersionsRequested: window.versionDrawer(side)
            }
            Rectangle { visible: !window.focusedSide; Layout.fillHeight: true; implicitWidth: 1; color: "#45494f" }
            ItemPane {
                id: right
                objectName: "rightPane"
                Layout.fillHeight: true
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                visible: window.focusedSide !== "left"
                rankController: window.rankController
                info: controller.right
                side: "right"
                active: window.activeSide === side
                focused: window.focusedSide === side
                muted: window.rightMuted
                onActivated: window.selectSide(side)
                onFocusRequested: window.focusSide(side)
                onVersionsRequested: window.versionDrawer(side)
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: window.width >= 1500 ? 2 : 1
            rowSpacing: 4
            RowLayout {
                Layout.fillWidth: true
                Decision { objectName: "leftPrefer"; decision: "left"; tone: "primary"; text: "Prefer left   1"; enabled: controller.can_compare && !controller.busy }
                Item { Layout.fillWidth: true }
                Decision { decision: "tie"; text: "Tie"; enabled: controller.can_compare && !controller.busy }
                Decision { decision: "skip"; text: "Skip"; enabled: !!(left.identity || right.identity) && !controller.busy }
                Decision { decision: "undo"; text: "Undo " + controller.undo_label; implicitWidth: 135; enabled: controller.can_undo && !controller.busy }
                Item { Layout.fillWidth: true }
                Decision { objectName: "rightPrefer"; decision: "right"; tone: "primary"; text: "Prefer right   2"; enabled: controller.can_compare && !controller.busy }
            }
            RowLayout {
                Layout.alignment: Qt.AlignRight
                visible: controller.can_delete
                component Removal: Decision { decision: "delete"; tone: "danger"; implicitWidth: 172 }
                Removal { text: "Delete left · " + (controller.left.size_label || "0 B"); files: [controller.left.id]; enabled: !controller.busy && !!left.identity }
                Removal { text: "Delete right · " + (controller.right.size_label || "0 B"); files: [controller.right.id]; enabled: !controller.busy && !!right.identity }
                Removal { text: "Delete both · " + controller.both_size; files: [controller.left.id, controller.right.id]; enabled: !controller.busy && !!left.identity && !!right.identity }
            }
        }
        Label {
            Layout.fillWidth: true
            text: controller.message
            color: controller.failed ? "#fca1a9" : "#aebccc"
            elide: Text.ElideRight
            ToolTip.text: text
            ToolTip.visible: statusHover.hovered && truncated
            HoverHandler { id: statusHover }
            font.pixelSize: 13
        }
    }

    Shortcut { autoRepeat: false; sequence: "1"; enabled: !window.dialogsOpen; onActivated: window.pairAction("left", window.pairKeys()) }
    Shortcut { autoRepeat: false; sequence: "2"; enabled: !window.dialogsOpen; onActivated: window.pairAction("right", window.pairKeys()) }
    Shortcut { autoRepeat: false; sequence: "T"; enabled: !window.dialogsOpen; onActivated: window.pairAction("tie", window.pairKeys()) }
    Shortcut { autoRepeat: false; sequence: "S"; enabled: !window.dialogsOpen; onActivated: window.pairAction("skip", window.pairKeys()) }
    Shortcut { autoRepeat: false; sequence: "U"; enabled: !window.dialogsOpen; onActivated: window.pairAction("undo", window.pairKeys()) }
    Shortcut { autoRepeat: false; sequence: "Space"; enabled: !window.dialogsOpen; onActivated: (window.activeSide === "left" ? left : right).toggle() }
    Shortcut { autoRepeat: false; sequence: "F"; enabled: !window.dialogsOpen; onActivated: window.focusSide(window.activeSide) }
    Shortcut { autoRepeat: false; sequence: "Escape"; enabled: !window.dialogsOpen; onActivated: { if (window.focusedSide) window.focusedSide = ""; else (window.activeSide === "left" ? left : right).reset() } }
    Shortcut { autoRepeat: false; sequence: "Ctrl+O"; enabled: !window.dialogsOpen && !controller.busy; onActivated: sources.open() }

    Dialog {
        id: sources
        objectName: "sourcesDialog"
        anchors.centerIn: parent
        modal: true
        width: Math.min(window.width - 48, 560)
        title: "Open a ranking collection"

        ColumnLayout {
            anchors.fill: parent
            spacing: 12
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
                Button {
                    text: "Open domain"
                    enabled: !!domain.text.trim() && !controller.busy
                    onClicked: { sources.close(); controller.open_domain(domain.text.trim()); }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Button { text: "Select files"; onClicked: fileDialog.open() }
                Button { text: "Select folder"; onClicked: folderDialog.open() }
                Button { text: "Open Stash"; onClicked: { sources.close(); controller.open_stash(); } }
            }
            Label {
                visible: recents.count > 0
                text: "Recent collections"
                font.bold: true
            }
            ListView {
                id: recents
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(210, contentHeight)
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
        edge: Qt.RightEdge
        width: Math.min(600, window.width * 0.6)
        height: window.height

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 12
            Label {
                text: "Other versions"
                font.pixelSize: 20
                font.bold: true
            }
            ListView {
                Layout.fillHeight: true
                Layout.fillWidth: true
                clip: true
                spacing: 6
                model: (window.versionSide === "left" ? controller.left.versions : controller.right.versions) || []
                delegate: ColumnLayout {
                    required property var modelData
                    width: ListView.view.width
                    spacing: 5
                    Label { Layout.fillWidth: true; text: modelData.label; wrapMode: Text.Wrap; font.bold: true }
                    Label { Layout.fillWidth: true; text: modelData.path; wrapMode: Text.WrapAnywhere; color: "#aebccc" }
                    Label { Layout.fillWidth: true; text: modelData.details; wrapMode: Text.Wrap; color: "#aebccc" }
                    RowLayout {
                        Button {
                            text: "Play version"
                            onClicked: { controller.preview_version(modelData); versionPreview.open(); }
                        }
                        Decision {
                            decision: "delete"
                            files: [modelData.id]
                            text: "Delete version · " + modelData.size_label
                            palette.button: "#502d36"
                            palette.buttonText: "#ffd4d7"
                            enabled: !controller.busy

                        }
                    }
                    Rectangle { Layout.fillWidth: true; height: 1; color: "#313947" }
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
