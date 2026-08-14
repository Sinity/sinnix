package dev.sinnix.phone.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.Canvas
import androidx.compose.material3.MaterialTheme
import dev.sinnix.phone.capture.Coverage
import dev.sinnix.phone.capture.Grade
import dev.sinnix.phone.ui.theme.Palette
import kotlin.math.max
import kotlin.math.min

/** A flat panel. No elevation anywhere in this app: separation is hairline and spacing. */
@Composable
fun Card(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit,
) {
    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(Palette.Surface)
                .border(1.dp, Palette.Hairline, RoundedCornerShape(14.dp))
                .let { if (onClick != null) it.clickable(onClick = onClick) else it }
                .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        content = content,
    )
}

@Composable
fun SectionLabel(text: String) {
    Text(
        text.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        color = Palette.TextFaint,
        letterSpacing = 1.5.sp,
    )
}

/** A machine-state line: label in prose, value in monospace. */
@Composable
fun StatRow(label: String, value: String, tone: Color = Palette.Text) {
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = Palette.TextDim)
        Text(
            value,
            style = MaterialTheme.typography.labelMedium,
            color = tone,
            fontFamily = FontFamily.Monospace,
        )
    }
}

/**
 * A graded row: glyph, claim, and the evidence for it.
 *
 * The evidence string is required rather than optional on purpose. A row that
 * says "OK" with nothing to quote is exactly the shape this app is built to
 * distrust, so the type makes it awkward to write one.
 */
@Composable
fun GradeRow(grade: Grade, label: String, evidence: String, onClick: (() -> Unit)? = null) {
    val tone =
        when (grade) {
            Grade.EVIDENCED -> Palette.Evidenced
            Grade.UNVERIFIED -> Palette.Unverified
            Grade.BROKEN -> Palette.Broken
        }
    Row(
        Modifier.fillMaxWidth()
            .let { if (onClick != null) it.clickable(onClick = onClick) else it }
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Text(grade.glyph, color = tone, style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodyMedium, color = Palette.Text)
            Text(
                evidence,
                style = MaterialTheme.typography.labelSmall,
                color = Palette.TextFaint,
            )
        }
    }
}

/** The transport label. Never "connected" — always the measurement and its age. */
@Composable
fun TransportBadge(text: String, live: Boolean) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier.width(7.dp)
                .height(7.dp)
                .clip(RoundedCornerShape(4.dp))
                .background(if (live) Palette.Evidenced else Palette.Unverified)
        )
        Spacer(Modifier.width(8.dp))
        Text(text, style = MaterialTheme.typography.labelSmall, color = Palette.TextDim)
    }
}

/**
 * The capture ribbon: 168 cells, one per hour of the last week.
 *
 * A shape rather than a number, because "is it running" and "was there a hole
 * on Tuesday" are the same question asked at two zoom levels and a percentage
 * answers neither. No labels and no legend — the detail is one tap deeper, and
 * a legend on a 168-cell grid is bigger than the grid.
 */
@Composable
fun RibbonView(coverage: Coverage, modifier: Modifier = Modifier) {
    Canvas(modifier.fillMaxWidth().height(64.dp)) {
        val cols = Coverage.CELLS / Coverage.DAYS // 24
        val rows = Coverage.DAYS
        val gap = 1.5f
        val cellW = (size.width - gap * (cols - 1)) / cols
        val cellH = (size.height - gap * (rows - 1)) / rows
        for (i in 0 until Coverage.CELLS) {
            val day = i / cols
            val hour = i % cols
            val color =
                when (coverage.cells[i]) {
                    Coverage.COVERED -> Palette.RibbonCovered
                    Coverage.SILENT -> Palette.RibbonSilent
                    Coverage.HOLE -> Palette.RibbonHole
                    else -> Palette.RibbonUnknown
                }
            drawRect(
                color = color,
                topLeft =
                    androidx.compose.ui.geometry.Offset(
                        hour * (cellW + gap),
                        day * (cellH + gap),
                    ),
                size = androidx.compose.ui.geometry.Size(cellW, cellH),
            )
        }
    }
}

