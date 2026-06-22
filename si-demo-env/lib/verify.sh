#!/usr/bin/env bash
# Engine verify-driver (the gate). Non-destructive; safe to run any time.
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"
load_config
load_secrets
verify_gate
