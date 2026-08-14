package dev.sinnix.phone.ui.sleep

import android.app.AlarmManager
import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.instruments.sleep.SleepAlarm
import dev.sinnix.phone.ui.Card
import dev.sinnix.phone.ui.SectionLabel
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.theme.Palette
import java.util.Calendar

/**
 * Arming the sleep-inertia protocol.
 *
 * The instrument existed and could not be started: `SleepAlarm.scheduleWake`
 * had no caller anywhere in the app, so the one measurement that has to be
 * anchored to a real waking moment was unreachable.
 *
 * The protocol, stated where the operator arms it rather than only in a bead:
 * the alarm fires, dismissing it launches a ten-trial PVT immediately, and two
 * follow-ups at +10 and +30 minutes turn one point into a decay curve. The
 * whole reason it lives on the phone is that a lab has to wake you to catch
 * this, and being woken is the confound.
 *
 * It is opt-in, per-night, and never becomes the default alarm app. Hijacking
 * someone's morning to run a test on them is a good way to make them stop.
 */
@Composable
fun SleepRitualScreen(nav: NavController) {
    val ctx = LocalContext.current
    var hour by remember { mutableStateOf(Prefs.wakeHour(ctx).toFloat()) }
    var minute by remember { mutableStateOf(Prefs.wakeMinute(ctx).toFloat()) }
    var armed by remember { mutableStateOf(Prefs.wakeArmed(ctx)) }
    var note by remember { mutableStateOf<String?>(null) }

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card {
            SectionLabel("Wake")
            Text(
                "%02d:%02d".format(hour.toInt(), minute.toInt()),
                style = MaterialTheme.typography.displaySmall,
                color = Palette.Text,
            )
            Text("hour", style = MaterialTheme.typography.labelSmall, color = Palette.TextFaint)
            Slider(
                value = hour,
                onValueChange = { hour = it },
                valueRange = 0f..23f,
                steps = 22,
                colors = SliderDefaults.colors(thumbColor = Palette.Accent,
                    activeTrackColor = Palette.AccentDim),
            )
            Text("minute", style = MaterialTheme.typography.labelSmall, color = Palette.TextFaint)
            Slider(
                value = minute,
                onValueChange = { minute = it },
                valueRange = 0f..55f,
                steps = 10,
                colors = SliderDefaults.colors(thumbColor = Palette.Accent,
                    activeTrackColor = Palette.AccentDim),
            )
        }

        Card {
            SectionLabel("What it does")
            Text(
                "The alarm goes off. Dismissing it runs ten reaction trials, right " +
                    "there on the lock screen, before you are properly up — then " +
                    "again at ten and thirty minutes. Three points is a decay curve; " +
                    "one is a number.",
                style = MaterialTheme.typography.bodyMedium,
                color = Palette.TextDim,
            )
        }

        note?.let {
            Card { Text(it, style = MaterialTheme.typography.bodyMedium, color = Palette.Unverified) }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            VerbButton(if (armed) "Re-arm" else "Arm for tonight", Modifier.weight(1f)) {
                val refused = exactAlarmsRefused(ctx)
                if (refused != null) {
                    // Said, not swallowed. An inertia probe at an unknown offset
                    // from waking is not a measurement of inertia, so a protocol
                    // that quietly did not arm would be worse than one that
                    // refused loudly.
                    note = refused
                    return@VerbButton
                }
                SleepAlarm.scheduleWake(ctx, nextOccurrence(hour.toInt(), minute.toInt()))
                Prefs.setWake(ctx, hour.toInt(), minute.toInt(), true)
                armed = true
                note = "armed for %02d:%02d".format(hour.toInt(), minute.toInt())
            }
            if (armed) {
                VerbButton("Disarm", Modifier.weight(1f)) {
                    SleepAlarm.cancel(ctx)
                    Prefs.setWake(ctx, hour.toInt(), minute.toInt(), false)
                    armed = false
                    note = "disarmed"
                }
            }
        }
    }
}

/**
 * Whether the platform will honour an alarm clock, checked before arming.
 *
 * Returns the reason it will not, or null. `canScheduleExactAlarms` is the only
 * way to know without trying, and trying means finding out at 07:00 that the
 * alarm was never set.
 */
private fun exactAlarmsRefused(ctx: Context): String? {
    val am = ctx.getSystemService(AlarmManager::class.java) ?: return "no alarm service"
    return if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.S &&
        !am.canScheduleExactAlarms()
    ) {
        "Exact alarms are not permitted for this app, so the protocol cannot be " +
            "anchored to a real waking moment. Grant them in Settings first."
    } else {
        null
    }
}

/** The next time that clock reads this, today or tomorrow. */
private fun nextOccurrence(hour: Int, minute: Int): Long {
    val cal =
        Calendar.getInstance().apply {
            set(Calendar.HOUR_OF_DAY, hour)
            set(Calendar.MINUTE, minute)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
    if (cal.timeInMillis <= System.currentTimeMillis()) {
        cal.add(Calendar.DAY_OF_YEAR, 1)
    }
    return cal.timeInMillis
}
