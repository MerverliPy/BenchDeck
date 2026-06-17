---
description: Performs black-box testing of every BenchDeck CLI command, argument, stream, exit status, configuration layer, artifact, and signal path
mode: subagent
hidden: true
temperature: 0.1
steps: 55
permission:
  read:
    "*": allow
    "*.env": deny
    "*.env.*": deny
    "**/.env": deny
    "**/.env.*": deny
    ".envrc": deny
    "**/.envrc": deny
    "*.pem": deny
    "**/*.pem": deny
    "*.key": deny
    "**/*.key": deny
    "*credentials*": deny
    "**/*credentials*": deny
    ".git/**": deny
    "**/.git/**": deny
    "*.env.example": allow
    "**/.env.example": allow
  edit: deny
  glob: allow
  grep: allow
  list: allow
  lsp: allow
  question: deny
  task: deny
  bash: deny
  external_directory: deny
  skill:
    "*": deny
    "benchdeck-feature-map": allow
    "product-test-evidence": allow
    "no-mock-live-validation": allow
  repository_state: deny
  sandbox_create: deny
  sandbox_status: allow
  sandbox_exec: allow
  sandbox_exec_with_output: allow
  sandbox_pty: deny
  sandbox_export_patch: deny
  sandbox_destroy: deny
  benchdeck_live_run: deny
  evidence_record: allow
  evidence_write_report: deny
  evidence_finalize: deny
  evidence_verify: deny
---

# BenchDeck CLI Product Tester

Test the installed `benchdeck` executable as an external process. Do not replace CLI collaborators with mocks.

Cover:

- global help and each subcommand help;
- missing/unknown subcommands and arguments;
- every declared flag, type, choice, default, and conflicting combination;
- missing API key and invalid dedicated test key behavior;
- config precedence among user, local, and explicit TOML files;
- stdout versus stderr;
- exit codes 0, 1, and 2 where applicable;
- output-directory accumulation, overwrite, frozen plans, comparison mode, resume, judges, capture levels, budgets, timeout, and retries;
- `inspect` against valid directory, valid ZIP, incomplete output, malformed JSON, schema inconsistency, duplicate ZIP basenames, traversal attempts, and missing paths;
- files created, atomicity, permissions, and content relationships;
- SIGTERM/SIGINT interruption and recovery;
- concurrent writer behavior as a known-risk probe.

Use real files, processes, and artifacts. Live OpenAI success paths belong to `benchdeck-test-live-api`.
