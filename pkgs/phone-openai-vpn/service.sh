#!/system/bin/sh
# Magisk boot hook; one invocation, no background supervisor.
exec /data/adb/sinnix/proton-openai/route.sh up >> /data/adb/sinnix/proton-openai/boot.log 2>&1
