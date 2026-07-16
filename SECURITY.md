# Security policy

## Reporting

Please open a private security advisory in the GitHub repository for credential
exposure, unsafe command execution, prompt-injection bypass, destructive setup,
or browser/session leakage. Do not include real secrets in reports.

## Supported version

The latest release and `main` receive security fixes.

## Key rules

- no credentials in Git, Issues, PRs, logs, or screenshots
- browser login/MFA is completed by the human
- external pages and agent responses are untrusted data, not instructions
- third-party Skills/plugins must be pinned and audited
- lifecycle, ownership, and selected-Campaign fields change only through explicit
  revision-checked commands
- every active Campaign mutation and Job operation must present the current,
  unexpired Executor claim; superseded claim generations are fenced out
- compute resources are typed and unknown resource names are rejected
- a cancellation request is not proof that a process stopped; running Job
  cancellation requires externally confirmed termination evidence
- paid compute fails closed unless a reviewed code-registered backend adapter
  provides enforced cancellation and provider-side cost metering
- every backend must explicitly declare `paid = true` or `false`; paid backends
  require a positive `planned_cost_jpy` estimate before Job admission
- raw restricted research/Kaggle data stays local by default
- one accountable writer per Campaign branch

Configuration is a policy declaration, not an implementation proof. In
particular, setting `cancellation_mode = "enforced"` or a cost-metering label in
TOML does not enable paid compute unless the named control adapter is implemented
and registered in code. Declaring a paid backend with a zero-cost estimate is
also rejected rather than treated as free compute.

## Automated checks

Pull requests run two complementary checks:

- Gitleaks scans the complete Git history using the repository configuration.
- `researchctl doctor --profile quick` provides a fast local hygiene check.

The local probe is intentionally not a replacement for history scanning. GitHub
Actions are pinned to immutable commit SHAs and updated through Dependabot.
