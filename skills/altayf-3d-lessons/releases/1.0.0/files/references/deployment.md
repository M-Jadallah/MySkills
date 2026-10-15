# Deployment — Docker Compose on Coolify

## Project layout delivered to the user

```
/mnt/agents/output/app
├── index.html
├── styles.css
├── js/engine.js      (fixed engine — do not modify per lesson)
├── js/app.js         (lesson wiring)
├── Dockerfile
├── docker-compose.yml
└── nginx.conf
```

**Zero dependencies**: the engine is a self-contained pseudo-3D canvas renderer — no Three.js, no CDN, no build step. Everything works offline inside the container. Do not add external script/style CDNs unless the user asks.

## Docker files (template already includes them)

- `Dockerfile`: `nginx:alpine`, copies the site into `/usr/share/nginx/html`, writes `/usr/share/nginx/html/health.json`, and defines a `HEALTHCHECK` using busybox `wget` against `http://localhost/health.json`. Coolify rejects unhealthy containers — this endpoint keeps the deployment green.
- `nginx.conf`: listens on 80, gzip on, short cache for `css|js`, no-cache for `health.json` and `index.html`.
- `docker-compose.yml`: builds from `.`, exposes port 80 (Coolify maps its own domain/port), `restart: unless-stopped`.

## Coolify steps to hand to the user

1. Push the project folder to the Git repo Coolify watches.
2. In Coolify: resource type **Docker Compose** (or Dockerfile — both work), port `80`.
3. Set the domain; deploy. Healthcheck path `/health.json` is already served.
4. The site is fully static — no environment variables needed.
