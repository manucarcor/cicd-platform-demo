import os
import re
import subprocess
import pytest


def run_in_target(cmd: str) -> subprocess.CompletedProcess:
    """Execute command in the target pod via kubectl exec."""
    kube_pod = os.environ.get('KUBE_POD')
    kube_ns = os.environ.get('KUBE_NS', 'nexus')
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
                    if base in line or 'nexus' in line:
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


@pytest.mark.nexus
def test_nexus_ports_listening():
    """Verify Nexus HTTP and Docker registry ports are listening."""
    # Nexus default ports: 8081 (HTTP), 8082 (Docker hosted), 8083 (Docker group)
    ports_env = os.environ.get('nexus_ports') or os.environ.get('NEXUS_PORTS')
    if ports_env:
        ports = [int(p.strip()) for p in ports_env.split(',') if p.strip()]
    else:
        ports = [8081, 8082, 8083]

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


@pytest.mark.nexus
def test_nexus_data_directory_exists():
    """Verify Nexus data directory exists and is mounted."""
    nexus_data = '/nexus-data'
    runner = run_in_target(f'test -d {nexus_data} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'Nexus data directory {nexus_data} not found'


@pytest.mark.nexus
def test_nexus_sonatype_work_directory():
    """Verify Nexus sonatype-work directory exists (legacy but often present)."""
    work_dir = '/nexus-data/sonatype-work'
    runner = run_in_target(f'test -d {work_dir} && echo OK || echo MISSING')
    # This is optional in newer versions, so just log if missing
    if 'MISSING' in runner.stdout:
        pytest.skip(f'Optional sonatype-work directory {work_dir} not found (expected for modern Nexus)')


@pytest.mark.nexus
def test_nexus_db_directory_exists():
    """Verify Nexus database directory exists."""
    db_dir = '/nexus-data/db'
    runner = run_in_target(f'test -d {db_dir} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'Nexus database directory {db_dir} not found'


@pytest.mark.nexus
def test_nexus_blobs_directory_exists():
    """Verify Nexus blobs directory exists (stores repository content)."""
    blobs_dir = '/nexus-data/blobs'
    runner = run_in_target(f'test -d {blobs_dir} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'Nexus blobs directory {blobs_dir} not found'


@pytest.mark.nexus
def test_nexus_etc_directory_exists():
    """Verify Nexus etc directory exists (configuration files)."""
    etc_dir = '/nexus-data/etc'
    runner = run_in_target(f'test -d {etc_dir} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'Nexus etc directory {etc_dir} not found'


@pytest.mark.nexus
def test_nexus_properties_file_exists():
    """Verify nexus.properties file exists."""
    props_file = '/nexus-data/etc/nexus.properties'
    runner = run_in_target(f'test -f {props_file} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'Nexus properties file {props_file} not found'


@pytest.mark.nexus
def test_nexus_process_running():
    """Verify Nexus Java process is running."""
    runner = run_in_target('ps aux | grep -i nexus | grep -i java | grep -v grep || echo MISSING')
    assert 'MISSING' not in runner.stdout, 'Nexus Java process not found'
    assert 'java' in runner.stdout.lower(), 'Nexus process does not appear to be Java'


@pytest.mark.nexus
def test_nexus_log_directory_exists():
    """Verify Nexus log directory exists."""
    log_dir = '/nexus-data/log'
    runner = run_in_target(f'test -d {log_dir} && echo OK || echo MISSING')
    assert 'OK' in runner.stdout, f'Nexus log directory {log_dir} not found'


@pytest.mark.nexus
def test_nexus_log_file_exists():
    """Verify Nexus log file exists and contains entries."""
    log_file = '/nexus-data/log/nexus.log'
    runner = run_in_target(f'test -f {log_file} && wc -l {log_file} || echo MISSING')
    output = runner.stdout.strip()
    assert 'MISSING' not in output, f'Nexus log file {log_file} not found'
    # Verify log file has content (at least 1 line)
    lines_match = re.search(r'(\d+)', output)
    if lines_match:
        line_count = int(lines_match.group(1))
        assert line_count > 0, f'Nexus log file {log_file} is empty'


@pytest.mark.nexus
def test_nexus_tmp_directory_writable():
    """Verify Nexus tmp directory exists and is writable."""
    tmp_dir = '/nexus-data/tmp'
    test_file = f'{tmp_dir}/test-write-{os.getpid()}.txt'
    runner = run_in_target(f'echo test > {test_file} && test -f {test_file} && rm {test_file} && echo OK || echo FAIL')
    assert 'OK' in runner.stdout, f'Nexus tmp directory {tmp_dir} is not writable'
