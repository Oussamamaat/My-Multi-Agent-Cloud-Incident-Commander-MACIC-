# Product Requirements Document
# Multi-Agent Cloud Incident Commander (MACIC)
**Version:** 1.0  
**Author:** [Your Name]  
**Status:** Draft  
**Goal:** Portfolio-grade + Deep Learning  
**Runtime Target:** Local (Ollama + Docker/minikube) → Cloud (AWS/GCP)

---

## Table of Contents
1. [Project Summary](#1-project-summary)
2. [Learning Objectives](#2-learning-objectives)
3. [The Golden Rule — AI vs. Non-AI Boundaries](#3-the-golden-rule--ai-vs-non-ai-boundaries)
4. [System Architecture](#4-system-architecture)
5. [Tech Stack & Rationale](#5-tech-stack--rationale)
6. [Ollama Model Strategy](#6-ollama-model-strategy)
7. [Functional Requirements by Phase](#7-functional-requirements-by-phase)
8. [Data Models](#8-data-models)
9. [Agent & Tool Specifications](#9-agent--tool-specifications)
10. [Human-in-the-Loop Design](#10-human-in-the-loop-design)
11. [Failure Scenarios to Simulate](#11-failure-scenarios-to-simulate)
12. [Non-Functional Requirements](#12-non-functional-requirements)
13. [Cloud Migration Path](#13-cloud-migration-path)
14. [Portfolio Positioning](#14-portfolio-positioning)
15. [Out of Scope](#15-out-of-scope)
16. [Risk Register](#16-risk-register)

---

## 1. Project Summary

MACIC is a local-first, multi-agent automation system that mimics an autonomous Site Reliability Engineer (SRE). When a production container crashes or misbehaves, MACIC:

1. Catches the alert automatically
2. Investigates logs and metrics via specialized agents
3. Proposes a surgical infrastructure fix (e.g., a `deployment.yaml` patch)
4. **Stops and asks a human to approve** before touching anything
5. Applies the fix and verifies recovery

The system is built on a finite state graph using LangGraph, powered by locally running open-source LLMs via Ollama, and runs against a real (simulated) Kubernetes-like environment on your laptop using Docker Compose + minikube.

---

## 2. Learning Objectives

This section is the most important one for you as a student. Every phase is mapped to a concrete skill you will gain.

| Phase | What You Build | What You Actually Learn |
|---|---|---|
| Phase 1 | Vulnerable FastAPI app + Docker Compose | Docker networking, container health, volume mounts, app instrumentation |
| Phase 1 | Local Prometheus scraping | Observability fundamentals: metrics, scrape intervals, PromQL basics |
| Phase 2 | LangGraph state graph | How stateful agent orchestration actually works (not just "calling an LLM") |
| Phase 2 | Pydantic state model | Type safety in Python, data contracts between services |
| Phase 2 | Tool functions (kubectl, log reader) | Subprocess safety, sandboxing side effects, typed APIs over raw shell |
| Phase 3 | HITL CLI gate | Deterministic safety boundaries — a critical production engineering concept |
| Phase 3 | End-to-end loop | How to wire distributed components: alert → diagnosis → patch → verify |
| Phase 3 | Post-mortem report generation | Using LLMs for summarization/reporting (appropriate AI use) |
| Phase 4 | minikube deployment | Real K8s: pods, namespaces, deployments, resource limits, kubectl workflows |
| Phase 4 | Cloud deployment (EKS/GKE) | Cloud-native infra: managed clusters, IAM, load balancers, kubeconfig |

### Skills You Will Be Able To Claim After This Project
- Python async orchestration with LangGraph
- K8s resource management and manifest engineering
- Container observability with Prometheus
- Multi-agent system design with clear tool boundaries
- Production safety patterns (HITL, sandboxed execution, typed state)
- Local LLM integration with Ollama

---

## 3. The Golden Rule — AI vs. Non-AI Boundaries

This is the most common mistake students make with AI projects: **using LLMs for things that must be deterministic**. Here is the exact boundary for MACIC.

### ✅ WHERE TO USE AI (LLM Agents)

These tasks involve **interpretation, synthesis, and reasoning** — things only a language model can do well:

| Task | Agent | Why AI is the right tool |
|---|---|---|
| Parse raw logs and identify anomaly patterns (OOM, timeout, exit codes) | Investigator | Logs are unstructured text; pattern matching rules can't cover every case |
| Map a root cause summary to a specific config file parameter | DevOps Agent | Requires understanding the *meaning* of a YAML field, not just its presence |
| Write the remediation diff/patch (e.g., bump memory from 128Mi to 512Mi) | DevOps Agent | Code generation from a natural language diagnosis |
| Write the Post-Mortem Incident Report in human-readable prose | Triage Agent | Summarization and structured prose generation |
| Explain the risk level of a proposed change in plain English | Triage Agent | Contextual reasoning for the human reviewer |

### ❌ WHERE NOT TO USE AI (Keep It Deterministic Code)

These tasks require **100% predictability** — an LLM should never be in the execution path:

| Task | What To Use Instead | Why AI is dangerous here |
|---|---|---|
| State machine transitions in LangGraph | Explicit Python `if/else` conditions | LLM routing is non-deterministic; you need guaranteed flow control |
| Executing `kubectl apply` or shell commands | Python `subprocess` with strict argument lists | An LLM generating a shell command to execute is a major security risk |
| The HITL approval gate | `input()` / Slack interactive button | An AI must **never** approve its own changes |
| Fetching logs from the container | Python `subprocess` / K8s Python SDK | Deterministic data collection; no interpretation needed yet |
| Syntax/schema validation of the generated manifest | `yamllint` / `kubectl --dry-run` | You need a guarantee, not a guess |
| Health checks after remediation | Direct HTTP probe or `kubectl rollout status` | Binary pass/fail — AI adds zero value here |
| Routing/classifying the incoming alert type | Simple regex or schema matching on the payload | Prevent LLM hallucinating an alert category |

> **The mental model:** Use AI to *think*, use code to *act*. The LLM is the brain; Python is the hands.

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              LOCAL SANDBOX (Docker Compose / minikube)       │
│                                                             │
│   ┌─────────────────┐        ┌──────────────────────────┐  │
│   │  FastAPI App    │        │  Prometheus               │  │
│   │  (Vulnerable)   │───────►│  (Metrics Scraper)       │  │
│   │  /simulate-oom  │        │  localhost:9090           │  │
│   │  /corrupt-env   │        └──────────────────────────┘  │
│   └────────┬────────┘                                       │
│            │ crashes → writes logs                          │
└────────────┼───────────────────────────────────────────────-┘
             │ Alert Payload (HTTP POST or log tail trigger)
             ▼
┌─────────────────────────────────────────────────────────────┐
│                MACIC ORCHESTRATION LAYER                     │
│              (LangGraph State Graph + Ollama)                │
│                                                             │
│  IncidentState (Pydantic) flows through the graph           │
│                                                             │
│  ┌───────────────┐   ┌────────────────┐  ┌──────────────┐  │
│  │ Triage Agent  │──►│ Investigator   │─►│ DevOps Agent │  │
│  │ (Commander)   │   │ Agent          │  │ (Fixer)      │  │
│  │               │◄──│ [READ-ONLY     │  │ [READ/WRITE  │  │
│  │  Ollama LLM   │   │  tools only]   │  │  sandbox]    │  │
│  └───────────────┘   └────────────────┘  └──────┬───────┘  │
│                                                  │          │
│                         Proposed Patch / Diff    │          │
└──────────────────────────────────────────────────┼──────────┘
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────┐
│             HUMAN-IN-THE-LOOP GATE (HITL)                   │
│                                                             │
│  Phase 1: Rich CLI terminal prompt with colored diff        │
│  Phase 2 (extension): Slack interactive message + button    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  [CRITICAL INCIDENT AUDIT GATE]                     │   │
│  │  Root Cause: OOMKilled — web-app exceeded 128Mi     │   │
│  │  Proposed Fix: memory limit → 512Mi                 │   │
│  │  Risk Score: LOW (resource-only change, no logic)   │   │
│  │  Approve? (y/n): _                                  │   │
│  └─────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────┘
                                │ y
                                ▼
┌─────────────────────────────────────────────────────────────┐
│            AUTOMATED RECONCILIATION LAYER                   │
│  1. Apply patch (kubectl apply / hot-reload)                │
│  2. Wait for rollout  (kubectl rollout status)              │
│  3. Health check probe (HTTP GET /health → 200 OK)          │
│  4. Log result to IncidentState.execution_log               │
│  5. Generate & print Post-Mortem Report (LLM)               │
└─────────────────────────────────────────────────────────────┘
```

### Agent Interaction Model

- Agents share a **single Pydantic state object** passed through the LangGraph graph
- Each agent only modifies its **own fields** in the state (strict write domains)
- No agent can call another agent directly — all communication goes through the shared state
- Tool calls are **pure Python functions**, not agent-to-agent messages

---

## 5. Tech Stack & Rationale

| Layer | Technology | Why This Choice (Learning Value) |
|---|---|---|
| **Orchestration** | LangGraph (Python) | Industry-standard for multi-agent state graphs; teaches cyclic execution and checkpointing |
| **LLM Runtime** | Ollama (local) | Zero cost, no API key management, teaches model serving; swap to cloud LLM later |
| **LLM Models** | See Section 6 | Different models for different agents based on task type |
| **App Framework** | FastAPI | Modern async Python; teaches HTTP, background tasks, health endpoints |
| **Container Runtime** | Docker + Docker Compose | Universal foundation; teaches networking, volumes, environment variables |
| **Orchestration (later)** | minikube → EKS/GKE | Progressive K8s complexity: local first, real cluster second |
| **Observability** | Prometheus + python-prometheus-client | Industry standard; teaches metrics types (counter, gauge, histogram) |
| **State Validation** | Pydantic v2 | Type safety, serialization, teaches data contracts between distributed components |
| **CLI Output** | Rich (Python library) | Beautiful terminal output; makes the HITL gate professional and demo-ready |
| **K8s SDK** | kubernetes-python-client | Official SDK; avoids raw subprocess kubectl calls, teaches API-first tooling |
| **Config/IaC** | Kubernetes YAML manifests | Foundational before jumping to Terraform; teaches resource primitives directly |

### Libraries You Will Install
```bash
pip install langgraph langchain-ollama pydantic fastapi uvicorn \
            prometheus-client kubernetes rich python-dotenv pyyaml
```

---

## 6. Ollama Model Strategy

Since you're using Ollama, model selection matters a lot — different agents have different needs.

### Recommended Setup

```bash
# Pull these models locally
ollama pull llama3.1:8b          # General reasoning (Triage Agent)
ollama pull deepseek-coder:6.7b  # Code/YAML analysis (DevOps Agent)
```

### Model Assignment Per Agent

| Agent | Recommended Model | Why |
|---|---|---|
| Triage Agent (Commander) | `llama3.1:8b` | Needs strong reasoning and natural language; will write the post-mortem |
| Investigator Agent | `llama3.1:8b` | Log interpretation requires contextual understanding, not code generation |
| DevOps Agent | `deepseek-coder:6.7b` | Specialised in code/config; better at reading YAML and producing valid diffs |

### Hardware Reality Check

| Your Setup | What Works |
|---|---|
| 8GB RAM laptop | `llama3.1:8b` will be slow (~30-60s per response) — still usable for development |
| 16GB RAM | Comfortable for `llama3.1:8b`, can experiment with `llama3.1:13b` |
| GPU (any VRAM) | Massive speed boost; set `OLLAMA_GPU_LAYERS=99` |
| 8GB RAM struggling | Fall back to `llama3.2:3b` — smaller but still functional |

> **Tip:** During development, add streaming output to your agent calls so you can see the model "thinking" in real time — it makes debugging much easier and also looks impressive in demos.

---

## 7. Functional Requirements by Phase

### Phase 1 — Local Sandbox & Telemetry (Estimated: 1–2 days)

#### FR-1.1: Vulnerable Application
- FastAPI app with at minimum two chaotic routes:
  - `GET /simulate-oom` — triggers memory exhaustion using a growing list allocation loop
  - `GET /corrupt-env` — unsets a critical environment variable and causes a config validation crash
- App must expose `GET /health` returning `{"status": "ok"}` when healthy
- App must emit structured logs (JSON format) to stdout
- Prometheus metrics endpoint at `GET /metrics`

#### FR-1.2: Docker Compose Environment
- Service: `web-app` (your FastAPI app)
- Service: `prometheus` (scraping `web-app:8000/metrics`)
- Shared Docker network with DNS resolution between services
- Resource limits declared on `web-app` to make OOM crashes real:
  ```yaml
  deploy:
    resources:
      limits:
        memory: 128m
  ```
- Volume mount for your K8s manifests directory (used by DevOps agent later)

#### FR-1.3: Alert Trigger Mechanism
- A Python script `trigger_incident.py` that:
  1. Calls `GET /simulate-oom` on the app
  2. Waits for the crash
  3. Builds an alert payload dict and hands it to the MACIC entrypoint
- Alert payload schema:
  ```python
  {
    "alert_name": "OOMKilled",
    "target_service": "web-app",
    "namespace": "default",
    "timestamp": "2025-01-15T14:32:00Z",
    "severity": "critical"
  }
  ```

---

### Phase 2 — Agent System & Tool Engineering (Estimated: 3–5 days)

#### FR-2.1: Shared Incident State (Pydantic)
```python
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
```

#### FR-2.2: Tool Specifications

**Tool 1 — get_container_logs**
```
Input:  service_name: str, tail_lines: int = 100
Output: str (raw log text)
Method: subprocess ["docker", "logs", "--tail", str(tail_lines), service_name]
        OR kubernetes_client.CoreV1Api().read_namespaced_pod_log(...)
Side effects: NONE (read-only)
```

**Tool 2 — get_prometheus_metrics**
```
Input:  query: str (PromQL), endpoint: str = "http://localhost:9090"
Output: str (formatted JSON metrics snapshot)
Method: HTTP GET to Prometheus API /api/v1/query
Side effects: NONE (read-only)
```

**Tool 3 — read_manifest**
```
Input:  file_path: str
Output: str (raw YAML content)
Validation: Path must be inside allowed sandbox directory only
Side effects: NONE (read-only)
```

**Tool 4 — write_proposed_manifest**
```
Input:  file_path: str, new_content: str
Output: str (unified diff between old and new content)
Method: Write to a TEMP file path, never overwrite original
        Generate diff using Python `difflib.unified_diff`
Side effects: Writes to /tmp/proposed_*.yaml only, never to live manifests
```

**Tool 5 — validate_manifest_syntax**
```
Input:  file_path: str
Output: bool, error_message: Optional[str]
Method: subprocess ["kubectl", "apply", "--dry-run=client", "-f", file_path]
Side effects: NONE (dry-run only, touches no cluster state)
```

**Tool 6 — apply_manifest (POST-APPROVAL ONLY)**
```
Input:  file_path: str
Output: str (kubectl output)
Method: subprocess ["kubectl", "apply", "-f", file_path]
Guardrail: This tool is ONLY callable from the Reconciliation node,
           which only executes after approval_status == True
Side effects: MODIFIES CLUSTER STATE — must never be reachable without HITL
```

**Tool 7 — check_service_health**
```
Input:  service_url: str, retries: int = 5, delay_seconds: int = 3
Output: bool, response_time_ms: float
Method: HTTP GET with retry loop using httpx
Side effects: NONE
```

#### FR-2.3: LangGraph State Graph

```
[START]
   │
   ▼
[triage_node]        ← Receives alert, logs start of incident, routes to investigator
   │
   ▼
[investigate_node]   ← Calls get_container_logs + get_prometheus_metrics, runs LLM analysis
   │
   ▼
[devops_node]        ← Reads manifest, calls LLM to generate patch, calls write_proposed_manifest
   │
   ▼
[hitl_gate_node]     ← DETERMINISTIC: displays diff, blocks on human input, sets approval_status
   │
   ├── approval_status == False → [abort_node] → [END]
   │
   └── approval_status == True
          │
          ▼
      [reconcile_node]  ← Applies manifest, waits for rollout, runs health check
          │
          ▼
      [report_node]     ← LLM generates post-mortem, prints to terminal
          │
          ▼
        [END]
```

---

### Phase 3 — End-to-End Loop & HITL Gate (Estimated: 2–3 days)

#### FR-3.1: HITL CLI Gate (Rich Terminal)
The gate node must display the following using the `rich` Python library:

```
╔══════════════════════════════════════════════════════════════╗
║           🚨 CRITICAL INCIDENT AUDIT GATE 🚨                ║
╠══════════════════════════════════════════════════════════════╣
║  Incident:    OOMKilled — container web-app                  ║
║  Timestamp:   2025-01-15 14:32:00 UTC                       ║
║  Root Cause:  Container exceeded memory limit (128Mi).       ║
║               Process was killed by OOM killer (exit 137).   ║
╠══════════════════════════════════════════════════════════════╣
║  PROPOSED CHANGE:                                            ║
║  --- deployment.yaml (current)                               ║
║  +++ deployment.yaml (proposed)                              ║
║  @@ -15 @@                                                   ║
║  -  memory: "128Mi"                                          ║
║  +  memory: "512Mi"                                          ║
╠══════════════════════════════════════════════════════════════╣
║  Risk Score:  LOW (resource-only change, no logic modified)  ║
║  Reasoning:   [Agent's explanation of the fix]              ║
╚══════════════════════════════════════════════════════════════╝
  Approve execution? (y/n): 
```

#### FR-3.2: Post-Mortem Report (LLM Generated)
After successful reconciliation, the Triage Agent generates a structured report:
```markdown
# Incident Post-Mortem — [timestamp]
## Summary
## Timeline of Events
## Root Cause
## Resolution Applied
## Verification Result
## Recommended Follow-up Actions
```
This report is printed to the terminal AND saved to `./reports/postmortem_[timestamp].md`.

#### FR-3.3: Abort Path
If the human enters `n` at the HITL gate:
- Set `approval_status = False` in state
- Log "Incident flagged for manual investigation" to `execution_log`
- Print a clean "Incident escalated to on-call engineer" message
- Save partial state (with root cause and proposed diff) to `./reports/escalated_[timestamp].json`
- Exit cleanly

---

### Phase 4 — minikube & Cloud Migration (Estimated: 3–5 days)

#### FR-4.1: minikube Local Cluster
- Port Docker Compose environment to proper K8s manifests:
  - `deployment.yaml` for web-app with resource limits
  - `service.yaml` (ClusterIP)
  - `configmap.yaml` for environment variables
  - `namespace.yaml` (use `macic-sandbox` namespace, not `default`)
- All tool functions switch from Docker SDK to `kubernetes-python-client`
- `trigger_incident.py` uses `kubectl port-forward` to expose the service locally

#### FR-4.2: Cloud Deployment (EKS or GKE)
- Provision a single-node managed cluster (cheapest tier)
- Push Docker image of vulnerable app to ECR (AWS) or GCR (GCP)
- Deploy MACIC orchestrator as a local process pointing to cloud kubeconfig
- Document teardown steps clearly (to avoid surprise cloud bills)

---

## 8. Data Models

### Alert Payload Schema (inbound)
```python
class AlertPayload(BaseModel):
    alert_name: str
    target_service: str
    namespace: str
    timestamp: str
    severity: Literal["info", "warning", "critical"]
```

### Remediation Plan (DevOps Agent output)
```python
class RemediationPlan(BaseModel):
    file_path: str
    original_content: str
    proposed_content: str
    unified_diff: str
    reasoning: str
    risk_score: Literal["LOW", "MEDIUM", "HIGH"]
    change_type: Literal["resource", "config", "network", "rollback"]
```

### Execution Result (Reconciliation output)
```python
class ExecutionResult(BaseModel):
    applied: bool
    kubectl_output: str
    health_check_passed: bool
    response_time_ms: Optional[float]
    error_message: Optional[str]
```

---

## 9. Agent & Tool Specifications

### Agent 1: Triage Agent (Commander)

- **LangGraph node name:** `triage_node`
- **Model:** `llama3.1:8b`
- **Writes to state:** `execution_log`, `post_mortem_report`
- **Read access:** Full state (supervisor role)
- **System prompt design:**
  > You are a senior SRE incident commander. You receive infrastructure alerts and coordinate a structured incident response. You are methodical, precise, and never take action without verifying facts first. You summarize findings clearly for non-technical stakeholders.
- **Does NOT call:** Any write tools. Never writes to cluster or filesystem.

### Agent 2: Investigator Agent

- **LangGraph node name:** `investigate_node`
- **Model:** `llama3.1:8b`
- **Tools available:** `get_container_logs`, `get_prometheus_metrics`
- **Writes to state:** `raw_logs`, `metrics_snapshot`, `root_cause_analysis`
- **System prompt design:**
  > You are a read-only infrastructure forensic analyst. You have access to container logs and Prometheus metrics. Your job is to identify the precise technical root cause of an incident. You look for exit codes, OOM events, connection timeouts, and configuration errors. You output a structured root cause analysis with evidence.
- **Output format:** Root cause as structured text with: Diagnosis, Evidence (log lines), Exit Code if applicable, Confidence Level

### Agent 3: DevOps Agent (Infra Fixer)

- **LangGraph node name:** `devops_node`
- **Model:** `deepseek-coder:6.7b`
- **Tools available:** `read_manifest`, `write_proposed_manifest`, `validate_manifest_syntax`
- **Writes to state:** `current_manifest`, `proposed_diff`, `remediation_reasoning`, `risk_score`
- **System prompt design:**
  > You are a senior DevOps engineer. You receive a root cause analysis of a production incident and the current Kubernetes manifest. Your job is to produce the minimum viable change to resolve the issue. You do not over-engineer. You explain your reasoning and assess risk. You never modify logic, only configuration.
- **Guardrail:** Cannot call `apply_manifest`. That tool is physically unavailable to this agent.

---

## 10. Human-in-the-Loop Design

### HITL Gate — Non-Negotiable Rules

1. The HITL node is a **pure Python function** — no LLM involved
2. Execution **fully pauses** until a human provides input
3. The gate validates input strictly: only `y` / `yes` triggers approval; anything else aborts
4. The gate cannot be bypassed programmatically (no `auto_approve` flag in production mode)
5. The gate logs the human's decision + timestamp to `execution_log`

### Phase 2 Extension: Slack Integration (Optional)
When you're ready to extend to Slack:
- Use **Slack Block Kit** to send an interactive message with Approve/Reject buttons
- Use **Slack Socket Mode** (no public URL needed for local testing)
- The gate becomes a webhook listener that blocks until it receives a callback
- Required Slack scopes: `chat:write`, `commands`, `interactive_components`

---

## 11. Failure Scenarios to Simulate

Start with Scenario 1, get the full loop working, then add the others progressively.

| # | Scenario | Route | Expected Root Cause | Expected Fix |
|---|---|---|---|---|
| 1 | Out-of-Memory Kill | `GET /simulate-oom` | Exit code 137, OOMKilled | Increase `resources.limits.memory` |
| 2 | Missing Env Variable | `GET /corrupt-env` | `KeyError` on `DATABASE_URL` | Add missing key to ConfigMap |
| 3 | CPU Throttling | `GET /cpu-spike` | Excessive CPU throttle events | Increase `resources.limits.cpu` |
| 4 | Crash Loop | `GET /crash-loop` | CrashLoopBackOff, exit 1 on startup | Fix init logic / env binding |

Each scenario must produce different log patterns so the Investigator agent has genuinely varied inputs to analyze.

---

## 12. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Agent response time (Ollama local) | < 90 seconds per agent call on 16GB RAM |
| State graph must be deterministic | Same input always produces same execution path (only LLM outputs vary) |
| No credentials in code | All secrets (API keys, kubeconfig path) via `.env` file, never hardcoded |
| Sandboxed file writes | Proposed manifests written to `/tmp/macic_proposed/` only, never live paths |
| Idempotent reconciliation | Running `kubectl apply` twice must produce the same result |
| Structured logging | All `execution_log` entries include timestamp + agent name + action |
| Graceful error handling | If any agent fails (LLM timeout, tool error), the graph catches it and escalates to HITL |

---

## 13. Cloud Migration Path

When you're ready to move from local to cloud, follow this sequence to avoid chaos:

```
Step 1: Get minikube working locally with K8s manifests
        (validates your manifests are correct before touching cloud)

Step 2: Create a free-tier or minimal cloud cluster
        AWS:  eksctl create cluster --name macic-demo --nodes 1 --node-type t3.small
        GCP:  gcloud container clusters create macic-demo --num-nodes=1 --machine-type=e2-small

Step 3: Push your Docker image to a registry
        AWS:  ECR (Elastic Container Registry)
        GCP:  GCR (Google Container Registry) or Artifact Registry

Step 4: Update your kubeconfig to point to the cloud cluster
        aws eks update-kubeconfig --name macic-demo --region us-east-1
        gcloud container clusters get-credentials macic-demo

Step 5: Run MACIC orchestrator locally, pointing to cloud cluster
        (you don't need to deploy MACIC itself to the cloud yet)

Step 6 (later): Deploy MACIC as a cloud workload with proper IAM roles
```

> **Cost warning:** Always run `kubectl delete cluster` or use spot/preemptible instances. A single-node cluster costs ~$0.10/hour. Set a calendar reminder to tear it down after demos.

---

## 14. Portfolio Positioning

### What Makes This Different From Generic AI Projects

Most student AI projects are wrappers: call an API, display the output. MACIC demonstrates:

1. **Stateful orchestration** — you understand LangGraph's graph model, not just `chain.invoke()`
2. **Tool isolation** — read-only vs. read-write agents with explicit boundaries
3. **Production safety culture** — HITL gates, sandboxed writes, dry-run validation
4. **Infrastructure knowledge** — you're reading real K8s YAML, running real kubectl commands
5. **Observability** — Prometheus metrics, not just print statements

### Resume Impact Statement
> *"Designed and built MACIC, an event-driven multi-agent platform automation system using LangGraph and locally-served open-source LLMs (Ollama/Llama3). Engineered three specialized tool-bounded agents that autonomously diagnose K8s container failures, generate infrastructure patches, and escalate changes through a deterministic Human-in-the-Loop safety gate — eliminating unsafe autonomous execution."*

### What To Prepare For Interviews
- Be ready to explain **why you chose LangGraph** over a simple script (state persistence, cycle support, explicit graph topology)
- Be ready to explain **why AI is NOT in the execution path** — this shows engineering maturity
- Bring a **2-minute demo video** (record the full loop: crash → analysis → diff → approval → recovery)
- Push everything to GitHub with a clean `README.md` that includes the architecture diagram

---

## 15. Out of Scope (For Now)

These are good future extensions but should not be attempted during the initial build:

- Multi-cluster incident routing
- Automated rollback (revert to previous deployment version without human) — intentionally excluded for safety
- Production traffic replay
- AI-generated Terraform plans (too complex; start with K8s YAML only)
- Real Prometheus alertmanager webhook integration (start with manual trigger script)
- Fine-tuning a custom model on incident logs

---

## 16. Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Ollama model too slow for development iteration | High | Medium | Use smaller model (3b) for fast testing; use 8b only for final demos |
| K8s manifest generated by LLM is invalid | Medium | Low | `validate_manifest_syntax` tool catches this before HITL gate |
| Docker OOM crash kills the MACIC orchestrator too | Low | High | Run MACIC orchestrator outside of Docker (on host); only the vulnerable app is containerised |
| Cloud cluster costs accumulate | Medium | Medium | Use minikube for 95% of development; cloud only for final demo |
| LangGraph graph gets into infinite loop | Medium | Low | Add a `max_iterations` counter to `IncidentState`; abort if exceeded |
| Agent "hallucinates" a risky diff | Medium | Low | HITL gate catches this — human reviews every proposed change |

---

*PRD Version 1.0 — Build MACIC phase by phase. Do not skip the HITL gate.*
