package dev.sinnix.phone.ui.steering

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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import dev.sinnix.phone.AppGraph
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.instruments.OfferPolicy
import dev.sinnix.phone.sync.Inbox
import dev.sinnix.phone.ui.Card
import dev.sinnix.phone.ui.SectionLabel
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.theme.Palette
import kotlinx.coroutines.launch
import org.json.JSONObject

/**
 * The steering front-end.
 *
 * Three screens, all answerable standing up, all riding the same rule: the app
 * never sends anything itself. It writes what the operator decided, prime acts,
 * and a receipt comes back. That is what lets a ready queue exist on a device
 * that is offline half the time without ever claiming something happened that
 * did not.
 *
 * Every one of them renders the staleness of what it is showing. A menu from
 * this morning and a menu from four days ago look identical unless the screen
 * says which one it is holding, and acting on the wrong one is worse than not
 * acting.
 */
@Composable
fun RitualScreen(nav: NavController) {
    val ctx = LocalContext.current
    val transport = remember { AppGraph.transport(ctx) }
    val scope = rememberCoroutineScope()

    var steering by remember { mutableStateOf<JSONObject?>(null) }
    var live by remember { mutableStateOf(false) }
    val chosen = remember { mutableStateMapOf<String, Float>() }
    var sent by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        val (s, isLive) = transport.steering()
        steering = s
        live = isLive
    }

    val menu = steering?.optJSONArray("menu")

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card {
            SectionLabel("Morning")
            Text(
                "One to three intentions, with how likely you think each is.",
                style = MaterialTheme.typography.bodyMedium,
                color = Palette.TextDim,
            )
            Text(
                if (live) "live from prime" else OfferPolicy.stalenessOf(ctx, Inbox.STEERING),
                style = MaterialTheme.typography.labelSmall,
                color = if (live) Palette.Evidenced else Palette.Unverified,
            )
        }

        if (menu == null || menu.length() == 0) {
            Card {
                Text(
                    "No standing menu has reached the phone yet.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Palette.TextDim,
                )
            }
        } else {
            for (i in 0 until menu.length()) {
                val item = menu.optJSONObject(i) ?: continue
                val id = item.optString("id")
                val picked = chosen.containsKey(id)
                Card(onClick = {
                    if (picked) chosen.remove(id) else if (chosen.size < 3) chosen[id] = 0.5f
                }) {
                    Text(
                        item.optString("title", id),
                        style = MaterialTheme.typography.titleMedium,
                        color = if (picked) Palette.Accent else Palette.Text,
                    )
                    if (picked) {
                        // A coarse slider, not a number field. A probability
                        // typed to the percent is false precision, and the
                        // calibration curve it feeds cares about the decade.
                        Slider(
                            value = chosen[id] ?: 0.5f,
                            onValueChange = { chosen[id] = it },
                            steps = 9,
                            colors =
                                SliderDefaults.colors(
                                    thumbColor = Palette.Accent,
                                    activeTrackColor = Palette.AccentDim,
                                ),
                        )
                        Text(
                            probabilityWord((chosen[id] ?: 0.5f)),
                            style = MaterialTheme.typography.labelMedium,
                            color = Palette.TextDim,
                        )
                    }
                }
            }
        }

        sent?.let {
            Card { Text(it, style = MaterialTheme.typography.labelMedium, color = Palette.TextDim) }
        }

        VerbButton("Commit", Modifier.fillMaxWidth()) {
            val payload =
                chosen.entries.map { (id, p) ->
                    JSONObject().put("id", id).put("probability", Math.round(p * 10) / 10.0)
                }
            scope.launch {
                val path =
                    transport.send(
                        "steering_ritual",
                        "intentions", org.json.JSONArray(payload),
                    )
                Events.record(ctx, "steering_ritual", "count", payload.size, "path", path.name)
                sent = path.label
            }
        }
    }
}

