# role_cicd_tests

Automated testing role for CI/CD services (Jenkins, Nexus, GitLab) deployed on Kubernetes.

## Overview

This role executes pytest-based tests to validate the health and functionality of CI/CD service deployments. It auto-discovers pods in the cluster and runs comprehensive checks including:

- **Port listening verification**: Ensures service ports are bound and listening
- **Process checks**: Verifies critical service processes are running
- **File system checks**: Validates required directories and configuration files exist
- **Kubernetes resource checks**: Confirms pods, services, ingresses, and PVCs are healthy
- **Service-specific tests**: Custom checks for each CI/CD service

## Supported Services

- **Jenkins**: CI/CD automation server
- **Nexus**: Artifact repository manager
- **GitLab**: Git repository and CI/CD platform
- **GitLab Runner**: GitLab CI/CD job execution agent

## Requirements

- Ansible 2.9+
- kubectl configured with cluster access
- Python 3.x on the control node
- Pytest and dependencies (installed automatically via venv)

## Role Variables

### Required
- `role_cicd_tests_test_target`: Service to test (jenkins, nexus, gitlab, or gitlab-runner)

### Optional
- `kube_ns`: Kubernetes namespace (defaults to role_cicd_tests_test_target value)
- `KUBE_POD`: Specific pod name (auto-discovered if not set)

## Dependencies

None. The role creates a Python virtual environment and installs dependencies automatically.

## Example Playbook

```yaml
---
- name: Run CI/CD service tests
  hosts: localhost
  gather_facts: false
  roles:
    - role: role_cicd_tests
      role_cicd_tests_test_target: jenkins

- name: Test all services
  hosts: localhost
  gather_facts: false
  tasks:
    - include_role:
        name: role_cicd_tests
      vars:
        role_cicd_tests_test_target: "{{ item }}"
      loop:
        - jenkins
        - nexus
        - gitlab
```

## Running Tests

Execute tests via the deployment playbook with tags:

```bash
# Test Jenkins only
ansible-playbook -i inventories/local/hosts.ini Step03-test.yml --tags jenkins

# Test Nexus only
ansible-playbook -i inventories/local/hosts.ini Step03-test.yml --tags nexus

# Test GitLab only
ansible-playbook -i inventories/local/hosts.ini Step03-test.yml --tags gitlab

# Test all services
ansible-playbook -i inventories/local/hosts.ini Step03-test.yml
```

## Test Structure

```
role_cicd_tests/
├── tasks/
│   └── main.yml                      # Main orchestration tasks
├── files/
│   ├── run-tests.sh                  # Bash test runner
│   ├── requirements.txt              # Python dependencies
│   └── parse_junit.py                # JUnit XML parser
├── tests/
│   ├── test_jenkins_checks.py        # Jenkins-specific tests
│   ├── test_nexus_checks.py          # Nexus-specific tests
│   ├── test_gitlab_checks.py         # GitLab-specific tests
│   └── test_cicd_services_checks.py  # Common Kubernetes tests
├── pytest.ini                        # Pytest configuration
└── meta/
    └── main.yml                      # Role metadata
```

## Test Categories

### Jenkins Tests
- HTTP (8080) and agent (50000) ports listening
- Jenkins home directory and configuration files exist
- Java process running
- Plugins and jobs directories present
- Version file readable

### Nexus Tests
- HTTP (8081) and Docker registry ports listening
- Nexus data directory and subdirectories exist
- Java process running
- Database and blobs directories present
- Configuration files readable
- Log files contain entries

### GitLab Tests
- HTTP (80), HTTPS (443), and SSH (22) ports listening
- Data, config, and logs directories exist
- Core services running (PostgreSQL, Redis, Nginx, Puma, Sidekiq)
- Repository and uploads directories present
- Version manifest readable

### Common Kubernetes Tests
- Pod running and ready
- Container ready with minimal restarts
- Service exists with active endpoints
- Ingress configured (if present)
- PVCs bound (if used)
- StatefulSet/Deployment healthy

## Output

Tests produce:
1. **Console output**: Real-time pytest execution results
2. **JUnit XML**: `/tmp/test-results-{service}.xml` for CI/CD integration
3. **Summary**: Parsed totals (passed/failed/errors/skipped)

Example output:
```
Tests: total=15
passed=14 failures=1
errors=0 skipped=0
```

## Troubleshooting

**Pod not found:**
- Verify service is deployed: `kubectl get pods -n {namespace}`
- Check label selector matches: `app.kubernetes.io/name={service}-chart`

**Tests failing:**
- Review pod logs: `kubectl logs -n {namespace} {pod-name}`
- Verify service is fully initialized (may take several minutes)
- Check resource constraints (CPU/memory limits)

**Python/pytest errors:**
- Virtual environment is created automatically at `roles/role_cicd_tests/.venv-cicd-tests`
- Delete `.venv-cicd-tests` directory to force recreation

## License

MIT

## Author

CI/CD Team
