package dev.sinnix.phone.core

import java.text.ParseException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * The two timestamp shapes, and the one parser that reads both.
 *
 * There are two on purpose. Fields carry extended ISO because that is what
 * every consumer downstream — jq, python, the drain, lynchpin — parses without
 * being told. Filenames carry the compact form because sdcardfs rejects colons
 * outright: an extended stamp in a filename fails every open with EPERM while
 * the recorder looks otherwise healthy. Reaching for the wrong one has cost
 * this program a day already, so they are named for where they go rather than
 * for what they look like.
 */
object Stamps {

    /** Extended ISO-8601. The shape every timestamp FIELD uses. */
    fun iso(ms: Long): String = format("yyyy-MM-dd'T'HH:mm:ss'Z'", ms)

    /** Compact ISO basic. The shape every FILENAME uses. */
    fun compact(ms: Long): String = format("yyyyMMdd'T'HHmmss'Z'", ms)

    /** UTC calendar day, for the events day-file name. */
    fun day(ms: Long): String = format("yyyyMMdd", ms)

    /**
     * Parse either shape.
     *
     * Records written before 2026-08-14 carry the compact stamp in fields
     * because the event writer reached for the wrong helper. The log is
     * append-only, so those lines cannot be rewritten — and a reducer that
     * silently returned 0 for them would drop real coverage on the floor and
     * show an empty ribbon over a week that was fully captured.
     */
    fun parse(stamp: String?): Long {
        if (stamp.isNullOrEmpty()) return 0L
        val pattern =
            if (stamp.indexOf('-') > 0) "yyyy-MM-dd'T'HH:mm:ss'Z'" else "yyyyMMdd'T'HHmmss'Z'"
        return try {
            formatter(pattern).parse(stamp)?.time ?: 0L
        } catch (e: ParseException) {
            0L
        }
    }

    private fun format(pattern: String, ms: Long): String = formatter(pattern).format(Date(ms))

    private fun formatter(pattern: String): SimpleDateFormat =
        SimpleDateFormat(pattern, Locale.US).apply { timeZone = TimeZone.getTimeZone("UTC") }
}
