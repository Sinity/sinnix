package dev.sinnix.phone.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Place
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.core.content.ContextCompat
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import dev.sinnix.phone.capture.AmbientService
import dev.sinnix.phone.capture.Status
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Notifications
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.sync.InboxWatcher
import dev.sinnix.phone.ui.capture.CaptureScreen
import dev.sinnix.phone.ui.capture.GrantsScreen
import dev.sinnix.phone.ui.estate.EstateScreen
import dev.sinnix.phone.ui.home.HomeScreen
import dev.sinnix.phone.ui.instrument.InstrumentsScreen
import dev.sinnix.phone.ui.steering.ReadyQueueScreen
import dev.sinnix.phone.ui.steering.ResolveScreen
import dev.sinnix.phone.ui.steering.RitualScreen
import dev.sinnix.phone.ui.theme.Palette
import dev.sinnix.phone.ui.theme.SinnixTheme

/**
 * The one Activity.
 *
 * Everything that is not timing-critical or intent-entered is a route in here.
 * The bottom bar has four destinations because the app genuinely has four
 * things in it — the estate, the bench, the organ, and the place they meet —
 * and a drawer would hide three of them behind a gesture.
 */
class MainActivity : ComponentActivity() {

    private val requestNotifications =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            Events.record(this, "grant_transition", "grant", "POST_NOTIFICATIONS", "granted", granted)
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Notifications.ensureChannels(this)
        askForNotificationsOnce()
        // Decks registered here rather than as a side effect of visiting the
        // Bench: InstrumentActivity.launchOne resolves a deck id through this
        // registry, so a deck launched from a notification or an alarm would
        // otherwise resolve to nothing unless the operator happened to have
        // opened the shelf first.
        dev.sinnix.phone.decks.Decks.available(this)
        if (Prefs.speechLane(this)) dev.sinnix.phone.capture.SpeechService.start(this)

        setContent {
            SinnixTheme {
                Box(Modifier.fillMaxSize().background(Palette.Background)) {
                    AppScaffold(startRoute = intent?.getStringExtra("route"))
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
    }

    /**
     * Opening the app is itself a repair path, and it repairs two different
     * things.
     *
     * The obvious one: a dead service is restarted here rather than at the next
     * ten-minute watchdog sweep, because a person who opened the app because
     * something felt wrong should not wait out the rest of that interval.
     *
     * The subtle one, and the reason this is not just `if (!running) start()`:
     * a microphone-typed foreground service started from the **background**
     * runs without the while-in-use capability, and the platform responds by
     * silencing its recording rather than refusing it. `MY_PACKAGE_REPLACED`
     * starts the service from the background on every upgrade, so the state
     * this produces is a service that is genuinely running, genuinely writing
     * full-bitrate chunks, and recording exact zeroes — with logcat saying
     * "App op 27 missing, silencing record" and nothing else complaining.
     *
     * Cycling the recorder cannot fix that; the capability is decided when the
     * service starts, not when the recorder opens. Restarting the service
     * while an activity is in the foreground is the fix, and this is the only
     * place in the app that is reliably in the foreground.
     */
    override fun onResume() {
        super.onResume()
        if (Prefs.enabled(this)) {
            val muted = Status.read(this)?.optBoolean("muted", false) == true
            when {
                !AmbientService.running -> {
                    AmbientService.start(this)
                    Events.record(this, "capture_toggle", "state", "started", "by", "home_resume")
                }
                muted -> {
                    AmbientService.stop(this)
                    // A short gap so the old service has torn down before the
                    // new one asks for the microphone; starting into a
                    // still-live service would re-use the capability-less one.
                    window.decorView.postDelayed({ AmbientService.start(this) }, 700)
                    Events.record(
                        this,
                        "capture_toggle",
                        "state", "restarted",
                        "by", "foreground_reclaim",
                        "reason", "muted service cannot regain the microphone without a foreground start",
                    )
                }
            }
        }
        InboxWatcher.sweepOnce(this)
    }

    private fun askForNotificationsOnce() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted =
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED
        // Without this the foreground-service notification is invisible, which
        // makes the one surface the operator glances at most simply absent.
        if (!granted) requestNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
    }
}

private enum class Destination(
    val route: String,
    val label: String,
    val icon: ImageVector,
) {
    HOME("home", "Home", Icons.Filled.Home),
    ESTATE("estate", "Estate", Icons.Filled.Place),
    INSTRUMENTS("instruments", "Bench", Icons.Filled.List),
    CAPTURE("capture", "Capture", Icons.Filled.Settings),
}

@Composable
private fun AppScaffold(startRoute: String?) {
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val current = backStack?.destination?.route

    Scaffold(
        containerColor = Palette.Background,
        bottomBar = {
            NavigationBar(containerColor = Palette.Surface) {
                Destination.entries.forEach { d ->
                    NavigationBarItem(
                        selected = current == d.route,
                        onClick = {
                            nav.navigate(d.route) {
                                popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(d.icon, contentDescription = d.label) },
                        label = { Text(d.label) },
                        colors =
                            NavigationBarItemDefaults.colors(
                                selectedIconColor = Palette.Accent,
                                selectedTextColor = Palette.Accent,
                                indicatorColor = Palette.SurfaceHigh,
                                unselectedIconColor = Palette.TextFaint,
                                unselectedTextColor = Palette.TextFaint,
                            ),
                    )
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = nav,
            startDestination = startRoute?.takeIf { r -> Destination.entries.any { it.route == r } }
                ?: Destination.HOME.route,
            modifier = Modifier.padding(padding),
        ) {
            composable(Destination.HOME.route) { HomeScreen(nav) }
            composable(Destination.ESTATE.route) { EstateScreen(nav) }
            composable(Destination.INSTRUMENTS.route) { InstrumentsScreen(nav) }
            composable(Destination.CAPTURE.route) { CaptureScreen(nav) }
            composable("grants") { GrantsScreen(nav) }
            composable("settings") { dev.sinnix.phone.ui.settings.SettingsScreen(nav) }
            composable("sleep") { dev.sinnix.phone.ui.sleep.SleepRitualScreen(nav) }
            composable("ritual") { RitualScreen(nav) }
            composable("resolve") { ResolveScreen(nav) }
            composable("ready") { ReadyQueueScreen(nav) }
        }
    }
}
