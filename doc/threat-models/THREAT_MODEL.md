# Threat Model: LAVA (Linux Automated Validation Architecture)

## 1. System context

LAVA (Linux Automated Validation Architecture) is an open-source test lab automation platform developed by Linaro, primarily aimed at testing Linux kernel deployments on ARM devices (ARMv7 and later). It is a Python/Django web application that manages physical and virtual test devices, schedules automated test jobs, collects results, and dispatches test execution to remote dispatcher workers.

The system consists of multiple services: `lava-server` (Django web app with REST API, XML-RPC API, and web UI, served via Apache/gunicorn), `lava-scheduler` (periodically schedules jobs and dispatches them to workers), `lava-publisher` (receives events from LAVA services and forwards them to subscribers), `lava-coordinator` (message broker for multi-node jobs), `lava-worker` (pulls scheduled jobs over HTTP and starts `lava-run` on test machines to execute jobs on devices), and `lava-dispatcher-host` (manages Docker-based device sharing and test image pulls). These services run under systemd based Linux distribution, backed by PostgreSQL (SQLite supported for local use) and Celery for background tasks. The dispatcher interacts with physical hardware via UART, SSH, NFS, TFTP, IPMI, QEMU, and Docker containers.

Users include lab administrators (who configure devices and manage the infrastructure), test submitters (who submit YAML/JSON job definitions), and test device operators (who monitor and manage physical hardware). LAVA is deployed in research labs, CI environments, and certification labs where it has control over physical test hardware.

## 2. Assets

| asset | description | sensitivity |
|---|---|---|
| Device control | Physical/virtual test devices under LAVA control (power, serial console, boot control) | critical |
| Host process integrity | The dispatcher process runs privileged operations (QEMU, flash tools, UART access, Docker) on test hardware | critical |
| User authentication tokens | Crypto-random API tokens (128-char SystemRandom for XML-RPC; 32-char Django secure-random for user, worker, and job tokens) | critical |
| User accounts and passwords | Django user accounts with LDAP/OIDC integration | critical |
| SSH keys | SSH identity keys used for overlay deployment and DUT authentication | critical |
| Secret key | Django SECRET_KEY for cryptographic signing (sessions, CSRF, password reset) | critical |
| Job definitions | YAML/JSON test job specifications submitted by users, containing device config and test commands | high |
| Device configurations | Jinja2 templates stored on disk per device, controlling boot/deploy/test pipelines | high |
| Worker tokens | Tokens used by dispatcher workers to authenticate with the server | high |
| Docker container state | Container device mappings, BPF programs, and container configs | high |
| Docker image registry credentials | Credentials used by `lava_dispatcher_host` for `docker login` to pull test images | high |
| Service availability | Scheduler, dispatcher, and web UI uptime; lab operations depend on continuous test execution | high |
| Database contents | User records, device states, job history, test results, authentication data (PostgreSQL) | high |
| Test results | Test execution output, logs, and results data | medium |

## 3. Entry points and trust boundaries

| entry_point | description | trust_boundary | reachable_assets |
|---|---|---|---|
| XML-RPC API (`/RPC2`) | XML-RPC endpoint for job submission, device management, results reporting; token-authenticated | untrusted network → authenticated application logic | device control, user authentication tokens, job definitions, device configurations |
| REST API (`/api/`) | Django REST Framework endpoints for job CRUD, device management, results | untrusted network → authenticated application logic | device control, user authentication tokens, job definitions, device configurations, test results, database contents |
| Web UI (Django views) | Browser-accessible web interface for device management, job viewing, user account management | untrusted network → authenticated session | all assets |
| Job submission (YAML/JSON) | User-provided job definitions parsed (yaml_safe_load + voluptuous schema) and executed by dispatcher | authenticated user → job execution pipeline | device control, host process integrity, SSH keys, worker tokens |
| Device config import (`import_device_dictionary`, REST `POST /device/{id}/dictionary`) | Admin-writable Jinja2 device configuration stored on disk | authenticated admin → filesystem write | device configurations, device control, host process integrity |
| Dispatcher-host Unix socket (`/run/lava-dispatcher-host.sock`) | Async Unix socket server for sharing host devices with Docker containers | local process → container device access | Docker container state, device control |
| Test shell execution (pexpect on DUT) | Shell command execution on target devices via serial/SSH connections (ShellSession-wrapped pexpect) | dispatcher → target device | device control, SSH keys |
| Docker device sharing (BPF/eBPF) | BPF programs controlling device node access within Docker containers | dispatcher → host kernel → container | device control, Docker container state |
| ext4 image manipulation (debugfs) | debugfs-based overlay writing on disk images | dispatcher → disk image | device control |
| LDAP authentication and SSO config | LDAP bind and user/group search; server-side eval/exec of LDAP group-type configuration in settings | user credentials + admin config → LDAP server | user accounts and passwords, device control |
| Worker internal API (`/scheduler/internal/v1`) | REST endpoints for dispatcher workers to fetch job definitions and report status (lava-token header) | authenticated worker → job execution | job definitions, worker tokens |
| Dispatcher actions (subprocess) | 130+ subprocess.run/Popen calls across boot, deploy, and test actions: QEMU, flash tools, SSH, Docker, pexpect | scheduler decision → host process execution | host process integrity, service availability |
| Docker worker (lava-dispatcher-host) | Runs untrusted test Docker images with docker-cli, manages container lifecycle, pulls images via docker login | local Unix socket → container runtime | host process integrity, Docker image registry credentials |
| OIDC / social auth | OpenID Connect and social authentication backends (django-allauth) | external identity provider → user session | user authentication tokens |
| Celery worker (async tasks) | Background task queue for job scheduling, health checks, result processing | internal service → database + filesystem | host process integrity, service availability, database contents |
| Worker log reporting (`/scheduler/internal/v1/jobs/<id>/logs/`) | YAML log lines (incl. `lvl: results` dicts) reported by the worker with the job token; result lines are parsed into TestCase rows and metadata YAML files on disk | authenticated worker → database + filesystem | database contents, test results, service availability |
| Notification callbacks | HTTP callbacks to external URLs configured in job definitions (now able to carry remote artifact tokens) | internal → external network | service availability, database contents |

