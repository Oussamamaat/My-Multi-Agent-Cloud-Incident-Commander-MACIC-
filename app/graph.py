import os
import json
from datetime import datetime
from typing import Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from langgraph.graph import StateGraph, START, END
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from app.state import IncidentState

def _log(msg: str) -> str:
    return f"{datetime.utcnow().isoformat()}Z {msg}"
from app.tools import (
    get_container_logs,
    get_prometheus_metrics,
    read_manifest,
    write_proposed_manifest,
    apply_manifest,
    check_service_health,
)

llm = ChatOllama(model="llama3.1:latest", temperature=0)
llm2 = ChatOllama(model="qwen2.5-coder:latest", temperature=0)

investigate_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a read-only infrastructure forensic analyst. You have access to container logs and Prometheus metrics. Your job is to identify the precise technical root cause of an incident. You look for exit codes, OOM events, connection timeouts, and configuration errors. You output a structured root cause analysis with evidence."),
    ("human", "Service: {service}\nLogs:\n{logs}\nMetrics:\n{metrics}\n\nDiagnosis:\nEvidence:\nExit Code:\nConfidence Level:"),
])

devops_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a senior DevOps engineer. You receive a root cause analysis of a production incident and the current Kubernetes manifest. Your job is to produce the minimum viable change to resolve the issue. You do not over-engineer. You explain your reasoning and assess risk. You never modify logic, only configuration."),
    ("human", "Service: {service}\nRoot Cause: {root_cause}\nCurrent Manifest:\n{current_manifest}\n\n"
              "Respond with exactly three sections separated by these markers:\n"
              "---YAML---\n<your proposed manifest YAML>\n"
              "---REASONING---\n<your explanation>\n"
              "---RISK---\n<LOW|MEDIUM|HIGH>"),
])

triage_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a senior SRE incident commander. You receive infrastructure alerts and coordinate a structured incident response. You are methodical, precise, and never take action without verifying facts first. You summarize findings clearly for non-technical stakeholders."),
    ("human", "Alert Payload: {alert_payload}\n\nLog the incident and route to investigation.\n\n"
              "Respond with exactly one section with this marker:\n"
              "---ASSESSMENT---\n<your assessment of the incident and next steps>"),
])

report_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a senior SRE incident commander. You receive the final incident report and produce a post-mortem for stakeholders. You summarize findings clearly for non-technical stakeholders."),
    ("human", "Incident State: {state}\n\n"
              "Produce a structured post-mortem report in markdown with these sections:\n"
              "- Summary\n- Timeline of Events\n- Root Cause\n- Resolution Applied\n- Verification Result\n- Recommended Follow-up Actions"),
])

def triage_node(state: IncidentState) -> Dict[str, Any]:
    print("---[Triage Node]---")
    chain = triage_prompt | llm
    try:
        response = chain.invoke({"alert_payload": str(state.alert_payload)})
        assessment = response.content
    except Exception as e:
        assessment = f"(fallback) Alert received: {state.alert_payload.get('alert_name')}"
    print(assessment)
    msg = _log(f"[Triage] {assessment}")
    return {"execution_log": state.execution_log + [msg]}

def investigate_node(state: IncidentState) -> Dict[str, Any]:
    print("---[Investigate Node]---")
    service_name = state.alert_payload.get("target_service", "unknown")
    logs = get_container_logs(service_name)
    metrics = get_prometheus_metrics("up")
    chain = investigate_prompt | llm
    try:
        response = chain.invoke({"service": service_name, "logs": logs, "metrics": metrics})
        root_cause = response.content
    except Exception as e:
        root_cause = f"(fallback) OOM suspected for {service_name}. LLM unavailable: {e}"
    msg = _log(f"[Investigate] Fetched logs and metrics for {service_name}.")
    return {
        "raw_logs": logs,
        "metrics_snapshot": metrics,
        "root_cause_analysis": root_cause,
        "execution_log": state.execution_log + [msg],
    }

def _parse_devops_response(text: str, manifest: str) -> dict:
    parts = {"yaml": manifest, "reasoning": "Failed to parse LLM response.", "risk": "LOW"}
    try:
        if "---YAML---" in text and "---REASONING---" in text and "---RISK---" in text:
            after_yaml = text.split("---YAML---", 1)[1]
            parts["yaml"] = after_yaml.split("---REASONING---", 1)[0].strip()
            after_reason = after_yaml.split("---REASONING---", 1)[1]
            parts["reasoning"] = after_reason.split("---RISK---", 1)[0].strip()
            parts["risk"] = after_reason.split("---RISK---", 1)[1].strip().split("\n")[0].strip()
            if parts["risk"] not in ("LOW", "MEDIUM", "HIGH"):
                parts["risk"] = "LOW"
        else:
            import re
            yaml_blocks = re.findall(r"```(?:yaml)?\s*([\s\S]*?)```", text)
            if not yaml_blocks:
                yaml_blocks = re.findall(r"^---\s*\n([\s\S]*?)\n---", text, re.MULTILINE)
            if yaml_blocks:
                parts["yaml"] = yaml_blocks[0].strip()
            for label in ["REASONING", "---REASONING---"]:
                if label in text:
                    after = text.split(label, 1)[1]
                    for rlabel in ["RISK", "---RISK---"]:
                        if rlabel in after:
                            parts["reasoning"] = after.split(rlabel, 1)[0].strip()
                            break
                    else:
                        parts["reasoning"] = after.strip()
                    break
            for label in ["RISK", "---RISK---"]:
                if label in text:
                    after = text.split(label, 1)[1]
                    candidate = after.strip().split("\n")[0].strip().rstrip(":")
                    if candidate in ("LOW", "MEDIUM", "HIGH"):
                        parts["risk"] = candidate
                    break
    except Exception:
        parts["reasoning"] = "Parse error extracting LLM response sections."
    return parts

