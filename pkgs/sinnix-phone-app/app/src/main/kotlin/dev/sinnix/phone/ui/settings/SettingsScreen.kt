package dev.sinnix.phone.ui.settings

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.health.connect.client.PermissionController
import androidx.navigation.NavController
import dev.sinnix.phone.capture.SpeechService
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.ingress.HealthLane
import dev.sinnix.phone.ui.Card
import dev.sinnix.phone.ui.SectionLabel
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.theme.Palette

/**
 * The knobs, in one place, with their costs stated.
 *
 * Until now every one of these existed in `Prefs` with no way to reach it: the
 * hub address, the EMA cadence, the alarm, the lanes. A preference nothing
 * writes is a preference that does not exist, and four of them had accumulated.
 *
 * Each lane says what it costs rather than just what it is. "Location" tells
 * you nothing about whether to switch it on; "a fix every ten minutes, only
 * when you have moved 150 m" does.
 */
@Composable
fun SettingsScreen(nav: NavController) {
    val ctx = LocalContext.current

    var speech by remember { mutableStateOf(Prefs.speechLane(ctx)) }
    var location by remember { mutableStateOf(Prefs.locationLane(ctx)) }
    var health by remember { mutableStateOf(Prefs.healthLane(ctx)) }
    var sleepDetect by remember { mutableStateOf(Prefs.sleepDetect(ctx)) }
    var power by remember { mutableStateOf(Prefs.powerLane(ctx)) }
    var emaPerDay by remember { mutableStateOf(Prefs.emaPerDay(ctx).toFloat()) }
    var hub by remember { mutableStateOf(Prefs.hubBaseUrl(ctx)) }
    var receiver by remember { mutableStateOf(Prefs.receiverHost(ctx)) }

    val askLocation =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            Events.record(ctx, "grant_transition", "grant", "ACCESS_COARSE_LOCATION", "granted", granted)
            if (!granted) {
                Prefs.setLocationLane(ctx, false)
                location = false
            }
        }

    // Health Connect keeps its own permission state, so this is its contract
    // rather than the platform's RequestPermission. The result is written as
    // a grant transition for the same reason the notification listener's is:
    // a silent revocation should explain the gap it causes, not leave it to
    // be reconstructed months later. Unlike the location lane above, a denial
    // does NOT switch the lane off -- HealthLane already reports its own
    // blocked state as an event, and a lane that disables itself on refusal
    // is a lane nobody notices is off.
    val askHealth =
        rememberLauncherForActivityResult(
            PermissionController.createRequestPermissionResultContract()
        ) { granted: Set<String> ->
            Events.record(
                ctx,
                "grant_transition",
                "grant",
                "health_connect",
                "granted",
                granted.containsAll(HealthLane.QUERYABLE_PERMISSIONS),
                "granted_count",
                granted.size,
            )
        }

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card {
            SectionLabel("Lanes")

            LaneRow(
                "Speech to prime",
                "Streams what you say — and only what you say — to prime as it is " +
                    "said, on any network. The heaviest thing here: a second " +
                    "microphone and an outbound connection whenever you speak.",
                speech,
            ) { on ->
                val mic =
                    ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) ==
                        PackageManager.PERMISSION_GRANTED
                if (on && !mic) return@LaneRow
                speech = on
                Prefs.setSpeechLane(ctx, on)
                if (on) SpeechService.start(ctx) else SpeechService.stop(ctx)
                Events.record(ctx, "lane_toggle", "lane", "speech", "enabled", on)
            }

            LaneRow(
                "Location",
                "A coarse fix every ten minutes, and only once you have moved 150 m. " +
                    "The covariate that lets a reaction time know where it happened.",
                location,
            ) { on ->
                location = on
                Prefs.setLocationLane(ctx, on)
                Events.record(ctx, "lane_toggle", "lane", "location", "enabled", on)
                if (on) askLocation.launch(Manifest.permission.ACCESS_COARSE_LOCATION)
            }

            LaneRow(
                "Health Connect",
                "Reads steps, heart rate and sleep from the band directly, because " +
                    "the scheduled export has never once landed a file. " +
                    "Currently: ${HealthLane.availability(ctx)}.",
                health,
            ) { on ->
                health = on
                Prefs.setHealthLane(ctx, on)
                Events.record(ctx, "lane_toggle", "lane", "health", "enabled", on)
                // Same shape as the location lane: switching a lane on asks
                // for what it needs, instead of leaving the operator to
                // discover separately that it is on and starved.
                if (on) askHealth.launch(HealthLane.PERMISSIONS)
            }

            LaneRow(
                "Sleep estimate",
                "Infers sleep from stillness, dark and screen state — an estimate " +
                    "independent of the band, so the two disagreeing is a finding.",
                sleepDetect,
            ) { on ->
                sleepDetect = on
                Prefs.setSleepDetect(ctx, on)
            }

            LaneRow(
                "Battery and thermal",
                "A row on change or every fifteen minutes. Free: the capture " +
                    "service already reads both.",
                power,
            ) { on ->
                power = on
                Prefs.setPowerLane(ctx, on)
            }
        }

        Card {
            SectionLabel("Check-ins")
            Text(
                "${emaPerDay.toInt()} a day",
                style = MaterialTheme.typography.titleMedium,
                color = Palette.Text,
            )
            Slider(
                value = emaPerDay,
                onValueChange = { emaPerDay = it },
                onValueChangeFinished = { Prefs.setEmaPerDay(ctx, emaPerDay.toInt()) },
                valueRange = 0f..8f,
                steps = 7,
                colors =
                    SliderDefaults.colors(
                        thumbColor = Palette.Accent,
                        activeTrackColor = Palette.AccentDim,
                    ),
            )
            Text(
                "Jittered across waking hours, answerable from the shade. More " +
                    "samples is what makes this a method rather than a diary; fewer " +
                    "is what makes it get answered. Zero turns it off.",
                style = MaterialTheme.typography.bodySmall,
                color = Palette.TextDim,
            )
        }

        Card {
            SectionLabel("Sleep protocol")
            Text(
                if (Prefs.wakeArmed(ctx))
                    "armed for %02d:%02d".format(Prefs.wakeHour(ctx), Prefs.wakeMinute(ctx))
                else "not armed",
                style = MaterialTheme.typography.bodyMedium,
                color = if (Prefs.wakeArmed(ctx)) Palette.Accent else Palette.TextDim,
            )
            VerbButton("Sleep ritual", Modifier.fillMaxWidth()) { nav.navigate("sleep") }
        }

        Card {
            SectionLabel("Prime")
            OutlinedTextField(
                value = hub,
                onValueChange = {
                    hub = it
                    Prefs.setHubBaseUrl(ctx, it.trim())
                },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("hub base URL") },
            )
            OutlinedTextField(
                value = receiver,
                onValueChange = {
                    receiver = it
                    Prefs.setReceiverHost(ctx, it.trim())
                },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("speech receiver host:port") },
            )
            Text(
                "Two addresses because they are two services: the hub is HTTP " +
                    "through Caddy, the receiver is a raw socket on its own port. " +
                    "One field standing for both would break whenever either moved.",
                style = MaterialTheme.typography.labelSmall,
                color = Palette.TextFaint,
            )
        }

        Card {
            SectionLabel("Grants this screen cannot make")
            // ASK for the health permissions, rather than opening the Health
            // Connect settings screen and hoping. The old button did the
            // latter, which cannot work: an app that has never issued a
            // request does not appear in Health Connect's app list, so the
            // operator arrived at a screen with nothing on it to grant. The
            // request contract is the only route that puts the app in front
            // of the consent dialog. Falls back to the settings intent when
            // Health Connect is not installed, where there is nothing to
            // request from.
            VerbButton("Health Connect permissions", Modifier.fillMaxWidth()) {
                try {
                    askHealth.launch(HealthLane.PERMISSIONS)
                } catch (e: Exception) {
                    try {
                        ctx.startActivity(Intent("androidx.health.ACTION_HEALTH_CONNECT_SETTINGS"))
                    } catch (e2: Exception) {
                        ctx.startActivity(
                            Intent(
                                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                Uri.parse("package:${ctx.packageName}"),
                            )
                        )
                    }
                }
            }
            VerbButton("Exact alarms", Modifier.fillMaxWidth()) {
                try {
                    ctx.startActivity(Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM))
                } catch (e: Exception) {
                    ctx.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.parse("package:${ctx.packageName}")))
                }
            }
        }
    }
}

@Composable
private fun LaneRow(
    title: String,
    cost: String,
    checked: Boolean,
    onChange: (Boolean) -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 8.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyMedium, color = Palette.Text)
            Text(cost, style = MaterialTheme.typography.labelSmall, color = Palette.TextFaint)
        }
        Switch(
            checked = checked,
            onCheckedChange = onChange,
            colors =
                SwitchDefaults.colors(
                    checkedThumbColor = Palette.Accent,
                    checkedTrackColor = Palette.AccentDim,
                ),
        )
    }
}
