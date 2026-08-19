# Security

## Reporting

Please report suspected vulnerabilities privately through GitHub's security
advisory form for this repository. Do not include credentials, cookies, or
other sensitive data in a public issue.

## Runtime boundary

Normarchy runs inside the unsandboxed Omarchy shell with the current user's
permissions. It starts only these unprivileged local processes during playback:

- `python3` for the loopback stream helper
- `yt-dlp` for YouTube metadata and temporary media URLs
- `curl` for bounded media byte ranges

The helper binds to `127.0.0.1` with a random per-session token. Normarchy does
not use `sudo`, `pkexec`, cookies, API keys, shell installers, system services,
or predictable shared temporary state. It does not execute downloaded code.

## Supported version

Security fixes apply to the latest commit on the default branch and the latest
published release.
