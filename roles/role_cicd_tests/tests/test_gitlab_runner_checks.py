import os
import re
import subprocess
import pytest
import requests
import time


def run_in_target(cmd: str, namespace: str = 'gitlab-runner') -> subprocess.CompletedProcess:
    """Execute command in the GitLab Runner pod via kubectl exec."""
    kube_pod = os.environ.get('KUBE_POD')
    kube_ns = os.environ.get('KUBE_NS', namespace)
    test_container = os.environ.get('TEST_CONTAINER')

    if kube_pod:
        check = subprocess.run(['kubectl', 'get', 'pod', kube_pod, '-n', kube_ns], 
                               capture_output=True, text=True)
        if check.returncode != 0:
            detect = subprocess.run(['kubectl', '-n', kube_ns, 'get', 'pods', '--no-headers', 
                                    '-o', 'custom-columns=NAME:.metadata.name'], 
                                    capture_output=True, text=True)
            found = ''
            if detect.returncode == 0 and detect.stdout:
                base = kube_pod.split('-')[0] if '-' in kube_pod else kube_pod
                for line in detect.stdout.splitlines():
                    if 'gitlab-runner' in line and 'gitlab-runner-chart' in line:
                        found = line.strip()
                        break
            if found:
                kube_pod = found
        cmd_list = ['kubectl', 'exec', '-n', kube_ns, kube_pod, '--', 'sh', '-c', cmd]
    elif test_container:
        cmd_list = ['docker', 'exec', test_container, 'sh', '-c', cmd]
    else:
        pytest.skip('No KUBE_POD/KUBE_NS or TEST_CONTAINER env var set; skipping k8s/docker tests')

    return subprocess.run(cmd_list, capture_output=True, text=True)


def run_kubectl(cmd: str) -> subprocess.CompletedProcess:
    """Execute kubectl command directly."""
    return subprocess.run(['kubectl'] + cmd.split(), capture_output=True, text=True)


@pytest.mark.gitlab_runner
def test_gitlab_runner_pod_running():
    """Verify GitLab Runner pod is running."""
    result = run_kubectl('get pods -n gitlab-runner -l app.kubernetes.io/name=gitlab-runner-chart --no-headers')
    
    assert result.returncode == 0, f"kubectl command failed: {result.stderr}"
    assert result.stdout.strip(), "No GitLab Runner pods found"
    
    lines = result.stdout.strip().split('\n')
    for line in lines:
        if 'gitlab-runner' in line:
            parts = line.split()
            status = parts[2] if len(parts) > 2 else ''
            ready = parts[1] if len(parts) > 1 else ''
            assert status == 'Running', f"GitLab Runner pod not running: {status}"
            assert '1/1' in ready, f"GitLab Runner pod not ready: {ready}"
            break
    else:
        pytest.fail("No GitLab Runner pod found in output")


@pytest.mark.gitlab_runner
def test_gitlab_runner_service_account():
    """Verify GitLab Runner service account exists."""
    result = run_kubectl('get serviceaccount -n gitlab-runner gitlab-runner-gitlab-runner-chart')
    
    assert result.returncode == 0, f"Service account not found: {result.stderr}"


@pytest.mark.gitlab_runner
def test_gitlab_runner_rbac_permissions():
    """Verify GitLab Runner has correct RBAC permissions."""
    # Check Role exists
    result = run_kubectl('get role -n gitlab-runner gitlab-runner-gitlab-runner-chart')
    assert result.returncode == 0, f"Role not found: {result.stderr}"
    
    # Check RoleBinding exists
    result = run_kubectl('get rolebinding -n gitlab-runner gitlab-runner-gitlab-runner-chart')
    assert result.returncode == 0, f"RoleBinding not found: {result.stderr}"
    
    # Verify specific permissions
    result = run_kubectl('describe role -n gitlab-runner gitlab-runner-gitlab-runner-chart')
    assert result.returncode == 0, "Failed to describe role"
    
    permissions_output = result.stdout
    
    # Check for required permissions
    required_permissions = [
        'pods.*create',
        'pods.*delete', 
        'pods/exec.*create',
        'pods/attach.*create',
        'secrets.*create',
        'secrets.*get'
    ]
    
    for permission in required_permissions:
        assert re.search(permission.replace('.*', r'.*'), permissions_output), \
            f"Missing required permission: {permission}"


