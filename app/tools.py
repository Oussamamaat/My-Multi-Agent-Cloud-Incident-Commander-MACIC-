import subprocess
import urllib.request
import urllib.parse
import json
import os
import difflib
import time
from typing import Optional
from kubernetes import client, config

ALLOWED_MANIFEST_DIR = os.path.abspath("manifests")
TMP_PROPOSAL_DIR = "/tmp/macic_proposed"
MACIC_NAMESPACE = "macic-sandbox"

def _get_k8s_core_api():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api()

def get_container_logs(service_name: str, tail_lines: int = 100) -> str:
    v1 = _get_k8s_core_api()
    pods = v1.list_namespaced_pod(
        namespace=MACIC_NAMESPACE,
        label_selector=f"app={service_name}"
    )
    if not pods.items:
        return f"Error: No pods found for service {service_name} in {MACIC_NAMESPACE}"
    pod_name = pods.items[0].metadata.name
    logs = v1.read_namespaced_pod_log(
        name=pod_name,
        namespace=MACIC_NAMESPACE,
        tail_lines=tail_lines
    )
    return logs

def get_prometheus_metrics(query: str, endpoint: str = "http://localhost:9090") -> str:
    url = f"{endpoint}/api/v1/query?query={urllib.parse.quote(query)}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.dumps(json.loads(resp.read()), indent=2)

def read_manifest(file_path: str) -> str:
    abs_path = os.path.abspath(file_path)
    if not abs_path.startswith(ALLOWED_MANIFEST_DIR):
        raise PermissionError(f"Access denied: {file_path} is outside {ALLOWED_MANIFEST_DIR}")
    with open(abs_path) as f:
        return f.read()

def write_proposed_manifest(file_path: str, new_content: str) -> str:
    os.makedirs(TMP_PROPOSAL_DIR, exist_ok=True)
    tmp_path = os.path.join(TMP_PROPOSAL_DIR, os.path.basename(file_path))

    original = ""
    full_path = os.path.join(ALLOWED_MANIFEST_DIR, file_path)
    if os.path.exists(full_path):
        with open(full_path) as f:
            original = f.read()

    with open(tmp_path, "w") as f:
        f.write(new_content)

    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=file_path + " (current)",
        tofile=file_path + " (proposed)",
    ))
    return diff or "(no changes)"

def validate_manifest_syntax(file_path: str) -> tuple[bool, Optional[str]]:
    if not os.path.exists(file_path):
        return False, "File not found"
    result = subprocess.run(
        ["kubectl", "apply", "--dry-run=client", "-f", file_path],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode == 0:
        return True, None
    return False, result.stderr.strip()

def apply_manifest(file_path: str) -> str:
    result = subprocess.run(
        ["kubectl", "apply", "-f", file_path],
        capture_output=True, text=True, timeout=30
    )
    return result.stdout or result.stderr

def check_service_health(service_url: str, retries: int = 5, delay_seconds: int = 3) -> tuple[bool, float]:
    for attempt in range(retries):
        start = time.time()
        try:
            with urllib.request.urlopen(service_url, timeout=5) as resp:
                return resp.status == 200, (time.time() - start) * 1000
        except Exception:
            if attempt < retries - 1:
                time.sleep(delay_seconds)
    return False, 0.0
