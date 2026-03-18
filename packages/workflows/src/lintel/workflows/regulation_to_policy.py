"""Regulation-to-Policy workflow.

Converts selected regulations into a set of internal compliance policies,
procedures, assumptions, questions, and action items. The workflow:

1. **gather_context** — Reads the regulation(s), project description (or
   README/CLAUDE.md if empty), and any user-supplied additional context.
2. **analyse_regulation** — Uses an LLM to decompose the regulation into
   control domains, requirements, and risk areas relevant to the project's
   industry (IT, health, finance).
3. **generate_policies** — Produces draft CompliancePolicy + Procedure
   records, making reasonable assumptions where possible (e.g. data retention
   periods, encryption standards) and flagging questions for the user.
4. **approval_gate** — Pauses for human review of the generated artefacts.
5. **finalise** — Persists the approved policies/procedures and produces
   a summary with assumptions, questions, and action items.

The workflow follows real-world regulation-to-policy methodology:
- Gap analysis: compare regulation requirements against project context
- Risk-based prioritisation: focus on high-risk areas first
- Industry-specific defaults: apply sector norms (e.g. HIPAA safe harbour
  for health, PCI-DSS defaults for finance, ISO 27001 Annex A for IT)
- Assumption documentation: every decision the AI makes is recorded
- Human-in-the-loop: questions that cannot be safely assumed are surfaced
"""

from __future__ import annotations

from datetime import UTC
import json
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from langgraph.graph import END, StateGraph
import structlog

from lintel.workflows.nodes._event_helpers import AuditEmitter
from lintel.workflows.state import ThreadWorkflowState

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.agents.runtime import AgentRuntime

logger = structlog.get_logger()


def _get_audit_store(app_state: Any) -> Any:  # noqa: ANN401
    """Get the audit entry store from app_state."""
    if app_state is None:
        return None
    return getattr(app_state, "audit_entry_store", None)


