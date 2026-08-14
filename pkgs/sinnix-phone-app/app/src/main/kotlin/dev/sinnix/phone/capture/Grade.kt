package dev.sinnix.phone.capture

/**
 * How much the app actually knows about a thing.
 *
 * Used on the capture and grants screens, and on the transport label, and
 * nowhere else. The distinction they render is not decorative: MIUI revokes
 * grants with no event, microphone arbitration can feed the recorder silence
 * mid-use, a well-formed chunk can contain nothing at all, and a tailnet that
 * answered a minute ago may not answer now. On those surfaces "measured OK"
 * and "assumed OK" are different claims and are drawn differently.
 *
 * Elsewhere there are no grades. The app is not about its own reliability —
 * dressing home, instruments, steering or the estate remote in incident-history
 * vocabulary would make dev-time failures the subject of a tool whose subject
 * is capture, measurement and action.
 *
 * The rule is one-directional: nothing reaches [EVIDENCED] without a
 * measurement to name, and anything unverifiable stays [UNVERIFIED] rather
 * than being rounded up to OK.
 */
enum class Grade(val word: String, val glyph: String) {
    /** Measured, with the measurement quotable. */
    EVIDENCED("evidenced", "●"),

    /** Not measurable, or not measured yet. Never rendered as OK. */
    UNVERIFIED("unverified", "◌"),

    /** Measured, and wrong. */
    BROKEN("broken", "✕");

    companion object {
        /** `evidenced` only when there is a measurement; absence of proof is not proof. */
        fun of(measured: Boolean, healthy: Boolean): Grade =
            if (!measured) UNVERIFIED else if (healthy) EVIDENCED else BROKEN
    }
}
