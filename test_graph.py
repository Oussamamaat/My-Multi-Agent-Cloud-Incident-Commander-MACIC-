from app.graph import graph
from app.state import IncidentState

state = IncidentState(alert_payload={
    "alert_name": "OOMKilled",
    "target_service": "web-app",
    "namespace": "default",
    "timestamp": "2026-06-26T00:00:00Z",
    "severity": "critical",
})

# Pre-approve so HITL doesn't block in this test
state.approval_status = True
state.execution_log.append("[HITL] Pre-approved for test.")

result = graph.invoke(state)
print("--- Final State ---")
for entry in result["execution_log"]:
    print(f"  {entry}")
print(f"\nApproved: {result['approval_status']}")
print(f"Reconciled: {result['reconciliation_success']}")
print(f"Post-mortem (first 200 chars):")
print(result["post_mortem_report"][:200])
