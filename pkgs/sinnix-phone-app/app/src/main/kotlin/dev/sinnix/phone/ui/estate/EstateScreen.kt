package dev.sinnix.phone.ui.estate

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import dev.sinnix.phone.AppGraph
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.ui.Card
import dev.sinnix.phone.ui.SectionLabel
import dev.sinnix.phone.ui.StatRow
import dev.sinnix.phone.ui.TransportBadge
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.theme.Palette
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

/**
 * The estate remote.
 *
 * What it does: shows the verdict, lists what agents are doing, answers their
 * questions, and offers the bounded actions the hub's own API accepts.
 *
 * What it deliberately does not do: re-render anything the hub renders better.
 * Charts, logs, reports and the workload view are one deep link away in a
 * browser that is already on the tailnet, and duplicating them here would make
 * the app a dashboard — which is the one thing it was decided not to be.
 *
 * Where the action API has no verb for a target, the row says so instead of
 * finding another way. That is the same rule the hub's own pages follow, and
 * inheriting it is why there is no second control plane.
 */
@Composable
fun EstateScreen(nav: NavController) {
    val ctx = LocalContext.current
    val transport = remember { AppGraph.transport(ctx) }
    val scope = rememberCoroutineScope()

    var glance by remember { mutableStateOf<JSONObject?>(null) }
    var live by remember { mutableStateOf(false) }
    var reach by remember { mutableStateOf("checking…") }
    var jobs by remember { mutableStateOf<JSONArray?>(null) }
    var snapshot by remember { mutableStateOf<JSONObject?>(null) }
    var answering by remember { mutableStateOf<String?>(null) }
    var answer by remember { mutableStateOf("") }
    var lastAction by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        reach = transport.probe().describe()
        val (g, isLive) = transport.glance()
        glance = g
        live = isLive
        jobs = transport.jobs()
        snapshot = transport.snapshot()
    }

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    glance?.optString("verdict")?.ifEmpty { "estate quiet" } ?: "estate unknown",
                    style = MaterialTheme.typography.titleLarge,
                    color = Palette.Text,
                )
                TransportBadge(reach, live)
            }
            glance?.optJSONArray("tiles")?.let { tiles ->
                for (i in 0 until tiles.length()) {
                    val t = tiles.optJSONObject(i) ?: continue
                    StatRow(t.optString("label"), t.optString("value"))
                }
            }
            if (!live) {
                Text(
                    "read from the last drain — " +
                        dev.sinnix.phone.instruments.OfferPolicy.stalenessOf(
                            ctx,
                            dev.sinnix.phone.sync.Inbox.GLANCE,
                        ),
                    style = MaterialTheme.typography.labelSmall,
                    color = Palette.Unverified,
                )
            }
        }

        // Agent operations. A question waiting on a human is the one estate
        // event worth interrupting for, so answering it is the first verb here.
        Card {
            SectionLabel("Agents")
            val n = jobs?.length() ?: 0
            if (n == 0) {
                Text(
                    if (live) "nothing running" else "needs the tailnet",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Palette.TextDim,
                )
            }
            for (i in 0 until n) {
                val job = jobs?.optJSONObject(i) ?: continue
                val id = job.optString("id")
                Column(Modifier.padding(vertical = 8.dp)) {
                    Text(
                        job.optString("summary", job.optString("work_item", id)),
                        style = MaterialTheme.typography.bodyMedium,
                        color = Palette.Text,
                    )
                    Text(
                        listOfNotNull(
                                job.optString("backend").ifEmpty { null },
                                job.optString("model").ifEmpty { null },
                                job.optString("elapsed").ifEmpty { null },
                            )
                            .joinToString(" · "),
                        style = MaterialTheme.typography.labelSmall,
                        color = Palette.TextFaint,
                    )
                    if (job.optString("state") == "waiting_on_operator") {
                        Text(
                            job.optString("question"),
                            style = MaterialTheme.typography.bodyMedium,
                            color = Palette.Unverified,
                        )
                        if (answering == id) {
                            OutlinedTextField(
                                value = answer,
                                onValueChange = { answer = it },
                                modifier = Modifier.fillMaxWidth(),
                                label = { Text("answer") },
                            )
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                VerbButton("Send", Modifier.weight(1f)) {
                                    val text = answer
                                    scope.launch {
                                        val path = transport.answerJob(id, text)
                                        lastAction = path.label
                                        answering = null
                                        answer = ""
                                    }
                                }
                                VerbButton("Speak", Modifier.weight(1f)) {
                                    dev.sinnix.phone.ui.talk.TalkActivity.launchForJob(ctx, id)
                                }
                            }
                        } else {
                            VerbButton("Answer", Modifier.fillMaxWidth()) { answering = id }
                        }
                    }
                }
            }
        }

        ActionCards(snapshot, live) { target, verb, revision ->
            scope.launch {
                val (path, detail) = transport.action(target, verb, revision)
                lastAction = "$verb $target — ${path.label}: $detail"
            }
        }

        lastAction?.let {
            Card { Text(it, style = MaterialTheme.typography.labelSmall, color = Palette.TextDim) }
        }

        Card {
            SectionLabel("Deeper")
            Text(
                "Charts, logs and reports render on the hub. The app does not repeat them.",
                style = MaterialTheme.typography.bodySmall,
                color = Palette.TextDim,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("/" to "Verdict", "/work/" to "Work", "/services/" to "Services").forEach {
                    (path, label) ->
                    VerbButton(label, Modifier.weight(1f)) {
                        ctx.startActivity(
                            Intent(
                                Intent.ACTION_VIEW,
                                Uri.parse(Prefs.hubBaseUrl(ctx).trimEnd('/') + path),
                            )
                        )
                    }
                }
            }
        }
    }
}

/**
 * Bounded action cards, resolved from the estate's own attested inventory.
 *
 * A unit with no `observe.restartable` renders as not-restartable rather than
 * with a button that would 403, and an ad-hoc scope renders as visible and not
 * actionable. Both of those are the hub's existing doctrine; the phone is a
 * second face on the same API, not a second opinion about it.
 */
@Composable
private fun ActionCards(
    snapshot: JSONObject?,
    live: Boolean,
    onAction: (String, String, String?) -> Unit,
) {
    val units = snapshot?.optJSONArray("units") ?: return
    val revision = snapshot.optString("revision").ifEmpty { null }
    Card {
        SectionLabel("Actions")
        if (!live) {
            Text(
                "Actions need the tailnet. They are not queued — a restart half an " +
                    "hour late is a different action than the one you asked for.",
                style = MaterialTheme.typography.bodySmall,
                color = Palette.Unverified,
            )
            return@Card
        }
        for (i in 0 until units.length()) {
            val u = units.optJSONObject(i) ?: continue
            val name = u.optString("unit")
            val restartable = u.optBoolean("restartable", false)
            Row(
                Modifier.fillMaxWidth().padding(vertical = 6.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(name, style = MaterialTheme.typography.labelMedium, color = Palette.Text)
                    Text(
                        u.optString("state").ifEmpty { "unknown" },
                        style = MaterialTheme.typography.labelSmall,
                        color = Palette.TextFaint,
                    )
                }
                if (restartable) {
                    VerbButton("Restart") { onAction(name, "restart", revision) }
                } else {
                    Text(
                        "not restartable",
                        style = MaterialTheme.typography.labelSmall,
                        color = Palette.TextFaint,
                    )
                }
            }
        }
    }
}