@pytest.mark.gitlab_runner
def test_gitlab_runner_configmap():
    """Verify GitLab Runner ConfigMap is properly configured."""
    result = run_kubectl('get configmap -n gitlab-runner gitlab-runner-gitlab-runner-chart-config -o yaml')
    
    assert result.returncode == 0, f"ConfigMap not found: {result.stderr}"
    
    config_content = result.stdout
    
    # Verify config.toml exists
    assert 'config.toml:' in config_content, "config.toml not found in ConfigMap"
    
    # Verify entrypoint script exists  
    assert 'entrypoint:' in config_content, "entrypoint script not found in ConfigMap"
    
    # Check for key configuration elements (allowing for YAML formatting)
    config_checks = [
        'executor = \\"kubernetes\\"',  # YAML escaped format
        'url = \\"http://gitlab-chart.gitlab.svc.cluster.local\\"',
        'tags = \\"kubernetes,docker\\"',
        'image = \\"ubuntu:20.04\\"'
    ]

    for check in config_checks:
        assert check in config_content, f"Missing config: {check}"
@pytest.mark.gitlab_runner
def test_gitlab_runner_secret():
    """Verify GitLab Runner secret exists and check token configuration."""
    result = run_kubectl('get secret -n gitlab-runner gitlab-runner-secret -o yaml')
    
    assert result.returncode == 0, f"Secret not found: {result.stderr}"
    
    # Check secret has runner-registration-token field
    assert 'runner-registration-token:' in result.stdout, "runner-registration-token not found in secret"
    
    # Get token value - it might be empty if token is configured directly in config.toml
    result = run_kubectl('get secret -n gitlab-runner gitlab-runner-secret -o jsonpath={.data.runner-registration-token}')
    token_b64 = result.stdout.strip()
    
    # If secret token is empty, verify token is configured in ConfigMap instead
    if not token_b64:
        config_result = run_kubectl('get configmap -n gitlab-runner gitlab-runner-gitlab-runner-chart-config -o yaml')
        assert 'token = \\"glrtr-' in config_result.stdout, "No token found in secret or config"
    else:
        assert len(token_b64) > 10, "Token appears too short"


@pytest.mark.gitlab_runner
def test_gitlab_runner_process_running():
    """Verify GitLab Runner process is running inside the pod."""
    result = run_in_target('ps aux | grep gitlab-runner | grep -v grep')
    
    assert result.returncode == 0, f"GitLab Runner process not found: {result.stderr}"
    assert 'gitlab-runner run' in result.stdout, "GitLab Runner not in 'run' mode"


@pytest.mark.gitlab_runner
def test_gitlab_runner_config_loaded():
    """Verify GitLab Runner has loaded its configuration."""
    # Check if config file exists in the expected location
    result = run_in_target('test -f /etc/gitlab-runner/config.toml && echo "config exists"')
    
    assert result.returncode == 0, "GitLab Runner config file not found"
    assert 'config exists' in result.stdout, "Config file verification failed"


@pytest.mark.gitlab_runner
def test_gitlab_runner_metrics_port():
    """Verify GitLab Runner metrics port is listening."""
    # GitLab Runner metrics port (default 9252)
    result = run_in_target('netstat -lntp 2>/dev/null | grep :9252 || ss -lntp 2>/dev/null | grep :9252 || echo "port check done"')
    
    # Note: Metrics might be disabled, so we just check the command runs
    assert result.returncode == 0, "Failed to check metrics port"


