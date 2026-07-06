# Ansible CI/CD Pipeline (Unified)

This directory consolidates all numbered pipeline stages (`1.0`–`11.0`) and the SWIM image-server util into a single Ansible project with thin playbooks and reusable roles.

## Quick Start

```bash
cd "CICD Pipeline/ansible"

# Install collections
ansible-galaxy collection install -r collections/requirements.yml

# Vault password file lives at the CICD Pipeline root (shared by all playbooks).
# Create it once: echo 'your-vault-passphrase' > "../.vault_pass" && chmod 600 "../.vault_pass"
# ansible.cfg resolves vault_password_file = ../.vault_pass automatically.

# Configure secrets (catc_username / catc_password only — no separate dnac_* keys)
cp inventory/group_vars/catalyst_center/vault.yml.example inventory/group_vars/catalyst_center/vault.yml
ansible-vault encrypt inventory/group_vars/catalyst_center/vault.yml --vault-password-file ../.vault_pass

# For image server deployments
cp inventory/group_vars/image_servers/vars.yml.example inventory/group_vars/image_servers/vars.yml
cp inventory/group_vars/image_servers/vault.yml.example inventory/group_vars/image_servers/vault.yml

# Run a stage (no --vault-password-file needed when ansible.cfg is used)
ansible-playbook playbooks/01_site_hierarchy.yml
```

## Layout

```
CICD Pipeline/
├── .vault_pass                  # Vault passphrase (gitignored; shared by all stages)
└── ansible/
    ├── ansible.cfg              # vault_password_file = ../.vault_pass
    ├── inventory/hosts.yml      # catalyst_center, iosxe, nxos, image_servers
    ├── playbooks/               # Thin entry playbooks (01–11, site.yml)
    ├── roles/
    │   ├── catc_common/         # load_settings, auth_token, hierarchy paths
    │   ├── site_hierarchy/      # Stage 1.0
    │   └── …
    └── Settings/settings.json   # SSOT (../Settings/settings.json)
```

## Pipeline Order

Run stages individually or use the orchestrator (stages 1–10, excludes SWIM and backup):

```bash
ansible-playbook playbooks/site.yml
```

| Playbook | Original stage | Description |
|----------|----------------|-------------|
| `01_site_hierarchy.yml` | 1.0 | Build site hierarchy |
| `02_network_settings.yml` | 2.0 | Apply network settings |
| `03_credentials.yml` | 3.0 | CLI/SNMP/NETCONF credentials |
| `04_device_discovery.yml` | 4.0 | Device discovery |
| `05_assign_to_site.yml` | 5.0 | Assign devices to sites |
| `06_swim_*.yml` | 6.0 | SWIM lifecycle (manual) |
| `07_template_sync.yml` | 7.0 | GitHub template sync |
| `08_network_profile.yml` | 8.0 | Network profiles |
| `09_provision_devices.yml` | 9.0 | Device provisioning |
| `10_deploy_composite.yml` | 10.0 | Composite template deploy |
| `11_backup_lab_configs.yml` | 11.0 | IOS-XE/NX-OS config backup |
| `deploy_http_image_server.yml` | utils | SWIM HTTP image server |

## Common Overrides

```bash
# Debug mode (stages that supported DEBUG=true)
DEBUG=true ansible-playbook playbooks/04_device_discovery.yml

# Delete site hierarchy
ansible-playbook playbooks/01_site_hierarchy.yml -e state=deleted

# SWIM rollback (requires confirmation)
ansible-playbook playbooks/06_swim_rollback.yml \
  -e rollback_confirm=YES -e rollback_reload_ack=RELOAD_OK
```

## Migration Note

The numbered stage directories (`1.0-...` through `11.0-...`) retain their README and DIAGRAMS. Playbook logic has moved here; run playbooks from this directory going forward.
