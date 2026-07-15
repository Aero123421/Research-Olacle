# ADR-0006: Windows-first, dependency-light control plane

Status: accepted

## Context

The always-on research host is Windows. Bootstrap must be reliable before data
science environments are fully configured.

## Decision

The base CLI uses Python 3.11 standard library only, PowerShell bootstrap, GitHub
CLI, and local files. Data-science packages are optional extras. Host-specific
state is ignored. Linux CI verifies portability; Windows CI is authoritative.

## Consequences

Some rich data formats require optional extras. The control plane remains usable
offline and easier to repair.
