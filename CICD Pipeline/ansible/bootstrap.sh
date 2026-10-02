#!/usr/bin/env bash
# =============================================================================
# bootstrap.sh — pipeline stage 00 (jump host bootstrap)
# =============================================================================
# Closes the gap between what the dCloud image's `~/install-ansible.sh` leaves
# behind and what stages 01-11 actually need. The image script is baked into the
# pod and cannot be edited, so everything it misses is applied here instead.
#
# install-ansible.sh already provides:
#   ~/tecops-venv (Python 3.9), ansible-core 2.15, catalystcentersdk,
#   dnacentersdk, and the collections cisco.catalystcenter / cisco.dnac /
#   ansible.utils / community.general / cisco.ios / cisco.nxos.
#
# This script adds what it does not:
#   1. ../.vault_pass — must exist before Ansible starts at all, see below.
#   2. virl2_client <2.10, since cisco.cml 1.2.0 reads the Node.config
#      attribute that 2.10 removed. Without the SDK the CML inventory plugin
#      fails with "name 'ClientLibrary' is not defined" and cml.yml is skipped.
#   3. collections/requirements-jumphost.yml, repinning every collection to the
#      newest release that still admits ansible-core 2.15.
#   4. ../.env and a vault.yml for every group_vars directory shipping a
#      vault.yml.example. Created from their examples ONLY when absent, with
#      new vaults encrypted via ansible-vault. Existing files are never
#      overwritten or re-encrypted.
#
# Shell rather than a playbook because step 1 cannot be done from Ansible:
# ansible.cfg sets vault_password_file, and ansible-core resolves that path at
# startup, before the first task runs. A playbook that creates .vault_pass can
# therefore never start on a fresh clone.
#
# Does NOT touch apt or /usr/bin/python3 — install-ansible.sh repoints those at
# 3.8 so apt_pkg keeps working, and fighting it breaks package management.
#
# Idempotent and safe to re-run.
#
#   source ~/tecops-venv/bin/activate && ./bootstrap.sh
#   ./bootstrap.sh --report-only     # report what is missing, write nothing
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")"

ANSIBLE_DIR="$PWD"
PIPELINE_DIR="$(dirname "$ANSIBLE_DIR")"
VAULT_PASS="$PIPELINE_DIR/.vault_pass"
ENV_FILE="$PIPELINE_DIR/.env"
ENV_EXAMPLE="$PIPELINE_DIR/.env.example"
REQUIREMENTS="$ANSIBLE_DIR/collections/requirements-jumphost.yml"
GROUP_VARS="$ANSIBLE_DIR/inventory/group_vars"

REPORT_ONLY=no
case "${1:-}" in
    --report-only) REPORT_ONLY=yes ;;
    -h|--help) sed -n '2,37p' "$0"; exit 0 ;;
    "") ;;
    *) printf 'unknown argument: %s (try --help)\n' "$1" >&2; exit 2 ;;
esac

step() { printf '\n== %s\n' "$*"; }
ok()   { printf '   ok      %s\n' "$*"; }
chg()  { printf '   changed %s\n' "$*"; }
skip() { printf '   skip    %s\n' "$*"; }
warn() { printf '   WARN    %s\n' "$*"; }
die()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

CREATED=""
# Relative to the pipeline root, not basename: three group_vars files are all
# called vault.yml, so basenames would report "vault.yml, vault.yml, vault.yml".
note_created() { CREATED="${CREATED}${CREATED:+, }${1#"$PIPELINE_DIR/"}"; }

# ── Preflight ────────────────────────────────────────────────────────────────
step "Preflight"

command -v ansible-playbook >/dev/null 2>&1 ||
    die "ansible not on PATH. Run: source ~/tecops-venv/bin/activate"

# sys.prefix diverges from sys.base_prefix only inside a venv. Installing
# through any other interpreter puts virl2_client where Ansible will not see it.
python3 -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix else 1)' ||
    die "not running inside a virtualenv. Run: source ~/tecops-venv/bin/activate"

[ -f "$REQUIREMENTS" ] ||
    die "$REQUIREMENTS not found. Run this from 'CICD Pipeline/ansible' in a full clone."

ok "interpreter $(command -v python3)"
ok "$(ansible --version | head -1)"

# ── 1. Vault passphrase ──────────────────────────────────────────────────────
step "Vault passphrase"

if [ -e "$VAULT_PASS" ]; then
    ok "$(basename "$VAULT_PASS") already present"
elif [ "$REPORT_ONLY" = yes ]; then
    die "$VAULT_PASS is missing; re-run without --report-only to create it"
elif [ -f "$HOME/.vault_pass" ]; then
    # Reuse the pod-wide passphrase so an operator who already set one up keeps
    # a single source of truth across re-clones.
    ln -s "$HOME/.vault_pass" "$VAULT_PASS"
    chg "linked $(basename "$VAULT_PASS") -> $HOME/.vault_pass"
    note_created "$VAULT_PASS"
else
    ( umask 077
      dd if=/dev/urandom bs=1 count=64 2>/dev/null |
          base64 | tr -d '\n/+=' | cut -c1-32 > "$VAULT_PASS" )
    chmod 600 "$VAULT_PASS"
    chg "generated $(basename "$VAULT_PASS")"
    note_created "$VAULT_PASS"
fi

