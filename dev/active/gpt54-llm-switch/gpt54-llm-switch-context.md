# GPT-5.4 LLM Switch Context

## Relevant Files
- `agent/generator.py` — `/api/chat` answer generation
- `agent/intent_analyzer.py` — query intent classification
- `api/main.py` — diagnose + concept fallback LLM calls
- `requirements.txt` — Python dependencies
- `.env.example` — config documentation
- `Dockerfile` / `docker-compose.yml` — runtime rebuild path already exists

## Constraints
- Keep changes minimal and targeted.
- Do not overwrite unrelated in-progress meep-kb work.
- Current runtime only exposes `ANTHROPIC_API_KEY`; OpenAI key must be added separately.
- Should preserve graceful fallback until OpenAI key exists.

## Decision Log
- Use a shared root-level `llm_client.py` helper because `/app` is already on `sys.path` in `api/main.py`.
- Prefer environment-driven provider/model resolution instead of hard-coding Anthropic per call site.
- Default model target: `gpt-5.4`.

## Validation Approach
- Run targeted import/syntax checks for patched modules.
- Search for remaining direct Anthropic-only model calls in the patched paths.
- Report the operational next step: add `OPENAI_API_KEY` and restart container.

## Session Progress
- Added shared helper at `agent/llm_client.py` (container-mounted/copied path).
- Patched `/api/chat`, intent analysis, diagnose/fix, and concept fallback call sites to prefer GPT-5.4.
- Added `openai` dependency and `.env.example` entries.
- Static compile passed.
- Runtime is not yet truly on GPT-5.4 because current meep-kb `.env` still lacks `OPENAI_API_KEY`.
