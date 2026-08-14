package dev.sinnix.phone.instruments

/**
 * How a stimulus is presented and a response taken.
 *
 * Five engines cover the whole catalogue, and that is the design rather than a
 * coincidence: an instrument is a *configuration*, not a screen. A new
 * measurement should be a row in this file or a JSON deck pushed from prime,
 * never a new Activity — which is also what makes the deck player possible at
 * all.
 */
enum class Engine {
    /** Whole-screen response surface, timed against frame presentation. PVT, tapping, go/no-go. */
    REACTION,

    /** Adaptive up-down ladder over a rendered stimulus. Pitch JND, gap detection. */
    STAIRCASE,

    /** Hold the phone still (or a finger on the lens) and stream a trace to prime. */
    HOLD_STILL,

    /** N alternatives, one correct, latency and accuracy both recorded. Stroop, decks. */
    FORCED_CHOICE,

    /** Count something and report the count. Breath counting, Schandry heartbeat. */
    COUNTING,
}

/**
 * When an instrument is worth offering.
 *
 * Deliberately coarse. A scheduler that models the operator's day precisely is
 * a scheduler that is wrong precisely; three states are enough to stop
 * proposing a fifteen-minute staircase to someone who just woke up.
 */
enum class Energy {
    /** Needs a good state to be worth the data. */
    GOOD_ONLY,

    /** Fine any time. */
    ANY,

    /** Specifically useful when depleted — that is when the signal is there. */
    LOW_OK,
}

/**
 * One measurement, as configuration.
 *
 * [scoredOnDevice] is the honest half of the phone/prime split: anything the
 * phone can compute from its own event stream shows a number immediately;
 * anything needing a model ships a trace and gets a receipt. The field exists
 * so the UI can end the screen correctly rather than promise a score it will
 * never render.
 */
data class Instrument(
    val id: String,
    val title: String,
    val engine: Engine,
    val seconds: Int,
    val energy: Energy = Energy.ANY,
    val needsHeadphones: Boolean = false,
    val needsCamera: Boolean = false,
    val scoredOnDevice: Boolean = true,
    val blurb: String = "",
    /** Engine parameters. Decks supply this from JSON; built-ins hard-code it. */
    val config: Map<String, Any> = emptyMap(),
)

/**
 * The built-in catalogue.
 *
 * The cut list is part of the design and is recorded in docs/phone.md: no
 * panel-based CFF or contrast sensitivity (the display is not a photometric
 * instrument and its refresh clips foveal CFF before any PWM argument
 * applies), no pupillometry or saccades (they need face landmarks, which means
 * a model), no n-back or digit span (practice effects dominate the
 * longitudinal signal, so repeated measurement measures learning).
 */
object Catalogue {

    val PVT =
        Instrument(
            id = "pvt",
            title = "Reaction",
            engine = Engine.REACTION,
            seconds = 150,
            energy = Energy.ANY,
            blurb = "25 trials. Tap the instant the screen changes.",
            config = mapOf("trials" to 25, "isi_min_ms" to 2000, "isi_max_ms" to 10000),
        )

    val TAPPING =
        Instrument(
            id = "tapping",
            title = "Tapping",
            engine = Engine.REACTION,
            seconds = 40,
            blurb = "Tap as fast and as evenly as you can for 30 seconds.",
            config = mapOf("mode" to "free_tap", "duration_ms" to 30000),
        )

    val GO_NO_GO =
        Instrument(
            id = "go_no_go",
            title = "Go / no-go",
            engine = Engine.REACTION,
            seconds = 120,
            blurb = "Tap on the filled shape. Withhold on the hollow one.",
            config =
                mapOf(
                    "trials" to 40,
                    "isi_min_ms" to 900,
                    "isi_max_ms" to 2200,
                    "nogo_fraction" to 0.3,
                ),
        )

    val STROOP =
        Instrument(
            id = "stroop",
            title = "Stroop",
            engine = Engine.FORCED_CHOICE,
            seconds = 120,
            blurb = "Name the ink colour, not the word.",
            config = mapOf("trials" to 30, "incongruent_fraction" to 0.5),
        )

    val BREATH =
        Instrument(
            id = "breath_counting",
            title = "Breath counting",
            engine = Engine.COUNTING,
            seconds = 300,
            energy = Energy.LOW_OK,
            blurb = "Count breaths one to nine. Big button for 1–8, small for 9.",
            config = mapOf("cycle" to 9),
        )

