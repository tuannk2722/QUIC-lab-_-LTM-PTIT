#!/usr/bin/env bash
# Wait only for children owned by the caller. Never infer their exit status
# from /proc: Bash may reap a child between a liveness check and a signal.
managed_process_running() {
    local pid=$1 process_stat
    [[ -r /proc/$pid/stat ]] || return 1
    IFS= read -r process_stat 2>/dev/null < "/proc/$pid/stat" || return 1
    process_stat=${process_stat##*) }
    [[ ${process_stat%% *} != Z && ${process_stat%% *} != X ]]
}

wait_managed_process() {
    local pid=$1 steps=${2:-200} delay=${3:-.05} poll rc=0
    for ((poll=0;poll<steps;poll++)); do
        managed_process_running "$pid" || break
        sleep "$delay"
    done
    if managed_process_running "$pid"; then
        # ESRCH is harmless: the child may exit after the check. wait still
        # distinguishes a normal exit, a signal and a genuine forced kill.
        kill -KILL "$pid" 2>/dev/null || true
    fi
    wait "$pid" || rc=$?
    return "$rc"
}

stop_process() {
    local pid=$1 allow_signal=${2:-false} steps=${3:-200} rc=0
    [[ -n $pid ]] || return 0
    kill -TERM "$pid" 2>/dev/null || true
    wait_managed_process "$pid" "$steps" || rc=$?
    (( rc == 0 )) || [[ $allow_signal == true && ($rc == 130 || $rc == 143) ]]
}
