# Windows support

Windows is a first-class research host.

## Required baseline

- Windows 11 or supported Windows 10
- Git for Windows
- PowerShell 5.1+ or PowerShell 7
- Python 3.11+
- GitHub CLI
- ChatGPT desktop app with Codex

Optional tools are probed, not assumed: NVIDIA driver, Kaggle CLI, Claude Code,
Grok Build, Node/npx, agmsg, Chrome.

## agmsg and Bash

agmsg is implemented in Bash. On Windows, use Git Bash and pin its executable.
Do not let native PowerShell resolve `bash` to the WSL shim, because WSL and Git
Bash can use different HOME paths and therefore different SQLite databases.

Recommended Git Bash path:

```powershell
C:\Program Files\Git\bin\bash.exe
```

## Persistent jobs

Long GPU training should run as a managed OS process with PID/log/artifact paths
saved under ignored runtime state. The Goal session should checkpoint and return
to a control loop rather than relying on one uninterrupted terminal call.

## Paths

Machine-specific data/artifact roots, Chrome profile, Project URLs, PIDs, and
credentials stay under `.research-lab/local/` or `runtime/` and are ignored.
