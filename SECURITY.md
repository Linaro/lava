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
The LAVA documentation has a dedicated [Vulnerability handling](https://lava.readthedocs.io/en/latest/admin/vulnerability-handling.html) page describing the full triage, remediation, and disclosure process.

## Scope

In scope: the LAVA components in this repository: the LAVA server, dispatcher,
worker, and `lava-dispatcher-host`.

Out of scope:

- third-party dependencies; report those to their maintainers
- operator-configured deployments; misconfiguration of the host system
  (systemd units, Docker, network) is the operator's responsibility

## Supported versions

We support only the latest release. Security fixes ship in the latest
release through the regular channels (hotfix, support release, or major
release). We do not backport to older releases, so an older release stops
receiving security fixes: upgrade to stay covered.

## Safe harbor

We handle all vulnerability reports received through the channels above in
good faith. Research that follows this policy is treated as authorised under
our terms and applicable computer-misuse laws, and Linaro will not take
legal action against researchers who report vulnerabilities this way. Please
respect the embargo below while a fix is prepared.

## Disclosure and response

Please do not disclose the vulnerability publicly until a fix has been
released. The Linaro PSIRT triages reports, performs a risk assessment, and
works on a permanent solution (hotfix, support release, or major release
depending on the impact), as described in the VDP.

Separately from coordinated disclosure, the Linaro PSIRT assesses each
confirmed vulnerability and severe incident against the reporting duties of
the EU Cyber Resilience Act (Regulation (EU) 2024/2847). When the conditions
are met, it notifies the relevant CSIRTs and ENISA through the EU single
reporting platform within the CRA timelines (Article 14), and also considers
voluntary notification of vulnerabilities under Article 15. See the
[Vulnerability handling](https://lava.readthedocs.io/en/latest/admin/vulnerability-handling.html)
page for details.

## Cybersecurity policy

This file, together with the Vulnerability handling page and the
[VDP](https://www.linaro.org/vdp), is the cybersecurity policy of the LAVA
project, in the sense of Article 24(1) of the CRA:

- Secure development: all changes go through reviewed merge requests, and
  CI runs static analysis, secret scanning, SBOM generation and dependency
  vulnerability scanning (see `.gitlab-ci.yml`). We keep a threat model for
  the LAVA service at
  [`doc/threat-models/THREAT_MODEL.md`](doc/threat-models/THREAT_MODEL.md).
- Vulnerability handling: this file and the Vulnerability handling page.
- EU reporting: PSIRT assessment against Articles 14 and 15, as above.
- Information sharing: public security advisories, machine-readable security
  metadata in [`security-insights.yml`](security-insights.yml), and upstream
  reporting of third-party vulnerabilities. We cooperate with market
  surveillance authorities on request.

## Bug bounty

The LAVA project or Linaro does not offer a bug bounty program.
