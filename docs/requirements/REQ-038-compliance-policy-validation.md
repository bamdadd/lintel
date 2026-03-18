# REQ-038 — Compliance Policy Validation & Review Workflow

## Summary

After the regulation-to-policy workflow generates draft policies and procedures, they must pass through a structured validation workflow before being marked as active. This ensures legal/compliance teams can review, comment, request changes, and approve policies in a traceable, auditable manner.

---

## Problem Statement

AI-generated compliance policies are drafts by definition. Without structured validation:
- Policies may contain incorrect assumptions that go unchallenged
- There is no audit trail of who reviewed and approved each policy
- Version history is lost when policies are edited
- No mechanism exists to compare policy versions side-by-side
- Teams cannot collaboratively review policies with threaded comments

---

## Requirements

### R-038.1: Policy Review States

Each `CompliancePolicy` must support a review lifecycle:

| State | Description |
|-------|-------------|
| `draft` | Initial AI-generated state. Not yet reviewed. |
| `in_review` | Assigned to one or more reviewers. Comments are open. |
| `changes_requested` | Reviewer has requested modifications. |
| `approved` | All required reviewers have approved. |
| `active` | Published and enforceable. |
| `superseded` | Replaced by a newer version. |
| `archived` | No longer applicable. |

Transition rules:
- `draft` -> `in_review` (when review is initiated)
- `in_review` -> `changes_requested` | `approved` (by reviewer)
- `changes_requested` -> `in_review` (after edits are made)
- `approved` -> `active` (by compliance officer or automated)
- `active` -> `superseded` (when a new version is published)
- Any state -> `archived` (by compliance officer)

### R-038.2: Review Assignment

- A policy review requires at least one assigned reviewer
- Reviewers are identified by `user_id` or `role` (e.g. "compliance_officer", "legal_counsel", "ciso")
- The system should support required reviewers (must approve) vs optional reviewers (advisory)
- Review requests create `ApprovalRequest` records via the existing approval-requests API with `gate_type: "policy_review"`

### R-038.3: Review Comments

Each policy under review supports threaded comments:

```
PolicyReviewComment:
  comment_id: str
  policy_id: str
  reviewer_id: str
  section: str          # Which part of the policy (e.g. "description", "procedure:step-3")
  content: str          # The comment text
  status: "open" | "resolved" | "wont_fix"
  created_at: str
  resolved_at: str
  resolved_by: str
```

