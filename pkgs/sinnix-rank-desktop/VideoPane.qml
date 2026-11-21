import QtQuick
import QtMultimedia

Item {
    id: pane

    property alias source: player.source
    property alias volume: audio.volume
    property alias muted: audio.muted
    property var projection: ({})
    property real yaw: 0
    property real pitch: 0
    property real fov: 90
    property bool original: false

    readonly property int position: player.position
    readonly property int duration: player.duration
    readonly property bool playing: player.playbackState === MediaPlayer.PlayingState
    readonly property string playbackError: player.errorString
    readonly property bool perspective: !original
        && (projection?.projection === "equirect" || projection?.projection === "fisheye")

    function play() { player.play() }
    function pause() { player.pause() }
    function stop() { player.stop() }
    function seek(ms) {
        if (player.seekable)
            player.position = Math.max(0, Math.min(duration, ms))
    }
    function recenter() {
        yaw = 0
        pitch = 0
        fov = 90
    }

    clip: true

    Rectangle {
        anchors.fill: parent
        color: "black"
    }

    MediaPlayer {
        id: player
        videoOutput: video
        audioOutput: AudioOutput {
            id: audio
            muted: true
        }
    }

    VideoOutput {
        id: video
        anchors.fill: parent
        fillMode: pane.perspective ? VideoOutput.Stretch : VideoOutput.PreserveAspectFit
    }

    ShaderEffectSource {
        id: videoTexture
        sourceItem: pane.perspective ? video : null
        hideSource: pane.perspective
        visible: false
        smooth: true
        // Retain enough texture detail for a single-eye crop and zoom, using
        // one bounded offscreen texture per pane.
        readonly property real sourceWidth: Math.max(1, video.sourceRect.width)
        readonly property real sourceHeight: Math.max(1, video.sourceRect.height)
        readonly property real scaleFactor: Math.min(1, 4096 / Math.max(sourceWidth, sourceHeight))
        textureSize: Qt.size(Math.max(1, Math.round(sourceWidth * scaleFactor)),
                             Math.max(1, Math.round(sourceHeight * scaleFactor)))
    }

    ShaderEffect {
        id: perspectiveView
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height * 16 / 9)
        height: width * 9 / 16
        visible: pane.perspective
        fragmentShader: "shaders/perspective.frag.qsb"

        property var source: videoTexture
        property real sourceFov: Number(pane.projection?.hfov) || 180
        property real viewFov: pane.fov
        property real yaw: pane.yaw
        property real pitch: pane.pitch
        property int fisheye: pane.projection?.projection === "fisheye" ? 1 : 0
        property int layoutMode: pane.projection?.layout === "sbs" ? 1
                               : pane.projection?.layout === "tb" ? 2 : 0
        property int swapEye: pane.projection?.swap ? 1 : 0
        property size sourcePixels: videoTexture.textureSize

        MouseArea {
            anchors.fill: parent
            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
            property point last: Qt.point(0, 0)

            onPressed: mouse => { last = Qt.point(mouse.x, mouse.y) }

            onPositionChanged: mouse => {
                if (!pressed)
                    return
                const dx = (mouse.x - last.x) * pane.fov / width
                const dy = (mouse.y - last.y) * pane.fov / width
                pane.yaw = ((pane.yaw - dx + 180) % 360 + 360) % 360 - 180
                pane.pitch = Math.max(-90, Math.min(90, pane.pitch + dy))
                last = Qt.point(mouse.x, mouse.y)
            }

            onWheel: wheel => {
                const degrees = wheel.angleDelta.y * 5 / 120
                pane.fov = Math.max(30, Math.min(120, pane.fov - degrees))
            }
        }
    }
}
