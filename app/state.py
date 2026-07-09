from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class IncidentState(BaseModel):
    # Input
    alert_payload: dict

    # Investigator writes these
    raw_logs: Optional[str] = None
    metrics_snapshot: Optional[str] = None
    root_cause_analysis: Optional[str] = None

    # DevOps Agent writes these
    current_manifest: Optional[str] = None
    proposed_diff: Optional[str] = None
    remediation_reasoning: Optional[str] = None
    risk_score: Optional[str] = None   # "LOW" | "MEDIUM" | "HIGH"

    # HITL Gate writes this
    approval_status: bool = False
    approver_note: Optional[str] = None

    # Reconciliation writes these
    reconciliation_success: Optional[bool] = None
    health_check_result: Optional[str] = None

    # Triage Agent writes the final report
    post_mortem_report: Optional[str] = None

    # System
    execution_log: List[str] = []
    created_at: datetime = datetime.utcnow()