# Any pre-existing vault must open with the passphrase we are about to use,
# otherwise a freshly created one would silently orphan real credentials.
# Unencrypted files are skipped rather than failed: they cannot be a passphrase
# mismatch, and step 5 reports them separately. Testing them here would turn a
# plaintext placeholder into a misleading "wrong passphrase" error.
for existing in "$GROUP_VARS"/*/vault.yml; do
    [ -e "$existing" ] || continue
    [ "$(head -c 14 "$existing")" = '$ANSIBLE_VAULT' ] || continue
    ansible-vault view "$existing" --vault-password-file "$VAULT_PASS" >/dev/null 2>&1 ||
        die "$existing does not decrypt with $VAULT_PASS.
       Restore the original passphrase, or remove the stale vault and re-run."
done

# ── 2. CML SDK ───────────────────────────────────────────────────────────────
step "CML SDK"

if [ "$REPORT_ONLY" = yes ]; then
    if python3 -c 'import virl2_client' 2>/dev/null; then
        ok "virl2_client present"
    else
        skip "virl2_client MISSING"
    fi
else
    python3 -m pip install -q 'virl2_client>=2.0.0,<2.10.0'
    # Imports the exact symbol cisco.cml's inventory plugin needs — a bare
    # `import virl2_client` succeeds even when the SDK is unusable, and the
    # package exposes no __version__, so read it from the installed metadata.
    VIRL_VERSION="$(python3 -c 'from virl2_client import ClientLibrary
from importlib.metadata import version
print(version("virl2_client"))')" ||
        die "virl2_client installed but ClientLibrary will not import"
    ok "virl2_client $VIRL_VERSION"
fi

# ── 3. Collections ───────────────────────────────────────────────────────────
step "Collections"

if [ "$REPORT_ONLY" = yes ]; then
    skip "would install from $(basename "$REQUIREMENTS")"
else
    # requirements-jumphost.yml, not requirements.yml: the venv is Python 3.9,
    # which caps ansible-core at 2.15, while the default file targets 2.17.
    ansible-galaxy collection install -r "$REQUIREMENTS" --force >/dev/null
    chg "installed from $(basename "$REQUIREMENTS")"
fi

# ── 4. Credential files ──────────────────────────────────────────────────────
step "Credential files"

if [ -e "$ENV_FILE" ]; then
    ok "$(basename "$ENV_FILE") already present"
elif [ "$REPORT_ONLY" = yes ]; then
    skip "$(basename "$ENV_FILE") MISSING"
else
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    chg "seeded $(basename "$ENV_FILE") from $(basename "$ENV_EXAMPLE")"
    note_created "$ENV_FILE"
fi

# Discovered rather than hardcoded, so a new group_vars directory is picked up
# automatically the moment it ships a vault.yml.example.
for example in "$GROUP_VARS"/*/vault.yml.example; do
    [ -e "$example" ] || continue
    target="${example%.example}"
    group="$(basename "$(dirname "$example")")"

    if [ -e "$target" ]; then
        ok "$group/vault.yml already present"
    elif [ "$REPORT_ONLY" = yes ]; then
        skip "$group/vault.yml MISSING"
    else
        # Encrypt a temporary copy and move it into place only on success.
        # Encrypting $target directly leaves a PLAINTEXT vault behind if the
        # encrypt step fails, which then looks like a legitimate existing file
        # to the next run and is silently skipped. mv is atomic here because
        # the temp file shares a directory with the target.
        tmp="$target.tmp.$$"
        cp "$example" "$tmp"
        chmod 600 "$tmp"
        # --encrypt-vault-id is mandatory: ansible.cfg already sets
        # vault_password_file, so passing it again on the command line yields
        # two vault-ids both named "default" and encrypt refuses to choose
        # ("The vault-ids default,default are available to encrypt").
        # Decryption is unaffected, as view/edit simply try every id.
        if ! ansible-vault encrypt "$tmp" \
                --vault-password-file "$VAULT_PASS" \
                --encrypt-vault-id default >/dev/null; then
            rm -f "$tmp"
            die "failed to encrypt $group/vault.yml; no file was written"
        fi
        mv "$tmp" "$target"
        chg "seeded and encrypted $group/vault.yml"
        note_created "$target"
    fi
done

# Reads only the 14-byte magic header, never the plaintext body.
PLAINTEXT=""
for example in "$GROUP_VARS"/*/vault.yml.example; do
    target="${example%.example}"
    [ -e "$target" ] || continue
    if [ "$(head -c 14 "$target")" != '$ANSIBLE_VAULT' ]; then
        PLAINTEXT="${PLAINTEXT}${PLAINTEXT:+, }$target"
    fi
done

# ── 5. Report ────────────────────────────────────────────────────────────────
step "Summary"

if [ -n "$CREATED" ]; then
    ok "created this run: $CREATED"
else
    ok "nothing to create, all files present"
fi

# direnv is not installed on the dCloud jump host, so .env is never loaded
# automatically there. With CML_HOST unset the CML inventory plugin returns zero
# fabric hosts while still exiting 0, and later stages skip every device without
# reporting an error.
if [ -n "${CML_HOST:-}" ]; then
    ok "CML_HOST exported, dynamic inventory will resolve"
else
    warn "CML_HOST not exported. Run:  set -a; . ../.env; set +a"
    printf '           Without it the CML inventory silently returns ZERO fabric hosts.\n'
fi

[ -z "$PLAINTEXT" ] || warn "these vaults are NOT encrypted: $PLAINTEXT"

if [ -n "$CREATED" ]; then
    printf '\n   ACTION REQUIRED — new files hold placeholder values.\n'
    printf '   Edit vaults with: ansible-vault edit <file>\n'
fi

cat <<'EOF'

   Expected warnings that are NOT errors:
   - "cisco.catalystcenter does not support Ansible version 2.15.x" — held at
     2.9.0 deliberately; 2.3.1 returns dnac_response instead of
     catalystcenter_response and breaks stage 01.
   - "'Node.config' is deprecated" — virl2_client 2.9.x with cisco.cml 1.2.0,
     the pin is intentional.
   - "Found both group and host with same name: dhcp-server" — a CML node label
     matching a CML tag.
EOF