@Composable
fun ResolveScreen(nav: NavController) {
    val ctx = LocalContext.current
    val transport = remember { AppGraph.transport(ctx) }
    val scope = rememberCoroutineScope()

    var steering by remember { mutableStateOf<JSONObject?>(null) }
    val resolved = remember { mutableStateMapOf<String, String>() }
    var note by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) { steering = transport.steering().first }

    val commitments = steering?.optJSONArray("commitments")

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card {
            SectionLabel("Resolve")
            Text(
                "Yesterday's commitments. One tap each — the calibration curve lives on the hub.",
                style = MaterialTheme.typography.bodySmall,
                color = Palette.TextDim,
            )
            Text(
                OfferPolicy.stalenessOf(ctx, Inbox.STEERING),
                style = MaterialTheme.typography.labelSmall,
                color = Palette.TextFaint,
            )
        }

        if (commitments == null || commitments.length() == 0) {
            Card {
                Text("Nothing open.", style = MaterialTheme.typography.bodyMedium, color = Palette.TextDim)
            }
        }

        for (i in 0 until (commitments?.length() ?: 0)) {
            val c = commitments?.optJSONObject(i) ?: continue
            val id = c.optString("id")
            Card {
                Text(
                    c.optString("title", id),
                    style = MaterialTheme.typography.titleMedium,
                    color = Palette.Text,
                )
                c.optString("forecast").takeIf { it.isNotEmpty() }?.let {
                    Text(
                        "you said $it",
                        style = MaterialTheme.typography.labelSmall,
                        color = Palette.TextFaint,
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("done", "missed", "partly").forEach { outcome ->
                        VerbButton(
                            if (resolved[id] == outcome) "✓ $outcome" else outcome,
                            Modifier.weight(1f),
                        ) {
                            resolved[id] = outcome
                            scope.launch {
                                val path =
                                    transport.send(
                                        "steering_resolve",
                                        "id", id,
                                        "outcome", outcome,
                                    )
                                note = "$id · ${path.label}"
                            }
                        }
                    }
                }
            }
        }

        note?.let {
            Card { Text(it, style = MaterialTheme.typography.labelMedium, color = Palette.TextDim) }
        }
    }
}

/**
 * The ready queue: spend a stack, do not work a list.
 *
 * A visible count that goes down and nothing else. This is the
 * composition/transmission decoupling made physical — the hard part was
 * writing the thing, which already happened somewhere else; what is left is
 * one decision per card, and the UI should not make it feel like more.
 *
 * SEND writes an intent. It is never a send, and the label never says it was.
 */
@Composable
fun ReadyQueueScreen(nav: NavController) {
    val ctx = LocalContext.current
    val transport = remember { AppGraph.transport(ctx) }
    val scope = rememberCoroutineScope()

    var steering by remember { mutableStateOf<JSONObject?>(null) }
    val handed = remember { mutableStateMapOf<String, String>() }

    LaunchedEffect(Unit) { steering = transport.steering().first }

    val queue = steering?.optJSONArray("ready_queue")
    val remaining = (queue?.length() ?: 0) - handed.size

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card {
            Text(
                if (remaining <= 0) "stack spent" else "$remaining in the stack",
                style = MaterialTheme.typography.displaySmall,
                color = Palette.Text,
            )
            Text(
                OfferPolicy.stalenessOf(ctx, Inbox.STEERING),
                style = MaterialTheme.typography.labelSmall,
                color = Palette.TextFaint,
            )
        }

        for (i in 0 until (queue?.length() ?: 0)) {
            val item = queue?.optJSONObject(i) ?: continue
            val id = item.optString("id")
            if (handed.containsKey(id)) continue
            Card {
                Text(
                    item.optString("card", item.optString("title", id)),
                    style = MaterialTheme.typography.bodyMedium,
                    color = Palette.Text,
                )
                VerbButton("Send", Modifier.fillMaxWidth()) {
                    scope.launch {
                        val path =
                            transport.send(
                                "ready_send",
                                "id", id,
                                "queue_token", item.optString("send_token"),
                            )
                        handed[id] = path.label
                    }
                }
            }
        }

        handed.forEach { (id, label) ->
            Card {
                Text(
                    "$id — $label",
                    style = MaterialTheme.typography.labelMedium,
                    color = Palette.TextDim,
                )
                Text(
                    "prime confirms it as a notification",
                    style = MaterialTheme.typography.labelSmall,
                    color = Palette.TextFaint,
                )
            }
        }
    }
}

/** Words at the ends, because "70%" invites a precision nobody has. */
private fun probabilityWord(p: Float): String =
    when {
        p <= 0.15f -> "unlikely (${(p * 100).toInt()}%)"
        p >= 0.85f -> "near certain (${(p * 100).toInt()}%)"
        else -> "${(p * 100).toInt()}%"
    }
