package dev.sinnix.phone.ui.widget

import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp
import androidx.glance.GlanceId
import androidx.glance.GlanceModifier
import androidx.glance.GlanceTheme
import androidx.glance.action.actionStartActivity
import androidx.glance.action.clickable
import androidx.glance.appwidget.GlanceAppWidget
import androidx.glance.appwidget.GlanceAppWidgetReceiver
import androidx.glance.appwidget.provideContent
import androidx.glance.appwidget.updateAll
import androidx.glance.background
import androidx.glance.layout.Alignment
import androidx.glance.layout.Column
import androidx.glance.layout.Row
import androidx.glance.layout.fillMaxSize
import androidx.glance.layout.fillMaxWidth
import androidx.glance.layout.padding
import androidx.glance.text.Text
import androidx.glance.text.TextStyle
import androidx.glance.unit.ColorProvider
import dev.sinnix.phone.capture.Coverage
import dev.sinnix.phone.capture.Status
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.sync.Inbox
import dev.sinnix.phone.ui.mark.MarkActivity
import dev.sinnix.phone.ui.talk.TalkActivity
import dev.sinnix.phone.ui.theme.Palette
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * The home-screen widget.
 *
 * Glance makes this possible without hand-writing RemoteViews, which is what
 * kept a widget out of the previous design entirely — `AppWidgetProvider`
 * needs XML layouts, and the old build had no resource tree at all.
 *
 * It says two things and offers two verbs. Two, because a widget with a
 * scrolling list is a widget nobody reads: the estate line answers "is
 * anything wrong", the capture line answers "is it still recording", and Talk
 * and Mark are the verbs whose whole value is costing nothing to reach.
 */
class SinnixWidget : GlanceAppWidget() {

    companion object {
        /**
         * Redraw, from whatever just changed what the widget says.
         *
         * The provider declares `updatePeriodMillis="0"` deliberately: the
         * framework's minimum is thirty minutes and it wakes the device to
         * deliver it, which for a surface whose content changes on chunk
         * close and inbox arrival would be both too slow and too expensive.
         * Pushing on the event is cheaper and always current.
         */
        fun refresh(ctx: Context) {
            CoroutineScope(Dispatchers.Default).launch {
                try {
                    SinnixWidget().updateAll(ctx)
                } catch (e: Exception) {
                    // No widget placed, or the host is gone. Not a fault: the
                    // app works perfectly well without one on the home screen.
                }
            }
        }
    }

    override suspend fun provideGlance(context: Context, id: GlanceId) {
        val status = Status.read(context)
        val coverage = Coverage.of(context, System.currentTimeMillis())
        val glance = Inbox.readObject(context, Inbox.GLANCE)
        provideContent { WidgetBody(status, coverage, glance) }
    }
}

class SinnixWidgetReceiver : GlanceAppWidgetReceiver() {
    override val glanceAppWidget: GlanceAppWidget = SinnixWidget()
}

@Composable
private fun WidgetBody(status: JSONObject?, coverage: Coverage, glance: JSONObject?) {
    val heartbeat =
        Stamps.parse(status?.optString("updated_at").orEmpty()).let {
            if (it == 0L) -1L else (System.currentTimeMillis() - it) / 1000L
        }
    val alive = heartbeat in 0..120
    val muted = status?.optBoolean("muted") == true

    GlanceTheme {
        Column(
            GlanceModifier.fillMaxSize().background(Palette.Surface).padding(12.dp),
            verticalAlignment = Alignment.Vertical.CenterVertically,
        ) {
            Text(
                glance?.optString("verdict")?.ifEmpty { "estate quiet" } ?: "estate unknown",
                style = TextStyle(color = ColorProvider(Palette.Text)),
            )
            Text(
                when {
                    !alive -> "capture: no heartbeat"
                    muted -> "capture: no sound"
                    else -> "capture: unbroken ${coverage.unbrokenHours()}h"
                },
                style =
                    TextStyle(
                        color =
                            ColorProvider(
                                when {
                                    !alive -> Palette.Broken
                                    muted -> Palette.Unverified
                                    else -> Palette.Evidenced
                                }
                            )
                    ),
            )
            Row(GlanceModifier.fillMaxWidth().padding(top = 8.dp)) {
                Text(
                    "Talk",
                    modifier =
                        GlanceModifier.padding(8.dp)
                            .background(Palette.SurfaceHigh)
                            .clickable(actionStartActivity<TalkActivity>()),
                    style = TextStyle(color = ColorProvider(Palette.Accent)),
                )
                Text(
                    "Mark",
                    modifier =
                        GlanceModifier.padding(8.dp)
                            .background(Palette.SurfaceHigh)
                            .clickable(actionStartActivity<MarkActivity>()),
                    style = TextStyle(color = ColorProvider(Palette.Accent)),
                )
            }
        }
    }
}
