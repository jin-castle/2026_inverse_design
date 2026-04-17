# Diagnose Validator Integration Context

## Repository
`C:\Users\user\projects\meep-kb`

## Primary files
- `api/main.py` — target endpoint implementation
- `api/context_validator.py` — validation logic
- `api/fix_runner.py` — execution backend
- `api/diagnose_engine.py` — fixed code generation/search pipeline

## Integration points
### Endpoint
- `POST /api/diagnose/fix-and-run`

### Existing flow
1. Parse error and physics context
2. Search DB + vector KB
3. Generate or retrieve `fixed_code`
4. Run `run_fixed_code(fixed_code)`
5. If failed, LLM retry may generate another patch and run again

### Required change
Insert `validate_patch_context(fixed_code)` before each execution attempt.

## Intended behavior
- `hard_fail` => do not run Docker execution, return blocked `run_result`
- `soft_warning` / `needs_review` => run is allowed, but response must expose the warnings
- Retry path follows same rules

## Response additions
- `context_validation`
- `retry_context_validation`

## Verification plan
- `python -m py_compile api/main.py api/context_validator.py api/fix_runner.py`
- Focused local smoke test by importing endpoint module or small helper harness if runtime deps allow

## Constraints
- Keep patch additive and surgical
- Do not refactor diagnose logic broadly in this slice
- Do not change fix_runner contract unless needed
