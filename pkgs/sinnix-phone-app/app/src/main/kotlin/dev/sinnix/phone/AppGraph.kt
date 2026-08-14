package dev.sinnix.phone

import android.content.Context
import dev.sinnix.phone.estate.Transport

/**
 * The whole dependency graph, by hand.
 *
 * One process, one operator, one prime. A DI framework here would buy
 * constructor injection for test doubles that nothing in this app substitutes,
 * at the cost of an annotation processor in the build and a layer between
 * "where does Transport come from" and its answer.
 */
object AppGraph {

    @Volatile private var transport: Transport? = null

    fun transport(ctx: Context): Transport =
        transport
            ?: synchronized(this) {
                transport ?: Transport(ctx.applicationContext).also { transport = it }
            }
}
