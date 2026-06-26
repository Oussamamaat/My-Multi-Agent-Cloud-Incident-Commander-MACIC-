import json
import urllib.request
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"

def trigger_incident():
    print("Triggering incident...")

    try:
        req = urllib.request.Request(f"{BASE_URL}/simulate-oom")
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"App crashed as expected: {type(e).__name__}")
    else:
        print("Warning: App did not crash")
        return

    alert = {
        "alert_name": "OOMKilled",
        "target_service": "web-app",
        "namespace": "default",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "severity": "critical",
    }

    print("\nAlert Payload:")
    print(json.dumps(alert, indent=2))

if __name__ == "__main__":
    trigger_incident()