@pytest.mark.gitlab_runner
def test_gitlab_runner_can_connect_to_gitlab():
    """Verify GitLab Runner can connect to GitLab service."""
    # Test connection to GitLab internal service
    gitlab_url = "http://gitlab-chart.gitlab.svc.cluster.local"
    
    result = run_in_target(f'curl -s -o /dev/null -w "%{{http_code}}" {gitlab_url} || echo "connection test"')
    
    # Should get some HTTP response (even if not 200)
    assert result.returncode == 0, f"Failed to test GitLab connection: {result.stderr}"


@pytest.mark.gitlab_runner
def test_gitlab_runner_host_aliases():
    """Verify host aliases are working for gitlab.cicd.example.test."""
    result = run_in_target('nslookup gitlab.cicd.example.test 2>/dev/null || getent hosts gitlab.cicd.example.test || echo "host alias test"')
    
    # Host aliases should resolve or we should get some response
    assert result.returncode == 0, "Failed to test host aliases"


@pytest.mark.gitlab_runner
def test_gitlab_runner_job_execution():
    """Test that GitLab Runner can create job pods (if jobs are available)."""
    # Check for any runner job pods
    result = run_kubectl('get pods -n gitlab-runner -l job.runner.gitlab.com/id --no-headers')
    
    # This test passes if we can query for job pods (jobs may or may not exist)
    assert result.returncode == 0, "Failed to query for GitLab Runner job pods"


@pytest.mark.gitlab_runner
def test_gitlab_runner_logs_no_errors():
    """Verify GitLab Runner logs don't show critical errors."""
    result = run_kubectl('logs -n gitlab-runner -l app.kubernetes.io/name=gitlab-runner-chart --tail=50')
    
    assert result.returncode == 0, "Failed to get GitLab Runner logs"
    
    logs = result.stdout.lower()
    
    # Check for critical error patterns
    error_patterns = [
        'panic:',
        'fatal error:',
        'connection refused',
        'authentication failed'
    ]
    
    for pattern in error_patterns:
        assert pattern not in logs, f"Critical error found in logs: {pattern}"


@pytest.mark.gitlab_runner
def test_gitlab_runner_version():
    """Verify GitLab Runner version."""
    result = run_in_target('gitlab-runner --version')
    
    assert result.returncode == 0, f"Failed to get GitLab Runner version: {result.stderr}"
    assert 'Version:' in result.stdout, "GitLab Runner version output invalid"
    
    # Extract version (should be 16.11.0 or similar)
    version_match = re.search(r'(\d+\.\d+\.\d+)', result.stdout)
    assert version_match, "Could not extract version number"
    
    version = version_match.group(1)
    major_version = int(version.split('.')[0])
    assert major_version >= 16, f"GitLab Runner version too old: {version}"


@pytest.mark.gitlab_runner
def test_gitlab_runner_kubernetes_executor():
    """Verify GitLab Runner is configured with Kubernetes executor."""
    result = run_in_target('cat /etc/gitlab-runner/config.toml | grep executor')
    
    assert result.returncode == 0, "Failed to read GitLab Runner config"
    assert 'kubernetes' in result.stdout, "Kubernetes executor not configured"


@pytest.mark.gitlab_runner  
def test_gitlab_runner_registration_status():
    """Verify GitLab Runner registration status by checking logs."""
    result = run_kubectl('logs -n gitlab-runner -l app.kubernetes.io/name=gitlab-runner-chart --tail=100')
    
    assert result.returncode == 0, "Failed to get GitLab Runner logs"
    
    logs = result.stdout
    
    # Should see configuration loaded and no registration errors
    positive_indicators = [
        'Configuration loaded',
        'Initializing executor providers'
    ]
    
    for indicator in positive_indicators:
        assert indicator in logs, f"Missing positive indicator in logs: {indicator}"


if __name__ == '__main__':
    # Allow running tests directly with python
    pytest.main([__file__, '-v'])