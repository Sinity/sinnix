package dev.sinnix.phone;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.view.View;

/**
 * Seven days by twenty-four hours, one cell per hour.
 *
 * <p>The point is a two-second read: whether the last week is solid. Detail
 * lives one tap deeper, so this draws no labels, no numbers and no legend --
 * every pixel it spends on chrome is a pixel not spent on the shape of the
 * week.
 *
 * <p>A Canvas subclass because the build has no resource tree and therefore no
 * drawables; a grid of 168 child Views would also be an absurd way to draw 168
 * rectangles.
 */
final class RibbonView extends View {

  private static final int BG = 0xFF111418;
  private static final int UNKNOWN = 0xFF1B2026;
  private static final int COVERED = 0xFF6FC28A;
  private static final int SILENT = 0xFFD4A84A;
  private static final int HOLE = 0xFFE05561;

  private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
  private int[] cells = new int[Coverage.CELLS];

  RibbonView(Context ctx) {
    super(ctx);
    setBackgroundColor(BG);
  }

  void setCells(int[] next) {
    if (next != null && next.length == Coverage.CELLS) {
      cells = next;
      invalidate();
    }
  }

  @Override
  protected void onDraw(Canvas canvas) {
    super.onDraw(canvas);
    int w = getWidth();
    int h = getHeight();
    if (w <= 0 || h <= 0) {
      return;
    }
    // Gaps are drawn by insetting each cell rather than by spacing them out,
    // so the grid always fills the width exactly and rounding never leaves a
    // ragged right edge.
    float cw = w / (float) Coverage.HOURS;
    float ch = h / (float) Coverage.DAYS;
    float inset = Math.min(cw, ch) * 0.12f;

    for (int day = 0; day < Coverage.DAYS; day++) {
      for (int hour = 0; hour < Coverage.HOURS; hour++) {
        int state = cells[day * Coverage.HOURS + hour];
        paint.setColor(colorFor(state));
        float left = hour * cw + inset;
        float top = day * ch + inset;
        canvas.drawRect(left, top, left + cw - inset * 2, top + ch - inset * 2, paint);
      }
    }
  }

  private static int colorFor(int state) {
    switch (state) {
      case Coverage.COVERED:
        return COVERED;
      case Coverage.SILENT:
        return SILENT;
      case Coverage.HOLE:
        return HOLE;
      default:
        return UNKNOWN;
    }
  }
}
