#!/usr/bin/env bash
# Start Headlamp from Windows Git Bash, over SSH, without opening EC2 SG ports.
# Usage: ./headlamp.sh <EC2_PUBLIC_IP_OR_DNS> [PATH_TO_PEM]
set -euo pipefail

EC2_HOST="${1:?Usage: ./headlamp.sh <EC2_PUBLIC_IP_OR_DNS> [PATH_TO_PEM]}"
SSH_KEY="${2:-moomin-mamma.pem}"
PORT=8081
REMOTE="ubuntu@${EC2_HOST}"

if [[ ! -f "$SSH_KEY" ]]; then
  echo "SSH key not found: $SSH_KEY" >&2
  exit 1
fi

SSH_OPTS=(-i "$SSH_KEY" -o ExitOnForwardFailure=yes)

printf '\n=== Headlamp login token (valid for 1 hour; keep secret) ===\n'
ssh "${SSH_OPTS[@]}" "$REMOTE" \
  'sudo -n kubectl -n headlamp create token headlamp-viewer --duration=1h'

printf '\nOpen http://localhost:%s on your Windows laptop, and paste the token above.\n' "$PORT"
printf 'Keep this terminal open; Ctrl+C closes the connection.\n\n'

# SSH -L creates the Windows -> EC2 tunnel.
# The remote command creates EC2 localhost -> Headlamp Service port-forward.
ssh -tt "${SSH_OPTS[@]}" \
  -L "127.0.0.1:${PORT}:127.0.0.1:${PORT}" \
  "$REMOTE" \
  "sudo -n kubectl -n headlamp port-forward --address 127.0.0.1 svc/headlamp ${PORT}:80"
