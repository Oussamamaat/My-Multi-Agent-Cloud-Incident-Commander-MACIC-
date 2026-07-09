import sys
import time
from trigger_incident import trigger_incident
from app.graph import graph
from app.state import IncidentState
import subprocess 



def main():
    process = subprocess.Popen(
        ["kubectl", "port-forward", "deployment/web-app", "-n", "macic-sandbox", "8000:8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(3)
    try:
        alert = trigger_incident()
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
        process.terminate() 
        process.wait()
if __name__ == "__main__":
    main()

  