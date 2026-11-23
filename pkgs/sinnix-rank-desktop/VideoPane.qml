import QtQuick
import Sinnix.Video

Item {
    id: pane

    property alias source: video.source
    property alias volume: video.volume
    property alias muted: video.muted
    property var projection: ({})
    property real yaw: 0
    property real pitch: 0
    property real fov: 90
    property bool original: false

    readonly property int position: video.position
    readonly property int duration: video.duration
    readonly property bool playing: video.playing
    readonly property string playbackError: video.playbackError
    readonly property bool perspective: !original
        && (projection?.projection === "equirect" || projection?.projection === "fisheye")

    function play() { video.play() }
    function pause() { video.pause() }
    function stop() { video.stop() }
    function seek(ms) { video.seek(ms, true) }
    function scrub(ms) { video.seek(ms, false) }
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

    MpvOutput {
        id: video
        anchors.fill: parent
        stretch: pane.perspective
        // Retain detail after cropping to one eye without extending the
        // rendering pass to the full size of an 8K source.
        renderSize: pane.perspective ? Qt.size(4096, 2048) : Qt.size(-1, -1)
    }

    ShaderEffectSource {
        id: videoTexture
        sourceItem: pane.perspective ? video : null
        hideSource: pane.perspective
        visible: false
        smooth: true
        textureSize: video.renderSize
    }

    ShaderEffect {
        id: perspectiveView
        anchors.fill: parent
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
        property real viewAspect: height / Math.max(1, width)

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
