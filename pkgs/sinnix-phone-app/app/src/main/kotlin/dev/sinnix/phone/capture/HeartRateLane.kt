package dev.sinnix.phone.capture

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.content.Context
import android.content.pm.PackageManager
import android.util.Log
import dev.sinnix.phone.core.Events
import dev.sinnix.phone.core.Prefs
import dev.sinnix.phone.core.Stamps
import dev.sinnix.phone.core.Storage
import java.util.UUID
import org.json.JSONArray

/**
 * Live heart rate over the standard Bluetooth Heart Rate Service, straight
 * from the band.
 *
 * The vendor path is batched twice: Mi Fitness only reads the band on its own
 * BLE cadence, and only writes Health Connect when its Sync runs -- the
 * operator's heart rate reached the lake half an hour to two days late, and
 * the first attempt at closing that gap drove Mi Fitness's UI on screen every
 * drain, which made the phone unusable and was vetoed the same evening. This
 * lane is the correct shape: the band is a BLE peripheral two centimetres
 * from the phone, HRS (0x180D) is a public standard, and Android multiplexes
 * GATT clients over the one ACL link -- so subscribing here coexists with Mi
 * Fitness's own connection instead of fighting it.
 *
 * `autoConnect=true` makes the stack itself the reconnect policy: the connect
 * request stays pending inside the controller and completes whenever the band
 * is reachable, surviving walks out of range without any timer of ours. The
 * one case the stack will not solve is the band not exposing HRS at all --
 * some firmwares only publish it while their "share heart rate" setting is
 * on. That state is recorded as its own event and re-probed on a slow cadence
 * rather than treated as permanent, because a settings toggle on the band is
 * exactly the kind of thing that changes while nobody reinstalls the app.
 *
 * Samples buffer in memory and flush as one event per minute carrying the
 * full series -- the same shape HealthLane gives a Health Connect record, so
 * downstream reads both planes with one parser.
 */
class HeartRateLane(context: Context) {

    private val ctx: Context = context.applicationContext

    private var gatt: BluetoothGatt? = null
    private var connected = false
    private var subscribed = false
    private var lastState = ""
    private var ticksUntilRetry = 0

    /**
     * All Bluetooth work happens here, never on the caller's thread.
     *
     * Every entry point into the BT stack is a binder call that can block --
     * and on 2026-08-16 one did, for minutes, freezing the service handler
     * thread that also drives the audio heartbeat: the capture lane's health
     * checks stopped because a WATCH's radio stack was slow. The heartbeat
     * only ever hands this executor a job; if the previous job is still stuck
     * in the stack, `busy` makes the tick a no-op instead of a queue that
     * grows behind a wedged binder.
     */
    private val worker = java.util.concurrent.Executors.newSingleThreadExecutor { r ->
        Thread(r, "hr-live").apply { isDaemon = true }
    }
    private val busy = java.util.concurrent.atomic.AtomicBoolean(false)

    private val bpm = mutableListOf<Int>()
    private val at = mutableListOf<Long>()
    private var lastFlushMs = 0L

    fun tick() {
        if (!busy.compareAndSet(false, true)) return
        worker.execute {
            try {
                tickInner()
            } finally {
                busy.set(false)
            }
        }
    }

    private fun tickInner() {
        if (!Prefs.heartRateLane(ctx)) {
            if (gatt != null) stopInner()
            return
        }
        flushIfDue()
        if (gatt == null) {
            // Counted in heartbeats (20s): after a terminal-looking failure
            // the retry backs off to ~10 minutes instead of hammering the
            // stack, but a fresh process always tries immediately.
            if (ticksUntilRetry > 0) {
                ticksUntilRetry--
                return
            }
            start()
        }
    }

    @SuppressLint("MissingPermission")
    private fun start() {
        if (ctx.checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            state("no-permission")
            ticksUntilRetry = RETRY_TICKS
            return
        }
        val adapter = ctx.getSystemService(BluetoothManager::class.java)?.adapter
        if (adapter == null || !adapter.isEnabled) {
            state("bluetooth-off")
            ticksUntilRetry = RETRY_TICKS
            return
        }
        val band =
            adapter.bondedDevices.firstOrNull {
                (it.name ?: "").contains("Band", ignoreCase = true)
            }
        if (band == null) {
            state("no-bonded-band")
            ticksUntilRetry = RETRY_TICKS
            return
        }
        // DIRECT connect, not autoConnect. autoConnect waits for an
        // advertisement from the device -- and a band already connected to Mi
        // Fitness never advertises, so the pending connect never completed
        // and the lane sat silent (observed on first deploy). A direct
        // connect joins the existing ACL immediately, which is the ordinary
        // state of a worn band next to its phone; when the band is genuinely
        // out of range it fails in ~30s and the tick cadence retries.
        state("connecting")
        gatt = band.connectGatt(ctx, false, callback, BluetoothDevice.TRANSPORT_LE)
        if (gatt == null) {
            state("connect-rejected")
            ticksUntilRetry = RETRY_TICKS
        }
    }

    /** Service teardown: hand the close to the worker like everything else. */
    fun stop() {
        worker.execute { stopInner() }
    }