## 4. Threats

| id | threat | actor | surface | asset | impact | likelihood | status | controls | evidence |
|---|---|---|---|---|---|---|---|---|---|
| T1 | Remote code execution on dispatcher via malicious job definition | remote_auth | job submission (YAML/JSON) | device control, SSH keys, host process integrity | critical | likely | partially_mitigated | Job submission requires a valid token (token auth enforced in ExposedV2API); Sandboxed Jinja2 for device templates; voluptuous job schema validation; defusedxml for XML-RPC | CVE-related: unsafe yaml.load fix (debian #933918) |
| T2 | Arbitrary file write via device configuration import | remote_auth (admin) | device config import (XML-RPC/REST) | device configurations, device control | critical | likely | partially_mitigated | Permission checks (can_change); Jinja2 sandbox | |
| T13 | Worker token theft and impersonation | remote_unauth | worker internal API, dispatcher-server communication | job definitions, device control | critical | possible | partially_mitigated | Token-based worker auth (lava-token header); constant-time comparison on /scheduler/internal/v1 endpoints | |
| T16 | Host process compromise via malicious Docker image executed by dispatcher-host | remote_auth | Docker worker (lava-dispatcher-host) | host process integrity | critical | possible | unmitigated | none | |
| T17 | Supply-chain compromise of test Docker images pulled by dispatcher-host | supply_chain | Docker worker (lava-dispatcher-host) | host process integrity | critical | possible | unmitigated | none | |
| T7 | Code execution via LDAP configuration eval/exec | local_admin (config) | LDAP settings in settings/common.py | user accounts and passwords, device control | critical | rare | partially_mitigated | eval/exec only on file-based config (not user input); SafeLoader for YAML | |
| T12 | Supply-chain compromise via dependency update or vendored code | supply_chain | uv.lock, requirements.txt | all assets | critical | rare | unmitigated | none | |
| T5 | Privilege escalation via missing permission checks on API endpoints | remote_auth | REST API, XML-RPC API | device control, job definitions, device configurations | high | likely | partially_mitigated | DjangoModelPermissions for REST; permission check on the requested device/worker at submission (21455bd28) | bd5fd6684 (missing permission checks) |
| T3 | Authentication bypass via token enumeration or prediction | remote_unauth | XML-RPC/REST API | user authentication tokens, device control | high | possible | unmitigated | Crypto-random tokens (128-char SystemRandom for XML-RPC; 32-char Django secure-random otherwise); constant-time comparison on worker internal API and lava-publisher | |
| T8 | Container escape via device sharing through BPF/eBPF | local_user (dispatcher) | dispatcher-host Unix socket, Docker device sharing | device control, Docker container state | high | possible | partially_mitigated | Device sharing pinned to resolved node paths, resolved and validated server-side (115c2903a, 7f7b85f0d); /run bind mounts rejected (6f9915593) | 115c2903a, 6f9915593 |
| T10 | Unauthorized device access via Unix socket without authentication | local_user | dispatcher-host Unix socket | device control, Docker container state | high | possible | partially_mitigated | SO_PEERCRED peer check requires uid 0, fails closed (ecbd68ca8, external report) | ecbd68ca8 |
| T11 | SSRF via device configuration or job definition URLs | remote_auth | job submission, device config | device control | high | possible | unmitigated | none | |
| T14 | SQL injection via unparameterized query construction | remote_auth | REST API, XML-RPC API | test results, device configurations, database contents | high | possible | partially_mitigated | Django ORM; parameterized queries | |
| T18 | Path traversal via symlink-following tar extraction of test definition bundles | remote_auth | dispatcher actions (subprocess) | host process integrity | high | possible | unmitigated | none | 39e1b872f (tar binary for untar), d4ea55ea4 (follow symlinks when unarchiving) |
| T20 | Denial of service via unbounded Celery task execution (health checks, result processing) | remote_auth | Celery worker (async tasks) | service availability | high | possible | partially_mitigated | Celery task timeouts, Django health check limits | |
| T21 | Authentication token theft via insecure cookie configuration on non-HTTPS deployments | remote_unauth | REST API (/api/) | user authentication tokens | high | possible | partially_mitigated | SESSION_COOKIE_SECURE / CSRF_COOKIE_SECURE default to True | |
| T24 | SQL injection via materialized view name construction in results API | remote_auth | REST API (/api/) | database contents | high | possible | mitigated | psycopg2 quote_ident on view names (94ba2e449) | 94ba2e449 |
| T19 | OpenID Connect token confusion or session hijacking via misconfigured OIDC provider | remote_auth | OIDC / social auth | user authentication tokens | high | rare | unmitigated | django-allauth OIDC integration | |
| T25 | Cross-site request forgery (CSRF) via state-changing GET endpoints | remote_unauth (through a logged-in victim's browser session) | REST API job cancel; web UI job cancel/fail/toggle_favorite; remote-artifact token delete | job definitions, device control, user authentication tokens | high | possible | unmitigated | Nothing at HEAD. Django's CsrfViewMiddleware and DRF's SessionAuthentication only check CSRF on unsafe methods, so GET requests pass unchecked. The REST API accepts SessionAuthentication (settings/common.py:336). SESSION_COOKIE_SAMESITE is unset, and the Lax default still sends cookies when a browser navigates to a top-level GET link. | lava_rest_app/v02/views.py:525 (cancel is GET-only under DRF 3.18 @action default), lava_server/views.py:198 (token delete, @login_required only), lava_scheduler_app/views.py:2243/2255/2366 (job cancel/fail/toggle_favorite, no method guard, invoked from templates as <a href> links); a session-cookie GET with no CSRF token cancels a job and deletes a token |
| T4 | Cross-site scripting (XSS) via reflected input in web UI | remote_unauth | web UI (GET parameters, tag descriptions) | user sessions, all assets | medium | likely | partially_mitigated | Django auto-escaping; recent fixes for TagsColumn and query_custom templates | fa5e9c0a3 (query_custom XSS), 7c32944cb (TagsColumn XSS) |
| T6 | Information disclosure of private jobs via device status views | remote_unauth | web UI (DeviceTable), XML-RPC API | job definitions, device control | medium | likely | partially_mitigated | Permission-filtered job prefetches; PUBLIC_JOB_WINDOW_DAYS bounds anonymous access to older jobs (679dcd2d6) | b7aa7b802 (private job description leak) |
| T9 | Denial of service via resource exhaustion on job submission or device configuration rendering | remote_auth | job submission, device config rendering | service availability | medium | likely | unmitigated | No rate limiting or size caps found in code; opt-in REQUIRE_LOGIN / REQUIRE_LOGIN_PATHS gating of the query UI (f85c4dfc5); no size/depth limits in the voluptuous schema at HEAD | f85c4dfc5 |
| T15 | Insecure direct object reference (IDOR) on job and device endpoints | remote_auth | REST API, XML-RPC API | job definitions, device configurations, test results | medium | likely | partially_mitigated | Object-level permission checks on recent commits | 3df6fe866, 094570487 |
| T22 | Result forgery and file injection via crafted result log lines | remote_auth (job-token holder) | worker log reporting (`/scheduler/internal/v1/jobs/<id>/logs/`) | database contents, test results | medium | possible | partially_mitigated | Job-token auth, constant-time comparison; yaml_safe_load; map_scanned_results checks required keys and caps metadata at 4096 bytes | v1 bundle upload is gone; JUnit/TAP are output-only (lava_rest_app/v02/views.py). Vector: lava_scheduler_app/views.py:1334 → lava_results_app/dbutils.py:48 builds the metadata filename from attacker-controlled definition/case/level fields |
| T23 | Data exfiltration through notification callback URLs in job definitions | remote_auth | notification callbacks | database contents | medium | possible | partially_mitigated | voluptuous schema validation on submission; note: notifications now carry remote artifact tokens (e960f3604) | e960f3604 |

## 5. Deprioritized

| threat | reason |
|---|---|
| Repudiation: lack of audit logs for device configuration changes | LAVA maintains its own audit LogEntry model (replaced Django's unindexed LogEntry in 619ce6672 for performance); risk is medium and mitigated by existing logging infrastructure |
| Cross-site request forgery (CSRF) on token-authenticated surfaces (XML-RPC API, worker internal API) | XML-RPC is POST-only by protocol and requires token arguments; worker internal API requires a custom lava-token header, which browsers cannot set cross-origin. Web UI unsafe-method requests are CSRF-protected via Django middleware; sign-out is a POST form (7e3e3bd0c, merged). Note: CSRF on session-authenticated GET endpoints isn't deprioritized (tracked as T25) |
| Timing side-channel on token comparison | Crypto-random tokens provide sufficient entropy; constant-time comparison is used on the worker internal API and lava_server/management/commands/lava-publisher.py:289 |
| Man-in-the-middle on internal dispatcher-server communication | Internal communication is assumed to be on trusted lab network; TLS would add complexity. Risk accepted for lab environment |
| Cryptographic key extraction from dispatcher memory | Native code does not handle long-lived cryptographic material; keys are passed as CLI args or env vars |
| Physical access to test devices | Physical security is outside the scope of the software threat model; assumed to be controlled by lab security |
| DNS rebinding against internal lab services | LAVA is typically deployed behind a reverse proxy; DNS rebinding would require browser-based attack from untrusted network |

## 6. Open questions

- Is LAVA typically deployed on publicly accessible networks, or only within trusted lab VLANs?
- Who are the typical job submitters: trusted lab members only, or external CI systems (with lower trust)?
- Is there a WAF, rate limiter, or size limit upstream of the XML-RPC/REST API endpoints? (Confirmed at HEAD: none in LAVA code; deployment-side protection unknown)
- How are dispatcher workers provisioned, and is worker token generation automated or manual?
- What is the risk appetite for DoS via resource exhaustion on job submission or device config rendering?
- Are device configurations (Jinja2 templates) validated before being saved to disk, or accepted as-is?
- Is the Django SECRET_KEY rotated periodically, and how is it distributed to workers?
- Are Celery broker credentials (Redis/RabbitMQ) stored securely and rotated?
- What monitoring and alerting exists for suspicious API usage patterns?
- Are Docker images pulled by dispatcher-host from a private, signed registry, or from public Docker Hub?
- Is the Gunicorn process bound to localhost only, or directly accessible from the lab network?
- How are LDAP credentials (bind DN, password) stored: in env.yaml, in Django settings, or in a secrets manager?
- Is the PostgreSQL database accessible from the dispatcher network, or only from the web server tier?
- Are Celery worker tasks sandboxed (seccomp, namespaces, resource limits), or do they run with the same privileges as the scheduler?

## 7. Provenance

- mode: bootstrap
- date: 2026-10-01
- target: lava @ 5f130b35d
- inputs: git-log + debian changelog mined;
- owner: Fathi Boudra

## 8. Recommended mitigations

| mitigation | threat_ids | closes_class | effort |
|---|---|---|---|
| Add authentication and authorization to the dispatcher-host Unix socket (partially done: uid-0 peer check ecbd68ca8) | T8 | partial | M |
| Implement rate limiting and request size caps on all API endpoints | T9 | partial | M |
| Add size and depth limits on YAML job definitions before parsing (none in code at HEAD) | T9, T20 | partial | S |
| Validate and sanitize device configurations before filesystem write; add schema validation for Jinja2 templates | T2 | yes | M |
| Enable TLS for all internal dispatcher-server and worker communication | T13 | partial | S |
| Enforce HTTPS-only deployments; reject non-HTTPS REST/XML-RPC connections | T21 | yes | S |
| Add comprehensive audit logging for all device configuration changes and job submissions | T5, T6, T2 | partial | S |
| Implement dependency pinning with automated vulnerability scanning (SBOM already present in CI) | T12 | partial | S |
| Sign and verify Docker images before execution by dispatcher-host | T16, T17 | yes | L |
| Add input validation and length limits on all XML-RPC/REST API parameters | T1, T14, T15 | partial | M |
| Add input validation and sanitization for all subprocess argument construction | T1, T18 | partial | M |
| Add seccomp profiles and resource limits to Celery worker tasks | T20 | partial | M |
| Move LDAP group type configuration from eval/exec to a whitelist of allowed classes | T7 | yes | S |
| Make all state-changing endpoints POST-only: @action(methods=("post",)) on REST job cancel, @require_POST on token delete and web-UI job cancel/fail/toggle_favorite, convert <a href> triggers to CSRF-tokened POST forms; add CI guard rejecting routed views that change state without a method guard. | T25 | yes | S |
| Enforce OIDC state parameter validation and PKCE for all social auth flows | T19 | partial | S |
| Validate and sanitize worker-reported result lines and metadata file names before DB row / filesystem write | T22 | partial | S |
| Conduct regular penetration testing focused on the XML-RPC and REST APIs | T1, T3, T5, T11, T14 | partial | L |
