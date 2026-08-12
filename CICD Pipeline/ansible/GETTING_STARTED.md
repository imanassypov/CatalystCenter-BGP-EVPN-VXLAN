# Getting Started — dCloud Jump Host Setup

First-time setup for students. Follow these steps **in order**, once per pod. At
the end you will be able to run the pipeline stages (`01`–`11`) from the jump
host.

Everything runs on the dCloud **script server** (the "jump host"), not on your
laptop. It is the only host in the pod with reachability to both Catalyst Center
(`198.18.129.100`) and the CML fabric API (`198.18.128.11`).

| Step | What it does | Time |
|------|--------------|------|
| 1 | SSH into the jump host | 1 min |
| 2 | Run `~/install-ansible.sh` — Python venv, Ansible, SDKs, collections | ~10 min |
| 3 | Clone this repository | 1 min |
| 4 | Install the CML extras the script does not cover | 2 min |
| 5 | Create the vault password file | 1 min |
| 6 | Create `.env` (CML + device credentials) | 2 min |
| 7 | Create and encrypt `inventory/group_vars/catalyst_center/vault.yml` | 2 min |
| 8 | Verify, then run stage 01 | 5 min |

---

## Prerequisites

- An active dCloud session with the **Campus BGP EVPN** lab powered on.
- The jump host IP (`198.18.134.28` in the standard pod) and its `root` password
  from your dCloud session details.
- Two credentials you will be asked for later:
  - **Catalyst Center** API user/password (`admin` / lab password).
  - **CML** user/password (`admin` / lab password).

> **Never commit credentials.** Every file you create below (`.vault_pass`,
> `.env`, `vault.yml`) is already in `.gitignore`. Nothing you type in this
> guide should ever appear in a `git status` output as a new tracked file.

---

## Step 1 — SSH into the jump host

From your laptop (or the dCloud web terminal):

```bash
ssh root@198.18.134.28
```

Confirm you landed on the right box:

```bash
hostname && cat /etc/os-release | head -2
# dcloud
# NAME="Ubuntu"  VERSION="20.04.5 LTS (Focal Fossa)"
```

---

## Step 2 — Run the environment installer

The jump host image ships with `install-ansible.sh` already in the home
directory. Run it from `~/`:

```bash
cd ~
./install-ansible.sh
```

What it does:

