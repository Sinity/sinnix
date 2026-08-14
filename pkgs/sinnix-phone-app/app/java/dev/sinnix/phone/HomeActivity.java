package dev.sinnix.phone;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Home: is capture solid, and what does the estate want from me.
 *
 * <p>One scroll, no tabs, no bottom bar. The continuity ribbon takes the top
 * because "is the last week solid" is the question worth answering at a
 * glance; everything diagnosable is one tap deeper in {@link CaptureActivity}.
 *
 * <p>There are no trust grades on this screen beyond the ribbon's own summary.
 * Reliability vocabulary belongs on the two screens that face silent failure
 * as an ongoing reality; spreading it here would make incident history the
 * centre of a tool whose subject is capture, measurement and action.
 */
public final class HomeActivity extends Screen {

  private LinearLayout root;
  private RibbonView ribbon;
  private TextView epochLabel;
  private TextView headline;
  private TextView phoneLine;
  private TextView lakeLine;
  private TextView holeLine;

  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    root = mount();
    buildTitleRow();
    buildRibbonCard();
    buildNav();
  }

  @Override
  protected void onResume() {
    super.onResume();
    refresh();
  }

  private void buildTitleRow() {
    LinearLayout r = row();
    TextView title = text("sinnix capture", 15, TEXT_BRIGHT);
    title.setTypeface(Typeface.DEFAULT_BOLD);
    title.setLayoutParams(
        new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
    epochLabel = mono("", 11, TEXT_GHOST);
    epochLabel.setGravity(Gravity.END);
    r.addView(title);
    r.addView(epochLabel);
    root.addView(r);
    root.addView(spacer(dp(12)));
  }

  private void buildRibbonCard() {
    LinearLayout c = card();
    // The whole card is the target, not a small chevron: this is the most
    // tapped thing on the screen and a thumb should not have to aim.
    c.setClickable(true);
    c.setOnClickListener(v -> startActivity(new Intent(this, CaptureActivity.class)));

    headline = mono("reading…", 12, TEXT);
    c.addView(headline);
    c.addView(spacer(dp(8)));

    ribbon = new RibbonView(this);
    ribbon.setLayoutParams(
        new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(96)));
    c.addView(ribbon);
    c.addView(spacer(dp(4)));

    LinearLayout axis = row();
    for (String label : new String[] {"00", "06", "12", "18", "23"}) {
      TextView t = mono(label, 9, TEXT_GHOST);
      t.setLayoutParams(new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
      axis.addView(t);
    }
    c.addView(axis);
    c.addView(spacer(dp(10)));

    // Phone continuity and lake continuity are separate rows and never merged.
    // The drain deliberately tolerates a long gap -- a phone off wifi is not a
    // fault -- so folding them into one number would invent a problem.
    phoneLine = mono("", 11, TEXT_FAINT);
    lakeLine = mono("", 11, TEXT_FAINT);
    holeLine = mono("", 11, TEXT_FAINT);
    c.addView(phoneLine);
    c.addView(lakeLine);
    c.addView(holeLine);

    root.addView(c);
    root.addView(spacer(dp(12)));
  }

  private void buildNav() {
    root.addView(navRow("capture detail", CaptureActivity.class));
    root.addView(spacer(dp(8)));
    root.addView(navRow("grants", GrantsActivity.class));
    root.addView(spacer(dp(8)));
    root.addView(navRow("reaction check  ·  2 min", PvtActivity.class));
    root.addView(spacer(dp(8)));

    // An external Intent rather than a WebView: the hub is prime's surface,
    // and the system browser already holds the session and the extensions.
    TextView hub = text("open hub  ↗", 14, ACCENT);
    hub.setBackground(cardBackground());
    hub.setPadding(dp(12), dp(16), dp(12), dp(16));
    hub.setOnClickListener(
        v -> {
          try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(HUB_URL)));
          } catch (ActivityNotFoundException e) {
            hub.setText("open hub  ↗  — no browser handled it");
          }
        });
    root.addView(hub);
  }

  /** Reachable only over the tailnet; failing to open is a normal outcome off it. */
  private static final String HUB_URL = "http://sinnix-prime:8080/";

  private void refresh() {
    epochLabel.setText(Epoch.current(this).id);

    Coverage coverage = Coverage.of(this, System.currentTimeMillis());
    ribbon.setCells(coverage.cells);

    int covered = coverage.coveredHours();
    int known = coverage.knownHours();
    Grade grade = Grade.of(known > 0, coverage.holes.isEmpty() && covered > 0);
    headline.setText(grade.glyph + "  capture · " + grade.word + "          7 d  ▸");
    headline.setTextColor(grade.color);

    phoneLine.setText("phone   " + covered + " of " + known + " known hours carried sound");

    // The app cannot see the lake: the drain runs on prime and writes nothing
    // back to the device yet. Saying so is the honest render -- a green
    // "synced" here would be a claim about a machine this process has never
    // contacted. It becomes a real line when the drain leaves a receipt.
    lakeLine.setText("lake    " + Grade.UNVERIFIED.glyph + " no drain receipt on the phone");

    if (coverage.holes.isEmpty()) {
      holeLine.setText("holes   none in the last 7 days");
      holeLine.setTextColor(TEXT_FAINT);
    } else {
      long longest = 0;
      for (Coverage.Hole h : coverage.holes) {
        longest = Math.max(longest, h.hours());
      }
      holeLine.setText("holes   " + coverage.holes.size() + ", longest " + longest + " h");
      holeLine.setTextColor(Grade.BROKEN.color);
    }
  }
}
