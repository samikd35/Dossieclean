# Manual Checks

This directory is intentionally kept for optional, environment-specific diagnostics.

Guidelines:

- Do not commit scripts with real credentials, account IDs, private hostnames, or personal data.
- Keep any local one-off connectivity scripts in your own untracked workspace.
- Automated CI checks should remain in `tests/` and must run without external paid services.
