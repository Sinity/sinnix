package dev.sinnix.phone;

/**
 * How much the app actually knows about a thing.
 *
 * <p>Used on the capture and grants screens only. The distinction they render
 * is not decorative: MIUI revokes grants with no event, microphone arbitration
 * can feed the recorder silence mid-use, and a well-formed chunk can contain
 * nothing at all. On those screens "measured OK" and "assumed OK" are
 * different claims and are drawn differently.
 *
 * <p>Elsewhere in the app there are no grades. Dressing home, instruments or
 * Talk in reliability vocabulary would put dev-time incident history at the
 * centre of a tool whose subject is capture, measurement and action.
 *
 * <p>The rule is one-directional: nothing reaches {@link #EVIDENCED} without a
 * measurement to name, and anything unverifiable stays {@link #UNVERIFIED}
 * rather than being rounded up to OK.
 */
enum Grade {
  /** Measured, with the measurement quotable. */
  EVIDENCED("evidenced", '●', 0xFF6FC28A),
  /** Not measurable, or not measured yet. Never rendered as OK. */
  UNVERIFIED("unverified", '◌', 0xFFD4A84A),
  /** Measured, and wrong. */
  BROKEN("broken", '✕', 0xFFE05561);

  final String word;

  /**
   * A glyph as well as a colour, so the grade survives greyscale, colour
   * vision differences, and a screenshot pasted into a terminal.
   */
  final char glyph;

  final int color;

  Grade(String word, char glyph, int color) {
    this.word = word;
    this.glyph = glyph;
    this.color = color;
  }

  /** `evidenced` only when there is a measurement; absence of proof is not proof. */
  static Grade of(boolean measured, boolean healthy) {
    if (!measured) {
      return UNVERIFIED;
    }
    return healthy ? EVIDENCED : BROKEN;
  }
}
