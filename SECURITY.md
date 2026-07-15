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
- external pages and agent responses are untrusted data
- third-party Skills/plugins must be pinned and audited
- paid compute requires hard limits, metering, and auto-shutdown
- raw restricted research/Kaggle data stays local by default
- one accountable writer per Campaign branch
