# HAT dev on Hetzner Cloud: one-time setup

Every push (merge) to `dev` runs `.github/workflows/deploy-dev.yml`:

1. **build**: builds the image for linux/amd64 and pushes it to Docker Hub as
   `neritan/hat:dev` and `neritan/hat:<commit sha>`.
2. **deploy**: copies [`deploy/dev/compose.yaml`](../dev/compose.yaml) to the server
   (`/opt/hat-dev/compose.yaml`) over SSH, pins the new image in `/opt/hat-dev/.env`, logs in to
   Docker Hub, pulls it, runs `docker compose up -d`, waits for `create-site` (this
   creates the site on the first deploy and runs `bench migrate` after that), and restarts the app
   containers.
3. **smoke test**: checks that `DEV_URL/api/method/ping` answers.

You can also run it by hand: GitHub → Actions → *Deploy dev* → *Run workflow*.

## Current dev server

| | |
|---|---|
| Host | `2.31.138.132` (`ssh hetzner` as root, `deploy` user for GitHub Actions) |
| Server | x86_64, 2 vCPU / 4 GB RAM + 4 GB swap / 75 GB, Falkenstein, Ubuntu 26.04 |
| Set up | Docker 29.9, Compose v5.7, user `deploy` (docker group), `/opt/hat-dev/.env` with random passwords |
| Deploy key | `~/.ssh/hat-dev-deploy` in the devcontainer (public key in `/home/deploy/.ssh/authorized_keys`) |

Steps 1–3 below are already done for this server. Use them only to rebuild it or create another
one. Step 4 (GitHub) is still needed.

## 1. Two SSH keys

- **Your own key** for logging in, for example `~/.ssh/id_ed25519.pub`.
- **A deploy key** for GitHub Actions. Create it on your machine:

  ```bash
  ssh-keygen -t ed25519 -f ~/.ssh/hat-dev-deploy -N "" -C "github-actions hat dev"
  ```

## 2. Create the server

| Setting | Value |
|---|---|
| Type | x86 with **4 GB RAM or more** (the pipeline builds `linux/amd64`). 8 GB is more comfortable. |
| Location | Falkenstein (`fsn1`), Nuremberg (`nbg1`) or Helsinki (`hel1`) |
| Image | Ubuntu 24.04 |
| SSH keys | **both** keys from step 1 |
| Firewall | inbound TCP **22**, **80**, **443** (and **8080** while you still use plain HTTP) from anywhere |
| Cloud config | contents of [`cloud-init.yaml`](cloud-init.yaml) |

If you pick an Arm server (CAX) instead, change the `build` job in the workflow to
`runs-on: ubuntu-24.04-arm` and `platforms: linux/arm64`.

### With the Console
console.hetzner.cloud → your project → **Servers → Add server**. Fill in the table above. To make
the firewall: **Firewalls → Create firewall**, add inbound rules for TCP 22 and TCP 8080, then
apply it to the server. Paste `cloud-init.yaml` into **Cloud config**.

### Or with the `hcloud` CLI
Install it (`brew install hcloud`, or download a release from github.com/hetznercloud/cli), then
create an API token (Project → Security → API tokens, *Read & Write*):

```bash
hcloud context create hat            # paste the API token
hcloud ssh-key create --name me             --public-key-from-file ~/.ssh/id_ed25519.pub
hcloud ssh-key create --name hat-dev-deploy --public-key-from-file ~/.ssh/hat-dev-deploy.pub

hcloud firewall create --name hat-dev
hcloud firewall add-rule hat-dev --direction in --protocol tcp --port 22   --source-ips 0.0.0.0/0 --source-ips ::/0
hcloud firewall add-rule hat-dev --direction in --protocol tcp --port 8080 --source-ips 0.0.0.0/0 --source-ips ::/0
hcloud firewall add-rule hat-dev --direction in --protocol tcp --port 80   --source-ips 0.0.0.0/0 --source-ips ::/0
hcloud firewall add-rule hat-dev --direction in --protocol tcp --port 443  --source-ips 0.0.0.0/0 --source-ips ::/0

hcloud server create --name hat-dev --type cx32 --image ubuntu-24.04 --location fsn1 \
  --ssh-key me --ssh-key hat-dev-deploy --firewall hat-dev \
  --user-data-from-file deploy/hetzner/cloud-init.yaml

hcloud server ip hat-dev
```

