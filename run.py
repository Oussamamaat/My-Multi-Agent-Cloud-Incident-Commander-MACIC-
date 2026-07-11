import sys
import time
from trigger_incident import trigger_incident
from app.graph import graph
from app.state import IncidentState
import subprocess 



def main():
    scenario = sys.argv[1] if len(sys.argv) > 1 else "oom"
    processes = []
    try:
        for resource, port in [("deployment/web-app", "8000:8000"), ("deployment/prometheus", "9090:9090")]:
            p = subprocess.Popen(
                ["kubectl", "port-forward", resource, "-n", "macic-sandbox", port],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            processes.append(p)
        time.sleep(3)
        alert = trigger_incident(scenario)
        if not alert:
            print("No alert generated. Exiting.")
            sys.exit(1)

        state = IncidentState(alert_payload=alert)
        final_state = graph.invoke(state)

        print("\n=== FINAL STATE ===")
        for entry in final_state["execution_log"]:
            print(f"  {entry}")
        print(f"\nApproved: {final_state.get('approval_status', 'N/A')}")
        print(f"Reconciled: {final_state.get('reconciliation_success', 'N/A (aborted)')}")
        print(f"\nPost-mortem:\n{final_state.get('post_mortem_report', 'N/A (no report)')}")
    finally:
        for p in processes:
            p.terminate()
            p.wait(timeout=5)
if __name__ == "__main__":
    main()

  