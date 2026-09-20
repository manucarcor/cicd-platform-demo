import os
import re
import subprocess
import pytest


def run_in_target(cmd: str) -> subprocess.CompletedProcess:
    """Execute command in the target pod via kubectl exec."""
    kube_pod = os.environ.get('KUBE_POD')
    kube_ns = os.environ.get('KUBE_NS', 'jenkins')
    test_container = os.environ.get('TEST_CONTAINER')

    if kube_pod:
        # If the supplied pod doesn't exist, try to find a current pod in the namespace
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
                    if base in line or 'jenkins' in line:
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


@pytest.mark.jenkins
def test_jenkins_ports_listening():
    """Verify Jenkins HTTP and agent ports are listening."""
    # Jenkins default ports: 8080 (HTTP), 50000 (agent)
    ports_env = os.environ.get('jenkins_ports') or os.environ.get('JENKINS_PORTS')
    if ports_env:
        ports = [int(p.strip()) for p in ports_env.split(',') if p.strip()]
    else:
        ports = [8080, 50000]

    # Try ss, fallback to netstat
    runner = run_in_target('ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null || true')
    out = (runner.stdout or '') + (runner.stderr or '')
    # Fallback to /proc for minimal images
    if not out:
        proc = run_in_target('cat /proc/net/tcp 2>/dev/null || true')
        out = (proc.stdout or '') + (proc.stderr or '')

    assert out, 'Could not get listening ports output from target'

    for p in ports:
        if f':{p} ' in out or f':{p}\n' in out or f':{p}\r' in out or f':{p}:' in out:
            continue
        if f'*:{p} ' in out or f'*:{p}\n' in out or f'0.0.0.0:{p}' in out:
            continue
        # Accept hex port format from /proc/net/tcp
        hex_up = format(p, '04X')
        hex_lo = format(p, '04x')
        if f':{hex_up}' in out or f':{hex_lo}' in out:
            continue
        pytest.fail(f'Port {p} is not listening on target')


@pytest.mark.jenkins
def test_jenkins_home_directory_exists():
    """Verify JENKINS_HOME directory exists and is mounted."""
    jenkins_home = '/var/jenkins_home'
    runner = run_in_target(f'test -d {jenkins_home} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'Jenkins home directory {jenkins_home} not found'


@pytest.mark.jenkins
def test_jenkins_config_xml_exists():
    """Verify Jenkins config.xml exists (indicates initialization completed)."""
    config_path = '/var/jenkins_home/config.xml'
    runner = run_in_target(f'test -f {config_path} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'Jenkins config.xml not found at {config_path}'


@pytest.mark.jenkins
def test_jenkins_version_file_exists():
    """Verify Jenkins version file exists and is readable."""
    version_path = '/var/jenkins_home/jenkins.install.InstallUtil.lastExecVersion'
    runner = run_in_target(f'test -f {version_path} && cat {version_path} || echo MISSING')
    output = runner.stdout.strip()
    assert 'MISSING' not in output, f'Jenkins version file not found at {version_path}'
    # Verify version format (e.g., 2.426.1)
    assert re.match(r'\d+\.\d+', output), f'Invalid Jenkins version format: {output}'


@pytest.mark.jenkins
def test_jenkins_plugins_directory_exists():
    """Verify Jenkins plugins directory exists."""
    plugins_dir = '/var/jenkins_home/plugins'
    runner = run_in_target(f'test -d {plugins_dir} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'Jenkins plugins directory {plugins_dir} not found'


@pytest.mark.jenkins
def test_jenkins_jobs_directory_exists():
    """Verify Jenkins jobs directory exists."""
    jobs_dir = '/var/jenkins_home/jobs'
    runner = run_in_target(f'test -d {jobs_dir} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'Jenkins jobs directory {jobs_dir} not found'


@pytest.mark.jenkins
def test_jenkins_process_running():
    """Verify Jenkins Java process is running."""
    runner = run_in_target('ps aux | grep -i jenkins | grep -i java | grep -v grep || echo MISSING')
    assert 'MISSING' not in runner.stdout, 'Jenkins Java process not found'
    assert 'java' in runner.stdout.lower(), 'Jenkins process does not appear to be Java'


@pytest.mark.jenkins
def test_jenkins_init_groovy_directory():
    """Verify Jenkins init.groovy.d directory exists for initialization scripts."""
    init_dir = '/var/jenkins_home/init.groovy.d'
    runner = run_in_target(f'test -d {init_dir} && echo OK || echo MISSING')
    # Note: This is optional, so we just log a warning if missing
    if 'MISSING' in runner.stdout:
        pytest.skip(f'Optional init.groovy.d directory {init_dir} not found (expected for default setup)')
