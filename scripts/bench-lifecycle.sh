#!/usr/bin/env bash
# Sourced by bench.sh and lifecycle regression tests. Required globals:
# repo, out, merged, analyzed; run_user runs commands as the ordinary owner.
merge() {
    local rc=0
    # Finalization must survive a closed terminal / tee. Each child writes to
    # a user-owned durable log, including its machine-readable stdout.
    run_user python3 "$repo/scripts/bench-support.py" launch-log "$out/logs/merge.log" \
        "$repo/bin/bench" --merge="$out" || rc=$?
    (( rc <= 1 )) || return "$rc"
    [[ -f $out/merge.json && ! -e $out/INCOMPLETE ]] || return 1
    merged=true
    local operation
    for operation in validate summarize plot; do
        run_user python3 "$repo/scripts/bench-support.py" launch-log "$out/logs/$operation.log" \
            /usr/bin/python3 "$repo/analysis/$operation.py" "$out" || return 1
    done
    analyzed=true
    return "$rc"
}