## 3. Finish the server

```bash
IP=<server ip>
ssh deploy@$IP 'cloud-init status --wait && docker --version'   # takes a few minutes the first time
scp deploy/dev/.env.example deploy@$IP:/opt/hat-dev/.env
ssh deploy@$IP nano /opt/hat-dev/.env    # set strong ADMIN_PASSWORD and DB_ROOT_PASSWORD
ssh-keyscan -H $IP > hat-dev-known-hosts
```

The `.env` file stays only on the server. Leave `HAT_IMAGE` out, because the pipeline writes it.

## 4. GitHub secrets

**Docker Hub** (used by both jobs). First create a token: hub.docker.com → Account settings →
Personal access tokens → *Generate new token*, with access **Read & Write**. Then go to
github.com/neritan/hat_erp → Settings → Secrets and variables → Actions → **Repository secrets**:

| Name | Value |
|---|---|
| `DOCKERHUB_USERNAME` | `neritan` |
| `DOCKERHUB_TOKEN` | the token (not your Docker Hub password) |

**Environment `dev`** (used by the deploy job): Settings → Environments → **New environment**
`dev`. Under *Deployment branches*, choose **Selected branches** and add `dev`.

| Kind | Name | Value |
|---|---|---|
| Variable | `DEV_URL` | `https://<server ip>` (with HTTPS, see below), else `http://<server ip>:8080` |
| Variable | `DEPLOY_DIR` | `/opt/hat-dev` (optional; this is the default) |
| Secret | `DEPLOY_HOST` | server IP |
| Secret | `DEPLOY_USER` | `deploy` |
| Secret | `DEPLOY_SSH_KEY` | contents of `~/.ssh/hat-dev-deploy` (the **private** key) |
| Secret | `DEPLOY_KNOWN_HOSTS` | contents of `hat-dev-known-hosts` |

## HTTPS

`deploy/dev/compose.yaml` has an optional Caddy service (profile `https`) that serves the site on
port 443 with a Let's Encrypt certificate and redirects port 80 to it. For a server without a
domain, Let's Encrypt issues certificates for the IP address itself; they last about six days and
Caddy renews them automatically.

1. Open TCP 80 and 443 in the Hetzner firewall (see the `hcloud` commands above).
2. Add to `/opt/hat-dev/.env` on the server:

   ```
   COMPOSE_PROFILES=https
   PUBLIC_HOST=<server ip or domain>
   TRUST_UPSTREAM_FORWARDED_PROTO=on
   HTTP_PORT=127.0.0.1:8081
   ```

   `HTTP_PORT` moves nginx off port 8080, so Caddy can take it and redirect old
   `http://<server>:8080` links to HTTPS. nginx stays reachable from the server itself on 8081.

3. Set the GitHub variable `DEV_URL` to `https://<server ip or domain>`.
4. Deploy (merge into `dev` or *Run workflow*). Check the certificate with
   `docker compose logs https`.

Keep port 8080 open in the firewall if old `http://<server>:8080` links should keep working:
they are redirected to HTTPS. Remove it once nobody uses them.

## 5. First deploy

Merge into `dev`, or click *Run workflow*. The first run takes longer because `create-site`
installs ERPNext and HAT. Then open `DEV_URL` and log in as `Administrator` with
`ADMIN_PASSWORD` from the server's `.env`.

To change the server setup (services, ports, workers), edit `deploy/dev/compose.yaml` in the repo,
not on the server. The next deploy copies it over. Only `.env` is kept on the server.

Demo data (optional):

```bash
ssh deploy@$IP 'cd /opt/hat-dev && docker compose exec backend bench --site hat.localhost execute hat.setup.demo.create_demo'
```

## Troubleshooting

```bash
ssh deploy@$IP
cd /opt/hat-dev
docker compose ps
docker compose logs -f create-site backend
docker compose exec backend bench --site hat.localhost console
```

- *Permission denied (publickey)* in the deploy job: the deploy key wasn't selected when the
  server was created. Add `~/.ssh/hat-dev-deploy.pub` to `/home/deploy/.ssh/authorized_keys`.
- *Site not reachable*: check that the Hetzner firewall allows TCP 8080 and is applied to the server.
- *unauthorized* on `docker login` or the push: `DOCKERHUB_TOKEN` is wrong or expired, or it is
  read-only. Pushing needs a *Read & Write* token.
