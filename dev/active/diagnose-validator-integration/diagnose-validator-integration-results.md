# Diagnose Validator Integration Results

## Summary
Integrated `validate_patch_context()` into `/api/diagnose/fix-and-run` so patch execution is now gated before Docker validation. The same gate is applied to retry-generated fixes.

## Implemented changes
- Added `context_validation` before initial `run_fixed_code()` call
- Blocked execution on validator hard-fail with explicit blocked response payload
- Added `retry_context_validation` before retry execution
- Exposed both validation payloads in endpoint response

## Verification
### 1. Syntax validation
- `python -m py_compile api/main.py api/context_validator.py api/fix_runner.py`
- Status: PASS

### 2. Focused validator smoke test
Script:
- `dev/active/diagnose-validator-integration/smoke_test_context_validator.py`

Observed output:
- BLOCKED => `passed: False` for `resolution = 5`
- ALLOWED => `passed: True` for `resolution = 20`

Interpretation:
- Hard-fail path is active
- Allowed path remains runnable in principle
- Endpoint wiring in `api/main.py` now has the needed gate points

## Remaining gaps
- Real endpoint-level runtime test in the active FastAPI/container environment still recommended
- Validator is still heuristic; future work can make it use richer physics metadata
- Blocked responses currently encode validator blocking in `run_result` rather than raising HTTP errors for backward compatibility
