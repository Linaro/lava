# Anubis anti-bot protection

Because LAVA contains large number of kernel boot logs it is frequently scrapped by
AI bots which overloads the server and the database. To protect LAVA it is recommended
employing bot protection services such as [Anubis](https://anubis.techaro.lol/).

Depending on your reverse proxy configuration the Anubis deployment will differ.
Consult Anubis documentation for deployment details.

## Recommended Anubis configuration

LAVA has several internal HTTP endpoints which are used for XMLRPC and communication
between workers and server. [Anubis bot policy](https://anubis.techaro.lol/docs/admin/policies/)
should account for those and bypass the challenge.

Here is an example of a policy that requires challenge everywhere except for internal and API paths:

```yaml
---
bots:
  - import: (data)/meta/default-config.yaml
  - name: LAVA scheduler internal
    path_regex: '^/scheduler/internal'
    action: ALLOW
  - name: LAVA XLMRPC
    path_regex: '^/RPC2'
    action: ALLOW
  - name: LAVA healthz
    path_regex: '^/v1/healthz/$'
    action: ALLOW
  - name: LAVA REST API
    path_regex: '^/api'
    action: ALLOW
  - name: LAVA OIDC (Open ID Connect)
    path_regex: '^/oidc'
    action: ALLOW
  # Everything else must pass challenge
  - name: base
    expression: 'true'
    action: CHALLENGE
    challenge:  # Adjust to your preference
      difficulty: 6
      algorithm: fast
```

