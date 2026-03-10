# Stage Multi-Attempt Tracking & UI Enhancements

Created: 2026-03-10
Status: in-progress

## Tasks

### Backend: Stage Multi-Attempt Model
- [x] 1. Add `StageAttempt` dataclass to `contracts/types.py`
- [x] 2. Add `attempts: tuple[StageAttempt, ...]` field to `Stage` dataclass
- [x] 3. Update `_stage_tracking.py` — archive on re-entry via `_archive_and_reset`
- [x] 4. Update `_stage_tracking.py` — `update_stage` preserves attempts
- [x] 5. Update `_stage_tracking.py` — `append_log` preserves attempts
- [x] 6. `mark_running` accepts `inputs` param for stage inputs
- [ ] 7. Expose previous attempt context to agents (via state or config)

### Backend: Retry & User Interjection
- [ ] 8. Add API endpoint to retry a stage with optional additional prompt
- [ ] 9. Wire retry into workflow executor — resume from specific stage with injected prompt
- [ ] 10. Store user-provided prompt in attempt inputs

### UI: DAG & Loop Visualization
- [x] 11. Show review cycle count on review→implement edge label
- [x] 12. Show attempt history per stage in StageCard (collapsible per attempt)

### UI: Implementation Checklist
- [ ] 13. Show plan tasks as checklist in implement stage
- [ ] 14. Tick off checklist items as implemented (from agent outputs)
- [ ] 15. Add review feedback items to checklist when changes requested

### Serialization & Storage
- [x] 16. Update Postgres CrudStore `_reconstruct_nested` for nested tuple[DataClass, ...]
- [x] 17. UI TypeScript interface updated with attempts
- [x] 18. Tests: 8 new tests for StageAttempt model and archive/reset behavior
