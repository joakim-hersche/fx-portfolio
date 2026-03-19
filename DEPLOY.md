# Deployment Guide: Oracle Cloud Free Tier + Cloudflare

## Prerequisites

- An Oracle Cloud account (sign up at cloud.oracle.com — credit card required but never charged for always-free resources)
- A domain name (any registrar — Cloudflare, Namecheap, etc.)
- A Cloudflare account (free tier)
- SSH key pair on your Mac (`~/.ssh/id_rsa.pub` — if you don't have one, run `ssh-keygen -t ed25519`)

---

## Part 1: Provision Oracle Cloud VM

### 1.1 Create the instance

1. Log in to Oracle Cloud Console: https://cloud.oracle.com
2. Navigate to **Compute > Instances > Create Instance**
3. Configure:
   - **Name**: `market-dashboard`
   - **Placement**: Leave default (your home region)
   - **Image**: **Canonical Ubuntu 22.04** (click "Change image" > Ubuntu > 22.04 Minimal aarch64)
   - **Shape**: Click "Change shape" > **Ampere** > **VM.Standard.A1.Flex**
     - OCPUs: **4** (max free)
     - Memory: **24 GB** (max free)
   - **Networking**: Create new VCN or use existing. Ensure "Assign a public IPv4 address" is checked.
   - **SSH keys**: Upload your `~/.ssh/id_rsa.pub` (or paste the contents)
4. Click **Create**

If you get an "Out of capacity" error, try a different availability domain or try again later (Oracle's free tier capacity fluctuates). Some people use retry scripts — search "oci free tier retry script" if needed.

### 1.2 Note the public IP

Once the instance is running, copy the **Public IP** from the instance details page. You'll need this for SSH, Cloudflare DNS, and firewall rules.

### 1.3 Open port 8080 in Oracle's security list

Oracle blocks all inbound traffic by default except SSH (22). You must explicitly open port 8080.

1. From your instance details, click the **Subnet** link under "Primary VNIC"
2. Click the **Security List** (usually "Default Security List for ...")
3. Click **Add Ingress Rules**:
   - Source CIDR: `0.0.0.0/0`
   - Destination Port Range: `8080`
   - Description: `Market Dashboard HTTP`
4. Click **Add Ingress Rules**

---

## Part 2: Set up the VM

SSH into your instance (default user is `ubuntu`):

```bash
ssh ubuntu@<YOUR_PUBLIC_IP>
```

### 2.1 Update the system

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2 Open port 8080 in iptables

Oracle's Ubuntu images have iptables rules that block traffic even after the security list allows it:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT
sudo netfilter-persistent save
```

### 2.3 Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com | sudo sh

# Add your user to the docker group (avoids needing sudo)
sudo usermod -aG docker ubuntu

# Log out and back in for group change to take effect
exit
```

SSH back in:

```bash
ssh ubuntu@<YOUR_PUBLIC_IP>
```

Verify Docker works:

```bash
docker --version
```

### 2.4 Clone the repo and build

```bash
git clone https://github.com/<YOUR_USERNAME>/market-dashboard.git
cd market-dashboard
docker build -t market-dashboard .
```

### 2.5 Generate a storage secret

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy the output — you'll use it in the next step. This secret is used to encrypt user portfolio data and sign session cookies. If you change it later, all existing encrypted portfolios become unreadable.

### 2.6 Run the container

```bash
docker run -d \
  --name market-dashboard \
  --restart unless-stopped \
  -p 8080:8080 \
  -v market-dashboard-data:/app/.nicegui \
  -e STORAGE_SECRET="<PASTE_YOUR_SECRET_HERE>" \
  market-dashboard
```

Flags explained:
- `-d` — run in background
- `--restart unless-stopped` — auto-restart on crash or VM reboot
- `-p 8080:8080` — map host port to container port
- `-v market-dashboard-data:/app/.nicegui` — persist user data in a Docker volume
- `-e STORAGE_SECRET` — encryption key for portfolio data

### 2.7 Verify it's running

```bash
# Check container status
docker ps

# Check logs
docker logs market-dashboard

# Test HTTP response
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080
# Should print: 200
```

You can also visit `http://<YOUR_PUBLIC_IP>:8080` in your browser (no HTTPS yet).

---

## Part 3: Set up Cloudflare for HTTPS

### 3.1 Add your domain to Cloudflare

1. Log in to https://dash.cloudflare.com
2. Click **Add a site** > enter your domain > select **Free** plan
3. Cloudflare will scan existing DNS records. Review and continue.
4. Cloudflare gives you two nameservers (e.g., `anna.ns.cloudflare.com`, `bob.ns.cloudflare.com`)
5. Go to your domain registrar and **change the nameservers** to the ones Cloudflare provided
6. Wait for propagation (usually 5-30 minutes, can take up to 24h)

### 3.2 Add DNS record

In Cloudflare dashboard for your domain:

1. Go to **DNS > Records**
2. Add a record:
   - Type: **A**
   - Name: `dashboard` (or `@` for root domain, or whatever subdomain you want)
   - IPv4 address: `<YOUR_ORACLE_PUBLIC_IP>`
   - Proxy status: **Proxied** (orange cloud ON — this is what gives you HTTPS)
   - TTL: Auto
3. Click **Save**

### 3.3 Configure SSL/TLS

1. Go to **SSL/TLS > Overview**
2. Set encryption mode to **Full** (not "Full (strict)" — we don't have a valid cert on the origin)

This means:
- Browser -> Cloudflare: encrypted (HTTPS with Cloudflare's certificate)
- Cloudflare -> Oracle VM: encrypted (Cloudflare accepts the self-signed/unsigned connection)

### 3.4 Force HTTPS

1. Go to **SSL/TLS > Edge Certificates**
2. Enable **Always Use HTTPS** (redirects HTTP to HTTPS)

### 3.5 Enable WebSocket support

WebSockets are enabled by default on Cloudflare free tier. Verify:

1. Go to **Network**
2. Confirm **WebSockets** is ON

### 3.6 Create an origin rule to route port 443 -> 8080

By default, Cloudflare proxies to port 80 or 443 on your origin. Your app runs on 8080. You need to tell Cloudflare to connect to port 8080.

1. Go to **Rules > Origin Rules**
2. Click **Create rule**:
   - Rule name: `Route to 8080`
   - If: **Hostname equals** `dashboard.yourdomain.com`
   - Then: **Destination Port** > Override to `8080`
3. Click **Deploy**

### 3.7 Test

Visit `https://dashboard.yourdomain.com` in your browser. You should see the Market Dashboard with a valid HTTPS certificate.

---

## Updating the app

When you push new code:

```bash
ssh ubuntu@<YOUR_PUBLIC_IP>
cd market-dashboard
git pull
docker build -t market-dashboard .
docker stop market-dashboard
docker rm market-dashboard
docker run -d \
  --name market-dashboard \
  --restart unless-stopped \
  -p 8080:8080 \
  -v market-dashboard-data:/app/.nicegui \
  -e STORAGE_SECRET="<YOUR_SECRET>" \
  market-dashboard
```

The `-v market-dashboard-data:/app/.nicegui` volume persists between container recreations, so user portfolios survive updates.

---

## Troubleshooting

**Can't reach the app from browser:**
1. Check container is running: `docker ps`
2. Check container logs: `docker logs market-dashboard`
3. Check iptables: `sudo iptables -L INPUT -n --line-numbers` (port 8080 should be ACCEPT)
4. Check Oracle security list has the ingress rule for port 8080
5. Check Cloudflare origin rule routes to port 8080

**yfinance rate limiting:**
If you see errors fetching stock data, Yahoo may be throttling the Oracle IP. Edit `src/cache.py` and increase TTL values:
- `short_cache`: 900 -> 3600 (15min -> 1hr)
- `long_cache`: 86400 -> 172800 (24hr -> 48hr)
Then rebuild and redeploy.

**Lost user data after redeploy:**
Make sure you're using the `-v market-dashboard-data:/app/.nicegui` flag. Without it, the `.nicegui` directory lives inside the container and is destroyed on `docker rm`.

**"Out of capacity" when creating Oracle instance:**
- Try a different availability domain in the same region
- Try again later (capacity frees up periodically)
- Use a retry script that polls the API every few minutes
