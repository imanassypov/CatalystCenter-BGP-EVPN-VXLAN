#!/usr/bin/env sh
# =============================================================================
# bootstrap.sh — entry point for pipeline stage 00 on a fresh clone
# =============================================================================
# Creates ../.vault_pass, then runs 00_bootstrap_script_server.yml.
#
# The file cannot be created by the playbook itself: ansible.cfg sets
# vault_password_file, and ansible-core resolves that path at startup, before
# any task executes. On a fresh clone it aborts with
#   ERROR! The vault password file .../CICD Pipeline/.vault_pass was not found
#
# Do not try to dodge that by clearing the variable — an empty
# ANSIBLE_VAULT_PASSWORD_FILE resolves to the CWD, and Ansible then tries to
# execute the directory as a password script.
#
# Run from `CICD Pipeline/ansible` with the venv active:
#   source ~/tecops-venv/bin/activate && ./bootstrap.sh
# Extra arguments are passed through to ansible-playbook.
# =============================================================================
set -eu

cd "$(dirname "$0")"

VAULT_PASS="../.vault_pass"

if [ ! -e "$VAULT_PASS" ]; then
    if [ -f "$HOME/.vault_pass" ]; then
        # Reuse the pod-wide passphrase so an operator who already set one up
        # keeps a single source of truth across re-clones.
        ln -s "$HOME/.vault_pass" "$VAULT_PASS"
        echo "bootstrap: linked $VAULT_PASS -> $HOME/.vault_pass"
    else
        umask 077
        dd if=/dev/urandom bs=1 count=64 2>/dev/null |
            base64 | tr -d '\n/+=' | cut -c1-32 > "$VAULT_PASS"
        chmod 600 "$VAULT_PASS"
        echo "bootstrap: generated $VAULT_PASS"
    fi
else
    echo "bootstrap: $VAULT_PASS already present, left untouched"
fi

exec ansible-playbook playbooks/00_bootstrap_script_server.yml "$@"
