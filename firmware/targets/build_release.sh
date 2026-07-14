#!/usr/bin/env bash
# ----------------------------------------------------------------------------
# Build all firmware targets included in a WarmTDM release, in parallel.
#
# The target list is read from firmware/releases.yaml (the single source of
# truth) so it never drifts from what actually ships in a release.
#
# Each target builds in its own process with output tee'd to a per-target log.
# The script refuses to run against a dirty git tree (including submodules) so
# that every release image carries a clean git hash rather than "-dirty".
#
# Usage:
#   ./build_release.sh [-r RELEASE] [-j N] [-t SUBTARGET] [--force] [--list]
#
#   -r RELEASE    Release name in releases.yaml (default: warmTdm)
#   -j N          Max concurrent builds (default: all at once)
#   -t SUBTARGET  Make subtarget to invoke (default: prom)
#   --force       Build even if the git tree is dirty (NOT for releases)
#   --list        Print the resolved target list and exit
#   -h, --help    Show this help
# ----------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIRMWARE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$FIRMWARE_DIR/.." && pwd)"
RELEASES_YAML="$FIRMWARE_DIR/releases.yaml"

RELEASE="warmTdm"
SUBTARGET="prom"
JOBS=0            # 0 = unlimited (all at once)
FORCE=0
LIST_ONLY=0

usage() { sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -r) RELEASE="$2"; shift 2 ;;
        -j) JOBS="$2"; shift 2 ;;
        -t) SUBTARGET="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        --list) LIST_ONLY=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

# ----------------------------------------------------------------------------
# Resolve the target list for the requested release from releases.yaml
# ----------------------------------------------------------------------------
if [[ ! -f "$RELEASES_YAML" ]]; then
    echo "ERROR: releases.yaml not found at $RELEASES_YAML" >&2
    exit 1
fi

mapfile -t TARGETS < <(python3 - "$RELEASES_YAML" "$RELEASE" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1]))
rel_name = sys.argv[2]
releases = cfg.get("Releases") or {}
if rel_name not in releases:
    sys.exit(f"Release '{rel_name}' not found in releases.yaml. "
             f"Available: {', '.join(releases) or '(none)'}")
targets = releases[rel_name].get("Targets") or []
catalog = cfg.get("Targets") or {}
for t in targets:
    if t not in catalog:
        sys.exit(f"Release target '{t}' missing from Targets catalog.")
    print(t)
PY
)

if [[ ${#TARGETS[@]} -eq 0 ]]; then
    echo "ERROR: no targets resolved for release '$RELEASE'" >&2
    exit 1
fi

if [[ $LIST_ONLY -eq 1 ]]; then
    printf '%s\n' "${TARGETS[@]}"
    exit 0
fi

# ----------------------------------------------------------------------------
# Preflight checks
# ----------------------------------------------------------------------------
if ! command -v vivado >/dev/null 2>&1; then
    echo "ERROR: 'vivado' is not on PATH. Source your Vivado settings64.sh" >&2
    echo "       (e.g. 'source /path/to/Vivado/<version>/settings64.sh') first." >&2
    exit 1
fi

# Refuse to build a release from a dirty tree (includes submodule changes),
# so images never get stamped with a '-dirty' git hash.
if [[ $FORCE -eq 0 ]]; then
    DIRTY="$(cd "$REPO_DIR" && git status --porcelain)"
    if [[ -n "$DIRTY" ]]; then
        echo "ERROR: git working tree is dirty. Release images would be stamped '-dirty'." >&2
        echo "       Commit/stash changes (including submodule pointers), or pass --force" >&2
        echo "       to build anyway (not for a real release)." >&2
        echo >&2
        echo "$DIRTY" | sed 's/^/         /' >&2
        exit 1
    fi
fi

GIT_HASH="$(cd "$REPO_DIR" && git rev-parse --short HEAD)"
LOG_DIR="$SCRIPT_DIR/build_logs/${GIT_HASH}"
mkdir -p "$LOG_DIR"

echo "=============================================================="
echo " WarmTDM release build"
echo "   release   : $RELEASE"
echo "   subtarget : $SUBTARGET"
echo "   git hash  : $GIT_HASH"
echo "   targets   : ${TARGETS[*]}"
echo "   parallel  : $([[ $JOBS -eq 0 ]] && echo 'all at once' || echo "$JOBS at a time")"
echo "   logs      : $LOG_DIR"
echo "=============================================================="

# ----------------------------------------------------------------------------
# Build one target: cd into its dir, run make, tee to a log, record status.
# ----------------------------------------------------------------------------
build_one() {
    local target="$1"
    local log="$LOG_DIR/${target}.log"
    local start end
    start=$(date +%s)
    echo ">>> [$target] starting (log: $log)"
    if (cd "$SCRIPT_DIR/$target" && make "$SUBTARGET") >"$log" 2>&1; then
        end=$(date +%s)
        echo "OK      $target" > "$LOG_DIR/${target}.status"
        echo "<<< [$target] SUCCESS in $((end - start))s"
    else
        end=$(date +%s)
        echo "FAILED  $target" > "$LOG_DIR/${target}.status"
        echo "!!! [$target] FAILED after $((end - start))s (see $log)"
    fi
}

# ----------------------------------------------------------------------------
# Launch builds, honoring the concurrency cap.
# ----------------------------------------------------------------------------
pids=()
launched=0
for target in "${TARGETS[@]}"; do
    # Throttle when a concurrency cap is set.
    if [[ $JOBS -gt 0 ]]; then
        while [[ $(jobs -rp | wc -l) -ge $JOBS ]]; do
            wait -n 2>/dev/null || true
        done
    fi
    build_one "$target" &
    pids+=($!)
    launched=$((launched + 1))
done

# Wait for everything to finish (do not abort on first failure).
set +e
for pid in "${pids[@]}"; do
    wait "$pid"
done
set -e

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
echo
echo "=============================================================="
echo " Build summary ($GIT_HASH)"
echo "--------------------------------------------------------------"
fail=0
for target in "${TARGETS[@]}"; do
    status="$(cat "$LOG_DIR/${target}.status" 2>/dev/null || echo "MISSING $target")"
    printf '   %s\n' "$status"
    [[ "$status" == OK* ]] || fail=1
done
echo "=============================================================="

if [[ $fail -ne 0 ]]; then
    echo "One or more targets failed. See logs in $LOG_DIR" >&2
    exit 1
fi
echo "All targets built successfully."
