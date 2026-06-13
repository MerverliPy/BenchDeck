---
description: Run the complete sandboxed BenchDeck product-validation workflow
agent: benchdeck-product-tester
---
Perform a full repository-specific product test of the current BenchDeck state. Test every discovered CLI, TUI, artifact, integration, security, performance, and compatibility feature. Use the rootless-Docker sandbox, preserve all evidence, create candidate tests/fixes only in the disposable workspace, independently verify material results, and export a patch. Do not modify the host repository. Arguments or focus supplied by the user: $ARGUMENTS
