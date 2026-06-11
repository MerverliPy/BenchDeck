# BenchDeck

BenchDeck is an evidence-preserving LLM-agent benchmark harness with a live terminal dashboard designed
for narrow SSH sessions, including Termius on an iPhone.

It turns one or two Markdown agent files into a benchmark plan, runs isolated cases, handles one concrete
clarification turn, judges responses, and writes continuously viewable artifacts. The supplied benchmark
bundle is preserved as `fixtures/original_run.zip`.

## Why this repository exists

The original run showed a strong agent but exposed benchmark-infrastructure ambiguity: one empty response
was scored as an agent failure without raw response diagnostics, a policy-blocked required case reduced
coverage, scoring scales were inconsistent, and stored judge transcripts duplicated candidate output.
BenchDeck makes those states explicit rather than silently converting them into agent failures.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
export OPENAI_API_KEY='...'
```

BenchDeck checks that `OPENAI_API_KEY` is set before starting a run and exits with a clear error if
it is missing.

## Run a benchmark

```bash
benchdeck run \
  --agent-a examples/repository-integrity-agent.md \
  --model gpt-4o-mini \
  --judge-model gpt-4o-mini \
  --output-dir benchmark_out
```

The `--model` and `--judge-model` default to `gpt-4o-mini`. Specify any model your API key grants
access to.

Use a frozen plan instead of generating one (tip: `Snapshot.plan` is a plain `dict`, not a Pydantic model):

```bash
python - <<'PY'
import json
from pathlib import Path
from benchdeck.tui import load_snapshot

plan = load_snapshot(Path('fixtures/original_run.zip')).plan
Path('/tmp/benchmark_plan.json').write_text(json.dumps(plan, indent=2) + '\n')
PY
benchdeck run \
  --agent-a examples/repository-integrity-agent.md \
  --plan /tmp/benchmark_plan.json \
  --output-dir benchmark_out
```

Comparison mode (two agents, same cases):

```bash
benchdeck run \
  --agent-a examples/agent_a.md \
  --agent-b examples/agent_b.md \
  --output-dir benchmark_out
```

## Open the live TUI

In a second SSH session:

```bash
benchdeck tui benchmark_out
```

Open the supplied run immediately:

```bash
benchdeck tui fixtures/original_run.zip
```

Controls: `1-4` screens, `h/l` tabs, `j/k` move or scroll, `Enter` details, `e` export case as
Markdown, `r` reload, `q` quit.

## Inspect existing artifacts

```bash
benchdeck inspect fixtures/original_run.zip
```

The command detects incomplete coverage, empty outputs, duplicated judge transcripts, undeclared
scoring scales, misleading run status, and validates per-agent tallies against the JSON Schema at
`schemas/summary_tally.schema.json`.

## Artifact semantics

- Empty output is retried and recorded with response ID, request ID, status, raw response, and error data.
- Policy blocks and infrastructure failures are separate from agent failures.
- The rating scale is fixed at 0-4.
- Candidate output and judge output are stored separately.
- JSON files are atomically replaced so a watching TUI never reads a half-written checkpoint.
- `completed` means all required cases were judged; otherwise the run is `inconclusive`, `completed_with_failures`,
  `infrastructure_failed`, or `aborted`.

## Limitations

- **No multi-judge aggregation.** Each case is judged once per agent; there is no ensemble or
  disagreement reporting yet.
- **No budget cap.** No token or cost limit guards the run. A misconfigured run can generate
  significant API spend.
- **No signed releases or SBOM.** Distribution artifacts have not been published.
- **The TUI cannot launch or cancel runs.** It is read-only; runs are started from the CLI.
- **Comparison mode in the TUI is partial.** The case list and detail screens show per-agent
  judgments, but selection/filtering by agent is not yet implemented.
- **No Windows testing.** The harness and TUI are developed and tested on Linux and macOS.

## Development

```bash
ruff check .
ruff format --check .
mypy src/benchdeck/ --ignore-missing-imports
pytest
```

See `docs/architecture.md`, `docs/benchmark-contract.md`, and `docs/mobile-tui.md`.
