# Architecture

BenchDeck has four bounded layers:

1. **Planning** — infer or load a versioned benchmark plan.
2. **Execution** — run each case in a fresh model interaction and optionally apply one concrete clarification reply.
3. **Judging** — evaluate candidate output independently and preserve the raw judge response.
4. **Artifacts/UI** — atomically checkpoint JSON so the TUI can safely watch a live run.

The runner distinguishes model completion, judging, policy blocks, and infrastructure failures. An empty
text response is retried and cannot silently become an agent failure without diagnostic evidence.
