#!/system/bin/sh
# Android owns the one-shot launch. A child is killed with Kodi on this Shield,
# so commit only the next-start profile after Kodi's own settings save completes.
pid=$1
index=$2
profiles=$3
status=$4
dex=$5
log=$6
offset=$7
token=$8
committed=0
completed=0
cancel() {
    [ "$completed" = 1 ] || CLASSPATH="$dex" /system/bin/app_process /system/bin KodiProfileLauncher cancel "$token" >/dev/null 2>&1
}
trap cancel EXIT
trap 'exit 1' TERM INT
case "$pid:$index:$offset" in *[!0-9:]*|'') exit 1;; esac
[ "$pid" -gt 1 ] || exit 1
umask 077
CLASSPATH="$dex" /system/bin/app_process /system/bin KodiProfileLauncher arm "$token" > "$status.launch.log" 2>&1 || exit 1
/system/bin/toybox grep -q '^alarm_armed$' "$status.launch.log" || exit 1
printf '{"phase":"waiting_saved","pid":%s,"index":%s}\n' "$pid" "$index" > "$status"
i=0
while [ "$i" -lt 400 ]; do
    IFS= read -r proc_stat < /proc/self/stat || exit 1
    proc_fields=${proc_stat##*) }; set -f; set -- $proc_fields
    [ "$2" = "$pid" ] || exit 1
    size=$(/system/bin/toybox stat -c %s "$log") || exit 1
    [ "$size" -ge "$offset" ] || exit 1
    if [ "$size" -gt "$offset" ]; then
        chunk=$(/system/bin/toybox dd if="$log" bs=4096 skip="$offset" count="$((size-offset))" iflag=skip_bytes,count_bytes status=none)
        case "$chunk" in
          *' info <general>: Saving skin settings'*)
            if [ "$committed" = 0 ]; then
            /system/bin/toybox cp "$profiles" "$status.profiles-before.xml" || exit 1
            /system/bin/toybox sed "s#<lastloaded>[0-9][0-9]*</lastloaded>#<lastloaded>$index</lastloaded>#" "$profiles" > "$profiles.restart.tmp" || exit 1
            /system/bin/toybox grep -q "<lastloaded>$index</lastloaded>" "$profiles.restart.tmp" || exit 1
            /system/bin/toybox mv "$profiles.restart.tmp" "$profiles" || exit 1
            printf '{"phase":"profile_saved","pid":%s,"index":%s}\n' "$pid" "$index" > "$status"
            committed=1
            fi;;
        esac
        case "$chunk" in
          *' info <general>: Application stopped'*)
            [ "$committed" = 1 ] || exit 1
            # Kodi saved both settings and skin, waited for native jobs and
            # stopped Python services. Avoid NVIDIA graphics/PVR final teardown.
            IFS= read -r proc_stat < /proc/self/stat || exit 1
            proc_fields=${proc_stat##*) }; set -- $proc_fields
            [ "$2" = "$pid" ] || exit 1
            printf '{"phase":"profile_saved","pid":%s,"index":%s,"termination":"saved_settings_and_services_stopped"}\n' "$pid" "$index" > "$status"
            completed=1
            kill -KILL "$pid" || exit 1
            exit 0;;
        esac
    fi
    /system/bin/toybox usleep 20000
    i=$((i+1))
done
printf '{"phase":"save_timeout","pid":%s,"index":%s}\n' "$pid" "$index" > "$status"
exit 1
