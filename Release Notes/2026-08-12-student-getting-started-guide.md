# 2026-08-12 — Student getting-started guide for the dCloud jump host

## What changed

| File | Change |
|------|--------|
| `CICD Pipeline/ansible/GETTING_STARTED.md` | **New.** Eight-step, first-time setup guide for students working from the dCloud jump host. |
| `CICD Pipeline/ansible/collections/requirements-jumphost.yml` | **New.** Collection pins compatible with ansible-core 2.15. |
| `CICD Pipeline/ansible/README.md` | Quick Start setup block replaced by a pointer to the guide; jump host bootstrap section removed; requirements-file comparison added; layout tree and pipeline table updated. |
| `README.md` (root) | Removed the `00_ansible_jh_setup.yml` pipeline row; added a link to the guide. |
| `CICD Pipeline/.env.example` | Quoted `CML_LAB="BGP EVPN Campus"`. |
| `CICD Pipeline/ansible/playbooks/00_ansible_jh_setup.yml` | **Removed.** |
| `CICD Pipeline/ansible/roles/jumphost_setup/` | **Removed.** |
| `CICD Pipeline/ansible/inventory/group_vars/jumphosts/` | **Removed.** |
| `CICD Pipeline/ansible/inventory/static_inventory.yml` | Removed the `jumphosts` group. |
| `CICD Pipeline/ansible/.gitignore` | Removed the `jumphosts/vars.yml` entry. |

## Motivation

Students bootstrap the jump host with the image-provided `~/install-ansible.sh`,
which predates this repository. The gap between what that script installs and
what the pipeline needs produced three repeatable failures during lab delivery:

1. **`specifies unknown plugin 'cisco.cml.cml_inventory'`** — the script installs
   `cisco.catalystcenter`, `cisco.dnac`, `cisco.ios`, `cisco.nxos`,
   `ansible.utils`, and `community.general`, but neither `cisco.cml` nor the
   `virl2_client` SDK. Every command against `inventory/` then emits four
   warning lines and silently drops all fabric hosts.

2. **`ERROR! variable files must contain either a dictionary of variables, or a
   list of dictionaries. Got: <password>`** — students conflated the two vault
   artifacts and pasted the raw password into
   `inventory/group_vars/catalyst_center/vault.yml`. That file is loaded by
   `vars_files:` in every stage playbook and must be a YAML mapping;
   `CICD Pipeline/.vault_pass` is the file that takes a bare passphrase.

3. **Unexpected `New Vault password:` prompt** — `ansible-vault encrypt` run from
   `CICD Pipeline/` instead of `CICD Pipeline/ansible/`. Ansible only loads
   `ansible.cfg` from the current working directory, so
   `vault_password_file = ../.vault_pass` was never applied.

The guide documents the working directory rule once, prominently, and the
troubleshooting table maps each verbatim error string to its fix.

## `.env` quoting fix

`CICD Pipeline/.envrc` loads `.env` through direnv's `dotenv_if_exists`, which
tolerates unquoted values containing spaces. Students on the jump host have no
direnv and load the file with `set -a; . ./.env; set +a`, where bash word-splits
the value:

```
./.env: line 22: EVPN: command not found
```

`CML_LAB` is now quoted in `.env.example`. Existing `.env` files must be updated
by hand — they are gitignored.

## Environment documented

Verified live on the jump host (`dcloud`, Ubuntu 20.04.5 focal):

| Component | Value |
|-----------|-------|
| Installer | `~/install-ansible.sh` (image-provided) |
| Virtualenv | `~/tecops-venv` — Python 3.9.5 |
| Ansible | `ansible` 8.x → **ansible-core 2.15.13** |
| Collections path | `~/.ansible/collections` |
| Collections after Step 4 | `cisco.catalystcenter` 2.1.3, `cisco.dnac` 6.46.0, `cisco.ios` 11.5.1, `cisco.nxos` 12.1.0, `community.general` 13.3.0, `ansible.utils` 6.1.0, **`cisco.cml` 1.2.0** |

Note this is a different environment from the one an earlier draft of
`playbooks/00_ansible_jh_setup.yml` produced (CPython 3.11 + ansible-core 2.17
under `/opt/campus-evpn`). That playbook and its `jumphost_setup` role have been
**removed** — maintaining a second, divergent bootstrap path alongside the
image-provided `install-ansible.sh` gave students two ways to build the same box
and two sets of failure modes. `install-ansible.sh` is now the only supported
path, and this guide documents it.

## Documentation consolidation

`CICD Pipeline/ansible/README.md` previously carried its own Quick Start with
vault-creation and encryption commands, plus a full jump host bootstrap section.
That content now lives only in `GETTING_STARTED.md`; the README keeps the
per-session activation snippet and links out for everything else. Setup
instructions had drifted between the two files, which is what produced the
`--vault-password-file ../.vault_pass` examples that only work from one
directory.

## Collection pins for ansible-core 2.15

`install-ansible.sh` builds its venv on Python 3.9, and Python 3.9 caps
ansible-core at 2.15 — 2.16 requires a control node on 3.10+, and Ubuntu 20.04
focal has no 3.10 package (the deadsnakes focal pocket is empty upstream:
`main/binary-amd64/Packages` is 0 bytes). So 2.15 is a hard ceiling on the jump
host, not a preference.

