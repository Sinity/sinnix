package dev.sinnix.phone.ui.capture

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.PowerManager
import android.provider.Settings
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.navigation.NavController
import dev.sinnix.phone.capture.Grade
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import dev.sinnix.phone.ui.Card
import dev.sinnix.phone.ui.GradeRow
import dev.sinnix.phone.ui.SectionLabel
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.theme.Palette
import java.io.File

/**
 * Grants, probed rather than asked about.
 *
 * The storage row writes an actual file and deletes it. That is not paranoia
 * about the API — `isExternalStorageManager()` has returned true on this
 * device while `/sdcard/sinnix-ambient` was not writable, and the difference
 * between those two facts is every chunk recorded into a directory Termux
 * cannot read.
 *
 * MIUI autostart has no API at all, so it is permanently unverifiable and is
 * drawn that way. What stands in for a check is two weaker things, both shown:
 * an operator attestation with its date, and an inference from the log — a
 * boot event with no chunk close after it is evidence autostart is off. A
 * green tick there would be a lie in a self-knowledge instrument.
 */
@Composable
fun GrantsScreen(nav: NavController) {
    val ctx = LocalContext.current
    val storage = remember { probeStorage(ctx) }
    val notifications = remember { notificationsGranted(ctx) }
    val battery = remember { batteryExempt(ctx) }
    val mic = remember { micGranted(ctx) }
    val listener = remember { listenerEnabled(ctx) }
    val bootInference = remember { bootInference(ctx) }
    val attestedAt = remember { Prefs.autostartAttestedAt(ctx) }

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card {
            SectionLabel("Verifiable")
            GradeRow(
                Grade.of(true, mic),
                "Microphone",
                if (mic) "RECORD_AUDIO granted; the foreground service type satisfies the appop"
                else "RECORD_AUDIO not granted — capture cannot work",
            ) {
                openAppSettings(ctx)
            }
            GradeRow(
                Grade.of(true, storage.first),
                "All-files access",
                storage.second,
            ) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    ctx.startActivity(
                        Intent(
                            Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                            Uri.parse("package:${ctx.packageName}"),
                        )
                    )
                }
            }
            GradeRow(
                Grade.of(true, battery),
                "Battery optimisation exemption",
                if (battery) "on the Doze whitelist" else "not exempt — Doze will throttle rotation",
            ) {
                ctx.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            }
            GradeRow(
                Grade.of(true, notifications),
                "Notifications",
                if (notifications) "POST_NOTIFICATIONS granted"
                else "denied — the capture notification and every alert are invisible",
            ) {
                openAppSettings(ctx)
            }
            GradeRow(
                Grade.of(true, listener),
                "Notification listener",
                if (listener) "bound — the notification lane is capturing"
                else "not bound — the notification lane is off",
            ) {
                ctx.startActivity(Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS"))
            }
        }

        Card {
            SectionLabel("Unverifiable")
            GradeRow(
                Grade.UNVERIFIED,
                "MIUI background autostart",
                buildString {
                    append(
                        if (attestedAt == 0L) "never attested"
                        else "attested ${Stamps.iso(attestedAt).dropLast(1).replace('T', ' ')}"
                    )
                    append(" · ")
                    append(bootInference)
                },
            )
            Text(
                "There is no API for this setting and no adb assertion path. The app " +
                    "cannot check it, so it does not claim to. What it can do is notice " +
                    "that a boot produced no capture.",
                style = MaterialTheme.typography.bodySmall,
                color = Palette.TextDim,
            )
            VerbButton("Open the MIUI autostart list", Modifier.fillMaxWidth()) {
                try {
                    ctx.startActivity(
                        Intent().setClassName(
                            "com.miui.securitycenter",
                            "com.miui.permcenter.autostart.AutoStartManagementActivity",
                        )
                    )
                } catch (e: Exception) {
                    openAppSettings(ctx)
                }
            }
            VerbButton("I have turned it on", Modifier.fillMaxWidth()) {
                val now = System.currentTimeMillis()
                Prefs.setAutostartAttestedAt(ctx, now)
                Events.record(ctx, "attestation", "grant", "miui_autostart", "asserted", true)
            }
        }
    }
}

/**
 * Write a real file, then delete it.
 *
 * The API answer and the filesystem answer have disagreed on this device, and
 * only one of them is the one that matters at 3am when a chunk needs a home.
 */
private fun probeStorage(ctx: Context): Pair<Boolean, String> {
    if (!Storage.haveAllFilesAccess()) {
        return false to "isExternalStorageManager() is false"
    }
    val dir = File(Storage.SHARED_DIR)
    val probe = File(dir, ".sinnix-write-probe")
    return try {
        if (!dir.isDirectory && !dir.mkdirs()) {
            return false to "the API says granted, but $dir cannot be created"
        }
        probe.writeText("probe")
        val ok = probe.isFile && probe.length() > 0
        probe.delete()
        if (ok) true to "wrote and removed a probe file in ${Storage.SHARED_DIR}"
        else false to "the API says granted, but the probe write produced nothing"
    } catch (e: Exception) {
        false to "the API says granted, but writing failed: ${e.message}"
    }
}

/**
 * Did the last boot lead to capture?
 *
 * The only handle on autostart the app has. A boot event followed within a few
 * minutes by a closed chunk is evidence the grant is on; a boot with nothing
 * after it is evidence it is not. Neither is proof, and the wording says so.
 */
private fun bootInference(ctx: Context): String {
    val events = Events.recent(ctx, 7)
    val lastBoot =
        events.filter { it.optString("kind") == "boot" }.maxByOrNull {
            Stamps.parse(it.optString("ts"))
        } ?: return "no boot recorded in the last week"
    val bootAt = Stamps.parse(lastBoot.optString("ts"))
    val firstChunkAfter =
        events
            .filter { it.optString("kind") == "chunk_closed" }
            .map { Stamps.parse(it.optString("ts")) }
            .filter { it > bootAt }
            .minOrNull()
    return when {
        firstChunkAfter == null -> "last boot produced no chunk — autostart looks off"
        firstChunkAfter - bootAt < 10 * 60_000L ->
            "capture resumed ${(firstChunkAfter - bootAt) / 1000}s after the last boot"
        else -> "capture resumed ${(firstChunkAfter - bootAt) / 60_000}m after the last boot"
    }
}

private fun micGranted(ctx: Context): Boolean =
    ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) ==
        PackageManager.PERMISSION_GRANTED

private fun notificationsGranted(ctx: Context): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED

private fun batteryExempt(ctx: Context): Boolean =
    ctx.getSystemService(PowerManager::class.java)?.isIgnoringBatteryOptimizations(ctx.packageName) ==
        true

private fun listenerEnabled(ctx: Context): Boolean =
    Settings.Secure.getString(ctx.contentResolver, "enabled_notification_listeners")
        ?.contains(ctx.packageName) == true

private fun openAppSettings(ctx: Context) {
    ctx.startActivity(
        Intent(
            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.parse("package:${ctx.packageName}"),
        )
    )
}
