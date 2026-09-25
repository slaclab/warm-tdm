#!/bin/bash
# Run psu_ctrl.py on pc98970 via SSH from rdsrv433
# Usage: psu_ctrl_remote.sh [on|off|read]

set -euo pipefail

REMOTE_HOST="pc98970"
REMOTE_SCRIPT="/home/cryo/docker/warm-tdm/software/scripts/psu_ctrl.py"

if [ $# -lt 1 ] || [[ ! "$1" =~ ^(on|off|read)$ ]]; then
    echo "Usage: $0 [on|off|read]"
    exit 1
fi

ssh "$REMOTE_HOST" "python3 $REMOTE_SCRIPT $1"
