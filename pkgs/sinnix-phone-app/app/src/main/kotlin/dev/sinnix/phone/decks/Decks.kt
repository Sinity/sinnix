package dev.sinnix.phone.decks

import android.content.Context
import dev.sinnix.phone.instruments.Catalogue
import dev.sinnix.phone.instruments.Engine
import dev.sinnix.phone.instruments.Instrument
import dev.sinnix.phone.sync.Inbox
import org.json.JSONArray
import org.json.JSONObject

/**
 * Drill decks: instruments that arrive as data.
 *
 * A deck parameterizes an engine; it never ships code. That is the whole
 * property worth having — the catalogue becomes open-ended without an app
 * release, so a new drill is a JSON file prime writes into the inbox rather
 * than a build, a sideload, and an MIUI install dialog.
 *
 * What that costs is a version negotiation. A deck names an engine and an
 * engine version; if this build does not know them, the deck renders as
 * present-but-not-runnable with the reason shown. Degrading loudly is the
 * point: a deck that silently did something approximate would produce data
 * that looks like the real instrument and is not.
 */
object Decks {

    /** Bump when an engine's trial contract changes in a way old decks cannot satisfy. */
    private val SUPPORTED_ENGINE_VERSIONS =
        mapOf(
            "reaction" to 1,
            "forced_choice" to 1,
            "staircase" to 1,
            "counting" to 1,
            "hold_still" to 1,
        )

    data class DeckEntry(
        val instrumentId: String,
        val title: String,
        val status: String,
        val runnable: Boolean,
        val instrument: Instrument?,
    )

    private val loaded = HashMap<String, Instrument>()

    fun available(ctx: Context): List<DeckEntry> =
        Inbox.decks(ctx).map { (json, ageSeconds) ->
            val id = "deck:" + json.optString("id", "unnamed")
            val title = json.optString("title", id)
            val engineName = json.optString("engine")
            val version = json.optInt("engine_version", 1)
            val supported = SUPPORTED_ENGINE_VERSIONS[engineName]
            val missingAsset = missingAsset(ctx, json)

            when {
                supported == null ->
                    DeckEntry(id, title, "unknown engine '$engineName' — needs a newer app", false, null)
                version > supported ->
                    DeckEntry(
                        id,
                        title,
                        "engine $engineName v$version, this build speaks v$supported",
                        false,
                        null,
                    )
                missingAsset != null ->
                    DeckEntry(id, title, "asset missing: $missingAsset", false, null)
                else -> {
                    val instrument = toInstrument(id, title, engineName, json)
                    loaded[id] = instrument
                    DeckEntry(id, title, staleness(ageSeconds), true, instrument)
                }
            }
        }

    /** A deck's instrument, once [available] has parsed it. */
    fun byId(id: String): Instrument? = loaded[id]

    private fun staleness(ageSeconds: Long): String =
        when {
            ageSeconds < 3600 -> "pushed ${ageSeconds / 60}m ago"
            ageSeconds < 86_400 -> "pushed ${ageSeconds / 3600}h ago"
            else -> "pushed ${ageSeconds / 86_400}d ago"
        }

    private fun missingAsset(ctx: Context, json: JSONObject): String? {
        val assets = json.optJSONArray("assets") ?: return null
        for (i in 0 until assets.length()) {
            val name = assets.optString(i)
            if (name.isNotEmpty() && Inbox.deckAsset(ctx, name) == null) return name
        }
        return null
    }

    private fun toInstrument(
        id: String,
        title: String,
        engineName: String,
        json: JSONObject,
    ): Instrument {
        val engine =
            when (engineName) {
                "reaction" -> Engine.REACTION
                "staircase" -> Engine.STAIRCASE
                "hold_still" -> Engine.HOLD_STILL
                "counting" -> Engine.COUNTING
                else -> Engine.FORCED_CHOICE
            }
        val config = HashMap<String, Any>()
        json.optJSONObject("config")?.let { c ->
            c.keys().forEach { k -> config[k] = c.get(k) }
        }
        json.optJSONArray("trials")?.let { config["trials_data"] = toTrialList(it) }
        return Instrument(
            id = id,
            title = title,
            engine = engine,
            seconds = json.optInt("seconds", 120),
            needsHeadphones = json.optBoolean("needs_headphones", false),
            needsCamera = json.optBoolean("needs_camera", false),
            scoredOnDevice = json.optBoolean("scored_on_device", engine != Engine.HOLD_STILL),
            blurb = json.optString("blurb"),
            config = config,
        )
    }

    private fun toTrialList(arr: JSONArray): List<Map<String, Any?>> =
        (0 until arr.length()).mapNotNull { i ->
            val o = arr.optJSONObject(i) ?: return@mapNotNull null
            val map = HashMap<String, Any?>()
            o.keys().forEach { k ->
                map[k] =
                    when (val v = o.get(k)) {
                        is JSONArray -> (0 until v.length()).map { v.get(it) }
                        else -> v
                    }
            }
            map
        }

    /** Deck instruments plus built-ins, for the runner's id lookup. */
    fun resolve(id: String): Instrument? = byId(id) ?: Catalogue.byId(id)
}
