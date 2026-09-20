import os
import subprocess
import pytest


def run_kubectl(cmd: list) -> subprocess.CompletedProcess:
    """Execute kubectl command."""
    return subprocess.run(cmd, capture_output=True, text=True)


def get_service_info():
    """Get service name and namespace from environment."""
    test_target = os.environ.get('TEST_TARGET', 'jenkins')
    kube_ns = os.environ.get('KUBE_NS', test_target)
    chart_name = f'{test_target}-chart'
    return test_target, kube_ns, chart_name


@pytest.mark.jenkins
@pytest.mark.nexus
@pytest.mark.gitlab
def test_pod_running():
    """Verify the service pod is in Running phase."""
    test_target, kube_ns, chart_name = get_service_info()
    
    result = run_kubectl([
        'kubectl', 'get', 'pods', '-n', kube_ns,
        '-l', f'app.kubernetes.io/name={chart_name}',
        '-o', 'jsonpath={.items[0].status.phase}'
    ])
    
    assert result.returncode == 0, f'Failed to get pod status: {result.stderr}'
    phase = result.stdout.strip()
    assert phase == 'Running', f'Pod phase is {phase}, expected Running'


@pytest.mark.jenkins
@pytest.mark.nexus
@pytest.mark.gitlab
def test_pod_ready():
    """Verify the service pod is ready (all containers ready)."""
    test_target, kube_ns, chart_name = get_service_info()
    
    result = run_kubectl([
        'kubectl', 'get', 'pods', '-n', kube_ns,
        '-l', f'app.kubernetes.io/name={chart_name}',
        '-o', 'jsonpath={.items[0].status.conditions[?(@.type=="Ready")].status}'
    ])
    
    assert result.returncode == 0, f'Failed to get pod ready status: {result.stderr}'
    ready_status = result.stdout.strip()
    assert ready_status == 'True', f'Pod ready status is {ready_status}, expected True'


@pytest.mark.jenkins
@pytest.mark.nexus
@pytest.mark.gitlab
def test_container_ready():
    """Verify the main container in the pod is ready."""
    test_target, kube_ns, chart_name = get_service_info()
    
    result = run_kubectl([
        'kubectl', 'get', 'pods', '-n', kube_ns,
        '-l', f'app.kubernetes.io/name={chart_name}',
        '-o', 'jsonpath={.items[0].status.containerStatuses[0].ready}'
    ])
    
    assert result.returncode == 0, f'Failed to get container ready status: {result.stderr}'
    container_ready = result.stdout.strip()
    assert container_ready == 'true', f'Container ready is {container_ready}, expected true'


@pytest.mark.jenkins
@pytest.mark.nexus
@pytest.mark.gitlab
def test_no_restarts():
    """Verify the service pod has not restarted excessively (< 5 restarts)."""
    test_target, kube_ns, chart_name = get_service_info()
    
    result = run_kubectl([
        'kubectl', 'get', 'pods', '-n', kube_ns,
        '-l', f'app.kubernetes.io/name={chart_name}',
        '-o', 'jsonpath={.items[0].status.containerStatuses[0].restartCount}'
    ])
    
    assert result.returncode == 0, f'Failed to get restart count: {result.stderr}'
    restart_count = int(result.stdout.strip() or '0')
    assert restart_count < 5, f'Pod has restarted {restart_count} times (threshold: 5)'


@pytest.mark.jenkins
@pytest.mark.nexus
@pytest.mark.gitlab
def test_service_exists():
    """Verify the Kubernetes Service resource exists."""
    test_target, kube_ns, chart_name = get_service_info()
    
    result = run_kubectl([
        'kubectl', 'get', 'service', chart_name, '-n', kube_ns,
        '-o', 'jsonpath={.metadata.name}'
    ])
    
    assert result.returncode == 0, f'Service {chart_name} not found: {result.stderr}'
    service_name = result.stdout.strip()
    assert service_name == chart_name, f'Service name is {service_name}, expected {chart_name}'


@pytest.mark.jenkins
@pytest.mark.nexus
@pytest.mark.gitlab
def test_service_has_endpoints():
    """Verify the Service has active endpoints."""
    test_target, kube_ns, chart_name = get_service_info()
    
    result = run_kubectl([
        'kubectl', 'get', 'endpoints', chart_name, '-n', kube_ns,
        '-o', 'jsonpath={.subsets[0].addresses[0].ip}'
    ])
    
    assert result.returncode == 0, f'Failed to get endpoints: {result.stderr}'
    endpoint_ip = result.stdout.strip()
    assert endpoint_ip, f'Service {chart_name} has no active endpoints'
    # Verify it's a valid IP format
    parts = endpoint_ip.split('.')
    assert len(parts) == 4, f'Invalid endpoint IP format: {endpoint_ip}'


@pytest.mark.jenkins
@pytest.mark.nexus
@pytest.mark.gitlab
def test_ingress_exists():
    """Verify the Ingress resource exists."""
    test_target, kube_ns, chart_name = get_service_info()
    
    result = run_kubectl([
        'kubectl', 'get', 'ingress', chart_name, '-n', kube_ns,
        '-o', 'jsonpath={.metadata.name}'
    ])
    
    # Ingress may be optional, so just log if missing
    if result.returncode != 0 or not result.stdout.strip():
        pytest.skip(f'Ingress {chart_name} not found (may be optional): {result.stderr}')
    
    ingress_name = result.stdout.strip()
    assert ingress_name == chart_name, f'Ingress name is {ingress_name}, expected {chart_name}'


@pytest.mark.jenkins
@pytest.mark.nexus
@pytest.mark.gitlab
def test_pvc_bound():
    """Verify all PVCs for the service are bound."""
    test_target, kube_ns, chart_name = get_service_info()
    
    # Get all PVCs starting with the chart name pattern
    result = run_kubectl([
        'kubectl', 'get', 'pvc', '-n', kube_ns,
        '-o', 'jsonpath={.items[?(@.metadata.name=~".*' + test_target + '.*")].status.phase}'
    ])
    
    if result.returncode != 0 or not result.stdout.strip():
        pytest.skip(f'No PVCs found for {test_target} (may use emptyDir)')
    
    phases = result.stdout.strip().split()
    for phase in phases:
        assert phase == 'Bound', f'PVC phase is {phase}, expected Bound'


@pytest.mark.jenkins
@pytest.mark.nexus
@pytest.mark.gitlab
def test_statefulset_ready():
    """Verify StatefulSet has desired replicas ready."""
    test_target, kube_ns, chart_name = get_service_info()
    
    result = run_kubectl([
        'kubectl', 'get', 'statefulset', chart_name, '-n', kube_ns,
        '-o', 'jsonpath={.status.readyReplicas}'
    ])
    
    if result.returncode != 0:
        pytest.skip(f'StatefulSet {chart_name} not found (may use Deployment)')
    
    ready_replicas = result.stdout.strip()
    if not ready_replicas:
        pytest.fail(f'StatefulSet {chart_name} has no ready replicas')
    
    ready_count = int(ready_replicas)
    assert ready_count >= 1, f'StatefulSet has {ready_count} ready replicas, expected at least 1'