def devops_node(state: IncidentState) -> Dict[str, Any]:
    print("---[DevOps Node]---")
    service_name = state.alert_payload.get("target_service", "unknown")
    manifest = read_manifest("manifests/deployment.yaml")
    chain = devops_prompt | llm2
    try:
        response = chain.invoke({
            "service": service_name,
            "root_cause": state.root_cause_analysis,
            "current_manifest": manifest })
        parsed = _parse_devops_response(response.content, manifest)
    except Exception as e:
        print(f"[DevOps] LLM failed: {e}. Using fallback.")
        parsed = {"yaml": manifest, "reasoning": f"LLM call failed: {e}", "risk": "LOW"}
    diff = write_proposed_manifest("deployment.yaml", parsed["yaml"])
    msg = _log(f"[DevOps] Generated proposed manifest diff for {service_name}.")
    return {
        "current_manifest": manifest,
        "proposed_diff": diff,
        "remediation_reasoning": parsed["reasoning"],
        "risk_score": parsed["risk"],
        "execution_log": state.execution_log + [msg],
    }

def hitl_gate_node(state: IncidentState) -> Dict[str, Any]:
    console = Console()
    table = Table(show_header=False, box=None)
    table.add_column("Label", style="bold")
    table.add_column("Value")
    table.add_row("Incident", f"{state.alert_payload.get('alert_name')} — {state.alert_payload.get('target_service')}")
    table.add_row("Timestamp", state.alert_payload.get("timestamp", "unknown"))
    table.add_row("Root Cause", state.root_cause_analysis or "(pending)")
    table.add_row("Proposed Change", state.proposed_diff or "(no diff)")
    table.add_row("Risk Score", state.risk_score or "UNKNOWN")
    table.add_row("Reasoning", state.remediation_reasoning or "(none)")
    panel = Panel(table, title="CRITICAL INCIDENT AUDIT GATE", border_style="red")
    console.print(panel)
    choice = Prompt.ask("Approve execution?", choices=["y", "n"], default="n")
    approved = choice == "y"
    msg = _log(f"[HITL] {'Approved' if approved else 'Rejected'} by human.")
    console.print(f"\nDecision: {'APPROVED' if approved else 'REJECTED'}", style="green" if approved else "red")
    return {
        "approval_status": approved,
        "approver_note": msg,
        "execution_log": state.execution_log + [msg],
    }

def reconcile_node(state: IncidentState) -> Dict[str, Any]:
    print("---[Reconcile Node]---")
    apply_output = apply_manifest("manifests/deployment.yaml")
    ok, ms = check_service_health("http://localhost:8000/health")
    logs = [_log(f"[Reconcile] Manifest applied. Output: {apply_output.strip()}")]
    logs.append(_log(f"[Reconcile] Health check {'passed' if ok else 'failed'} ({ms:.0f}ms)."))
    msg = _log(f"[Reconcile] Health check {'passed' if ok else 'failed'} ({ms:.0f}ms).")
    return {
        "reconciliation_success": ok,
        "health_check_result": f"{'OK' if ok else 'FAIL'} — {ms:.0f}ms",
        "execution_log": state.execution_log + logs,
    }

def report_node(state: IncidentState) -> Dict[str, Any]:
    print("---[Report Node]---")
    chain = report_prompt | llm
    try:
        response = chain.invoke({"state": str(state.model_dump())})
        report = response.content
    except Exception as e:
        report = f"(fallback) Post-mortem could not be generated. LLM error: {e}"
    print(report)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    os.makedirs("reports", exist_ok=True)
    filepath = f"reports/postmortem_{timestamp}.md"
    with open(filepath, "w") as f:
        f.write(report)
    print(f"\n[Report] Saved to {filepath}")
    msg = _log(f"[Report] Post-mortem generated and saved to {filepath}.")
    return {
        "post_mortem_report": report,
        "execution_log": state.execution_log + [msg],
    }

def abort_node(state: IncidentState) -> Dict[str, Any]:
    print("---[Abort Node]---")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    os.makedirs("reports", exist_ok=True)
    partial = {
        "alert": dict(state.alert_payload),
        "root_cause": state.root_cause_analysis,
        "proposed_diff": state.proposed_diff,
        "remediation_reasoning": state.remediation_reasoning,
        "risk_score": state.risk_score,
        "escalated_at": timestamp,
    }
    filepath = f"reports/escalated_{timestamp}.json"
    with open(filepath, "w") as f:
        json.dump(partial, f, indent=2)
    msg = _log(f"[Abort] Incident escalated to on-call engineer. Partial state saved to {filepath}.")
    print(msg)
    return {"execution_log": state.execution_log + [msg]}

def route_after_hitl(state: IncidentState) -> str:
    return "reconcile" if state.approval_status else "abort"

builder = StateGraph(IncidentState)
builder.add_node("triage", triage_node)
builder.add_node("investigate", investigate_node)
builder.add_node("devops", devops_node)
builder.add_node("hitl_gate", hitl_gate_node)
builder.add_node("reconcile", reconcile_node)
builder.add_node("report", report_node)
builder.add_node("abort", abort_node)

builder.add_edge(START, "triage")
builder.add_edge("triage", "investigate")
builder.add_edge("investigate", "devops")
builder.add_edge("devops", "hitl_gate")
builder.add_conditional_edges("hitl_gate", route_after_hitl, {"reconcile": "reconcile", "abort": "abort"})
builder.add_edge("reconcile", "report")
builder.add_edge("report", END)
builder.add_edge("abort", END)

graph = builder.compile()
