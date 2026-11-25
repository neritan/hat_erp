# Hatix: dev server and deployment

*Meeting 26 Nov 2026 · state on 25 Nov 2026*

## In one line
Every merge to `dev` builds and deploys automatically to a Hetzner server, which runs over HTTPS. The latest merge (PR #11) is live.

## The dev server
| | |
|---|---|
| Address | **https://2.31.138.132** (old links to `http://2.31.138.132:8080` redirect to HTTPS) |
| Provider | Hetzner Cloud, Falkenstein (Germany) |
| Size | 2 vCPU, 4 GB RAM + 4 GB swap, 75 GB disk (20% used) |
| Software | ERPNext / Frappe **v16** + Hatix app, in Docker |
| Files and pictures | Hetzner Object Storage (S3), private bucket |
| Running now | build `9348895` (merge of PR #11, 25 Nov) |

## How a change goes live
1. A developer opens a pull request into `dev`, and it is reviewed and merged.
2. GitHub Actions **builds** the Hatix image and pushes it to Docker Hub (`neritan/hat`, tagged by commit).
3. GitHub Actions **deploys** it to the server over SSH: it pulls the image, updates the database (`migrate`) and restarts the app.
4. A **smoke test** checks that the site answers.

- No manual steps are needed. The deploy can also be started by hand from GitHub (Actions → *Deploy dev* → *Run workflow*).
- Each deploy is pinned to a commit, so going back to an earlier version means deploying that commit again.

## What was set up
- **Automatic pipeline**: Docker image and GitHub Actions workflow.
- **Server**: Hetzner server with Docker and a `deploy` user for GitHub.
- **HTTPS with Caddy**: a free Let's Encrypt certificate for the IP address.
  - The certificate lasts about 6 days and Caddy renews it automatically.
  - A fix lets browsers that connect by IP get the certificate.
- **Old HTTP links**: `:8080` now redirects to HTTPS, and the app itself is no longer reachable directly from outside.
- **S3 storage** for uploads, so files survive server rebuilds.
- **Setup guide** to rebuild the server or create a new one: `deploy/hetzner/README.md` and `cloud-init.yaml`.

## Known limits / to decide
1. **No domain name yet.** The site runs on an IP address.
   - A domain (for example `dev.hatix.al`) would give a normal 90-day certificate and a nicer link.
   - It is needed before any production setup.
2. **No outgoing email.** Password reset, welcome emails and email notifications don't go out. We need an SMTP account.
3. **The server runs Frappe 16; local development runs Frappe 17.**
   - Small differences exist. For example, the *Change Password* button is missing on the server, so passwords are set from the user's **Settings → Set New Password** field instead.
   - Should we upgrade the server image?
4. **Backups**: files are in S3, but no off-server database backup has been set up as part of this work. Should we add scheduled database backups to S3?
5. **Production**: only a dev environment exists today. Production needs a plan: separate server, domain, backups, monitoring and access rules.
6. **Security housekeeping**:
   - Rotate the S3 keys: they were displayed once during troubleshooting.
   - Change the demo users' passwords before external use.
   - Remove the duplicate `HTTP_PORT=8080` line in the server's `.env`.
7. **Firewall**: port 8080 stays open while old links are in use. Close it once nobody uses them.
