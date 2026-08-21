# Security Policy

## Reporting a vulnerability

The LAVA project is stewarded by Linaro. Security vulnerabilities in LAVA are
handled through the [Linaro Security Incident Handling Process (VDP)](https://www.linaro.org/vdp).

To report a vulnerability, email the Linaro Product Security Incident Response
Team (PSIRT) at **psirt@linaro.org**.

When reporting, please include:

- the affected component (server, dispatcher, worker, lava-dispatcher-host)
- the LAVA version or git commit
- steps to reproduce the issue
- exploit code, if available

Machine-readable details are published at <https://www.linaro.org/.well-known/security.txt>.

## Scope

In scope: the LAVA components in this repository: the LAVA server, dispatcher,
worker, and `lava-dispatcher-host`.

Out of scope:

- third-party dependencies; report those to their maintainers
- operator-configured deployments; misconfiguration of the host system
  (systemd units, Docker, network) is the operator's responsibility

## Disclosure and response

Please do not disclose the vulnerability publicly until a fix has been
released. The Linaro PSIRT triages reports, performs a risk assessment, and
works on a permanent solution (hotfix, support release, or major release
depending on the impact), as described in the VDP.

## Bug bounty

The LAVA project or Linaro does not offer a bug bounty program.