| Stage | Action |
|-------|--------|
| 0 | Repoints `/usr/bin/python3` at **3.8** so `apt` keeps working (the image's `apt_pkg` is built for 3.8) |
| 1–2 | `apt-get update` and installs **Python 3.9** from the deadsnakes PPA |
| 3 | Creates the virtualenv at **`~/tecops-venv`** and appends its activation to `~/.bashrc` |
| 4 | Installs `ansible` 8.x (**ansible-core 2.15**) into the venv |
| 5 | Installs `catalystcentersdk`, `dnacentersdk`, `github-clone` |
| 6 | Installs collections into **`~/.ansible/collections`**: `cisco.catalystcenter`, `cisco.dnac`, `ansible.utils`, `community.general`, `cisco.ios`, `cisco.nxos` |
| 7 | Checks for `~/.vault_pass` (warns if missing — we create it in Step 5) |
| 8 | Prints the installed versions |

The script is safe to re-run.

Activate the venv in your **current** shell (new shells activate it
automatically via `~/.bashrc`):

```bash
source ~/tecops-venv/bin/activate
```

Your prompt should now start with `(tecops-venv)`. Verify:

```bash
ansible --version | head -1
# ansible [core 2.15.13]
```

---

## Step 3 — Clone the repository

```bash
cd ~
git clone https://github.com/imanassypov/CatalystCenter-BGP-EVPN-VXLAN.git
```

> **Working directory rule — read this once, remember it forever.**
> Ansible only reads `ansible.cfg` from the **current** directory. This project's
> config lives at `CICD Pipeline/ansible/ansible.cfg`, so **every** `ansible`,
> `ansible-playbook`, `ansible-inventory`, and `ansible-vault` command in this
> lab must be run from:
>
> ```bash
> cd ~/CatalystCenter-BGP-EVPN-VXLAN/CICD\ Pipeline/ansible
> ```
>
> Run them from anywhere else and you will get missing inventory plugins,
> unresolved vault passwords, and interactive password prompts.

---

## Step 4 — Install the pinned collections and the CML SDK

`install-ansible.sh` predates the CML dynamic inventory, so it does **not**
install `cisco.cml` or the `virl2_client` SDK. Without them, every command
prints:

```
[WARNING]: Failed to load inventory plugin, skipping cisco.cml.cml_inventory
```

Install both, plus the jump-host collection set:

```bash
cd ~/CatalystCenter-BGP-EVPN-VXLAN/CICD\ Pipeline/ansible
source ~/tecops-venv/bin/activate

pip install 'virl2_client>=2.0.0,<2.10.0'
ansible-galaxy collection install -r collections/requirements-jumphost.yml --force
```

> **Use `requirements-jumphost.yml`, not `requirements.yml`.** The jump host venv
> is Python 3.9, which caps ansible-core at 2.15. The default
> `requirements.yml` targets a 2.17 control node and pulls collection releases
> that require ansible-core 2.16+, each of which then warns
> `Collection <name> does not support Ansible version 2.15.x`. The jump host
> file pins the newest release of each collection that still supports 2.15.

> **One warning is expected and correct:**
> `Collection cisco.catalystcenter does not support Ansible version 2.15.13`.
> That collection is deliberately held at 2.9.0. The newest 2.15-compatible
> release (2.3.1) returns results under `dnac_response`, while every role here
> reads `catalystcenter_response` — downgrading produces an empty site map and
> stage 01 fails with `[400] NCND00067: The request body is invalid`. 2.9.0 runs
> correctly on ansible-core 2.15 despite the declaration.

> `virl2_client` is pinned below 2.10 because `cisco.cml` 1.2.0 still uses the
> old `node.config` attribute, which 2.10 removed.

Confirm:

```bash
ansible-galaxy collection list 2>&1 | grep -E 'cisco\.|ansible\.utils'
# cisco.catalystcenter  2.9.0
# cisco.cml             1.2.0
# cisco.dnac            6.46.0
# cisco.ios             9.2.0
# cisco.nxos            9.4.0
# ansible.utils         5.1.2
```

---

## Step 5 — Create the vault password file

There are **two different vault files** and confusing them is the single most
common mistake in this lab:

| File | Holds | Format |
|------|-------|--------|
| `CICD Pipeline/.vault_pass` | The **passphrase** that locks/unlocks the vault | One bare line of text |
| `.../group_vars/<group>/vault.yml` | The **secrets themselves** | YAML `key: value` pairs, encrypted |

`ansible.cfg` points at the first one with `vault_password_file = ../.vault_pass`
— relative to `CICD Pipeline/ansible/`, i.e. `CICD Pipeline/.vault_pass`.

Create it (choose any passphrase you like — you will need it again if you ever
re-encrypt):

```bash
cd ~/CatalystCenter-BGP-EVPN-VXLAN/CICD\ Pipeline

read -rs -p 'Choose a vault passphrase: ' VP && printf '%s' "$VP" > .vault_pass && unset VP
chmod 600 .vault_pass
```

`read -rs` keeps the passphrase off your screen and out of `~/.bash_history`,
and `printf '%s'` writes it without a trailing newline.

Verify — the file must be exactly one line and readable only by you:

```bash
ls -l .vault_pass && wc -l .vault_pass
# -rw------- 1 root root 11 ... .vault_pass
# 0 .vault_pass          ← 0 means "no trailing newline", which is correct
```

> `install-ansible.sh` also mentions `~/.vault_pass`. That path is for the
> standalone TECOPS playbooks, **not** this repo. If you already created it and
> want to use the same passphrase, link it instead of retyping:
> `ln -sf ~/.vault_pass "$HOME/CatalystCenter-BGP-EVPN-VXLAN/CICD Pipeline/.vault_pass"`

---

## Step 6 — Create `.env`

`.env` carries the non-vault credentials — CML API, fabric device passwords, and
the jump host password. It sits next to `.vault_pass`:

```bash
cd ~/CatalystCenter-BGP-EVPN-VXLAN/CICD\ Pipeline
cp .env.example .env
chmod 600 .env
vi .env
```

Fill in at minimum:

| Variable | Value |
|----------|-------|
| `IOSXE_PASS` | Fabric device `net-admin` password (stage 11 backups) |
| `CML_PASSWORD` | CML `admin` password |
| `CML_HOST` / `CML_USERNAME` / `CML_LAB` | Already correct for the standard pod |

Load it into your shell. **Ansible does not read `.env` by itself** — the CML
inventory plugin reads these as environment variables:

```bash
set -a; . ./.env; set +a
```

Re-run that line in every new shell (or add it to `~/.bashrc`).

> Values containing spaces **must** be quoted, e.g. `CML_LAB="BGP EVPN Campus"`.
> Unquoted, `set -a; . ./.env` fails with `EVPN: command not found`.

---

## Step 7 — Create and encrypt the Catalyst Center vault

This is the file every playbook loads via `vars_files`. It must be a **YAML
mapping**, never a bare password string.

```bash
cd ~/CatalystCenter-BGP-EVPN-VXLAN/CICD\ Pipeline/ansible

cp inventory/group_vars/catalyst_center/vault.yml.example \
   inventory/group_vars/catalyst_center/vault.yml

vi inventory/group_vars/catalyst_center/vault.yml
```

The contents must look exactly like this — two keys, each `name: value`:

```yaml
---
catc_username: admin
catc_password: <your Catalyst Center password>

# Optional — only needed for stage 07 (GitHub template sync)
# git_token: <github personal access token>
```

Now encrypt it. Because you are inside `CICD Pipeline/ansible`, `ansible.cfg` is
picked up and the passphrase is read from `../.vault_pass` — you will **not** be
prompted:

```bash
ansible-vault encrypt inventory/group_vars/catalyst_center/vault.yml
# Encryption successful
```

Confirm it is encrypted and still decodes to a mapping:

```bash
head -1 inventory/group_vars/catalyst_center/vault.yml
# $ANSIBLE_VAULT;1.1;AES256

ansible-vault view inventory/group_vars/catalyst_center/vault.yml
# catc_username: admin
# catc_password: ...
```

To change a value later, edit in place — this decrypts, opens `$EDITOR`, and
re-encrypts in one step:

```bash
ansible-vault edit inventory/group_vars/catalyst_center/vault.yml
```

### Optional group vaults

Only needed for the SWIM and YANG Suite stages. Same pattern:

```bash
cp inventory/group_vars/image_servers/vars.yml.example  inventory/group_vars/image_servers/vars.yml
cp inventory/group_vars/image_servers/vault.yml.example inventory/group_vars/image_servers/vault.yml
ansible-vault encrypt inventory/group_vars/image_servers/vault.yml

cp inventory/group_vars/yangsuite_servers/vars.yml.example  inventory/group_vars/yangsuite_servers/vars.yml
cp inventory/group_vars/yangsuite_servers/vault.yml.example inventory/group_vars/yangsuite_servers/vault.yml
ansible-vault encrypt inventory/group_vars/yangsuite_servers/vault.yml
```

---

## Step 8 — Verify, then run stage 01

Every new shell needs these three lines:

```bash
source ~/tecops-venv/bin/activate
cd ~/CatalystCenter-BGP-EVPN-VXLAN/CICD\ Pipeline && set -a && . ./.env && set +a
cd ansible
```

Check the inventory resolves — CML groups appearing means the plugin, the SDK,
and your `.env` are all working:

```bash
ansible-inventory --graph
```

Expected (abbreviated):

```
@all:
  |--@catalyst_center:
  |  |--catalyst_center_api
  |--@iosxe:
  |  |--@cat9000v-uadp:
  |  |  |--leaf1
  |  |  |--spine1
  ...
```

Three messages are normal and can be ignored:

| Message | Why |
|---------|-----|
| `SSL Verification disabled` | `validate_certs: "no"` — CML uses a self-signed certificate |
| `'Node.config' is deprecated` | `virl2_client` 2.9.x with `cisco.cml` 1.2.0, which still reads the old attribute. The `<2.10.0` pin is deliberate — 2.10 removes it and breaks the plugin |
| `Found both group and host with same name: dhcp-server` | A CML node label matches a CML tag. Only matters if you `--limit dhcp-server` |
| `Collection cisco.catalystcenter does not support Ansible version 2.15.x` | 2.9.0 is pinned on purpose — see Step 4 |

Anything starting with `Failed to parse` is a real error — see Troubleshooting.

Then run the first stage:

```bash
ansible-playbook playbooks/01_site_hierarchy.yml
```

Continue with the stage order in [README.md](README.md#pipeline-order).

---

## Troubleshooting

Add `-e catc_debug=true` to any Catalyst Center stage to print the full HTTP
request and response for each API call.

> **Never share that output.** `catc_debug` also prints the `X-Auth-Token`
> bearer JWT, which is a live credential for your Catalyst Center. Redact it
> before pasting anywhere, and never commit a debug transcript.

| Symptom | Cause | Fix |
|---------|-------|-----|
| `specifies unknown plugin 'cisco.cml.cml_inventory'` | `cisco.cml` collection not installed | Step 4 |
| `Collection <name> does not support Ansible version 2.15.x` | Collections installed from `requirements.yml` (2.17 control node) instead of `requirements-jumphost.yml`. The `cisco.catalystcenter` one is expected — see Step 4 | `ansible-galaxy collection install -r collections/requirements-jumphost.yml --force` |
| Stage 01 fails `[400] NCND00067: The request body is invalid` on an area CREATE | `cisco.catalystcenter` downgraded below 2.4.0 — it returns `dnac_response`, the roles read `catalystcenter_response`, so `parentId` is sent empty | `ansible-galaxy collection install cisco.catalystcenter:2.9.0 --force` |
| `No module named 'virl2_client'` on CML tasks | SDK missing from the active venv | `pip install 'virl2_client>=2.0.0,<2.10.0'` |
| `ERROR! variable files must contain either a dictionary of variables ... Got: <your password>` | You pasted the raw password into `vault.yml` instead of `key: value` pairs | Rewrite `vault.yml` per Step 7, then re-encrypt |
| `New Vault password:` prompt during `ansible-vault encrypt` | You ran it from the wrong directory, so `ansible.cfg` was not loaded | `cd` into `CICD Pipeline/ansible` first, or add `--vault-password-file ../.vault_pass` |
| `Decryption failed` on any playbook | `.vault_pass` content ≠ the passphrase used to encrypt | Re-create `.vault_pass` (Step 5) or re-encrypt the vault with the current one |
| `[Errno -2] Name or service not known` from the CML plugin | `CML_HOST` is empty — `.env` not exported into this shell | `set -a; . ./.env; set +a` from `CICD Pipeline/` |
| `Client error - Authentication failed!` from the CML plugin | Wrong `CML_USERNAME` / `CML_PASSWORD`. Trailing `#` in a password is commonly dropped | Quote the value: `CML_PASSWORD="..."`, then test with `curl -sk -X POST "https://$CML_HOST/api/v0/authenticate" -H 'Content-Type: application/json' -d "{\"username\":\"$CML_USERNAME\",\"password\":\"$CML_PASSWORD\"}"` — expect HTTP 200 |
| `./.env: line NN: EVPN: command not found` | Unquoted value with spaces in `.env` | Quote it: `CML_LAB="BGP EVPN Campus"` |
| `Attempting to decrypt but no vault secrets found` | `.vault_pass` missing at `CICD Pipeline/.vault_pass` | Step 5 |
| `ModuleNotFoundError: No module named 'apt_pkg'` after any `apt` command | `/usr/bin/python3` was repointed away from 3.8 | `sudo update-alternatives --set python3 /usr/bin/python3.8` |
| `Network is unreachable` on `apt-get install` | Mirrors resolve to IPv6 first; the pod has no IPv6 route | `echo 'Acquire::ForceIPv4 "true";' \| sudo tee /etc/apt/apt.conf.d/99-force-ipv4` |
| CML inventory returns zero hosts | Lab not started, or `CML_LAB` does not match the lab title exactly | Check the lab name in the CML UI and re-export `.env` |
| Playbook cannot reach `198.18.129.100` | You are running from your laptop, not the jump host | SSH to the jump host first |

---

## Reference — where everything lives

```
~/tecops-venv/                                   # Python 3.9 venv (Ansible)
~/.ansible/collections/                          # Galaxy collections
~/CatalystCenter-BGP-EVPN-VXLAN/
└── CICD Pipeline/
    ├── .vault_pass                              # vault passphrase   (you create, gitignored)
    ├── .env                                     # CML/device creds   (you create, gitignored)
    ├── Settings/settings.json                   # single source of truth for all stages
    └── ansible/                                 # ← run every command from here
        ├── ansible.cfg
        ├── inventory/
        │   ├── cml.yml                          # dynamic CML inventory
        │   ├── static_inventory.yml
        │   └── group_vars/
        │       └── catalyst_center/vault.yml    # encrypted (you create, gitignored)
        └── playbooks/                           # 01–11 stages
```
