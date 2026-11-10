# Anubis scraping protection

Since LAVA contains a large number of test logs it may be frequently scanned by
AI scrapers which can overload the server and the database. To prevent resource
exhaustion of a LAVA instance it is recommended to employ scraper protection
services such as [Anubis](https://anubis.techaro.lol/).

Depending on your reverse proxy configuration, the Anubis deployment may differ.
Consult the [Anubis deployment environments documentation for details](https://anubis.techaro.lol/docs/category/environments).

## Recommended Anubis policy configuration

LAVA has several internal HTTP endpoints which are used for XML-RPC and communication
between workers and the server. The [Anubis bot policy](https://anubis.techaro.lol/docs/admin/policies/)
should account for those and bypass the challenge.

The following is an example of a policy that requires a challenge everywhere
except for internal worker communication and API paths:

```yaml
---
bots:
  # Move default policy import if you want to exclude API paths
  # from default block rules.
  - import: (data)/meta/default-config.yaml
  - name: LAVA scheduler internal
    path_regex: '^/scheduler/internal'
    action: ALLOW
  - name: LAVA XML-RPC
    path_regex: '^/RPC2'
    action: ALLOW
  - name: LAVA healthz
    path_regex: '^/v1/healthz/$'
    action: ALLOW
  - name: lava-publisher
    path_regex: '^/ws/'
    action: ALLOW
  - name: LAVA REST API
    path_regex: '^/api'
    action: ALLOW
  # Everything else must pass challenge
  - name: base
    expression: 'true'
    action: CHALLENGE
    challenge:  # Adjust to your preference
      difficulty: 6
      algorithm: fast
```
