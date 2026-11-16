#!/usr/bin/env bash
# Run ON THE VM after cloud-init completes; an existing checkout is never reset.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo." >&2; exit 1; fi
if [[ $# -ne 2 ]]; then echo "Usage: bootstrap.sh VERIFIED_AZURE_HOST EXACT_COMMIT" >&2; exit 1; fi
hostname=$1
commit=$2
if [[ ! $commit =~ ^[0-9a-f]{40}$ ]]; then echo "Use a full 40-character source commit." >&2; exit 1; fi
cloud-init status --wait
if [[ ! -d /srv/analogforge/repository/.git ]]; then
  git clone https://github.com/techtanush/NASAspaceApps.git /srv/analogforge/repository
fi
repo=/srv/analogforge/repository
git -C "$repo" fetch origin --prune
git -C "$repo" cat-file -e "$commit^{commit}"
# Dedicated detached release checkouts avoid changing a live server's code in place.
release="/var/lib/analogforge/releases/$commit"
if [[ ! -d $release ]]; then git -C "$repo" worktree add --detach "$release" "$commit"; fi
app="$release/analogforge"
if [[ ! -f /etc/analogforge/runtime.env ]]; then
  python3 "$app/ops/azure/create-env.py" "$hostname"
fi
exec "$app/ops/azure/deploy.sh" "$commit"
