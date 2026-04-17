# Diagnose Validator Integration Tasks

## Phase 1 — Docs
- [x] Create plan document
- [x] Create context document
- [x] Create tasks document

## Phase 2 — Implementation
- [x] Add initial patch validation before `run_fixed_code`
- [x] Block execution when validator returns hard_fail
- [x] Add retry patch validation before retry execution
- [x] Expose validation payloads in endpoint response

## Phase 3 — Verification
- [x] Run syntax validation
- [x] Run focused smoke test for blocked flow
- [x] Run focused smoke test for allowed flow

## Acceptance Criteria
- Hard-fail patch never reaches Docker execution
- Validation output is visible in API response
- Retry path uses identical validation gate
