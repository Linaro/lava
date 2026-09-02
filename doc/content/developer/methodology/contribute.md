# Contribution Guide

We want to make it as easy as possible for LAVA Software users to become
LAVA Software Community Project contributors, so we have created this
guide to help you get started.

The LAVA Software Community Project has published this Contribution
Guide, and all contributors will be expected to adhere to these
guidelines when submitting issues or merge requests. They are designed
to clarify the requirements for contributions, to make contributing more
efficient for all involved.

Following the guidelines is a great way to prevent your contributions
from being rejected or delayed. Most maintainers won't intend to
discredit your work or be tough on contributors. However, many are busy
and some may be working on LAVA in their free time. Well-formed
contributions are much easier to review and work with.

!!! info "See also"
    - [Code of Conduct](../code-of-conduct.md)
    - [Contributing Process](../tutorials/contributing.md)

### Conflicting priorities

Sometimes a request will be turned down because of conflicting
priorities. It is important to talk about the reasons on the mailing
list. Whether you're requesting a new feature, or providing a fix,
remember that the maintainer has to weigh up your contribution. They are
the people who may have to support the new code in the future, and
resources are often scarce. Try not to be discouraged if your feature
request or merge request is turned down. Be open-minded and, if
necessary, propose an alternative idea on the mailing list after hearing
their concerns.

## Pre-requisites to start

* LAVA is written in [Python](http://www.python.org/), so you will need
  to know (or be willing to learn) the language.
* The web interface is a [Django](https://www.djangoproject.com/)
  application so you will need to use and debug Django if you need to
  modify the web interface.
* LAVA uses [YAML][yaml] heavily internally, so you'll likely need to
  understand the syntax.
* LAVA also uses [Jinja2][jinja2].
* All LAVA software is maintained in [git](https://www.git-scm.org/).
* Some familiarity with [Debian](https://www.debian.org/) is going to be
  useful; helper scripts are available when preparing updated `.deb`
  packages based on your modifications.

LAVA is complex and designed to solve complex problems. This has
implications for how LAVA is developed, tested, deployed and used.

## Other elements involved

* The Django backend used with LAVA is
  [PostgreSQL](https://www.postgresql.org/).
* The LAVA UI includes JavaScript and CSS.
* LAVA also uses [ZMQ](http://zeromq.org/) and XML-RPC.

In addition, test jobs and device support can involve use of U-Boot,
GuestFS, fastboot, ADB, QEMU, Grub, SSH, Docker, and a wide variety
of other systems and tools.

## Updating documentation

We welcome contributions to improve our documentation. If you are
considering adding new features to LAVA or changing current behavior,
also please ensure that the changes include matching updates for the
documentation.

Wherever possible, all new sections of documentation should come
**with worked examples**.

* If the change relates to or includes particular test definitions to
  demonstrate the new support, add a test definition YAML file as an
  example.
* Use comments in the examples and link to existing terms and sections.

## Use of AI and LLM tools

The LAVA project welcomes contributions whether or not AI or large
language model (LLM) tools were used to produce them. Using such tools
to answer questions, explain code, analyze bugs, suggest or review
changes, and generate code is allowed, subject to the rules below.

With respect to AI and LLM tools, this policy is vendor-neutral: it
does not name, recommend, endorse, or advertise any AI or LLM tool or
vendor. Where a tool name appears in a commit message, it is supplied
solely by the contributor for attribution and is optional.

### You remain responsible

* You are fully responsible for everything you submit, exactly as if
  you had written it by hand. You must review and understand every line
  of AI-assisted code, and you must have run and verified the change
  (build, lint, tests) before submitting it. CI is a safety net, not a
  substitute for your own verification.
* You must have the legal right to contribute the code. Ensure the
  terms and conditions of the tool you used do not impose restrictions
  that conflict with LAVA's GPLv2-or-later license, the project's
  intellectual property policies, or the [Open Source Definition](https://opensource.org/osd/).
* If the tool's output contains third-party copyrighted material
  (including pre-existing open source code), you must confirm you have
  permission to include it under LAVA's licensing terms before
  contributing it.

### Developer's Certificate of Origin

The [Developer's Certificate of Origin](https://developercertificate.org/)
(`Signed-off-by`) certifies that *you* have the right to submit the
contribution. It must be written by you and never by an AI tool.
Adding, generating, or prompting a `Signed-off-by` line with an AI tool
is not allowed.

### Disclosure

* When a commit contains code created (in whole or in part) by an AI or
  LLM tool, the commit message must include an `Assisted-by: LLM` line,
  placed before the `Signed-off-by` line. If the code originated from a
  tool, your later editing, reformatting, or partial rewriting does not
  remove that requirement. What does not count: code you wrote yourself
  that the tool only mechanically changed (e.g. reformatting, sorting
  imports, typo fixes) does not need the `Assisted-by` line. Listing a
  specific tool is optional and, if done, at the contributor's own
  discretion:

  ```
  fix: worker: handle missing job state

  The worker crashed when the dispatcher state disappeared between
  polls. Add an explicit check and clean up the job instead.

  Assisted-by: LLM
  Signed-off-by: Jane Doe <jane@example.com>
  ```

  Optionally list the tool(s) used, e.g. `Assisted-by: LLM <tool>`.

* When an AI tool was used to draft a merge request description, an
  issue report, or review comments, briefly mention that in the text
  (for example, "drafted with LLM assistance").
* You are not required to use AI or LLM tools to contribute to LAVA,
  and no contributor is disadvantaged for declining to do so.

### Prohibited uses

* Do not submit AI-generated code without reading and understanding it.
* Do not let an AI tool add a `Signed-off-by` line.
* Do not disclose confidential data to third-party AI services: this
  includes production data from LAVA deployments, device credentials,
  tokens, customer job definitions, and any information that is not
  already publicly available in this repository. If you are employed or
  act on behalf of an organization, you must also comply with your
  employer's or organization's policies on the use of AI and LLM tools
  and on the data you may pass to them.
* Do not hide AI involvement in code or review content.

Maintainers may decline or return contributions that do not follow
these rules, in the same way they handle any contribution that does not
meet the project's existing guidelines. Submissions that appear to be
unreviewed tool output, or to be automated or bulk-generated, may be
declined without detailed review.

If your question or contribution concerns a potential security issue,
follow [SECURITY.md](https://gitlab.com/lava/lava/-/blob/master/SECURITY.md)
instead of the mailing list. Otherwise, if any of this is unclear for
your situation, ask on the [mailing list](https://lists.lavasoftware.org/mailman3/lists/)
before submitting.

--8<-- "refs.txt"
