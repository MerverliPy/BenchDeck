---
description: Test all BenchDeck behavior affected by current working-tree changes
agent: benchdeck-product-tester
---
Fingerprint the current repository and determine the transitive product impact of every changed path. Run the smallest complete sandboxed test matrix that covers the changed behavior and neighboring regressions. Preserve evidence, independently verify failures and repairs, and export a patch without modifying the host repository. Additional scope: $ARGUMENTS