- Comments can target specific sections of the policy
- Comments must be resolved (or marked won't-fix) before approval
- All comments are retained as part of the audit trail

### R-038.4: Version Comparison

When a policy is edited during review:
- The system creates a new version, preserving the previous version
- A diff view shows what changed between versions
- The regulation-clause-to-policy-section mapping is preserved across versions
- Version history includes: who edited, when, what changed, and why

```
PolicyVersion:
  version_id: str
  policy_id: str
  version_number: int
  content_snapshot: dict    # Full policy content at this version
  changed_by: str
  change_reason: str
  created_at: str
  diff_from_previous: dict  # Structured diff
```

### R-038.5: Assumption Validation

Each assumption produced by the AI must be individually validated:

```
AssumptionValidation:
  assumption_id: str
  policy_generation_run_id: str
  assumption_text: str
  basis: str
  confidence: str           # high, medium, low (from AI)
  validation_status: "pending" | "confirmed" | "overridden" | "rejected"
  validator_id: str          # Who validated
  override_value: str        # If overridden, what the correct value is
  validation_notes: str
  validated_at: str
```

- High-confidence assumptions may be auto-confirmed (configurable)
- Low-confidence assumptions must be manually validated
- Overridden assumptions trigger policy regeneration for affected sections

### R-038.6: Question Resolution

Each question produced by the AI must be answered before policy finalisation:

```
QuestionResolution:
  question_id: str
  policy_generation_run_id: str
  question_text: str
  why_it_matters: str
  default_if_no_answer: str
  resolution_status: "pending" | "answered" | "deferred" | "not_applicable"
  answer: str
  answered_by: str
  answered_at: str
  impact_on_policies: list[str]  # Which policy_ids are affected
```

- Unanswered questions block policy activation (not approval)
- Deferred questions are flagged for follow-up with a due date
- Answers can trigger policy content updates

### R-038.7: Audit Trail Requirements

Every validation action must produce an `AuditEntry` via the existing audit system:

| Action | Resource Type | Details |
|--------|---------------|---------|
| `policy_review_initiated` | `compliance_policy` | reviewer_ids, required vs optional |
| `policy_review_comment_added` | `compliance_policy` | comment_id, section, reviewer_id |
| `policy_review_comment_resolved` | `compliance_policy` | comment_id, resolved_by |
| `policy_approved` | `compliance_policy` | reviewer_id, version_number |
| `policy_changes_requested` | `compliance_policy` | reviewer_id, comment_count |
| `policy_version_created` | `compliance_policy` | version_number, changed_by, change_reason |
| `assumption_validated` | `policy_generation_run` | assumption_id, status, validator_id |
| `assumption_overridden` | `policy_generation_run` | assumption_id, original, override_value |
| `question_answered` | `policy_generation_run` | question_id, answer, answered_by |
| `policy_activated` | `compliance_policy` | activated_by, version_number |
| `policy_superseded` | `compliance_policy` | superseded_by_version |

### R-038.8: Compliance Dashboard Metrics

The validation workflow should expose metrics for the compliance overview:

- **Policies pending review**: count of policies in `draft` or `in_review` state
- **Open review comments**: count of unresolved comments across all policies
- **Unvalidated assumptions**: count of assumptions still `pending`
- **Unanswered questions**: count of questions still `pending`
- **Average review time**: time from `in_review` to `approved`
- **Review coverage**: percentage of policies that have been reviewed at least once

### R-038.9: Notification Integration

Using the existing `NotificationRule` system:
- Notify assigned reviewers when a policy is ready for review
- Notify the policy owner when changes are requested
- Notify the compliance team when all reviews are complete
- Notify when assumption overrides require policy regeneration

---

## API Endpoints (Planned)

```
POST   /compliance/policies/{policy_id}/reviews          # Initiate review
GET    /compliance/policies/{policy_id}/reviews           # List reviews
POST   /compliance/policies/{policy_id}/reviews/comments  # Add comment
PATCH  /compliance/policies/{policy_id}/reviews/comments/{id}  # Resolve comment
POST   /compliance/policies/{policy_id}/reviews/approve   # Approve
POST   /compliance/policies/{policy_id}/reviews/request-changes  # Request changes

GET    /compliance/policy-generations/{run_id}/assumptions  # List assumptions
PATCH  /compliance/policy-generations/{run_id}/assumptions/{id}  # Validate/override

GET    /compliance/policy-generations/{run_id}/questions    # List questions
PATCH  /compliance/policy-generations/{run_id}/questions/{id}  # Answer/defer

GET    /compliance/policies/{policy_id}/versions           # Version history
GET    /compliance/policies/{policy_id}/versions/{v1}/diff/{v2}  # Compare versions
```

---

## Implementation Priority

1. **Phase 1** (current): Policy review states + approval request integration (done)
2. **Phase 2**: Review comments + assumption/question validation endpoints
3. **Phase 3**: Version comparison + diff view
4. **Phase 4**: Dashboard metrics + notification integration

---

## Dependencies

- `lintel-approval-requests-api` — ApprovalRequest creation and lifecycle
- `lintel-audit-api` — AuditEntry recording for all validation actions
- `lintel-compliance-api` — CompliancePolicy and Procedure stores
- `lintel-notifications-api` — NotificationRule for reviewer notifications
- `lintel-domain` — New types: PolicyReviewComment, PolicyVersion, AssumptionValidation, QuestionResolution
