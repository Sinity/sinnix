import java.io.*;
import java.lang.reflect.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.util.*;

/** Root-only, bounded LineageOS profile lock policy; never edits credentials. */
public final class PhoneKeyguard {
    static final Path STATE = Paths.get("/data/adb/sinnix-phone-keyguard/lease");
    static Object api;
    static Class<?> iface, profileClass, parcelClass;

    static void connect() throws Exception {
        Class<?> process = Class.forName("android.os.Process");
        if (((Number) process.getMethod("myUid").invoke(null)).intValue() != 0)
            throw new IllegalStateException("root required");
        Class<?> tm = Class.forName("android.os.TelephonyServiceManager");
        Class.forName("android.telephony.TelephonyFrameworkInitializer")
            .getMethod("setTelephonyServiceManager", tm).invoke(null, tm.getConstructor().newInstance());
        Object service = Class.forName("android.os.ServiceManager")
            .getMethod("getService", String.class).invoke(null, "profile");
        if (service == null) throw new IllegalStateException("LineageOS profiles unavailable");
        iface = Class.forName("lineageos.app.IProfileManager");
        profileClass = Class.forName("lineageos.app.Profile");
        parcelClass = Class.forName("android.os.ParcelUuid");
        api = Class.forName("lineageos.app.IProfileManager$Stub")
            .getMethod("asInterface", Class.forName("android.os.IBinder")).invoke(null, service);
    }
    static Object parcel(String id) throws Exception {
        return parcelClass.getConstructor(UUID.class).newInstance(UUID.fromString(id));
    }
    static String id(Object profile) throws Exception {
        return profileClass.getMethod("getUuid").invoke(profile).toString();
    }
    static int mode(Object profile) throws Exception {
        Object setting = profileClass.getMethod("getScreenLockMode").invoke(profile);
        return ((Number) setting.getClass().getMethod("getValue").invoke(setting)).intValue();
    }
    static void set(Object profile, int value) throws Exception {
        Object setting = profileClass.getMethod("getScreenLockMode").invoke(profile);
        setting.getClass().getMethod("setValue", int.class).invoke(setting, value);
        iface.getMethod("updateProfile", profileClass).invoke(api, profile);
        Object active = iface.getMethod("getActiveProfile").invoke(api);
        if (id(active).equals(id(profile))) {
            if (!Boolean.TRUE.equals(iface.getMethod("setActiveProfile", parcelClass).invoke(api, parcel(id(profile)))))
                throw new IllegalStateException("profile activation refused");
        }
    }
    static void restore(String token) throws Exception {
        try (FileChannel channel = FileChannel.open(STATE.resolveSibling("recovery.lock"), StandardOpenOption.CREATE, StandardOpenOption.WRITE);
             FileLock lock = channel.lock()) {
            restoreLocked(token);
        }
    }
    static void restoreLocked(String token) throws Exception {
        if (!Files.exists(STATE)) return;
        List<String> fields = Files.readAllLines(STATE);
        if (fields.size() != 3) throw new IllegalStateException("invalid recovery record");
        if (token != null && !token.equals(fields.get(2))) return;
        Object profile = iface.getMethod("getProfile", parcelClass).invoke(api, parcel(fields.get(0)));
        if (profile == null) throw new IllegalStateException("original profile unavailable");
        // Preserve a subsequently selected policy; only undo our DISABLE value.
        if (mode(profile) == 2) {
            boolean active = id(iface.getMethod("getActiveProfile").invoke(api)).equals(id(profile));
            set(profile, Integer.parseInt(fields.get(1)));
            if (active && new ProcessBuilder("/system/bin/input", "keyevent", "KEYCODE_SLEEP").start().waitFor() != 0)
                throw new IllegalStateException("restored policy but could not put screen to sleep");
        }
        Files.delete(STATE);
        System.out.println("LOCK_POLICY_RESTORED");
    }
    public static void main(String[] args) {
        try {
            connect();
            if (args.length == 1 && args[0].equals("recover")) { restore(null); return; }
            if (args.length == 3 && args[0].equals("watchdog")) {
                System.out.println("WATCHDOG_READY"); System.out.flush();
                Thread.sleep((Long.parseLong(args[1]) + 2) * 1000);
                restore(args[2]); return;
            }
            if (args.length != 1) throw new IllegalArgumentException("expected duration seconds or recover");
            int seconds = Integer.parseInt(args[0]);
            if (seconds < 1 || seconds > 600) throw new IllegalArgumentException("duration must be 1..600 seconds");
            try (FileChannel channel = FileChannel.open(STATE.resolveSibling("lock"), StandardOpenOption.CREATE, StandardOpenOption.WRITE);
                 FileLock lock = channel.tryLock()) {
                if (lock == null) throw new IllegalStateException("another unlock lease is active");
                if (Files.exists(STATE)) throw new IllegalStateException("recover previous lease first");
                Object active = iface.getMethod("getActiveProfile").invoke(api);
                int old = mode(active);
                if (old == 2) throw new IllegalStateException("profile already disables lock; refusing ownership");
                String token = UUID.randomUUID().toString();
                Path next = STATE.resolveSibling("lease.new");
                Files.write(next, Arrays.asList(id(active), Integer.toString(old), token));
                Files.move(next, STATE, StandardCopyOption.ATOMIC_MOVE);
                try {
                    ProcessBuilder builder = new ProcessBuilder("/system/bin/setsid", "/system/bin/app_process", "/system/bin", "PhoneKeyguard", "watchdog", Integer.toString(seconds), token);
                    builder.redirectError(ProcessBuilder.Redirect.appendTo(STATE.resolveSibling("watchdog.log").toFile()));
                    Process watchdog = builder.start();
                    String ready = new BufferedReader(new InputStreamReader(watchdog.getInputStream())).readLine();
                    if (!"WATCHDOG_READY".equals(ready)) throw new IllegalStateException("recovery watchdog failed to start");
                    set(active, 2);
                    System.out.println("UNLOCK_LEASE_ACTIVE");
                    System.out.println("LEASE_PID=" + Class.forName("android.os.Process").getMethod("myPid").invoke(null)); System.out.flush();
                    Thread.sleep(seconds * 1000L);
                } finally { restore(token); }
            }
        } catch (Throwable failure) { failure.printStackTrace(); System.exit(1); }
    }
}
