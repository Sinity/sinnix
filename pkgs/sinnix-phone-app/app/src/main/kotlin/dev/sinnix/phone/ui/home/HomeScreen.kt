package dev.sinnix.phone.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import dev.sinnix.phone.AppGraph
import dev.sinnix.phone.capture.Coverage
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.instruments.OfferPolicy
import dev.sinnix.phone.sync.Outbox
import dev.sinnix.phone.ui.Card
import dev.sinnix.phone.ui.RibbonView
import dev.sinnix.phone.ui.SectionLabel
import dev.sinnix.phone.ui.TransportBadge
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.instrument.InstrumentActivity
import dev.sinnix.phone.ui.mark.MarkActivity
import dev.sinnix.phone.ui.talk.TalkActivity
import dev.sinnix.phone.ui.theme.Palette
import org.json.JSONObject

/**
 * The companion face.
 *
 * Three things, in this order: what the estate wants you to know (usually
 * nothing), the single thing it is asking of you (often nothing), and the
 * verbs. Everything else is a tab away.
 *
 * The one-card rule for the ask is load-bearing rather than aesthetic. A list
 * of pending obligations is exactly the shape that makes this whole category
 * of tool aversive; a single card is a question, and a question can be
 * answered or dismissed.
 */
@Composable
fun HomeScreen(nav: NavController) {
    val ctx = LocalContext.current
    val transport = remember { AppGraph.transport(ctx) }

    var glance by remember { mutableStateOf<JSONObject?>(null) }
    var liveGlance by remember { mutableStateOf(false) }
    var reach by remember { mutableStateOf<String?>(null) }
    var coverage by remember { mutableStateOf<Coverage?>(null) }
    var energy by remember { mutableStateOf(Prefs.energyState(ctx)) }
    var pending by remember { mutableStateOf(0) }

    LaunchedEffect(Unit) {
        coverage = Coverage.of(ctx, System.currentTimeMillis())
        pending = Outbox.pendingCount(ctx)
        val (g, live) = transport.glance()
        glance = g
        liveGlance = live
        reach = transport.probe().describe()
    }

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        GlanceStrip(glance, liveGlance, reach, pending)

        AskCard(ctx, nav, glance)

        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                VerbButton("Talk", Modifier.weight(1f)) { TalkActivity.launch(ctx) }
                VerbButton("Mark", Modifier.weight(1f)) { MarkActivity.launch(ctx) }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                VerbButton("Check", Modifier.weight(1f)) {
                    InstrumentActivity.launchCheck(ctx)
                }
                VerbButton("Send", Modifier.weight(1f)) { nav.navigate("ready") }
            }
        }

        // Energy state filters what the bench offers rather than what it can
        // run: a bad morning should change the proposal, never the catalogue.
        Card {
            SectionLabel("Energy")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("good", "any", "low").forEach { state ->
                    FilterChip(
                        selected = energy == state,
                        onClick = {
                            energy = state
                            Prefs.setEnergyState(ctx, state)
                        },
                        label = { Text(state) },
                        colors =
                            FilterChipDefaults.filterChipColors(
                                selectedContainerColor = Palette.AccentDim,
                                selectedLabelColor = Palette.Text,
                            ),
                    )
                }
            }
        }

        coverage?.let { c ->
            Card(onClick = { nav.navigate("capture") }) {
                SectionLabel("Capture, 7 days")
                RibbonView(c)
                Text(
                    "unbroken ${c.unbrokenHours()}h · ${c.coveredHours()}/${c.knownHours()} hours" +
                        if (c.holes.isEmpty()) "" else " · ${c.holes.size} holes",
                    style = MaterialTheme.typography.labelSmall,
                    color = Palette.TextDim,
                )
            }
        }

        Spacer(Modifier.height(8.dp))
    }
}

/**
 * The estate's verdict, and the resting state is nothing.
 *
 * Collapses to one quiet line when there is nothing wrong. Absence is the
 * healthy state — a counter that always shows a number trains the eye to stop
 * reading it, and then the one time it matters it is invisible.
 */
@Composable
private fun GlanceStrip(
    glance: JSONObject?,
    live: Boolean,
    reach: String?,
    pending: Int,
) {
    val verdict = glance?.optString("verdict").orEmpty()
    val attention = glance?.optJSONArray("attention")
    val quiet = attention == null || attention.length() == 0

    Card {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                when {
                    glance == null -> "estate unknown"
                    quiet -> verdict.ifEmpty { "estate quiet" }
                    else -> verdict.ifEmpty { "estate wants you" }
                },
                style = MaterialTheme.typography.titleMedium,
                color = if (quiet) Palette.TextDim else Palette.Text,
            )
            TransportBadge(reach ?: "checking…", live)
        }
        if (!quiet && attention != null) {
            for (i in 0 until attention.length()) {
                val item = attention.optJSONObject(i) ?: continue
                Text(
                    "• " + item.optString("text", item.optString("title")),
                    style = MaterialTheme.typography.bodyMedium,
                    color = Palette.Text,
                )
            }
        }
        if (pending > 0) {
            Text(
                "$pending queued for the next drain",
                style = MaterialTheme.typography.labelSmall,
                color = Palette.Unverified,
            )
        }
    }
}

/** Exactly one ask, chosen by priority. `nothing due` is a legitimate answer. */
@Composable
private fun AskCard(
    ctx: android.content.Context,
    nav: NavController,
    glance: JSONObject?,
) {
    val question = remember(glance) { OfferPolicy.currentAsk(ctx, glance) }
    Card(onClick = { question.route?.let { nav.navigate(it) } }) {
        SectionLabel("Asking")
        Text(question.title, style = MaterialTheme.typography.headlineSmall, color = Palette.Text)
        if (question.detail.isNotEmpty()) {
            Text(
                question.detail,
                style = MaterialTheme.typography.bodySmall,
                color = Palette.TextDim,
            )
        }
    }
}
