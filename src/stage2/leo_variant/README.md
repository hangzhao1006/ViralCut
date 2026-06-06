# Stage 2 — leo_variant (parallel implementation)

This is a **second, independent** multi-agent Stage 2 implementation, developed in
parallel by a teammate (originally on `feature/link`). It lives here alongside the
primary `src/stage2/` implementation so both can coexist without conflict.

> ⚠️ This is NOT wired into the primary pipeline. The two Stage 2 implementations
> are kept side-by-side until the team decides which to keep / how to merge.

## Relationship to the primary `src/stage2/`

| | Primary `src/stage2/` | `leo_variant/` |
|---|---|---|
| Layout | `agents/` pkg, `framework/`, `prompts/` | flat: `agents.py`, `orchestrator.py` |
| Schemas | `output_schema.py` (dataclass) | `schemas.py` (pydantic) |
| LLM client | `llm_client.py` | `openai` AsyncOpenAI → OpenRouter |
| Entry | `pipeline.py` | `pipeline_stage2.py` / `viralcut.py` |

The two share **no file names** — nothing here overwrites the primary implementation.

## Files

| File | Role |
|------|------|
| `schemas.py`         | pydantic models: `AgentFinding`, `SynthesisResult`, `ViralDimension`, `EvidenceItem` |
| `agents.py`          | per-dimension agent runner (`run_agent`) |
| `orchestrator.py`    | fan-out + cluster + synthesize (`run_viral_analysis`) |
| `pipeline_stage2.py` | CLI: evidence_package.json → analysis results |
| `viralcut.py`        | unified CLI: Stage 1 (link) → this Stage 2 |
| `__init__.py`        | package exports |

## Imports note

`agents.py` / `orchestrator.py` / `pipeline_stage2.py` use **flat** imports
(`from schemas import ...`). They resolve because each entrypoint (and this
package's `__init__.py`) inserts this directory onto `sys.path`. Do not "fix" them
to relative imports without testing both the package-import and script-run paths.

## Usage

```bash
# Stage 2 only, from an existing evidence_package.json
python src/stage2/leo_variant/pipeline_stage2.py path/to/evidence_package.json

# Full pipeline (Stage 1 link → this Stage 2)
python src/stage2/leo_variant/viralcut.py "https://www.youtube.com/shorts/..."
```

Requires `OPENROUTER_API_KEY` in the repo-root `.env`.
