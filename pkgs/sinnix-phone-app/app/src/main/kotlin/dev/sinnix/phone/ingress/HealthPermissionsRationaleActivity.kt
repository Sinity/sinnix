package dev.sinnix.phone.ingress

import android.app.Activity
import android.os.Bundle
import android.widget.Toast

/**
 * Health Connect's required answer to "why does this app want health data?".
 *
 * This exists because Health Connect will not list an app that cannot answer
 * `ACTION_SHOW_PERMISSIONS_RATIONALE`, and an app it does not list can never
 * hold health permissions -- no matter what the manifest declares or what
 * `pm grant` reports. That is the whole reason [HealthLane] read nothing:
 * not a broken pipeline, an app Health Connect could not see.
 *
 * Deliberately not a screen. The rationale is one sentence, the operator
 * arrives here from Health Connect's own UI already knowing what they are
 * granting, and a Compose activity here would be a second place to maintain
 * the same text. Show it and get out of the way.
 */
class HealthPermissionsRationaleActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Toast.makeText(
            this,
            "Sinnix reads steps, heart rate and sleep from Health Connect so the " +
                "band's data joins the rest of the estate's capture. It is read-only " +
                "and stays on your own machines.",
            Toast.LENGTH_LONG,
        ).show()
        finish()
    }
}