/**
 * A run's history against the operator's own spread.
 *
 * The band is the interquartile range of the same series, not a population
 * norm: the only comparison that means anything here is with yourself, and a
 * norm would invite the judgement this whole surface is built to avoid.
 */
@Composable
fun Sparkline(values: List<Double>, modifier: Modifier = Modifier, invertGood: Boolean = true) {
    if (values.isEmpty()) return
    Canvas(modifier.fillMaxWidth().height(44.dp)) {
        val sorted = values.sorted()
        val q1 = sorted[(sorted.size * 0.25).toInt().coerceIn(0, sorted.size - 1)]
        val q3 = sorted[(sorted.size * 0.75).toInt().coerceIn(0, sorted.size - 1)]
        val lo = sorted.first()
        val hi = sorted.last()
        val span = max(1e-6, hi - lo)

        fun y(v: Double): Float {
            val t = ((v - lo) / span).toFloat()
            return if (invertGood) t * size.height else (1f - t) * size.height
        }

        drawRect(
            color = Palette.AccentDim.copy(alpha = 0.22f),
            topLeft = androidx.compose.ui.geometry.Offset(0f, min(y(q1), y(q3))),
            size =
                androidx.compose.ui.geometry.Size(
                    size.width,
                    max(2f, kotlin.math.abs(y(q3) - y(q1))),
                ),
        )

        val stepX = if (values.size <= 1) 0f else size.width / (values.size - 1)
        var prev: androidx.compose.ui.geometry.Offset? = null
        values.forEachIndexed { i, v ->
            val p = androidx.compose.ui.geometry.Offset(i * stepX, y(v))
            prev?.let { drawLine(Palette.Accent, it, p, strokeWidth = 2.5f) }
            prev = p
        }
        prev?.let { drawCircle(Palette.Accent, radius = 4f, center = it) }
    }
}

/** A trial-progress arc for the instrument runners: no text, no countdown digits. */
@Composable
fun ProgressArc(fraction: Float, modifier: Modifier = Modifier) {
    Canvas(modifier.fillMaxWidth().height(4.dp)) {
        drawRect(Palette.Hairline, size = size)
        drawRect(
            Palette.Accent,
            size = androidx.compose.ui.geometry.Size(size.width * fraction.coerceIn(0f, 1f), size.height),
        )
    }
}

/** A big thumb-height verb. The home row is four of these. */
@Composable
fun VerbButton(label: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Box(
        modifier
            .heightIn(min = 60.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(Palette.SurfaceHigh)
            .border(1.dp, Palette.Hairline, RoundedCornerShape(12.dp))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = MaterialTheme.typography.titleMedium, color = Palette.Text)
    }
}

/** A ring, used by hold-still captures where a progress bar would read as a deadline. */
@Composable
fun HoldRing(fraction: Float, modifier: Modifier = Modifier) {
    Canvas(modifier) {
        val stroke = 10f
        val inset = stroke / 2
        drawArc(
            color = Palette.Hairline,
            startAngle = -90f,
            sweepAngle = 360f,
            useCenter = false,
            style = Stroke(width = stroke),
            topLeft = androidx.compose.ui.geometry.Offset(inset, inset),
            size = androidx.compose.ui.geometry.Size(size.width - stroke, size.height - stroke),
        )
        drawArc(
            color = Palette.Accent,
            startAngle = -90f,
            sweepAngle = 360f * fraction.coerceIn(0f, 1f),
            useCenter = false,
            style = Stroke(width = stroke),
            topLeft = androidx.compose.ui.geometry.Offset(inset, inset),
            size = androidx.compose.ui.geometry.Size(size.width - stroke, size.height - stroke),
        )
    }
}