def _get_approval_store(app_state: Any) -> Any:  # noqa: ANN401
    """Get the approval request store from app_state."""
    if app_state is None:
        return None
    return getattr(app_state, "approval_request_store", None)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """\
You are a senior compliance analyst specialising in converting external \
regulations into internal organisational policies. You have deep expertise \
in IT security (ISO 27001, SOC 2, Cyber Essentials, NIST 800-53), \
healthcare/medical (HIPAA, MDR, IEC 62304, ISO 14971, ISO 13485), and \
financial regulations (FCA, PSD2, SOX, DORA, AML, MiFID II, GDPR).

Your task is to analyse the provided regulation(s) in the context of the \
project described below and produce a structured analysis.

## Real-world methodology

When converting regulations to policies in practice, compliance teams:

1. **Map regulation controls to domains** — e.g. ISO 27001:2022 Annex A \
has 93 controls across 4 themes (Organisational, People, Physical, \
Technological). HIPAA has ~54 implementation specifications. PCI-DSS v4.0 \
has 12 requirements with ~250 sub-requirements.

2. **Perform gap analysis** — identify which controls are already addressed \
and which need new policies.

3. **Apply industry defaults** based on Secure Controls Framework (SCF) \
mappings and sector norms:
   - Healthcare: minimum 6-year data retention (HIPAA §164.530(j)), PHI \
encryption at rest and in transit (§164.312(a)(2)(iv)), role-based access \
with minimum necessary principle, audit trails retained 6 years
   - Finance: 7-year record retention (SOX §802, FCA SYSC 9), transaction \
monitoring, strong customer authentication (PSD2 RTS), segregation of \
duties (maker-checker), operational resilience (DORA Art. 11)
   - IT: MFA for all privileged access (NIST 800-63B), annual penetration \
testing, incident response within 72 hours (GDPR Art. 33), quarterly \
access reviews, patch management within 48h for critical vulns

4. **Risk-rate each control** — based on the regulation's own risk framework \
and the project's specific context

5. **Use "must" vs "should" language** — "must" for mandatory regulatory \
requirements, "should" for recommended best practices. This distinction \
matters for audits.

6. **Document assumptions** — every decision that could go either way must \
be captured. Distinguish between "accepted default" and "requires confirmation".

7. **Map single policy to multiple regulations** — e.g. an Access Control \
Policy may satisfy ISO 27001 A.5.15-A.5.18, HIPAA §164.312(a), PCI-DSS \
Req 7-8, and SOX Section 404. One policy, many regulatory sources.

## Cross-framework mapping

You MUST cross-reference each regulation requirement against these major \
compliance frameworks to identify overlapping controls. This prevents \
duplicate policies and ensures comprehensive coverage:

### Secure Controls Framework (SCF) mappings
Use SCF as the normalisation layer. Every control domain should reference \
applicable controls from ALL relevant frameworks, not just the input \
regulation. For example:

- **Access Control** maps to: ISO 27001 A.5.15-A.5.18, A.8.2-A.8.5 | \
SOC 2 CC6.1-CC6.3 | NIST 800-53 AC-1 to AC-25 | HIPAA §164.312(a)(1) | \
PCI-DSS Req 7, Req 8 | GDPR Art. 5(1)(f), Art. 32 | Cyber Essentials \
Access Control | DORA Art. 9(4)(c)
- **Data Protection / Encryption** maps to: ISO 27001 A.8.24 | SOC 2 \
CC6.1, CC6.7 | NIST 800-53 SC-8, SC-13, SC-28 | HIPAA §164.312(a)(2)(iv), \
§164.312(e)(1) | PCI-DSS Req 3, Req 4 | GDPR Art. 32(1)(a) | \
DORA Art. 9(4)(d)
- **Incident Response** maps to: ISO 27001 A.5.24-A.5.28 | SOC 2 CC7.3-CC7.5 | \
NIST 800-53 IR-1 to IR-10 | HIPAA §164.308(a)(6) | PCI-DSS Req 12.10 | \
GDPR Art. 33, Art. 34 | NIS2 Art. 23 | DORA Art. 17
- **Risk Management** maps to: ISO 27001 Clause 6.1, A.5.7 | SOC 2 CC3.1-CC3.4 | \
NIST 800-53 RA-1 to RA-9 | HIPAA §164.308(a)(1)(ii)(A) | ISO 14971 | \
DORA Art. 6 | FCA SYSC 7
- **Audit Logging** maps to: ISO 27001 A.8.15 | SOC 2 CC7.2 | NIST 800-53 \
AU-1 to AU-16 | HIPAA §164.312(b) | PCI-DSS Req 10 | GDPR Art. 5(2) | \
SOX Section 404 | DORA Art. 9(4)(b)
- **Business Continuity** maps to: ISO 27001 A.5.29-A.5.30 | SOC 2 A1.1-A1.3 | \
NIST 800-53 CP-1 to CP-13 | HIPAA §164.308(a)(7) | PCI-DSS Req 12.10.1 | \
DORA Art. 11-Art. 12 | FCA SYSC 15A
- **Vendor / Third Party Risk** maps to: ISO 27001 A.5.19-A.5.23 | SOC 2 \
CC9.2 | NIST 800-53 SA-9, SR-1 to SR-12 | HIPAA §164.308(b)(1) (BAA) | \
PCI-DSS Req 12.8-12.9 | DORA Art. 28-Art. 30 | FCA SYSC 8
- **Change Management** maps to: ISO 27001 A.8.32 | SOC 2 CC8.1 | \
NIST 800-53 CM-1 to CM-14 | PCI-DSS Req 6.5 | DORA Art. 9(4)(e) | \
IEC 62304 §8 (problem resolution / change control)
- **Personnel Security / Training** maps to: ISO 27001 A.6.1-A.6.8 | \
SOC 2 CC1.4 | NIST 800-53 AT-1 to AT-6, PS-1 to PS-9 | HIPAA \
§164.308(a)(5) | PCI-DSS Req 12.6 | GDPR Art. 39(1)(b) | \
DORA Art. 13(6)

### Gap analysis procedure
For EACH control domain identified:
1. List the PRIMARY regulation requirement (from the input regulation)
2. List ALL cross-referenced framework controls that overlap
3. Assess current coverage: "covered", "partial", or "gap" based on \
project context
4. Rate the risk: use the HIGHEST risk rating from any applicable framework
5. Note which cross-referenced controls would be satisfied by a single \
policy (consolidation opportunity)

Output ONLY valid JSON matching this schema:
```json
{
  "regulation_summary": "Brief summary of the regulation and its scope",
  "industry": "it|health|finance|general",
  "applicable_control_count": 0,
  "control_domains": [
    {
      "domain": "Domain name (e.g. Access Control)",
      "regulation_references": ["Specific clause references from input regulation"],
      "cross_framework_references": {
        "iso27001": ["A.5.15", "A.5.16"],
        "soc2": ["CC6.1"],
        "nist_800_53": ["AC-1", "AC-2"],
        "hipaa": [],
        "pci_dss": [],
        "gdpr": ["Art. 32"],
        "dora": [],
        "cyber_essentials": [],
        "iec_62304": [],
        "iso_14971": []
      },
      "requirements": ["Requirement 1", "Requirement 2"],
      "risk_level": "low|medium|high|critical",
      "gap_status": "covered|partial|gap",
      "relevance_note": "Why this domain matters for this project"
    }
  ],
  "recommended_policies": [
    {
      "name": "Policy name",
      "description": "What this policy covers — use 'must' for mandatory, 'should' for recommended",
      "regulation_references": ["Specific clause/section of the regulation"],
      "cross_framework_references": ["ISO 27001 A.5.15", "SOC 2 CC6.1", "NIST AC-2"],
      "risk_level": "low|medium|high|critical",
      "consolidation_note": "Which other framework requirements this single policy satisfies",
      "procedures": [
        {
          "name": "Procedure name",
          "steps": ["Step 1", "Step 2"],
          "owner_role": "Suggested owner role",
          "evidence_artifacts": ["What auditors will ask to see as proof of compliance"]
        }
      ]
    }
  ],
  "framework_coverage_matrix": {
    "iso27001": {"total_applicable": 0, "covered": 0, "partial": 0, "gap": 0},
    "soc2": {"total_applicable": 0, "covered": 0, "partial": 0, "gap": 0},
    "nist_800_53": {"total_applicable": 0, "covered": 0, "partial": 0, "gap": 0},
    "hipaa": {"total_applicable": 0, "covered": 0, "partial": 0, "gap": 0},
    "pci_dss": {"total_applicable": 0, "covered": 0, "partial": 0, "gap": 0},
    "gdpr": {"total_applicable": 0, "covered": 0, "partial": 0, "gap": 0}
  },
  "assumptions": [
    {
      "assumption": "Data retention period set to 7 years",
      "basis": "SOX §802 default for financial records",
      "confidence": "high|medium|low",
      "overridable": true
    }
  ],
  "questions": [
    {
      "question": "Does the project handle payment card data directly?",
      "why_it_matters": "Determines if PCI-DSS scope applies",
      "default_if_no_answer": "Assume no direct card handling"
    }
  ],
  "action_items": [
    {
      "action": "Confirm data classification scheme with security team",
      "priority": "high|medium|low",
      "owner_suggestion": "Security Lead"
    }
  ]
}
```
Do NOT include markdown fencing. Output raw JSON only.\
"""

