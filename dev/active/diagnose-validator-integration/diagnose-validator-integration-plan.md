# Diagnose Validator Integration Plan

## Executive Summary
Integrate the existing context-aware validator into the `/api/diagnose/fix-and-run` execution path so generated or retrieved patches are screened before Docker execution. Preserve current behavior for diagnosis while making execution safer and more explainable.

## Current State
- `context_validator.py` already exists with `validate_patch_context()`.
- `/api/task/generate` already returns `context_validation`.
- `/api/diagnose/fix-and-run` imports `validate_patch_context` but does not actually use it to gate execution.
- `fix_runner.py` performs security blocking and lightweight runtime execution, but it does not know about patch context review status.

## Target State
- `/api/diagnose/fix-and-run` validates `fixed_code` before `run_fixed_code()`.
- If validator returns `hard_fail`, execution is blocked and the API explains why.
- If validator returns warnings/review items, they are returned in the response even when execution proceeds.
- Retry-generated fixes also go through the same validation gate.
- Response includes explicit `context_validation` and `retry_context_validation` payloads.

## Phases
1. Document plan/context/tasks
2. Patch `api/main.py` for validator gating
3. Keep response schema explicit and backward-friendly
4. Run syntax validation
5. Run focused smoke test for blocked/allowed flows
6. Update docs and task checklist

## Risks
- `main.py` is already large and partially modified; patch should stay surgical.
- Existing clients may assume `run_result` is always present when `fixed_code` exists.
- Retry path must mirror initial validation behavior to avoid inconsistent safety.

## Success Criteria
- Initial patch is blocked on validator hard_fail.
- Safe patch continues to `run_fixed_code()`.
- Retry patch is also validated before execution.
- Response surfaces validation outputs clearly.
