import json
import urllib.request
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"

def trigger_incident(scenario="oom"):
    print("Triggering incident...")
    if scenario == "oom":
        url = "/simulate-oom"
        alert_name = "OOMKilled"
    elif scenario == "corrupt-env":
        url = "/corrupt-env"
        alert_name = "EnvVarMissing"
    elif scenario == "cpu-spike":
        url = "/cpu-spike"
        alert_name = "CPUThrottling"
    elif scenario == "crash-loop":
        url = "/crash-loop"
        alert_name = "CrashLoopBackOff"
    else:
        print(f"Unknown scenario: {scenario}")
        return
    try:
        req = urllib.request.Request(f"{BASE_URL}{url}")
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"App crashed as expected: {type(e).__name__}")
    else:
        print("Warning: App did not crash")
        return

    alert = {
        "alert_name": alert_name,
        "target_service": "web-app",
        "namespace": "default",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": "critical",
    }

    print("\nAlert Payload:")
    print(json.dumps(alert, indent=2))
    return alert

if __name__ == "__main__":
    trigger_incident()
