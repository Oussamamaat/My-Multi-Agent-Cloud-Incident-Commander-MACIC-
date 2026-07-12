from pydantic import BaseModel
from typing import List, Optional, Literal
from datetime import datetime


class AlertPayload(BaseModel):
    alert_name: str
    target_service: str
    namespace: str
    timestamp: str
    severity: Literal["info", "warning", "critical"]


class RemediationPlan(BaseModel):
    file_path: str
    original_content: str
    proposed_content: str
    unified_diff: str
    reasoning: str
    risk_score: Literal["LOW", "MEDIUM", "HIGH"]
    change_type: Literal["resource", "config", "network", "rollback"]


class ExecutionResult(BaseModel):
    applied: bool
    kubectl_output: str
    health_check_passed: bool
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None


class IncidentState(BaseModel):
    alert_payload: dict

    raw_logs: Optional[str] = None
    metrics_snapshot: Optional[str] = None
    root_cause_analysis: Optional[str] = None

    current_manifest: Optional[str] = None
    proposed_diff: Optional[str] = None
    remediation_reasoning: Optional[str] = None
    risk_score: Optional[str] = None

    approval_status: bool = False
    approver_note: Optional[str] = None

    reconciliation_success: Optional[bool] = None
    health_check_result: Optional[str] = None

    post_mortem_report: Optional[str] = None

    execution_log: List[str] = []
    created_at: datetime = datetime.utcnow()
