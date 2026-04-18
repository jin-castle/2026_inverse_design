# GPT-5.4 LLM Switch Tasks

## Phase 1 — Shared helper
- [x] Add `agent/llm_client.py` with provider/model resolution and unified text generation API
- [x] Support OpenAI GPT-5.4 preferred path
- [x] Keep Anthropic fallback path

## Phase 2 — Patch call sites
- [x] Update `agent/generator.py`
- [x] Update `agent/intent_analyzer.py`
- [x] Update `api/main.py` diagnose/fallback call sites

## Phase 3 — Config/docs
- [x] Add `openai` dependency to `requirements.txt`
- [x] Add env examples for `OPENAI_API_KEY` and model override

## Phase 4 — Validation
- [x] Run static/import smoke test
- [x] Confirm remaining direct model strings only where intentionally preserved
- [x] Commit only relevant files

## Acceptance Criteria
- [x] meep-kb code prefers GPT-5.4 for user-facing LLM responses when OpenAI key is configured
- [x] service still degrades gracefully without OpenAI key
- [x] changes are committed cleanly without unrelated repo noise
