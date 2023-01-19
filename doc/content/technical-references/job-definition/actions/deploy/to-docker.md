# Docker

## Docker deploy

Download the given docker image:

```yaml
actions:
- deploy:
    to: docker
    os: debian
    image: debian:sid
```

## Local images

The deploy action can use local docker images, just add `local: true`:

```yaml
actions:
- deploy:
    to: docker
    os: debian
    image:
      name: debian:sid
      local: true
```

