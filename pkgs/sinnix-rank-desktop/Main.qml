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
    color: "#10141a"
    title: controller.title ? controller.title + " · Preference ranking" : "Preference ranking"

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

    function pairAction(action) {
        if (controller.busy)
            return;
        if (action === "left" || action === "right" || action === "tie") {
            if (!controller.can_compare)
                return;
            if (action === "tie")
                controller.tie();
            else
                controller.prefer(action === "left" ? 0 : 1);
        } else if (action === "skip" && (controller.left.key || controller.right.key)) {
            controller.skip();
        } else if (action === "undo" && controller.can_undo) {
            controller.undo();
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
        padding: 12
        implicitHeight: headerRow.implicitHeight + 2 * padding
        background: Rectangle {
            color: "#171d25"
            Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: "#394250" }
        }

        RowLayout {
            id: headerRow
            anchors.fill: parent
            anchors.margins: appBar.padding
            spacing: 12

            Button {
                text: "Open"
                enabled: !controller.busy
                onClicked: sources.open()
                Accessible.name: "Open a ranking collection"
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Label {
                    Layout.fillWidth: true
                    text: controller.title || "Preference ranking"
                    font.pixelSize: 19
                    font.bold: true
                    elide: Text.ElideRight
                }
                Label {
                    Layout.fillWidth: true
                    text: controller.source_label
                    visible: !!text
                    color: "#aebccc"
                    elide: Text.ElideRight
                }
            }
            ComboBox {
                id: scope
                visible: controller.can_scope
                enabled: !controller.busy
                Accessible.name: "Video type"
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
                model: [
                    { title: "Largest first · winner stays", value: "largest" },
                    { title: "Most informative · fresh pairs", value: "informative" }
                ]
                currentIndex: Math.max(0, indexOfValue(controller.order))
                onActivated: controller.set_order(currentValue)
            }
            ToolButton {
                text: "Refresh"
                enabled: !controller.busy && !!controller.title
                onClicked: controller.refresh()
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

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
                onPreferred: window.pairAction(side)
                onVersionsRequested: window.versionDrawer(side)
            }
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
                onPreferred: window.pairAction(side)
                onVersionsRequested: window.versionDrawer(side)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Button { text: "Tie · T"; enabled: controller.can_compare && !controller.busy; onClicked: window.pairAction("tie") }
            Button { text: "Skip · S"; enabled: !!(controller.left.key || controller.right.key) && !controller.busy; onClicked: window.pairAction("skip") }
            Button { text: "Undo · U"; enabled: controller.can_undo && !controller.busy; onClicked: window.pairAction("undo") }
            Item { Layout.fillWidth: true }
            Flow {
                visible: controller.can_delete
                spacing: 6
                component DeleteButton: Button {
                    palette.button: "#502d36"
                    palette.buttonText: "#ffd4d7"
                }
                DeleteButton {
                    text: "Delete left · " + controller.left.size_label
                    visible: !!controller.left.id
                    enabled: !controller.busy
                    onClicked: controller.delete_files([controller.left.id])
                }
                DeleteButton {
                    text: "Delete right · " + controller.right.size_label
                    visible: !!controller.right.id
                    enabled: !controller.busy
                    onClicked: controller.delete_files([controller.right.id])
                }
                DeleteButton {
                    text: "Delete both · " + controller.both_size
                    visible: !!controller.left.id && !!controller.right.id
                    enabled: !controller.busy
                    onClicked: controller.delete_files([controller.left.id, controller.right.id])
                }
            }
        }

        Label {
            Layout.fillWidth: true
            text: controller.message
            color: controller.failed ? "#fca1a9" : "#aebccc"
            visible: !!text
            wrapMode: Text.Wrap
            font.pixelSize: 13
        }
    }

    Shortcut { autoRepeat: false; sequence: "1"; enabled: !sources.visible && !versions.visible && !previewVisible(); onActivated: window.pairAction("left") }
    Shortcut { autoRepeat: false; sequence: "2"; enabled: !sources.visible && !versions.visible && !previewVisible(); onActivated: window.pairAction("right") }
    Shortcut { autoRepeat: false; sequence: "T"; enabled: !sources.visible && !versions.visible && !previewVisible(); onActivated: window.pairAction("tie") }
    Shortcut { autoRepeat: false; sequence: "S"; enabled: !sources.visible && !versions.visible && !previewVisible(); onActivated: window.pairAction("skip") }
    Shortcut { autoRepeat: false; sequence: "U"; enabled: !sources.visible && !versions.visible && !previewVisible(); onActivated: window.pairAction("undo") }
    Shortcut { autoRepeat: false; sequence: "Space"; enabled: !sources.visible && !versions.visible && !previewVisible(); onActivated: (window.activeSide === "left" ? left : right).toggle() }
    Shortcut { autoRepeat: false; sequence: "F"; enabled: !sources.visible && !versions.visible && !previewVisible(); onActivated: window.focusSide(window.activeSide) }
    Shortcut { autoRepeat: false; sequence: "Escape"; enabled: !!window.focusedSide && !sources.visible && !versions.visible && !previewVisible(); onActivated: window.focusedSide = "" }
    Shortcut { autoRepeat: false; sequence: "Ctrl+O"; enabled: !controller.busy; onActivated: sources.open() }

    function previewVisible() {
        return versionPreview.visible;
    }

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
                        Button {
                            text: "Delete version · " + modelData.size_label
                            palette.button: "#502d36"
                            palette.buttonText: "#ffd4d7"
                            enabled: !controller.busy
                            onClicked: controller.delete_files([modelData.id])
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
            onPreferred: {}
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