    @SuppressLint("MissingPermission")
    private fun stopInner() {
        flush()
        try {
            gatt?.close()
        } catch (e: Exception) {
            Log.w(Storage.TAG, "hr-live: close failed", e)
        }
        gatt = null
        connected = false
        subscribed = false
    }

    private val callback =
        object : BluetoothGattCallback() {
            @SuppressLint("MissingPermission")
            override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
                if (newState == BluetoothProfile.STATE_CONNECTED) {
                    connected = true
                    state("connected")
                    g.discoverServices()
                } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                    // A direct connect that drops or fails is finished; close
                    // it and let the tick cadence open a fresh one. A DROPPED
                    // session retries within a minute -- the band walked out
                    // of range mid-stream. A connect that never succeeded
                    // backs off to ten minutes: on this band it means LE is
                    // not connectable at all (Mi Fitness owns it over classic
                    // Bluetooth, and LE only comes up with the band's share-HR
                    // setting), and a per-minute retry is 3,000 identical
                    // failure events a day.
                    val wasConnected = connected
                    state(if (wasConnected) "disconnected" else "connect-failed")
                    connected = false
                    subscribed = false
                    flush()
                    try {
                        g.close()
                    } catch (e: Exception) {
                        Log.w(Storage.TAG, "hr-live: close failed", e)
                    }
                    gatt = null
                    ticksUntilRetry = if (wasConnected) SHORT_RETRY_TICKS else RETRY_TICKS
                }
            }

            @SuppressLint("MissingPermission")
            override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
                val hr = g.getService(HRS)?.getCharacteristic(HR_MEASUREMENT)
                if (hr == null) {
                    // Not an error: some firmwares expose HRS only while the
                    // band's share-heart-rate setting is on. Close and probe
                    // again later; autoConnect would otherwise happily hold a
                    // connection that can never produce a sample.
                    state("no-hrs-service")
                    stop()
                    ticksUntilRetry = RETRY_TICKS
                    return
                }
                g.setCharacteristicNotification(hr, true)
                val cccd = hr.getDescriptor(CCCD)
                if (cccd != null) {
                    @Suppress("DEPRECATION")
                    cccd.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                    @Suppress("DEPRECATION")
                    g.writeDescriptor(cccd)
                }
                subscribed = true
                state("subscribed")
            }

            @Deprecated("pre-33 callback shape; still what MIUI 13 delivers")
            override fun onCharacteristicChanged(
                g: BluetoothGatt,
                characteristic: BluetoothGattCharacteristic,
            ) {
                @Suppress("DEPRECATION")
                onSample(characteristic.value ?: return)
            }

            override fun onCharacteristicChanged(
                g: BluetoothGatt,
                characteristic: BluetoothGattCharacteristic,
                value: ByteArray,
            ) {
                onSample(value)
            }
        }

    /** HR Measurement, GATT spec: flags byte, then uint8 or uint16 bpm. */
    private fun onSample(value: ByteArray) {
        if (value.isEmpty()) return
        val flags = value[0].toInt()
        val hr =
            if (flags and 0x01 == 0) {
                if (value.size < 2) return
                value[1].toInt() and 0xFF
            } else {
                if (value.size < 3) return
                (value[1].toInt() and 0xFF) or ((value[2].toInt() and 0xFF) shl 8)
            }
        if (hr <= 0) return
        synchronized(bpm) {
            bpm.add(hr)
            at.add(System.currentTimeMillis())
        }
        flushIfDue()
    }

    private fun flushIfDue() {
        val now = System.currentTimeMillis()
        if (now - lastFlushMs >= FLUSH_MILLIS) flush()
    }

    private fun flush() {
        val samples: List<Int>
        val times: List<Long>
        synchronized(bpm) {
            if (bpm.isEmpty()) {
                lastFlushMs = System.currentTimeMillis()
                return
            }
            samples = bpm.toList()
            times = at.toList()
            bpm.clear()
            at.clear()
        }
        lastFlushMs = System.currentTimeMillis()
        Events.record(
            ctx,
            "hr_live",
            "samples", samples.size,
            "bpm", JSONArray(samples),
            "sample_times", JSONArray(times.map { Stamps.iso(it) }),
            "mean_bpm", samples.average(),
            "min_bpm", samples.min(),
            "max_bpm", samples.max(),
            "source", "band-hrs",
        )
    }

    /** Transitions only: a state repeated is a state already on record. */
    private fun state(s: String) {
        if (s == lastState) return
        lastState = s
        Events.record(ctx, "hr_live_state", "state", s)
        Log.i(Storage.TAG, "hr-live: $s")
    }

    companion object {
        private val HRS = UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb")
        private val HR_MEASUREMENT = UUID.fromString("00002a37-0000-1000-8000-00805f9b34fb")
        private val CCCD = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")
        private const val FLUSH_MILLIS = 60_000L
        private const val RETRY_TICKS = 30 // 30 heartbeats at 20s = 10 minutes
        private const val SHORT_RETRY_TICKS = 3 // one minute, for transient drops
    }
}
