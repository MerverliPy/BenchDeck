# BenchDeck

BenchDeck is an evidence-preserving LLM-agent benchmark harness with a live terminal dashboard designed
for narrow SSH sessions, including Termius on an iPhone.

It turns one or two Markdown agent files into a benchmark plan, runs isolated cases, handles one concrete
clarification turn, judges responses, and writes continuously viewable artifacts. The supplied benchmark
bundle is included under `fixtures/original_run` as a regression fixture.

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

## Run a benchmark

```bash
benchdeck run \
  --agent-a examples/repository-integrity-agent.md \
  --model gpt-5.5 \
  --judge-model gpt-5.5 \
  --output-dir benchmark_out
```

Use a frozen plan instead of generating one:

```bash
benchdeck run \
  --agent-a examples/repository-integrity-agent.md \
  --plan fixtures/original_run/benchmark_plan.json \
  --output-dir benchmark_out
```

## Open the live TUI

In a second SSH session:

```bash
benchdeck tui benchmark_out
```

Open the supplied run immediately:

```bash
benchdeck tui fixtures/original_run
```

Controls: `1-4` screens, `h/l` tabs, `j/k` move or scroll, Enter details, `r` reload, `q` quit.

## Inspect existing artifacts

```bash
benchdeck inspect fixtures/original_run
```

The command detects incomplete coverage, empty outputs, duplicated judge transcripts, undeclared scoring
scales, and misleading run status.

## Artifact semantics

- Empty output is retried and recorded with response ID, request ID, status, raw response, and error data.
- Policy blocks and infrastructure failures are separate from agent failures.
- The rating scale is fixed at 0-4.
- Candidate output and judge output are stored separately.
- JSON files are atomically replaced so a watching TUI never reads a half-written checkpoint.
- `completed` means all required cases were judged; otherwise the run is `inconclusive` or failed.

## Development

```bash
ruff check .
pytest
```

See `docs/architecture.md`, `docs/benchmark-contract.md`, and `docs/mobile-tui.md`.