Installing the default `collections/requirements.yml` there pulls current
releases that declare `requires_ansible: >=2.16.0`, and each one warns:

```
[WARNING]: Collection ansible.utils does not support Ansible version 2.15.13
```

Five collections were affected: `ansible.utils` 6.1.0, `ansible.netcommon`
8.6.2, `cisco.catalystcenter` 2.9.0, `cisco.ios` 11.5.1, `cisco.nxos` 12.1.0.

`collections/requirements-jumphost.yml` pins the newest release of each
collection whose `requires_ansible` still admits 2.15, determined from the
Galaxy v3 API rather than guessed:

| Collection | Control node (`requirements.yml`) | Jump host (`requirements-jumphost.yml`) |
|---|---|---|
| `cisco.catalystcenter` | 2.9.0 | 2.9.0 — **exception, see below** |
| `cisco.dnac` | 6.46.0 | 6.46.0 |
| `cisco.ios` | `>=4.0.0` → 11.5.1 | **9.2.0** |
| `cisco.nxos` | `>=5.0.0` → 12.1.0 | **9.4.0** |
| `cisco.cml` | `>=1.2.0` | 1.2.0 |
| `ansible.utils` | (transitive) 6.1.0 | **5.1.2** |
| `ansible.netcommon` | (transitive) 8.6.2 | **7.2.0** |
| `ansible.posix` | `>=1.5.0` | **2.1.0** |
| `community.general` | `>=8.0.0,<11.0.0` | 10.7.9 |

### `cisco.catalystcenter` cannot be downgraded

2.3.1 is the newest release that admits ansible-core 2.15, and every module in
it reports results under `dnac_response`. The `catalystcenter_response` key that
every role in this repo reads was introduced in 2.4.0. Pinning 2.3.1 therefore
leaves `catc_all_sites.catalystcenter_response` undefined,
`roles/catc_common/tasks/build_site_id_map.yml` falls through its
`| default('')` and produces an empty `site_id_map`, and the first area create
posts an empty parent:

```
URL:  https://<catc>/dna/intent/api/v1/areas
Body: { "name": "PODS", "parentId": "" }
Status: 400 - Bad Request
fatal: [catalyst_center_api]: FAILED! => {"dnac_response": null,
  "msg": "[400] Bad Request - NCND00067: The request body is invalid"}
```

The `"dnac_response": null` in that failure is the tell — 2.9.0 would have
reported `catalystcenter_response`. Both requirements files therefore pin 2.9.0,
and the jump host emits one expected
`Collection cisco.catalystcenter does not support Ansible version 2.15.13`
warning, documented as ignorable in the guide, the README, and the pin file
itself. 2.9.0 is verified working on ansible-core 2.15.13.

## Validation

Executed on the jump host in the student environment:

```
$ pip install 'virl2_client>=2.0.0,<2.10.0'
$ ansible-galaxy collection install 'cisco.cml:>=1.2.0'
cisco.cml:1.2.0 was installed successfully

$ cd ~/CatalystCenter-BGP-EVPN-VXLAN/CICD\ Pipeline && set -a && . ./.env && set +a
$ cd ansible && ansible-inventory --list --limit catalyst_center
    "catalyst_center": { "hosts": ["catalyst_center_api"] },
    "iosxe": { "children": ["cat9000v-uadp", "cat8000v"] },
    "nxos":  { "children": ["nxosv9000"] }
```

No inventory warnings remained after the `cisco.cml` install.

After applying `requirements-jumphost.yml`, the only version-support warning
left is the deliberate `cisco.catalystcenter` one, and stage 01 completes end to
end against the pod Catalyst Center:

```
$ ansible-inventory --graph 2>&1 | grep -i warning
[WARNING]: Found both group and host with same name: dhcp-server

$ ansible-playbook playbooks/01_site_hierarchy.yml --syntax-check 2>&1 | grep -i warning
[WARNING]: Found both group and host with same name: dhcp-server
[WARNING]: Collection cisco.catalystcenter does not support Ansible version 2.15.13

$ ansible-playbook playbooks/01_site_hierarchy.yml
PLAY RECAP
catalyst_center_api : ok=29  changed=0  unreachable=0  failed=0  skipped=76
```

The remaining messages are expected: `Node.config is deprecated`
(`virl2_client` 2.9.x with `cisco.cml` 1.2.0, pinned deliberately), the
group/host name collision on `dhcp-server` (a CML node label matching a CML
tag), and the single `cisco.catalystcenter` version-support warning.

## Security note

`-e catc_debug=true` enables the collection's `catalystcenter_debug` flag, which
prints the full request transcript **including the `X-Auth-Token` bearer JWT**.
Use it only for local troubleshooting; never paste that output into an issue,
chat, or commit.

## Operational impact

None to the fabric or to Catalyst Center — documentation and one example-file
edit. Students should be pointed at
`CICD Pipeline/ansible/GETTING_STARTED.md` as the single entry point for pod
setup.
