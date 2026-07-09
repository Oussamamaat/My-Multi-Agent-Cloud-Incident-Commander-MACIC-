import sys
from trigger_incident import trigger_incident
from app.graph import graph
from app.state import IncidentState

def main():
    alert = trigger_incident()
    if not alert:
        print("No alert generated. Exiting.")
        sys.exit(1)

    state = IncidentState(alert_payload=alert)
    final_state = graph.invoke(state)

    print("\n=== FINAL STATE ===")
    for entry in final_state["execution_log"]:
        print(f"  {entry}")
    print(f"\nApproved: {final_state['approval_status']}")
    print(f"Reconciled: {final_state['reconciliation_success']}")
    print(f"\nPost-mortem:\n{final_state['post_mortem_report']}")

if __name__ == "__main__":
    main()
