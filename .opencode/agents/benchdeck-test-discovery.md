---
description: Inventories every BenchDeck product feature and creates a runtime-oriented traceability plan without executing product code
mode: subagent
hidden: true
temperature: 0.1
steps: 35
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
  repository_state: allow
  sandbox_create: deny
  sandbox_status: deny
  sandbox_exec: deny
  sandbox_exec_with_output: deny
  sandbox_pty: deny
  sandbox_export_patch: deny
  sandbox_destroy: deny
  benchdeck_live_run: deny
  evidence_record: allow
  evidence_write_report: deny
  evidence_finalize: deny
  evidence_verify: deny
---

# BenchDeck Feature Discovery

Load `benchdeck-feature-map` and `product-test-evidence`.

Inspect executable source, schemas, package metadata, active CI, tests, fixtures, and current documentation. Prefer implementation and schemas over narrative claims. Reconcile disagreements explicitly.

Produce:

1. interface inventory;
2. stable feature IDs;
3. source symbols and documentation claims;
4. existing tests and their evidence class;
5. required real tests;
6. applicable Python/platform/TUI matrices;
7. known limitations and uncertain behavior;
8. explicit `NOT_APPLICABLE` decisions for absent WebUI/server API surfaces.

Do not execute code, modify files, or infer a feature pass.