    val PITCH_JND =
        Instrument(
            id = "pitch_jnd",
            title = "Pitch discrimination",
            engine = Engine.STAIRCASE,
            seconds = 180,
            needsHeadphones = true,
            blurb = "Two tones. Tap the half that was higher.",
            config =
                mapOf(
                    "base_hz" to 1000.0,
                    "start_delta_hz" to 60.0,
                    "min_delta_hz" to 0.5,
                    "reversals" to 8,
                    "tone_ms" to 400,
                    "gap_ms" to 300,
                ),
        )

    val GAP_DETECTION =
        Instrument(
            id = "gap_detection",
            title = "Gap detection",
            engine = Engine.STAIRCASE,
            seconds = 180,
            needsHeadphones = true,
            blurb = "Two bursts. Tap the half that had a gap in it.",
            config =
                mapOf(
                    "base_hz" to 1000.0,
                    "start_gap_ms" to 40.0,
                    "min_gap_ms" to 1.0,
                    "reversals" to 8,
                    "tone_ms" to 500,
                    "gap_ms" to 300,
                ),
        )

    val PPG =
        Instrument(
            id = "ppg",
            title = "Pulse",
            engine = Engine.HOLD_STILL,
            seconds = 75,
            needsCamera = true,
            scoredOnDevice = false,
            blurb = "Cover the rear camera and the flash with one fingertip.",
            config = mapOf("mode" to "ppg", "duration_ms" to 60000),
        )

    val TREMOR =
        Instrument(
            id = "tremor",
            title = "Tremor",
            engine = Engine.HOLD_STILL,
            seconds = 45,
            scoredOnDevice = false,
            blurb = "Hold the phone out in front of you, as still as you can.",
            config = mapOf("mode" to "imu", "duration_ms" to 30000),
        )

    val SWAY =
        Instrument(
            id = "sway",
            title = "Sway",
            engine = Engine.HOLD_STILL,
            seconds = 60,
            scoredOnDevice = false,
            blurb = "Phone in your pocket. Stand still, eyes closed, feet together.",
            config = mapOf("mode" to "imu_sway", "duration_ms" to 45000),
        )

    /**
     * Heartbeat counting with the phone supplying its own ground truth.
     *
     * The reason this is a phone instrument at all: Schandry counting normally
     * needs an ECG in the room to score against, and finger-PPG running in the
     * same session provides it.
     */
    val INTEROCEPTION =
        Instrument(
            id = "interoception",
            title = "Interoception",
            engine = Engine.COUNTING,
            seconds = 120,
            needsCamera = true,
            scoredOnDevice = false,
            blurb = "Count your heartbeats without taking a pulse. Finger on the lens.",
            config = mapOf("mode" to "schandry", "windows_ms" to listOf(25000, 35000, 45000)),
        )

    /**
     * CFF through the torch LED rather than the panel — no refresh ceiling and
     * no PWM confound. Viability depends on how fast setTorchMode actually
     * switches on this device, which the instrument measures first and records
     * either way.
     */
    val TORCH_CFF =
        Instrument(
            id = "torch_cff",
            title = "Flicker fusion",
            engine = Engine.STAIRCASE,
            seconds = 150,
            needsCamera = true,
            blurb = "Look at the torch. Tap when it stops looking like flicker.",
            config =
                mapOf(
                    "mode" to "torch",
                    "start_hz" to 20.0,
                    "max_hz" to 70.0,
                    "reversals" to 6,
                ),
        )

    /** The micro-PVT fired on alarm dismissal. Shorter, because inertia decays fast. */
    val SLEEP_INERTIA_PVT =
        Instrument(
            id = "sleep_inertia_pvt",
            title = "Just awake",
            engine = Engine.REACTION,
            seconds = 60,
            energy = Energy.LOW_OK,
            blurb = "Ten trials, right now, before you are properly up.",
            config = mapOf("trials" to 10, "isi_min_ms" to 1500, "isi_max_ms" to 5000),
        )

    val all: List<Instrument> =
        listOf(
            PVT,
            TAPPING,
            GO_NO_GO,
            STROOP,
            BREATH,
            PITCH_JND,
            GAP_DETECTION,
            PPG,
            TREMOR,
            SWAY,
            INTEROCEPTION,
            TORCH_CFF,
            SLEEP_INERTIA_PVT,
        )

    fun byId(id: String): Instrument? = all.firstOrNull { it.id == id }
}
