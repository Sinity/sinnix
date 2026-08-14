package dev.sinnix.phone.capture

import android.content.Context
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Stamps

/**
 * What the last week of capture actually looks like, one cell per hour.
 *
 * A reduction of the event log, not of the chunk directory: chunks leave the
 * phone on the next drain, so a listing answers "what is still here", which is
 * a question about the drain rather than about capture.
 *
 * Hours are graded, not merely present/absent. An hour whose chunks all
 * captured silence is not coverage — that is the whole lesson of the archive
 * that turned out 29 of 111 empty — so it renders as a hole with a cause.
 */
class Coverage private constructor(val originMs: Long) {

    val cells = IntArray(CELLS)
    val holes = ArrayList<Hole>()

    /** One contiguous run of hours that captured nothing, with what is known about why. */
    data class Hole(val startMs: Long, val endMs: Long, val cause: String) {
        val hours: Long get() = ((endMs - startMs) / 3_600_000L).coerceAtLeast(1L)
    }

    fun coveredHours(): Int = cells.count { it == COVERED }

    fun knownHours(): Int = cells.count { it != UNKNOWN }

    /**
     * The most recent unbroken run of covered hours, in hours.
     *
     * The headline number on the capture screen: "unbroken 14h" says something
     * a percentage cannot, because a week that is 90% covered with a hole this
     * morning and a week that is 90% covered with a hole last Tuesday are
     * different situations.
     */
    fun unbrokenHours(): Int {
        var n = 0
        for (i in CELLS - 1 downTo 0) {
            when (cells[i]) {
                COVERED -> n++
                UNKNOWN -> if (n > 0) return n else Unit
                else -> return n
            }
        }
        return n
    }

    private fun collectHoles() {
        var i = 0
        while (i < CELLS) {
            val state = cells[i]
            if (state != HOLE && state != SILENT) {
                i++
                continue
            }
            var j = i
            while (j + 1 < CELLS && cells[j + 1] == state) j++
            holes.add(
                Hole(
                    originMs + i * 3_600_000L,
                    originMs + (j + 1L) * 3_600_000L,
                    if (state == SILENT) "recorder running, microphone produced no sample"
                    else "no chunk closed in this window",
                )
            )
            i = j + 1
        }
    }

    companion object {
        const val DAYS = 7
        const val HOURS = 24
        const val CELLS = DAYS * HOURS

        /** No chunk claimed this hour. Before the app existed, this is simply unknown. */
        const val UNKNOWN = 0

        /** Chunks closed in this hour and carried sound. */
        const val COVERED = 1

        /** Chunks closed, and every one of them was silent. */
        const val SILENT = 2

        /** Bounded by two covered hours with nothing between them: a real gap. */
        const val HOLE = 3

        private fun hourFloor(ms: Long): Long = ms - (ms % 3_600_000L)

        /** Reduce the week's events. [nowMs] lands in the last cell. */
        fun of(ctx: Context, nowMs: Long): Coverage {
            val origin = hourFloor(nowMs) - (CELLS - 1L) * 3_600_000L
            val c = Coverage(origin)

            val sawChunk = BooleanArray(CELLS)
            val sawSound = BooleanArray(CELLS)

            for (e in Events.recent(ctx, DAYS + 1)) {
                if (e.optString("kind") != "chunk_closed") continue
                var startedAt = Stamps.parse(e.optString("started_at"))
                if (startedAt == 0L) startedAt = Stamps.parse(e.optString("ts"))
                val idx = ((hourFloor(startedAt) - origin) / 3_600_000L).toInt()
                if (idx < 0 || idx >= CELLS) continue
                sawChunk[idx] = true
                if (!e.optBoolean("captured_nothing", false)) sawSound[idx] = true
            }

            // An hour with no chunk only counts as a hole once capture has been
            // seen on both sides of it. Leading emptiness is the time before
            // the app existed, and trailing emptiness is usually the hour still
            // in progress — neither is a failure, and calling them one would
            // make the ribbon cry wolf on every fresh install.
            var first = -1
            var last = -1
            for (i in 0 until CELLS) {
                if (sawChunk[i]) {
                    if (first < 0) first = i
                    last = i
                }
            }

            for (i in 0 until CELLS) {
                c.cells[i] =
                    when {
                        sawChunk[i] -> if (sawSound[i]) COVERED else SILENT
                        first >= 0 && i > first && i < last -> HOLE
                        else -> UNKNOWN
                    }
            }

            c.collectHoles()
            return c
        }
    }
}
