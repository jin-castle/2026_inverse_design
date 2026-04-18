# GPT-5.4 LLM Switch Plan

## Executive Summary
Switch meep-kb user-facing LLM responses from Anthropic Claude defaults to OpenAI GPT-5.4, while preserving safe fallback behavior if `OPENAI_API_KEY` is not configured yet.

## Current State
- `/api/chat` generation uses `agent/generator.py` with Anthropic Claude Sonnet 4.5.
- intent analysis uses `agent/intent_analyzer.py` with Claude Haiku 4.5.
- diagnose/fix endpoints in `api/main.py` use Claude Sonnet 4.6.
- concept fallback in `api/main.py` uses Claude 3.5 Haiku.
- Runtime container currently has `ANTHROPIC_API_KEY` only; `OPENAI_API_KEY` is absent.

## Goal State
- Shared LLM helper abstracts provider/model selection.
- Default preferred model becomes `gpt-5.4` when `OPENAI_API_KEY` is present.
- Existing Anthropic path remains as fallback so the service does not hard-break before key provisioning.
- Config/documentation clearly indicate required env vars.

## Phases
1. Add shared LLM client helper.
2. Patch generator, intent analyzer, and API fallback/diagnose paths to use helper.
3. Add `openai` dependency and env example entries.
4. Smoke-test imports/config and summarize runtime requirement (`OPENAI_API_KEY` + restart).

## Risks
- GPT-5.4 may require prompt formatting differences from Anthropic.
- Container will not truly switch until `OPENAI_API_KEY` is configured and the service restarts.
- Repo is already dirty, so changes must be path-scoped and commit carefully.

## Success Criteria
- Codebase prefers GPT-5.4 for all LLM-backed answer flows.
- No hard dependency on Anthropic-only client remains in patched answer paths.
- A basic static/import smoke test passes.
- Changes are committed without sweeping unrelated files.
