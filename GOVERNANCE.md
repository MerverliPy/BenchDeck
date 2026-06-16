# Governance

## Maintainership

BenchDeck is currently maintained by the repository owner (`MerverliPy`).
All significant decisions are made through the issue tracker and pull
request review process.

## Decision-making

1. **Proposal**: file an issue describing the change, rationale, and any
   alternatives considered.
2. **Discussion**: the maintainer and any interested contributors discuss
   the proposal in the issue thread.
3. **Implementation**: a pull request implements the accepted proposal.
   The PR must include tests and documentation updates.
4. **Review and merge**: the maintainer reviews the PR, verifies the CI
   checks pass, and merges.

For small fixes (typos, test additions, dependency pin updates), the
proposal and discussion steps may be skipped.

## Security

Security vulnerabilities must be reported privately. See
[SECURITY.md](SECURITY.md) for instructions. The maintainer will
acknowledge the report within 5 business days and provide a timeline
for remediation.

## Code of Conduct

All participants are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
Violations may be reported to the maintainer. The maintainer will review
and respond to reports within 5 business days.

## Becoming a maintainer

Contributors who have demonstrated sustained, high-quality contributions
(including code, documentation, testing, and review) may be invited to
become co-maintainers by the current maintainer.

## Hosted enforcement

The following controls require configuration in the GitHub repository
settings and **cannot be verified from repository contents alone**:

- **Branch protection rules** (require PR reviews, status checks before merge)
- **CODEOWNERS required reviews** (enforce review by designated owners)
- **Tag protection rules** (prevent deletion or force-push of release tags)
- **Environment protection** (`pypi`, `product-test` environments with
  required approvers)
- **Dependabot security updates** (enabled separately from the
  configuration file)

These must be verified by a repository administrator through the GitHub
UI or API. The presence of configuration files (`.github/CODEOWNERS`,
`.github/dependabot.yml`) does not guarantee enforcement.
