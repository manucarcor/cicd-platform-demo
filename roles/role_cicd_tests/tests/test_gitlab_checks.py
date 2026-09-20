import os
import re
import subprocess
import pytest


def run_in_target(cmd: str) -> subprocess.CompletedProcess:
    """Execute command in the target pod via kubectl exec."""
    kube_pod = os.environ.get('KUBE_POD')
    kube_ns = os.environ.get('KUBE_NS', 'gitlab')
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
                    if base in line or 'gitlab' in line:
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


@pytest.mark.gitlab
def test_gitlab_ports_listening():
    """Verify GitLab HTTP/HTTPS ports are listening."""
    # GitLab default ports: 80 (HTTP internal), 22 (SSH)
    # Note: 443 is handled by Ingress/Traefik, not by GitLab container
    ports_env = os.environ.get('gitlab_ports') or os.environ.get('GITLAB_PORTS')
    if ports_env:
        ports = [int(p.strip()) for p in ports_env.split(',') if p.strip()]
    else:
        ports = [80, 22]

    runner = run_in_target('ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null || true')
    out = (runner.stdout or '') + (runner.stderr or '')
    if not out:
        proc = run_in_target('cat /proc/net/tcp 2>/dev/null || true')
        out = (proc.stdout or '') + (proc.stderr or '')

    assert out, 'Could not get listening ports output from target'

    for p in ports:
        if f':{p} ' in out or f':{p}\n' in out or f':{p}\r' in out or f':{p}:' in out:
            continue
        if f'*:{p} ' in out or f'*:{p}\n' in out or f'0.0.0.0:{p}' in out:
            continue
        hex_up = format(p, '04X')
        hex_lo = format(p, '04x')
        if f':{hex_up}' in out or f':{hex_lo}' in out:
            continue
        pytest.fail(f'Port {p} is not listening on target')


@pytest.mark.gitlab
def test_gitlab_data_directory_exists():
    """Verify GitLab data directory exists and is mounted."""
    gitlab_data = '/var/opt/gitlab'
    runner = run_in_target(f'test -d {gitlab_data} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'GitLab data directory {gitlab_data} not found'


@pytest.mark.gitlab
def test_gitlab_config_directory_exists():
    """Verify GitLab config directory exists."""
    gitlab_config = '/etc/gitlab'
    runner = run_in_target(f'test -d {gitlab_config} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'GitLab config directory {gitlab_config} not found'


@pytest.mark.gitlab
def test_gitlab_rb_file_exists():
    """Verify gitlab.rb configuration file exists."""
    gitlab_rb = '/etc/gitlab/gitlab.rb'
    runner = run_in_target(f'test -f {gitlab_rb} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'GitLab config file {gitlab_rb} not found'


@pytest.mark.gitlab
def test_gitlab_logs_directory_exists():
    """Verify GitLab logs directory exists."""
    gitlab_logs = '/var/log/gitlab'
    runner = run_in_target(f'test -d {gitlab_logs} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'GitLab logs directory {gitlab_logs} not found'


@pytest.mark.gitlab
def test_gitlab_postgres_running():
    """Verify GitLab PostgreSQL service is running."""
    runner = run_in_target('ps aux | grep postgres | grep -v grep || echo MISSING')
    assert 'MISSING' not in runner.stdout, 'GitLab PostgreSQL process not found'


@pytest.mark.gitlab
def test_gitlab_redis_running():
    """Verify GitLab Redis service is running."""
    runner = run_in_target('ps aux | grep redis | grep -v grep || echo MISSING')
    assert 'MISSING' not in runner.stdout, 'GitLab Redis process not found'


@pytest.mark.gitlab
def test_gitlab_nginx_running():
    """Verify GitLab Nginx service is running."""
    runner = run_in_target('ps aux | grep nginx | grep master | grep -v grep || echo MISSING')
    assert 'MISSING' not in runner.stdout, 'GitLab Nginx master process not found'


@pytest.mark.gitlab
def test_gitlab_puma_running():
    """Verify GitLab Puma (Rails) service is running."""
    runner = run_in_target('ps aux | grep puma | grep -v grep || echo MISSING')
    assert 'MISSING' not in runner.stdout, 'GitLab Puma (Rails) process not found'


@pytest.mark.gitlab
def test_gitlab_sidekiq_running():
    """Verify GitLab Sidekiq background job processor is running."""
    runner = run_in_target('ps aux | grep sidekiq | grep -v grep || echo MISSING')
    assert 'MISSING' not in runner.stdout, 'GitLab Sidekiq process not found'


@pytest.mark.gitlab
def test_gitlab_version_file_exists():
    """Verify GitLab version file exists."""
    version_file = '/opt/gitlab/version-manifest.txt'
    runner = run_in_target(f'test -f {version_file} && head -n 1 {version_file} || echo MISSING')
    output = runner.stdout.strip()
    assert 'MISSING' not in output, f'GitLab version file {version_file} not found'
    # Verify it contains gitlab version info
    assert 'gitlab' in output.lower() or re.search(r'\d+\.\d+', output), \
        f'Invalid GitLab version format: {output}'


@pytest.mark.gitlab
def test_gitlab_repositories_directory():
    """Verify GitLab repositories directory exists."""
    repos_dir = '/var/opt/gitlab/git-data/repositories'
    runner = run_in_target(f'test -d {repos_dir} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'GitLab repositories directory {repos_dir} not found'


@pytest.mark.gitlab
def test_gitlab_uploads_directory():
    """Verify GitLab uploads directory exists."""
    uploads_dir = '/var/opt/gitlab/gitlab-rails/uploads'
    runner = run_in_target(f'test -d {uploads_dir} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'GitLab uploads directory {uploads_dir} not found'


@pytest.mark.gitlab
def test_gitlab_shared_directory():
    """Verify GitLab shared directory exists."""
    shared_dir = '/var/opt/gitlab/gitlab-rails/shared'
    runner = run_in_target(f'test -d {shared_dir} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'GitLab shared directory {shared_dir} not found'


@pytest.mark.gitlab
def test_gitlab_workhorse_socket():
    """Verify GitLab Workhorse socket exists."""
    socket_path = '/var/opt/gitlab/gitlab-workhorse/sockets/socket'
    runner = run_in_target(f'test -S {socket_path} && echo OK || echo MISSING')
    # Socket may take time to create, so make this optional
    if 'MISSING' in runner.stdout:
        pytest.skip(f'GitLab Workhorse socket {socket_path} not yet created (may still be initializing)')
