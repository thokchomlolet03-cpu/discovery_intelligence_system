# Google Cloud VM Checklist

This runbook is for the deployment shape we finalized:

- develop on your MacBook
- push changes to GitHub
- let GitHub Actions deploy to one Google Cloud VM
- run the full stack on that VM for now

## Local Tools

Recommended local setup on your MacBook:

- Google Cloud CLI (`gcloud`)
- VS Code
- VS Code Remote SSH extension

Cloud Code is optional. It can manage Compute Engine VMs, but its strongest workflow is around Cloud Run and GKE. For this single-VM setup, `gcloud` plus Remote SSH is the simpler default.

## Variables

Replace these values before running commands:

```bash
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export ZONE="us-central1-a"
export INSTANCE_NAME="discovery-prod"
export STATIC_IP_NAME="discovery-prod-ip"
export MACHINE_TYPE="e2-standard-4"
export BOOT_DISK_SIZE="100GB"
export DEPLOY_USER="YOUR_LINUX_USERNAME"
export DEPLOY_PATH="/srv/discovery-intelligence"
```

`e2-standard-4` is a reasonable starting point for this app, but treat that as an initial recommendation rather than a hard requirement.

## Step 1: Authenticate Locally

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project "$PROJECT_ID"
gcloud config set compute/region "$REGION"
gcloud config set compute/zone "$ZONE"
```

## Step 2: Reserve A Static IP

```bash
gcloud compute addresses create "$STATIC_IP_NAME" \
  --region "$REGION"

gcloud compute addresses describe "$STATIC_IP_NAME" \
  --region "$REGION"
```

Save the returned IP address. You will use it for DNS and for the GitHub `DEPLOY_HOST` secret.

## Step 3: Create The VM

```bash
gcloud compute instances create "$INSTANCE_NAME" \
  --zone "$ZONE" \
  --machine-type "$MACHINE_TYPE" \
  --create-disk=auto-delete=yes,boot=yes,device-name="$INSTANCE_NAME",image-family=ubuntu-2204-lts,image-project=ubuntu-os-cloud,mode=rw,size="$BOOT_DISK_SIZE",type=pd-balanced \
  --address="$STATIC_IP_NAME" \
  --tags=discovery-app \
  --metadata=enable-oslogin=TRUE
```

## Step 4: Open Network Access

Start simple:

```bash
gcloud compute firewall-rules create discovery-app-web \
  --network=default \
  --allow=tcp:80,tcp:443,tcp:8000 \
  --target-tags=discovery-app
```

This keeps port `8000` available for the initial phase. Later, you can put Nginx or Caddy in front and keep only `80` and `443` public.

## Step 5: Prepare SSH Access

Test direct access first:

```bash
gcloud compute ssh "$INSTANCE_NAME" --zone "$ZONE"
```

Then populate your local SSH config so VS Code Remote SSH can reuse it:

```bash
gcloud compute config-ssh
```

If you want the IDE connection path, install the Remote SSH extension:

```bash
code --install-extension ms-vscode-remote.remote-ssh
```

Then in VS Code:

1. Open the Command Palette.
2. Run `Remote-SSH: Connect to Host`.
3. Choose the host that `gcloud compute config-ssh` added.

## Step 6: Install Docker On The VM

SSH into the VM and run:

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
newgrp docker
docker --version
docker compose version
```

## Step 7: Prepare The VM Directory

On the VM:

```bash
sudo mkdir -p "$DEPLOY_PATH"
sudo chown "$USER":"$USER" "$DEPLOY_PATH"
mkdir -p "$DEPLOY_PATH/data"
mkdir -p "$DEPLOY_PATH/postgres"
```

## Step 8: Prepare The Production `.env`

Create a production `.env` locally from [.env.example](/Users/lolet/discovery_system/.env.example).

At minimum, fill in:

- `DISCOVERY_IMAGE_REPOSITORY`
- `DISCOVERY_IMAGE_TAG`
- `DISCOVERY_APP_BASE_URL`
- `DISCOVERY_HOST_PORT`
- `DISCOVERY_PERSISTENT_DATA_DIR`
- `DISCOVERY_POSTGRES_DATA_DIR`
- `DISCOVERY_POSTGRES_DB`
- `DISCOVERY_POSTGRES_USER`
- `DISCOVERY_POSTGRES_PASSWORD`
- `DISCOVERY_DATABASE_URL`
- `DISCOVERY_SESSION_SECRET`
- Paddle values if billing is enabled

For this single-VM setup, the database URL should look like:

```bash
DISCOVERY_DATABASE_URL=postgresql+psycopg://discovery:YOUR_DB_PASSWORD@db:5432/discovery
```

Recommended path values:

```bash
DISCOVERY_PERSISTENT_DATA_DIR=/srv/discovery-intelligence/data
DISCOVERY_POSTGRES_DATA_DIR=/srv/discovery-intelligence/postgres
```

## Step 9: Configure GitHub Secrets

Add these repository or environment secrets in GitHub:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_PRIVATE_KEY`
- `DEPLOY_PATH`
- `DISCOVERY_ENV_FILE`
- `GHCR_USERNAME`
- `GHCR_READ_TOKEN`

Suggested values:

- `DEPLOY_HOST`: your VM static IP or DNS name
- `DEPLOY_USER`: your Linux username on the VM
- `DEPLOY_PATH`: `/srv/discovery-intelligence`
- `DISCOVERY_ENV_FILE`: the full multi-line contents of your production `.env`

For `DEPLOY_SSH_PRIVATE_KEY`, use the private key that matches the SSH identity you will use to access the VM from GitHub Actions.

## Step 10: First Deployment

Once the GitHub secrets are set:

1. Push to `main`.
2. Wait for `Build and Publish` to finish.
3. Wait for `Deploy` to start automatically.

You can also trigger deploy manually from GitHub Actions if needed.

## Step 11: Verify The App

From your MacBook:

```bash
curl -fsS "http://YOUR_VM_IP:8000/healthz"
```

If you set a domain and HTTPS later, switch the healthcheck URL accordingly.

On the VM:

```bash
cd "$DEPLOY_PATH"
docker compose --env-file .env ps
docker compose --env-file .env logs --tail=100 app
docker compose --env-file .env logs --tail=100 db
```

## What I Still Need From You

To finish the cloud-side setup with you, send me:

- your Google Cloud `PROJECT_ID`
- your chosen `REGION`
- your chosen `ZONE`
- the Linux username you want on the VM
- the domain or subdomain you want for the app, if any
