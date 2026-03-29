# Production Deployment Guide

Discovery Intelligence is designed to run cleanly as a single-VM deployment on Google Cloud while you continue developing from your MacBook.

For a command-by-command first-time setup, use [docs/google-cloud-vm-checklist.md](/Users/lolet/discovery_system/docs/google-cloud-vm-checklist.md).
For the current budget-based VM auto-stop guardrail, use [docs/cost-control.md](/Users/lolet/discovery_system/docs/cost-control.md).

This deployment mode uses:

- one Google Compute Engine VM
- one Docker Compose stack on that VM
- one app container
- one PostgreSQL container
- a persistent host directory mounted to `/app/data` for uploads, reports, and artifact blobs
- a persistent host directory for PostgreSQL data
- GHCR for versioned container images
- GitHub Actions to deploy from GitHub to the VM over SSH

## Recommended Workflow

The intended development and release flow is:

1. Make and test changes on your MacBook.
2. Push the changes from your MacBook to GitHub.
3. GitHub Actions runs CI.
4. GitHub Actions builds a container image and publishes it to GHCR, tagged with the commit SHA.
5. GitHub Actions copies `docker-compose.yml` and `scripts/` to the Google Cloud VM.
6. GitHub Actions writes the production `.env` file from a GitHub secret.
7. GitHub Actions runs `scripts/deploy.sh <commit-sha>` over SSH on the VM.
8. The VM pulls the new image, starts PostgreSQL if needed, runs migrations, restarts the app, and checks `/healthz`.

This gives you the exact flow you asked for:

- MacBook -> GitHub
- GitHub -> Google Cloud VM

## Server Layout

Recommended server directory structure:

```text
/srv/discovery-intelligence/
├── docker-compose.yml
├── .env
├── scripts/
├── data/
└── postgres/
```

- `docker-compose.yml` and `scripts/` come from this repo.
- `.env` contains production environment variables and must never be committed.
- `data/` is the persistent bind-mounted artifact directory. Do not delete it during deploys.
- `postgres/` stores PostgreSQL data for the single-VM database container.

## Required Environment Variables

Copy `.env.example` to `.env` and set at minimum:

- `DISCOVERY_IMAGE_REPOSITORY`
- `DISCOVERY_IMAGE_TAG`
- `DISCOVERY_DATABASE_URL`
- `DISCOVERY_POSTGRES_DB`
- `DISCOVERY_POSTGRES_USER`
- `DISCOVERY_POSTGRES_PASSWORD`
- `DISCOVERY_POSTGRES_DATA_DIR`
- `DISCOVERY_SESSION_SECRET`
- `DISCOVERY_APP_BASE_URL`
- `DISCOVERY_PERSISTENT_DATA_DIR`
- `DISCOVERY_HOST_PORT`
- `PADDLE_API_KEY`
- `PADDLE_WEBHOOK_SECRET`
- `PADDLE_PRO_PRICE_ID`

Recommended production values:

- `DISCOVERY_APP_ENV=production`
- `DISCOVERY_AUTO_APPLY_MIGRATIONS=false`
- `WEB_CONCURRENCY=1`
- `DISCOVERY_ALLOWED_ARTIFACT_ROOTS=/app/data`
- `DISCOVERY_SESSION_SAME_SITE=lax`
- `DISCOVERY_DATABASE_URL=postgresql+psycopg://discovery:YOUR_PASSWORD@db:5432/discovery`

`WEB_CONCURRENCY=1` is deliberate for now because analysis jobs still run in-process.
`DISCOVERY_SESSION_SAME_SITE=lax` is recommended once Paddle hosted billing is enabled so authenticated browser sessions survive the top-level return navigation back from Paddle.

## First-Time Google Cloud VM Setup

1. Create a Linux VM in Google Compute Engine and reserve a static external IP for it.
2. Point your DNS name at that static IP.
3. Install Docker Engine and the Docker Compose plugin on the VM.
4. Create the deployment directory, for example `/srv/discovery-intelligence`.
5. Copy `docker-compose.yml` and `scripts/` from this repo into that directory.
6. Create `/srv/discovery-intelligence/.env` from `.env.example`.
7. Create the persistent directories configured by:
   - `DISCOVERY_PERSISTENT_DATA_DIR`
   - `DISCOVERY_POSTGRES_DATA_DIR`
8. Log the server into GHCR:

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
```

9. Run the first deploy:

```bash
cd /srv/discovery-intelligence
./scripts/deploy.sh latest
```

10. In Paddle, configure the production or sandbox webhook destination to point at:

```text
https://YOUR_APP_HOST/api/webhooks/paddle
```

Use the same signing secret in `PADDLE_WEBHOOK_SECRET`.

## GitHub Actions Secrets

The deploy workflow expects these repository or environment secrets:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_PRIVATE_KEY`
- `DEPLOY_PATH`
- `DISCOVERY_ENV_FILE`
- `GHCR_USERNAME`
- `GHCR_READ_TOKEN`

Use your Google Cloud VM public IP or DNS name for `DEPLOY_HOST`.

`DISCOVERY_ENV_FILE` should be the full multi-line contents of the production `.env` file.
This file must include the PostgreSQL settings for the local VM database and the Paddle billing variables used by the app.

## Manual Migration

If you need to run migrations without restarting the app:

```bash
cd /srv/discovery-intelligence
./scripts/migrate.sh
```

The migration script starts the local PostgreSQL container if needed and waits for it before running Alembic.

## Roll Forward / Roll Back

Images are published with commit-SHA tags. To deploy or roll back to a specific image:

```bash
cd /srv/discovery-intelligence
./scripts/deploy.sh <commit-sha>
```

This changes the app image without deleting the persistent `data/` or `postgres/` directories.

Do not run Alembic downgrades automatically as part of rollback. Rollbacks should only move the app image back to a previously compatible release.

## Backup And Recovery

Because the full system lives on one VM, you should protect both host directories:

- `DISCOVERY_PERSISTENT_DATA_DIR`
- `DISCOVERY_POSTGRES_DATA_DIR`

At minimum, schedule regular VM disk snapshots or regular PostgreSQL backups plus file backups for `/app/data`.

## Current Limitations

- The app is still a single-server deployment.
- Background analysis jobs are still in-process threads.
- Artifact blobs remain on the server filesystem instead of object storage.
- The VM is a single failure domain unless you add backups and restore procedures.
- There is no separate worker tier, queue, or HA setup yet.
- There is no full observability stack yet; rely on container logs and `/healthz`.
- Paddle is the external Merchant of Record, but product entitlements are still enforced from the app's local workspace billing state after webhook synchronization.
