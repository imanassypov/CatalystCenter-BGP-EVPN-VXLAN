# Ansible CI/CD Pipeline

Single Ansible project for Catalyst Center provisioning (stages 1–11), SWIM, and config backup. All automation runs from this directory.

## Quick Start

```bash
cd "CICD Pipeline/ansible"

ansible-galaxy collection install -r collections/requirements.yml

# Vault password (once): echo 'passphrase' > "../.vault_pass" && chmod 600 "../.vault_pass"

# Catalyst Center API (+ optional git_token for stage 7)
cp inventory/group_vars/catalyst_center/vault.yml.example inventory/group_vars/catalyst_center/vault.yml
ansible-vault encrypt inventory/group_vars/catalyst_center/vault.yml --vault-password-file ../.vault_pass

# Stage 11 device SSH creds come from Settings/settings.json (no separate vault)

# Image server (before SWIM import)
cp inventory/group_vars/image_servers/vars.yml.example inventory/group_vars/image_servers/vars.yml
cp inventory/group_vars/image_servers/vault.yml.example inventory/group_vars/image_servers/vault.yml
ansible-vault encrypt inventory/group_vars/image_servers/vault.yml --vault-password-file ../.vault_pass

# YANG Suite (NETCONF/YANG lab utility)
cp inventory/group_vars/yangsuite_servers/vars.yml.example inventory/group_vars/yangsuite_servers/vars.yml
cp inventory/group_vars/yangsuite_servers/vault.yml.example inventory/group_vars/yangsuite_servers/vault.yml
ansible-vault encrypt inventory/group_vars/yangsuite_servers/vault.yml --vault-password-file ../.vault_pass

ansible-playbook playbooks/01_site_hierarchy.yml
```

## Layout

```
CICD Pipeline/
├── .vault_pass
├── Settings/settings.json       # SSOT for all stages
└── ansible/
    ├── inventory/               # hosts + group_vars (vault, connection)
    ├── playbooks/               # 01–11, site.yml, deploy_* utilities
    ├── roles/                   # site_hierarchy, swim, template_sync, http_image_server, yangsuite_docker, …
    ├── config-backups/          # stage 11 output (gitignored timestamps)
    ├── logs/                    # SWIM evidence JSON (gitignored)
    └── docs/swim/               # SWIM reference diagrams
```

## Pipeline Order

Full orchestrator (stages 1–10, excludes SWIM and backup):

```bash
ansible-playbook playbooks/site.yml
```

| Playbook | Stage | Description |
|----------|-------|-------------|
| `01_site_hierarchy.yml` | 1 | Build site hierarchy |
| `02_network_settings.yml` | 2 | Apply network settings |
| `03_credentials.yml` | 3 | CLI/SNMP/NETCONF credentials |
| `04_device_discovery.yml` | 4 | Device discovery |
| `05_assign_to_site.yml` | 5 | Assign devices to sites |
| `06_swim_*.yml` | 6 | SWIM lifecycle (run in order; see below) |
| `07_template_sync.yml` | 7 | GitHub template sync |
| `08_network_profile.yml` | 8 | Network profiles |
| `09_provision_devices.yml` | 9 | Device provisioning |
| `10_deploy_composite.yml` | 10 | Composite template deploy |
| `11_backup_lab_configs.yml` | 11 | IOS-XE/NX-OS config backup |
| `deploy_http_image_server.yml` | 6 prep | HTTP image server |
| `deploy_yangsuite.yml` | util | Cisco YANG Suite (Docker) |

### SWIM (stage 6)

```bash
ansible-playbook playbooks/deploy_http_image_server.yml
ansible-playbook playbooks/06_swim_preflight.yml
ansible-playbook playbooks/06_swim_import_and_tag.yml
ansible-playbook playbooks/06_swim_distribute.yml
ansible-playbook playbooks/06_swim_activate.yml
ansible-playbook playbooks/06_swim_postcheck.yml
```

### YANG Suite (Docker)

Deploys [Cisco YANG Suite](https://developer.cisco.com/docs/yangsuite/) from the upstream [CiscoDevNet/yangsuite](https://github.com/CiscoDevNet/yangsuite) repository. Replaces the interactive `start_yang_suite.sh` prompts with Ansible templates (`setup.env`, self-signed nginx certs, `docker compose up`).

```bash
ansible-playbook playbooks/deploy_yangsuite.yml
# UI: https://<yangsuite_server_ip>:8443/
```

**Operations (health / restart):** see project skill
`.cursor/skills/yangsuite-jumpserver/` — scripts `yangsuite-health.sh` and
`yangsuite-restart.sh`. Memory note: `MEMORY.md` in that folder.

If `:8443` is connection refused, the Compose stack is usually stopped; restart
with `docker compose up -d` in `/opt/yangsuite/docker` on the host.

## Common Overrides

```bash
DEBUG=true ansible-playbook playbooks/04_device_discovery.yml
ansible-playbook playbooks/01_site_hierarchy.yml -e state=deleted
ansible-playbook playbooks/06_swim_rollback.yml -e rollback_confirm=YES -e rollback_reload_ack=RELOAD_OK
ansible-playbook playbooks/deploy_http_image_server.yml \
  -e '{"image_local_paths":["/abs/cat9kv.SSA.bin","/abs/cat9kv.SPA.bin"]}'
```

Role task files include pre/post data structure comments for each API interaction.
