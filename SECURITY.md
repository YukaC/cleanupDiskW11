# Security Policy

## Supported Versions

Security fixes are applied on the `main` branch (and the current default release branch). Pre-release/beta tags may receive fixes at maintainer discretion; older unsupported tags are not patched unless stated in a release note.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

- Prefer a **private security advisory** on GitHub (Repository → Security → Advisories → Report a vulnerability), or
- Email **agusyuk25@gmail.com** with a clear description, steps to reproduce, and impact.

We will acknowledge receipt and work on a fix; please allow reasonable time before public disclosure.

## Scope

**CleanupOs** (`cleanUpDisk`) runs with elevated privileges on the host OS to delete or quarantine files. In scope:

- Bypass of safety denylist / path classification that could delete critical system paths
- Privilege escalation or arbitrary command execution via the CLI, GUI, or installer
- Unsafe handling of quarantine, snapshots, or audit logs that enables data loss or tampering

Out of scope: general Windows/Linux/macOS bugs outside this tool, issues in third-party package managers, or problems caused only by local config not shipped in this repository.
