# Contributing to cicd-platform-demo

Thank you for your interest in contributing to this project! This document provides guidelines and information for contributors.

## Development Guidelines

### Code Style
- Follow Ansible best practices and conventions
- Use descriptive variable and task names
- Keep tasks idempotent and atomic
- Use proper YAML formatting and indentation

### Testing
- Ensure all playbooks pass `ansible-lint` validation
- Run `ansible-playbook --syntax-check` before submitting
- Where possible, verify against a real Kubernetes cluster (or kind/k3d)
  before submitting — this repo has no CI cluster to deploy against yet

### Security
- Never commit unencrypted secrets or passwords
- Use `ansible-vault` for any sensitive information
- Follow the principle of least privilege
- Document security implications of changes

## Ansible-lint Compliance

```bash
# Install ansible-lint
pip install ansible-lint

# Run lint checks
ansible-lint

# With vault password file
ANSIBLE_VAULT_PASSWORD_FILE=.vault_pass ansible-lint
```

### Common Issues and Solutions

#### Variable Naming
- Use lowercase with underscores: `my_variable`
- Avoid using reserved keywords
- Use descriptive names that indicate purpose

#### Task Names
- Start with uppercase letter
- Be descriptive and specific
- Use consistent naming patterns

## Directory Structure

```
├── Step*.yml                    # Sequential deployment playbooks
├── roles/                       # Ansible roles
│   ├── role_name/
│   │   ├── tasks/main.yml      # Main tasks
│   │   ├── defaults/main.yml   # Default variables
│   │   ├── templates/          # Jinja2 templates (Helm values, etc.)
│   │   └── files/              # Static files (test suites, scripts)
├── inventories/                 # Environment inventories
│   └── environment/
│       ├── hosts.ini           # Inventory definition
│       └── group_vars/         # Group variables (all.yml, secret.yml)
├── scripts/                     # Standalone helper scripts
└── README.md                   # Documentation
```

## Variable Management

### Variable Precedence
1. Role defaults (`roles/*/defaults/main.yml`)
2. Inventory group vars (`inventories/*/group_vars/`)
3. Inventory host vars (`inventories/*/host_vars/`)
4. Playbook variables
5. Command line variables (`-e`)

### Secret Management
- Use `ansible-vault` for sensitive data (`secret.yml`, never `secret.yml`
  itself in git — see `secret.yml.example`)
- Store the vault password securely (a password manager, or a
  `.vault_pass` file outside version control)
- Never commit unencrypted secrets
- Regularly rotate sensitive credentials

## Submitting Changes

### Before Submitting
1. Test your changes thoroughly
2. Run `ansible-lint` to ensure compliance
3. Update documentation if needed
4. Add an entry to `CHANGELOG.md`

### Change Categories
- **Bug fixes**: Corrections to existing functionality
- **Features**: New functionality or enhancements
- **Breaking changes**: Changes that affect existing behavior
- **Documentation**: Updates to docs, README, or comments
- **Security**: Security-related improvements or fixes

### Documentation Updates
- Update README.md for user-facing changes
- Update role documentation (`roles/*/README.md`) for role changes
- Add troubleshooting information for common issues

## Reporting Issues

- Use descriptive titles
- Include error messages and logs
- Specify Kubernetes and Ansible versions
- Provide minimal reproduction steps
- Include relevant configuration (redacted — never paste secrets)

## Best Practices

### Ansible Development
- Use specific module versions when possible
- Implement proper error handling
- Use check mode compatibility
- Document complex logic
- Use tags for selective execution (`--tags jenkins`, etc.)

### Security Considerations
- Validate user inputs
- Use secure defaults
- Implement least privilege access
- Document security implications

Thank you for contributing to making this project better!
