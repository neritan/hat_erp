# HAT dev environment (Docker Compose)

Runs ERPNext + HAT on one host: nginx, gunicorn, websocket, two workers,
scheduler, MariaDB and two Redis instances.

The shared dev server on Hetzner is deployed automatically on every merge to `dev`; see
[`deploy/hetzner/README.md`](../hetzner/README.md). The steps below are for running it on any host by hand.

## First start

```bash
cd deploy/dev
cp .env.example .env     # set ADMIN_PASSWORD and DB_ROOT_PASSWORD
docker compose up -d --build
docker compose logs -f create-site   # wait until the site is created
```

Open `http://<host>:8080` and log in as `Administrator`.

## Update after code changes

```bash
docker compose up -d --build   # rebuilds the image; create-site runs `migrate`
```

## Useful commands

```bash
docker compose exec backend bench --site hat.localhost console
docker compose exec backend bench --site hat.localhost backup --with-files
docker compose down        # stop (data kept in volumes)
docker compose down -v     # stop and DELETE all data
```
