package dev.sinnix.phone.ui.instrument

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import dev.sinnix.phone.decks.Decks
import dev.sinnix.phone.instruments.OfferPolicy
import dev.sinnix.phone.instruments.RunRecord
import dev.sinnix.phone.ui.Card
import dev.sinnix.phone.ui.SectionLabel
import dev.sinnix.phone.ui.Sparkline
import dev.sinnix.phone.ui.VerbButton
import dev.sinnix.phone.ui.theme.Palette

/**
 * The bench.
 *
 * A proposal at the top, the whole catalogue below it. The shelf exists so the
 * offer policy can afford to be opinionated: an operator who wants a PVT right
 * now should not have to argue with a scheduler, and a scheduler that has to
 * accommodate every deliberate run stops making good proposals.
 */
@Composable
fun InstrumentsScreen(nav: NavController) {
    val ctx = LocalContext.current
    val check = remember { OfferPolicy.assembleCheck(ctx) }
    val shelf = remember { OfferPolicy.shelf(ctx) }
    val decks = remember { Decks.available(ctx) }
    val recent = remember { OfferPolicy.recentRuns(ctx, 14).takeLast(6).reversed() }

    Column(
        Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Card {
            SectionLabel("Check")
            if (check.isEmpty()) {
                Text(
                    "Nothing to propose right now.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = Palette.TextDim,
                )
            } else {
                Text(
                    check.joinToString(" · ") { it.title },
                    style = MaterialTheme.typography.titleMedium,
                    color = Palette.Text,
                )
                Text(
                    "${(check.sumOf { it.seconds } + 59) / 60} minutes",
                    style = MaterialTheme.typography.labelSmall,
                    color = Palette.TextFaint,
                )
                VerbButton("Run the check", Modifier.fillMaxWidth()) {
                    InstrumentActivity.launchCheck(ctx)
                }
            }
        }

        if (decks.isNotEmpty()) {
            Card {
                SectionLabel("Decks from prime")
                decks.forEach { deck ->
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 6.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(
                                deck.title,
                                style = MaterialTheme.typography.bodyMedium,
                                color = if (deck.runnable) Palette.Text else Palette.TextFaint,
                            )
                            Text(
                                deck.status,
                                style = MaterialTheme.typography.labelSmall,
                                color =
                                    if (deck.runnable) Palette.TextFaint else Palette.Unverified,
                            )
                        }
                        if (deck.runnable) {
                            VerbButton("Run", Modifier.padding(start = 12.dp)) {
                                InstrumentActivity.launchOne(ctx, deck.instrumentId)
                            }
                        }
                    }
                }
            }
        }

        Card {
            SectionLabel("Shelf")
            shelf.forEach { (instrument, blocked) ->
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 6.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text(
                            instrument.title,
                            style = MaterialTheme.typography.bodyMedium,
                            color = if (blocked == null) Palette.Text else Palette.TextFaint,
                        )
                        Text(
                            blocked ?: "${instrument.seconds}s · ${instrument.engine.name.lowercase()}",
                            style = MaterialTheme.typography.labelSmall,
                            color = if (blocked == null) Palette.TextFaint else Palette.Unverified,
                        )
                    }
                    if (blocked == null) {
                        VerbButton("Run", Modifier.padding(start = 12.dp)) {
                            InstrumentActivity.launchOne(ctx, instrument.id)
                        }
                    }
                }
            }
        }

        if (recent.isNotEmpty()) {
            Card {
                SectionLabel("Recent runs")
                recent.forEach { run ->
                    val id = run.optString("instrument")
                    val history = remember(id) { RunRecord.history(ctx, id, "median_rt_ms") }
                    Column(Modifier.padding(vertical = 6.dp)) {
                        Text(
                            "$id · ${run.optString("ts").takeLast(9).dropLast(1)}",
                            style = MaterialTheme.typography.labelMedium,
                            color = Palette.TextDim,
                        )
                        if (history.size >= 3) Sparkline(history)
                    }
                }
            }
        }
    }
}