GENERATE_POLICIES_PROMPT = """\
You are a compliance policy writer. Given the regulation analysis below, \
produce the final set of policies and procedures as JSON.

## Policy writing standards

Each policy MUST be specific and actionable — not vague platitudes:
- Use "must" for mandatory requirements (regulatory), "should" for \
recommended practices (best practice). This distinction is critical for audits.
- Include concrete, measurable requirements with specific values.
- Reference the regulation clause(s) each policy statement satisfies.
- Assign clear ownership and review cadence.
- Design for attestation: every requirement must be testable/auditable.

## Industry-specific defaults (apply where not explicitly specified)

**IT/Information Security (ISO 27001, SOC 2, Cyber Essentials, NIST):**
- Authentication: MFA required for all privileged access; passwords minimum \
12 chars with complexity or passphrase (NIST 800-63B)
- Patch management: critical/zero-day within 48h, high within 7 days, \
medium within 30 days, low within 90 days
- Incident response: detect within 24h, contain within 72h, notify within \
72h for personal data (GDPR Art. 33)
- Access reviews: quarterly for privileged accounts, annual for standard
- Data retention: as per legal minimum or 3 years default; destruction \
within 90 days of expiry
- Penetration testing: annual external, quarterly internal vulnerability scans
- Change management: peer review required for production; rollback plan mandatory
- Backup: daily incremental, weekly full; tested restore quarterly
- Vendor risk: annual due diligence for critical vendors, biennial for others

**Healthcare (HIPAA, MDR, IEC 62304):**
- PHI encryption: AES-256 at rest, TLS 1.2+ in transit (HIPAA §164.312(a)(2)(iv))
- Access control: role-based, minimum necessary principle (§164.502(b))
- Audit trails: all PHI access logged, logs retained 6 years (§164.530(j))
- Business associate agreements: required for ALL third parties with PHI access
- Breach notification: 60 days to individuals (HIPAA), 72 hours to \
supervisory authority (GDPR), immediate internal escalation
- Training: annual HIPAA awareness for all staff, role-specific quarterly \
for PHI handlers
- Data retention: minimum 6 years from creation or last effective date
- Risk analysis: annual formal risk assessment (§164.308(a)(1)(ii)(A))

**Finance (FCA, SOX, PSD2, DORA, AML):**
- Transaction records: 7 years retention (SOX §802, FCA SYSC 9)
- Strong customer authentication: two independent factors minimum (PSD2 RTS)
- Segregation of duties: maker-checker for all financial transactions
- AML screening: real-time for high-risk transactions, batch daily for standard
- Operational resilience: RTO < 2h for critical systems, < 24h for important \
(DORA Art. 11); tested semi-annually
- Third-party risk: annual due diligence, contract clauses for audit rights \
and data protection
- Consumer duty: evidence of good outcomes monitoring, annual fair value \
assessment (FCA Consumer Duty)
- Record keeping: complete audit trail for all client interactions

## Cross-framework consolidation

When writing policies, you MUST consolidate overlapping requirements from \
multiple frameworks into a single policy. Use the cross_framework_references \
from the analysis to:

1. Write ONE Access Control Policy that satisfies ISO 27001 A.5.15-A.5.18, \
SOC 2 CC6.1-CC6.3, NIST AC-2, HIPAA §164.312(a), and PCI-DSS Req 7-8 \
simultaneously — not five separate policies.

2. Include a "satisfies" field listing every framework control the policy \
addresses. Auditors from different frameworks can then trace to the same policy.

3. Each procedure step must specify what evidence it produces. Auditors \
need to verify compliance, so every requirement must be testable. Examples:
   - "Review access lists quarterly → produce signed-off access review log"
   - "Encrypt data at rest using AES-256 → configuration audit report"
   - "Run vulnerability scan monthly → scan report with remediation dates"

4. Include attestation requirements: who signs off, how often, what record \
is kept.

Output JSON matching this schema:
```json
{
  "policies": [
    {
      "name": "Policy name",
      "description": "Full policy description with specific requirements",
      "regulation_ids": ["reg-id-1"],
      "regulation_references": ["ISO 27001 A.5.15", "HIPAA §164.312(a)"],
      "cross_framework_satisfies": ["SOC 2 CC6.1", "NIST AC-2", "PCI-DSS Req 7"],
      "risk_level": "low|medium|high|critical",
      "owner": "Suggested owner role",
      "review_cadence": "annual|quarterly|after_incident",
      "attestation": "Who signs off and how often",
      "tags": ["access-control", "authentication"]
    }
  ],
  "procedures": [
    {
      "name": "Procedure name",
      "description": "What this procedure implements",
      "policy_name": "Parent policy name (must match a policy above)",
      "steps": ["Step 1 (specific, actionable)", "Step 2", "Step 3"],
      "owner": "Suggested owner role",
      "evidence_artifacts": ["What this procedure produces as proof of compliance"],
      "review_cadence": "quarterly|annual|after_incident"
    }
  ],
  "assumptions": [
    {
      "assumption": "Description of what was assumed",
      "basis": "Why this default was chosen",
      "confidence": "high|medium|low"
    }
  ],
  "questions": [
    {
      "question": "What needs to be answered",
      "impact": "What changes if the answer differs from the assumption",
      "priority": "high|medium|low"
    }
  ],
  "action_items": [
    {
      "action": "Specific next step",
      "priority": "high|medium|low",
      "owner_suggestion": "Who should do this"
    }
  ],
  "summary": "Executive summary of what was generated and critical next steps"
}
```
Do NOT include markdown fencing. Output raw JSON only.\
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_configurable(config: RunnableConfig | None) -> dict[str, Any]:
    """Extract configurable dict from LangGraph config."""
    if config is None:
        return {}
    return config.get("configurable", {})


def _get_runtime(config: RunnableConfig | None, state: dict[str, Any]) -> AgentRuntime | None:
    """Get agent runtime from config or registry fallback."""
    configurable = _get_configurable(config)
    runtime = configurable.get("agent_runtime")
    if runtime is None:
        run_id = state.get("run_id", "")
        if run_id:
            from lintel.workflows.nodes._runtime_registry import get_runtime

            runtime = get_runtime(run_id)
    return runtime


def _get_app_state(config: RunnableConfig | None, state: dict[str, Any]) -> Any:  # noqa: ANN401
    """Get the app state for store access."""
    configurable = _get_configurable(config)
    app_state = configurable.get("app_state")
    if app_state is None:
        run_id = state.get("run_id", "")
        if run_id:
            from lintel.workflows.nodes._runtime_registry import get_app_state

            app_state = get_app_state(run_id)
    return app_state


async def _resolve_project_description(
    app_state: Any,  # noqa: ANN401
    project_id: str,
    sandbox_manager: Any = None,  # noqa: ANN401
    sandbox_id: str | None = None,
    workspace_path: str = "",
) -> str:
    """Get project description, falling back to README/CLAUDE.md from the repo.

    Priority:
    1. Project.description field (if non-empty)
    2. CLAUDE.md from the sandbox workspace (if available)
    3. README.md from the sandbox workspace (if available)
    4. Empty string
    """
    # Try project store
    project_store = getattr(app_state, "project_store", None) if app_state else None
    if project_store is not None:
        try:
            project = await project_store.get(project_id)
            if project and project.get("description"):
                return project["description"]
        except Exception:
            logger.debug("resolve_project_description_store_failed", project_id=project_id)

    # Try reading from sandbox
    if sandbox_manager is not None and sandbox_id is not None:
        repo_path = workspace_path or "/workspace/repo"
        for filename in ("CLAUDE.md", "README.md"):
            try:
                result = await sandbox_manager.exec_in_sandbox(
                    sandbox_id,
                    ["cat", f"{repo_path}/{filename}"],
                )
                content = result.get("stdout", "").strip() if isinstance(result, dict) else ""
                if content and len(content) > 20:
                    return f"[From {filename}]\n{content[:3000]}"
            except Exception:
                continue

    return ""


def _parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON from LLM response, handling markdown fencing."""
    cleaned = text.strip()
    # Strip markdown code fences if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def gather_context(
    state: ThreadWorkflowState,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Gather regulation details, project context, and additional user input.

    Reads from:
    - regulation_store: fetches full regulation records
    - project_store: gets project description
    - sandbox: reads README/CLAUDE.md if description is empty
    - state: additional_context, industry_context from the trigger
    """
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config or {})
    await tracker.mark_running("gather_context")

    configurable = _get_configurable(config)
    app_state = _get_app_state(config, state)
    sandbox_manager = configurable.get("sandbox_manager")
    sandbox_id: str | None = state.get("sandbox_id")

    # Extract trigger context from sanitized_messages (set by the trigger endpoint)
    messages = state.get("sanitized_messages", [])
    trigger_context = "\n".join(messages) if messages else ""

    project_id = state.get("project_id", "")

    # Resolve project description with README fallback
    await tracker.append_log("gather_context", "Resolving project description...")
    project_description = await _resolve_project_description(
        app_state,
        project_id,
        sandbox_manager=sandbox_manager,
        sandbox_id=sandbox_id,
        workspace_path=state.get("workspace_path", ""),
    )
    if project_description:
        source = "project description" if not project_description.startswith("[From") else (
            project_description.split("]")[0].replace("[From ", "")
        )
        await tracker.append_log("gather_context", f"Project context from: {source}")
    else:
        await tracker.append_log("gather_context", "No project description found")

    # Fetch regulation details
    regulation_details: list[dict[str, Any]] = []
    regulation_store = getattr(app_state, "regulation_store", None) if app_state else None
    if regulation_store is not None:
        # Parse regulation IDs from trigger context
        try:
            trigger_data = json.loads(trigger_context) if trigger_context else {}
        except json.JSONDecodeError:
            trigger_data = {}
        reg_ids = trigger_data.get("regulation_ids", [])
        for reg_id in reg_ids:
            try:
                reg = await regulation_store.get(reg_id)
                if reg:
                    regulation_details.append(reg)
            except Exception:
                logger.debug("gather_context_reg_fetch_failed", reg_id=reg_id)

    await tracker.append_log(
        "gather_context",
        f"Gathered {len(regulation_details)} regulation(s), "
        f"project description: {len(project_description)} chars",
    )

    # Build the assembled context as research_context for downstream nodes
    context_parts = []
    if regulation_details:
        context_parts.append("## Regulations\n")
        for reg in regulation_details:
            context_parts.append(
                f"### {reg.get('name', 'Unknown')}\n"
                f"- Authority: {reg.get('authority', 'N/A')}\n"
                f"- Description: {reg.get('description', 'N/A')}\n"
                f"- Risk level: {reg.get('risk_level', 'medium')}\n"
                f"- Tags: {', '.join(reg.get('tags', []))}\n"
                f"- ID: {reg.get('regulation_id', '')}\n"
            )

    if project_description:
        context_parts.append(f"## Project Context\n{project_description}\n")

    industry = ""
    additional_context = ""
    if trigger_context:
        try:
            td = json.loads(trigger_context)
            industry = td.get("industry_context", "general")
            additional_context = td.get("additional_context", "")
        except json.JSONDecodeError:
            additional_context = trigger_context

    if industry:
        context_parts.append(f"## Industry: {industry}\n")
    if additional_context:
        context_parts.append(f"## Additional Context\n{additional_context}\n")

    assembled_context = "\n".join(context_parts)

    # Emit audit entry for context gathering
    audit_store = _get_audit_store(app_state)
    await AuditEmitter.emit(
        audit_store,
        actor_id="regulation-to-policy-workflow",
        actor_type="agent",
        action="gather_context_completed",
        resource_type="policy_generation_run",
        resource_id=state.get("run_id", ""),
        details={
            "regulation_count": len(regulation_details),
            "project_id": project_id,
            "industry": industry or "general",
        },
    )

    await tracker.mark_completed(
        "gather_context",
        outputs={
            "regulation_count": len(regulation_details),
            "project_description_chars": len(project_description),
            "industry": industry,
        },
    )

    return {
        "current_phase": "gathering_context",
        "research_context": assembled_context,
        "agent_outputs": [
            {
                "node": "gather_context",
                "summary": f"Gathered context: {len(regulation_details)} regulations, "
                f"industry={industry or 'general'}",
                "regulation_count": len(regulation_details),
                "industry": industry or "general",
            }
        ],
    }


async def analyse_regulation(
    state: ThreadWorkflowState,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Analyse regulation(s) using LLM to identify control domains and requirements."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config or {})
    await tracker.mark_running("analyse_regulation")

    runtime = _get_runtime(config, state)
    context = state.get("research_context", "")

    if not context:
        await tracker.append_log("analyse_regulation", "No context available — cannot analyse")
        await tracker.mark_completed("analyse_regulation", error="No regulation context gathered")
        return {
            "current_phase": "failed",
            "error": "No regulation context to analyse",
            "agent_outputs": [{"node": "analyse_regulation", "verdict": "failed"}],
        }

    # Without runtime, produce a structured placeholder from the context
    if runtime is None:
        logger.warning("analyse_no_runtime", msg="No AgentRuntime — returning raw context")
        await tracker.append_log("analyse_regulation", "No LLM runtime — using raw context")
        await tracker.mark_completed("analyse_regulation", outputs={"mode": "no_llm"})
        return {
            "current_phase": "analysing",
            "agent_outputs": [
                {
                    "node": "analyse_regulation",
                    "summary": "Analysis complete (no LLM — raw context passed through)",
                    "analysis": {},
                }
            ],
        }

    await tracker.append_log("analyse_regulation", "Analysing regulations with LLM...")
    await tracker.log_llm_context("analyse_regulation", "researcher", "analyse_regulation")

    from lintel.agents.types import AgentRole
    from lintel.contracts.types import ThreadRef

    thread_ref_str = state.get("thread_ref", "")
    parts = thread_ref_str.split("/")
    thread_ref = (
        ThreadRef(workspace_id=parts[0], channel_id=parts[1], thread_ts=parts[2])
        if len(parts) == 3
        else ThreadRef(workspace_id="compliance", channel_id="policy-gen", thread_ts=thread_ref_str)
    )

    async def _on_activity(activity: str) -> None:
        if activity:
            await tracker.append_log("analyse_regulation", activity)

    result = await runtime.execute_step(
        thread_ref=thread_ref,
        agent_role=AgentRole.RESEARCHER,
        step_name="analyse_regulation",
        messages=[
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        tools=[],
        max_iterations=1,
        on_activity=_on_activity,
        run_id=state.get("run_id", ""),
    )

    response_text = result.get("content", "")
    usage = StageTracker.extract_token_usage(result)
    analysis = _parse_json_response(response_text)

    if not analysis:
        await tracker.append_log("analyse_regulation", "Failed to parse LLM response as JSON")
        await tracker.mark_completed("analyse_regulation", error="Invalid JSON response from LLM")
        return {
            "current_phase": "failed",
            "error": "Failed to parse regulation analysis",
            "agent_outputs": [
                {"node": "analyse_regulation", "verdict": "failed", "raw": response_text[:500]}
            ],
            "token_usage": [usage],
        }

    domain_count = len(analysis.get("control_domains", []))
    policy_count = len(analysis.get("recommended_policies", []))
    await tracker.append_log(
        "analyse_regulation",
        f"Analysis complete: {domain_count} control domains, {policy_count} recommended policies",
    )
    await tracker.append_log(
        "analyse_regulation",
        f"Tokens: {usage['input_tokens']} in / {usage['output_tokens']} out",
    )
    # Emit audit entry for regulation analysis
    app_state = _get_app_state(config, state)
    coverage = analysis.get("framework_coverage_matrix", {})
    gap_count = sum(v.get("gap", 0) for v in coverage.values() if isinstance(v, dict))
    await AuditEmitter.emit(
        _get_audit_store(app_state),
        actor_id="regulation-to-policy-workflow",
        actor_type="agent",
        action="analyse_regulation_completed",
        resource_type="policy_generation_run",
        resource_id=state.get("run_id", ""),
        details={
            "domain_count": domain_count,
            "policy_count": policy_count,
            "framework_gaps": gap_count,
            "tokens_used": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        },
    )

    await tracker.mark_completed(
        "analyse_regulation",
        outputs={"domain_count": domain_count, "policy_count": policy_count, "token_usage": usage},
    )

    return {
        "current_phase": "analysing",
        "agent_outputs": [
            {
                "node": "analyse_regulation",
                "summary": f"Analysed: {domain_count} domains, {policy_count} policies recommended",
                "analysis": analysis,
            }
        ],
        "token_usage": [usage],
    }


async def generate_policies(
    state: ThreadWorkflowState,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Generate draft policies and procedures from the regulation analysis."""
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config or {})
    await tracker.mark_running("generate_policies")

    runtime = _get_runtime(config, state)

    # Find the analysis from the previous node
    analysis: dict[str, Any] = {}
    for output in reversed(state.get("agent_outputs", [])):
        if isinstance(output, dict) and output.get("node") == "analyse_regulation":
            analysis = output.get("analysis", {})
            break

    context = state.get("research_context", "")

    if not analysis and not context:
        await tracker.mark_completed("generate_policies", error="No analysis available")
        return {
            "current_phase": "failed",
            "error": "No regulation analysis to generate policies from",
            "agent_outputs": [{"node": "generate_policies", "verdict": "failed"}],
        }

    # Build the user message with analysis + original context
    user_content_parts = []
    if analysis:
        analysis_json = json.dumps(analysis, indent=2)
        user_content_parts.append(f"## Regulation Analysis\n```json\n{analysis_json}\n```\n")
    if context:
        user_content_parts.append(f"## Original Context\n{context}\n")
    user_content = "\n".join(user_content_parts)

    if runtime is None:
        logger.warning("generate_no_runtime", msg="No AgentRuntime — returning analysis as-is")
        await tracker.append_log("generate_policies", "No LLM runtime — passing analysis through")
        await tracker.mark_completed("generate_policies", outputs={"mode": "no_llm"})
        return {
            "current_phase": "generating",
            "agent_outputs": [
                {
                    "node": "generate_policies",
                    "summary": "Policies drafted (no LLM — analysis passed through)",
                    "generated": {"policies": [], "procedures": [], "assumptions": [],
                                  "questions": [], "action_items": [], "summary": ""},
                }
            ],
        }

    await tracker.append_log("generate_policies", "Generating policies with LLM...")
    await tracker.log_llm_context("generate_policies", "planner", "generate_policies")

    from lintel.agents.types import AgentRole
    from lintel.contracts.types import ThreadRef

    thread_ref_str = state.get("thread_ref", "")
    parts = thread_ref_str.split("/")
    thread_ref = (
        ThreadRef(workspace_id=parts[0], channel_id=parts[1], thread_ts=parts[2])
        if len(parts) == 3
        else ThreadRef(workspace_id="compliance", channel_id="policy-gen", thread_ts=thread_ref_str)
    )

    async def _on_activity(activity: str) -> None:
        if activity:
            await tracker.append_log("generate_policies", activity)

    result = await runtime.execute_step(
        thread_ref=thread_ref,
        agent_role=AgentRole.PLANNER,
        step_name="generate_policies",
        messages=[
            {"role": "system", "content": GENERATE_POLICIES_PROMPT},
            {"role": "user", "content": user_content},
        ],
        tools=[],
        max_iterations=1,
        on_activity=_on_activity,
        run_id=state.get("run_id", ""),
    )

    response_text = result.get("content", "")
    usage = StageTracker.extract_token_usage(result)
    generated = _parse_json_response(response_text)

    if not generated or not generated.get("policies"):
        await tracker.append_log("generate_policies", "Failed to parse policy generation response")
        await tracker.mark_completed("generate_policies", error="Invalid or empty policy response")
        return {
            "current_phase": "failed",
            "error": "Failed to generate policies",
            "agent_outputs": [
                {"node": "generate_policies", "verdict": "failed", "raw": response_text[:500]}
            ],
            "token_usage": [usage],
        }

    pol_count = len(generated.get("policies", []))
    proc_count = len(generated.get("procedures", []))
    assumption_count = len(generated.get("assumptions", []))
    question_count = len(generated.get("questions", []))

    await tracker.append_log(
        "generate_policies",
        f"Generated {pol_count} policies, {proc_count} procedures, "
        f"{assumption_count} assumptions, {question_count} questions",
    )
    await tracker.append_log(
        "generate_policies",
        f"Tokens: {usage['input_tokens']} in / {usage['output_tokens']} out",
    )
    # Emit audit entry for policy generation
    app_state = _get_app_state(config, state)
    await AuditEmitter.emit(
        _get_audit_store(app_state),
        actor_id="regulation-to-policy-workflow",
        actor_type="agent",
        action="generate_policies_completed",
        resource_type="policy_generation_run",
        resource_id=state.get("run_id", ""),
        details={
            "policy_count": pol_count,
            "procedure_count": proc_count,
            "assumption_count": assumption_count,
            "question_count": question_count,
            "tokens_used": usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        },
    )

    await tracker.mark_completed(
        "generate_policies",
        outputs={
            "policy_count": pol_count,
            "procedure_count": proc_count,
            "token_usage": usage,
        },
    )

    return {
        "current_phase": "generating",
        "agent_outputs": [
            {
                "node": "generate_policies",
                "summary": f"Generated {pol_count} policies, {proc_count} procedures",
                "generated": generated,
            }
        ],
        "token_usage": [usage],
    }


