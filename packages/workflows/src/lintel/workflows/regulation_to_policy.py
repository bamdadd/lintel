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

from typing import Any

from langgraph.graph import END, StateGraph

from lintel.workflows.state import ThreadWorkflowState

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """\
You are a senior compliance analyst specialising in converting external \
regulations into internal organisational policies. You have deep expertise \
in IT security (ISO 27001, SOC 2, Cyber Essentials), healthcare/medical \
(HIPAA, MDR, IEC 62304, ISO 14971), and financial regulations (FCA, PSD2, \
SOX, DORA, AML, MiFID II, GDPR).

Your task is to analyse the provided regulation(s) in the context of the \
project described below and produce a structured analysis.

## Real-world methodology

When converting regulations to policies in practice, compliance teams:

1. **Map regulation controls to domains** — e.g. ISO 27001 Annex A maps to
   access control, cryptography, operations security, etc.
2. **Perform gap analysis** — identify which controls are already addressed
   and which need new policies.
3. **Apply industry defaults** — e.g.:
   - Healthcare: minimum 6-year data retention (HIPAA), PHI encryption at
     rest and in transit, role-based access with audit trails
   - Finance: 7-year record retention (SOX/FCA), transaction monitoring,
     strong customer authentication (PSD2), segregation of duties
   - IT: 90-day password rotation or MFA, annual penetration testing,
     incident response within 72 hours (GDPR), quarterly access reviews
4. **Risk-rate each control** — based on the regulation's own risk framework
   and the project's specific context
5. **Document assumptions** — every decision that could go either way

Output ONLY valid JSON matching this schema:
```json
{
  "regulation_summary": "Brief summary of the regulation and its scope",
  "industry": "it|health|finance|general",
  "control_domains": [
    {
      "domain": "Domain name (e.g. Access Control)",
      "requirements": ["Requirement 1", "Requirement 2"],
      "risk_level": "low|medium|high|critical",
      "relevance_note": "Why this domain matters for this project"
    }
  ],
  "recommended_policies": [
    {
      "name": "Policy name",
      "description": "What this policy covers and enforces",
      "regulation_reference": "Specific clause/section of the regulation",
      "risk_level": "low|medium|high|critical",
      "procedures": [
        {
          "name": "Procedure name",
          "steps": ["Step 1", "Step 2"],
          "owner_role": "Suggested owner role"
        }
      ]
    }
  ],
  "assumptions": [
    "Assumption 1 (e.g. Data retention period set to 7 years per SOX defaults)",
    "Assumption 2"
  ],
  "questions": [
    "Question 1 (e.g. Does the project handle payment card data directly?)",
    "Question 2"
  ],
  "action_items": [
    "Action 1 (e.g. Confirm data classification scheme with security team)",
    "Action 2"
  ]
}
```
Do NOT include markdown fencing. Output raw JSON only.\
"""

GENERATE_POLICIES_PROMPT = """\
You are a compliance policy writer. Given the analysis below, produce the \
final set of policies and procedures as JSON.

Each policy must be specific and actionable — not vague platitudes. Include:
- Concrete requirements (e.g. "All PII must be encrypted at rest using AES-256")
- Measurable criteria (e.g. "Access reviews must be completed quarterly")
- Clear ownership (e.g. "Security team", "Engineering lead", "DPO")
- Review cadence (e.g. "Annual review", "After each incident")

For each industry, apply standard defaults where the user hasn't specified:

**IT/Information Security:**
- Password policy: minimum 12 chars or MFA required
- Patch management: critical patches within 48 hours
- Incident response: detect within 24h, contain within 72h
- Access reviews: quarterly for privileged, annual for standard
- Data retention: as per legal minimum or 3 years default
- Penetration testing: annual external, quarterly internal scans
- Change management: peer review required for production changes

**Healthcare:**
- PHI encryption: AES-256 at rest, TLS 1.2+ in transit
- Access control: role-based, minimum necessary principle
- Audit trails: 6-year retention
- Business associate agreements: required for all third parties
- Breach notification: within 60 days (HIPAA) or 72 hours (GDPR)
- Training: annual HIPAA awareness, role-specific quarterly
- Data retention: minimum 6 years from last activity

**Finance:**
- Transaction records: 7-year retention
- Strong customer authentication: two-factor minimum
- Segregation of duties: maker-checker for transactions
- AML screening: real-time for high-risk, batch for standard
- Operational resilience: RTO < 2 hours for critical systems
- Third-party risk: annual due diligence reviews
- Consumer duty: evidence of good outcomes monitoring

Output JSON matching this schema:
```json
{
  "policies": [
    {
      "name": "Policy name",
      "description": "Full policy description with specific requirements",
      "regulation_ids": ["reg-id-1"],
      "risk_level": "low|medium|high|critical",
      "owner": "Suggested owner",
      "review_cadence": "annual|quarterly|after_incident",
      "tags": ["tag1", "tag2"]
    }
  ],
  "procedures": [
    {
      "name": "Procedure name",
      "description": "What this procedure implements",
      "policy_name": "Parent policy name (must match a policy above)",
      "steps": ["Step 1", "Step 2", "Step 3"],
      "owner": "Suggested owner"
    }
  ],
  "assumptions": ["Final list of assumptions made"],
  "questions": ["Final list of questions for the user"],
  "action_items": ["Final list of action items"],
  "summary": "Executive summary of what was generated and key next steps"
}
```
Do NOT include markdown fencing. Output raw JSON only.\
"""


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


async def gather_context(state: ThreadWorkflowState) -> dict[str, Any]:
    """Gather regulation details, project context, and additional user input."""
    return {
        "current_phase": "gathering_context",
        "agent_outputs": [{"node": "gather_context", "summary": "Context gathered"}],
    }


async def analyse_regulation(state: ThreadWorkflowState) -> dict[str, Any]:
    """Analyse regulation(s) to identify control domains and requirements."""
    return {
        "current_phase": "analysing",
        "agent_outputs": [{"node": "analyse_regulation", "summary": "Regulation analysed"}],
    }


async def generate_policies(state: ThreadWorkflowState) -> dict[str, Any]:
    """Generate draft policies, procedures, assumptions, and questions."""
    return {
        "current_phase": "generating",
        "agent_outputs": [{"node": "generate_policies", "summary": "Policies generated"}],
    }


async def finalise_policies(state: ThreadWorkflowState) -> dict[str, Any]:
    """Persist approved policies and produce final summary."""
    return {
        "current_phase": "completed",
        "agent_outputs": [{"node": "finalise", "summary": "Policies finalised"}],
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


def _gate(name: str) -> Any:  # noqa: ANN401
    fn = lambda s: s  # noqa: E731
    fn.__name__ = name
    fn.__qualname__ = name
    return fn


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
    g.add_node("approval_gate_policies", _gate("approval_gate_policies"))
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
