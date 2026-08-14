package dev.sinnix.phone.capture

import android.content.Intent
import android.graphics.drawable.Icon
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import dev.sinnix.phone.R
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.ui.MainActivity
import org.json.JSONObject

/**
 * Capture state in the quick-settings shade.
 *
 * The shade is where a phone is actually looked at, so this is the cheapest
 * possible answer to "is it still recording" — no unlock, no app launch.
 *
 * It deliberately does **not** toggle capture. A control that can end a
 * multi-hour recording with one mis-swipe, from a surface people swipe through
 * without looking, is a hazard rather than a convenience; stopping is a
 * deliberate act and lives on the capture screen. Tapping here opens the app.
 */
class CaptureTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        render()
    }

    override fun onClick() {
        super.onClick()
        val intent =
            Intent(this, MainActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                putExtra("route", "capture")
            }
        // The Intent overload, not the PendingIntent one: this compiles against
        // targetSdk 33, matching the device, and the replacement only exists
        // from 34. Raising the target is not free here — see the manifest.
        @Suppress("DEPRECATION")
        startActivityAndCollapse(intent)
    }

    private fun render() {
        val tile = qsTile ?: return
        val status = Status.read(this)
        val age = status?.let { ageSeconds(it) } ?: -1
        val recording = status?.optBoolean("recording", false) == true
        val muted = status?.optBoolean("muted", false) == true
        val live = age >= 0 && age * 1000L < STALE_MILLIS

        // ACTIVE only for capture that is provably producing. A stale
        // status.json still says recording=true, and that claim is exactly what
        // a dead recorder leaves behind — so liveness is judged from the
        // heartbeat's age and the microphone's own amplitude, never from the
        // flag alone.
        when {
            live && recording && !muted -> {
                tile.state = Tile.STATE_ACTIVE
                setSubtitleCompat(tile, "${status?.optInt("chunks_closed", 0) ?: 0} chunks")
            }
            live && muted -> {
                tile.state = Tile.STATE_INACTIVE
                setSubtitleCompat(tile, "no sound")
            }
            status == null -> {
                tile.state = Tile.STATE_INACTIVE
                setSubtitleCompat(tile, "never started")
            }
            else -> {
                tile.state = Tile.STATE_INACTIVE
                setSubtitleCompat(tile, if (age < 0) "unknown" else "${age}s stale")
            }
        }
        tile.label = "Sinnix capture"
        tile.icon = Icon.createWithResource(this, R.drawable.ic_capture)
        tile.updateTile()
    }

    private fun setSubtitleCompat(tile: Tile, s: String) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) tile.subtitle = s
    }

    private fun ageSeconds(status: JSONObject): Long {
        val updated = Stamps.parse(status.optString("updated_at"))
        return if (updated == 0L) -1 else (System.currentTimeMillis() - updated) / 1000L
    }

    companion object {
        /** A heartbeat older than this means the writer is gone, whatever the file claims. */
        private const val STALE_MILLIS = 90_000L
    }
}