async def finalise_policies(
    state: ThreadWorkflowState,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Persist approved policies/procedures and update the generation run.

    Creates actual CompliancePolicy and Procedure records in their respective
    stores, then updates the PolicyGenerationRun with results.
    """
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config or {})
    await tracker.mark_running("finalise")

    app_state = _get_app_state(config, state)

    # Find the generated data from the previous node
    generated: dict[str, Any] = {}
    for output in reversed(state.get("agent_outputs", [])):
        if isinstance(output, dict) and output.get("node") == "generate_policies":
            generated = output.get("generated", {})
            break

    if not generated:
        await tracker.append_log("finalise", "No generated policies found — skipping persistence")
        await tracker.mark_completed("finalise", outputs={"persisted": False})
        return {
            "current_phase": "completed",
            "agent_outputs": [{"node": "finalise", "summary": "Nothing to persist"}],
        }

    project_id = state.get("project_id", "")
    run_id = state.get("run_id", "")

    # Find regulation IDs from context
    regulation_ids: list[str] = []
    for output in state.get("agent_outputs", []):
        if isinstance(output, dict) and output.get("node") == "gather_context":
            break
    # Also extract from generated policies
    for pol in generated.get("policies", []):
        for rid in pol.get("regulation_ids", []):
            if rid not in regulation_ids:
                regulation_ids.append(rid)

    # Persist CompliancePolicy records
    policy_store = getattr(app_state, "compliance_policy_store", None) if app_state else None
    procedure_store = getattr(app_state, "procedure_store", None) if app_state else None
    generation_store = getattr(app_state, "policy_generation_store", None) if app_state else None

    created_policy_ids: list[str] = []
    created_procedure_ids: list[str] = []
    policy_name_to_id: dict[str, str] = {}

    if policy_store is not None:
        from lintel.domain.types import CompliancePolicy, ComplianceStatus, RiskLevel

        for pol_data in generated.get("policies", []):
            policy_id = f"{run_id}-pol-{uuid4().hex[:8]}"
            risk = pol_data.get("risk_level", "medium")
            try:
                risk_level = RiskLevel(risk)
            except ValueError:
                risk_level = RiskLevel.MEDIUM

            policy = CompliancePolicy(
                policy_id=policy_id,
                project_id=project_id,
                name=pol_data.get("name", "Untitled Policy"),
                description=pol_data.get("description", ""),
                regulation_ids=tuple(pol_data.get("regulation_ids", regulation_ids)),
                owner=pol_data.get("owner", ""),
                status=ComplianceStatus.DRAFT,
                risk_level=risk_level,
                review_date=pol_data.get("review_cadence", ""),
                tags=tuple(pol_data.get("tags", [])),
            )
            try:
                await policy_store.add(policy)
                created_policy_ids.append(policy_id)
                policy_name_to_id[pol_data.get("name", "")] = policy_id
                await tracker.append_log("finalise", f"Created policy: {pol_data.get('name', '')}")
            except Exception:
                logger.warning("finalise_policy_create_failed", policy_id=policy_id, exc_info=True)

    if procedure_store is not None:
        from lintel.domain.types import ComplianceStatus, Procedure

        for proc_data in generated.get("procedures", []):
            proc_id = f"{run_id}-proc-{uuid4().hex[:8]}"
            parent_policy_name = proc_data.get("policy_name", "")
            parent_policy_ids = []
            if parent_policy_name in policy_name_to_id:
                parent_policy_ids.append(policy_name_to_id[parent_policy_name])

            procedure = Procedure(
                procedure_id=proc_id,
                project_id=project_id,
                name=proc_data.get("name", "Untitled Procedure"),
                description=proc_data.get("description", ""),
                policy_ids=tuple(parent_policy_ids),
                steps=tuple(proc_data.get("steps", [])),
                owner=proc_data.get("owner", ""),
                status=ComplianceStatus.DRAFT,
            )
            try:
                await procedure_store.add(procedure)
                created_procedure_ids.append(proc_id)
                proc_name = proc_data.get("name", "")
                await tracker.append_log("finalise", f"Created procedure: {proc_name}")
            except Exception:
                logger.warning("finalise_proc_create_failed", proc_id=proc_id, exc_info=True)

    # Flatten assumptions/questions/action_items for the run record
    assumptions = [
        a.get("assumption", a) if isinstance(a, dict) else str(a)
        for a in generated.get("assumptions", [])
    ]
    questions = [
        q.get("question", q) if isinstance(q, dict) else str(q)
        for q in generated.get("questions", [])
    ]
    action_items = [
        a.get("action", a) if isinstance(a, dict) else str(a)
        for a in generated.get("action_items", [])
    ]
    summary = generated.get("summary", "")

    # Update the PolicyGenerationRun record
    if generation_store is not None and run_id:
        try:
            from datetime import datetime

            await generation_store.update(run_id, {
                "status": "completed",
                "generated_policy_ids": created_policy_ids,
                "generated_procedure_ids": created_procedure_ids,
                "assumptions": assumptions,
                "questions": questions,
                "action_items": action_items,
                "summary": summary,
                "completed_at": datetime.now(tz=UTC).isoformat(),
            })
            await tracker.append_log("finalise", "Updated generation run record")
        except Exception:
            logger.warning("finalise_update_run_failed", run_id=run_id, exc_info=True)

    # Emit audit entries for each persisted policy
    audit_store = _get_audit_store(app_state)
    for policy_id in created_policy_ids:
        await AuditEmitter.emit(
            audit_store,
            actor_id="regulation-to-policy-workflow",
            actor_type="agent",
            action="compliance_policy_created",
            resource_type="compliance_policy",
            resource_id=policy_id,
            details={"run_id": run_id, "project_id": project_id, "status": "draft"},
        )
    for proc_id in created_procedure_ids:
        await AuditEmitter.emit(
            audit_store,
            actor_id="regulation-to-policy-workflow",
            actor_type="agent",
            action="procedure_created",
            resource_type="procedure",
            resource_id=proc_id,
            details={"run_id": run_id, "project_id": project_id, "status": "draft"},
        )

    # Summary audit entry for the whole finalisation
    await AuditEmitter.emit(
        audit_store,
        actor_id="regulation-to-policy-workflow",
        actor_type="agent",
        action="finalise_completed",
        resource_type="policy_generation_run",
        resource_id=run_id,
        details={
            "policy_ids": created_policy_ids,
            "procedure_ids": created_procedure_ids,
            "assumption_count": len(assumptions),
            "question_count": len(questions),
            "action_item_count": len(action_items),
        },
    )

    await tracker.append_log(
        "finalise",
        f"Finalised: {len(created_policy_ids)} policies, "
        f"{len(created_procedure_ids)} procedures persisted",
    )
    await tracker.mark_completed(
        "finalise",
        outputs={
            "policy_ids": created_policy_ids,
            "procedure_ids": created_procedure_ids,
            "assumption_count": len(assumptions),
            "question_count": len(questions),
            "action_item_count": len(action_items),
        },
    )

    return {
        "current_phase": "completed",
        "agent_outputs": [
            {
                "node": "finalise",
                "summary": (
                    f"Persisted {len(created_policy_ids)} policies and "
                    f"{len(created_procedure_ids)} procedures. "
                    f"{len(assumptions)} assumptions, {len(questions)} questions, "
                    f"{len(action_items)} action items for review."
                ),
                "policy_ids": created_policy_ids,
                "procedure_ids": created_procedure_ids,
                "assumptions": assumptions,
                "questions": questions,
                "action_items": action_items,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Conditional edge
# ---------------------------------------------------------------------------


def _check_phase(state: ThreadWorkflowState) -> str:
    """Stop the workflow on error or failure."""
    if state.get("error"):
        return "close"
    phase = state.get("current_phase", "")
    if phase in ("closed", "failed"):
        return "close"
    outputs = state.get("agent_outputs", [])
    for output in reversed(outputs):
        if isinstance(output, dict) and output.get("verdict") == "failed":
            return "close"
    return "continue"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


async def approval_gate_policies(
    state: ThreadWorkflowState,
    config: RunnableConfig = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Create an ApprovalRequest and pause for human review.

    This node creates a PENDING approval request via the existing
    ApprovalRequest API so that a human can review the generated
    policies, assumptions, and questions before they are persisted.
    The workflow executor's interrupt mechanism pauses execution here;
    the approval is resolved via POST /approval-requests/{id}/approve
    or /reject.
    """
    from lintel.workflows.nodes._stage_tracking import StageTracker

    tracker = StageTracker(config or {})
    await tracker.mark_running("approval_gate_policies")

    app_state = _get_app_state(config, state)
    run_id = state.get("run_id", "")

    # Count what's pending review
    pol_count = 0
    question_count = 0
    assumption_count = 0
    for output in reversed(state.get("agent_outputs", [])):
        if isinstance(output, dict) and output.get("node") == "generate_policies":
            generated = output.get("generated", {})
            pol_count = len(generated.get("policies", []))
            question_count = len(generated.get("questions", []))
            assumption_count = len(generated.get("assumptions", []))
            break

    # Create an ApprovalRequest record
    approval_store = _get_approval_store(app_state)
    approval_id = ""
    if approval_store is not None:
        from lintel.domain.types import ApprovalRequest

        approval_id = str(uuid4())
        approval = ApprovalRequest(
            approval_id=approval_id,
            run_id=run_id,
            gate_type="policy_review",
            requested_by="regulation-to-policy-workflow",
        )
        try:
            await approval_store.add(approval)
            await tracker.append_log(
                "approval_gate_policies",
                f"Approval request created: {approval_id}",
            )
        except Exception:
            logger.warning("approval_gate_create_failed", run_id=run_id, exc_info=True)

    # Emit audit entry for approval gate
    await AuditEmitter.emit(
        _get_audit_store(app_state),
        actor_id="regulation-to-policy-workflow",
        actor_type="agent",
        action="approval_requested",
        resource_type="policy_generation_run",
        resource_id=run_id,
        details={
            "approval_id": approval_id,
            "gate_type": "policy_review",
            "policies_pending": pol_count,
            "questions_pending": question_count,
            "assumptions_pending": assumption_count,
        },
    )

    await tracker.append_log(
        "approval_gate_policies",
        f"Awaiting human review: {pol_count} policies, "
        f"{assumption_count} assumptions, {question_count} questions",
    )
    await tracker.mark_completed(
        "approval_gate_policies",
        outputs={"approval_id": approval_id, "status": "pending"},
    )

    return {
        **state,
        "current_phase": "awaiting_approval",
        "pending_approvals": [
            *(state.get("pending_approvals") or []),
            {
                "approval_id": approval_id,
                "gate_type": "policy_review",
                "policies_pending": pol_count,
            },
        ],
    }


def build_regulation_to_policy_graph() -> StateGraph[Any]:
    """Build the regulation-to-policy workflow graph.

    Flow:
        gather_context → analyse_regulation → generate_policies
        → approval_gate → finalise → END

    The approval gate pauses execution so a human can review the
    generated policies, assumptions, and questions before they are
    persisted.
    """
    g: StateGraph[Any] = StateGraph(ThreadWorkflowState)

    g.add_node("gather_context", gather_context)
    g.add_node("analyse_regulation", analyse_regulation)
    g.add_node("generate_policies", generate_policies)
    g.add_node("approval_gate_policies", approval_gate_policies)
    g.add_node("finalise", finalise_policies)
    g.add_node("close", lambda s: {**s, "current_phase": "closed"})

    g.set_entry_point("gather_context")
    g.add_edge("gather_context", "analyse_regulation")
    g.add_conditional_edges(
        "analyse_regulation",
        _check_phase,
        {"continue": "generate_policies", "close": "close"},
    )
    g.add_conditional_edges(
        "generate_policies",
        _check_phase,
        {"continue": "approval_gate_policies", "close": "close"},
    )
    g.add_edge("approval_gate_policies", "finalise")
    g.add_edge("finalise", END)
    g.add_edge("close", END)

    return g
