package dev.sinnix.phone;

import android.app.Activity;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.util.TypedValue;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/**
 * The shared vocabulary every screen is built from.
 *
 * <p>The package has no resource tree -- no layouts, no styles, no drawables
 * (see pkg.nix) -- so what would normally live in XML lives here instead: the
 * palette, the spacing unit, and the handful of view constructors. Keeping it
 * in one place is what stops "built in code" from meaning "built differently
 * on every screen".
 */
abstract class Screen extends Activity {

  static final int BG = 0xFF0B0D10;
  static final int CARD = 0xFF111418;
  static final int BORDER = 0xFF242A32;
  static final int TEXT = 0xFFE6E9EE;
  static final int TEXT_BRIGHT = 0xFFF4F6F9;
  static final int TEXT_DIM = 0xFFB8BFC9;
  static final int TEXT_FAINT = 0xFF7A828E;
  static final int TEXT_GHOST = 0xFF4A525D;
  static final int ACCENT = 0xFF5AC8C8;
  static final int LAKE = 0xFF6AA3E0;

  /** The scrolling column every screen hangs its cards on. */
  LinearLayout mount() {
    ScrollView scroll = new ScrollView(this);
    scroll.setBackgroundColor(BG);
    LinearLayout col = column();
    col.setPadding(dp(14), dp(14), dp(14), dp(28));
    scroll.addView(col);
    setContentView(scroll);
    return col;
  }

  int dp(int value) {
    return (int)
        TypedValue.applyDimension(
            TypedValue.COMPLEX_UNIT_DIP, value, getResources().getDisplayMetrics());
  }

  LinearLayout column() {
    LinearLayout l = new LinearLayout(this);
    l.setOrientation(LinearLayout.VERTICAL);
    l.setLayoutParams(
        new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    return l;
  }

  LinearLayout row() {
    LinearLayout l = new LinearLayout(this);
    l.setOrientation(LinearLayout.HORIZONTAL);
    l.setLayoutParams(
        new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
    return l;
  }

  TextView text(String s, int sp, int color) {
    TextView t = new TextView(this);
    t.setText(s);
    t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
    t.setTextColor(color);
    return t;
  }

  TextView mono(String s, int sp, int color) {
    TextView t = text(s, sp, color);
    t.setTypeface(Typeface.MONOSPACE);
    return t;
  }

  View spacer(int px) {
    View v = new View(this);
    v.setLayoutParams(new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, px));
    return v;
  }

  LinearLayout card() {
    LinearLayout c = column();
    c.setBackground(cardBackground());
    c.setPadding(dp(12), dp(12), dp(12), dp(12));
    return c;
  }

  GradientDrawable cardBackground() {
    GradientDrawable d = new GradientDrawable();
    d.setColor(CARD);
    d.setStroke(dp(1), BORDER);
    return d;
  }

  /**
   * A card whose border style, not only its colour, carries the grade.
   *
   * <p>Dashed for unverified and doubled for broken, so the three states stay
   * distinguishable in greyscale, with any colour vision, and in a screenshot
   * someone has pasted into a terminal.
   */
  GradientDrawable gradeBackground(Grade grade) {
    GradientDrawable d = new GradientDrawable();
    d.setColor(CARD);
    switch (grade) {
      case UNVERIFIED:
        d.setStroke(dp(1), grade.color, dp(3), dp(3));
        break;
      case BROKEN:
        d.setStroke(dp(2), grade.color);
        break;
      default:
        d.setStroke(dp(1), grade.color);
        break;
    }
    return d;
  }

  /** A tappable row leading somewhere else. */
  TextView navRow(String label, Class<?> target) {
    TextView t = text(label + "  ▸", 14, TEXT_BRIGHT);
    t.setBackground(cardBackground());
    t.setPadding(dp(12), dp(16), dp(12), dp(16));
    t.setOnClickListener(
        v -> startActivity(new android.content.Intent(this, target)));
    return t;
  }

  /** A back affordance, since there is no action bar to inherit one from. */
  TextView backRow() {
    TextView t = mono("◂ back", 12, TEXT_FAINT);
    t.setPadding(0, dp(4), 0, dp(12));
    t.setOnClickListener(v -> finish());
    return t;
  }
}
