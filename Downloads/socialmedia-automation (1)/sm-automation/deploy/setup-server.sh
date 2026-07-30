#!/usr/bin/env bash
# Server-side setup for NICDC Social Studio (Debian/Ubuntu).
# Expects the project tarball at /tmp/sm-automation.tar.gz
# Usage: sudo bash setup-server.sh <PUBLIC_BASE_URL>   e.g. http://34.12.34.56
set -euo pipefail

PUBLIC_BASE_URL="${1:?Usage: sudo bash setup-server.sh <PUBLIC_BASE_URL, e.g. http://YOUR_VM_IP>}"
APP_DIR=/opt/sm-automation

echo "== Installing system packages =="
apt-get update -qq
apt-get install -y -qq python3 python3-venv nginx

echo "== Unpacking application to ${APP_DIR} =="
mkdir -p "$APP_DIR"
tar -xzf /tmp/sm-automation.tar.gz -C "$APP_DIR"

echo "== Creating virtualenv and installing dependencies =="
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install -q --upgrade pip
"$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "== Preparing runtime directories =="
mkdir -p "$APP_DIR/data/images" "$APP_DIR/data/published"
chown -R www-data:www-data "$APP_DIR"

echo "== Installing systemd services =="
sed "s|__PUBLIC_BASE_URL__|${PUBLIC_BASE_URL}|" "$APP_DIR/deploy/sm-studio.service" > /etc/systemd/system/sm-studio.service
cp "$APP_DIR/deploy/sm-mock-apis.service" /etc/systemd/system/sm-mock-apis.service
systemctl daemon-reload
systemctl enable --now sm-mock-apis sm-studio
systemctl restart sm-mock-apis sm-studio

echo "== Configuring nginx =="
cp "$APP_DIR/deploy/nginx-sm-studio.conf" /etc/nginx/sites-available/sm-studio
ln -sf /etc/nginx/sites-available/sm-studio /etc/nginx/sites-enabled/sm-studio
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "== Health checks =="
sleep 2
curl -sf http://127.0.0.1:8000/health && echo "  main app OK"
curl -sf http://127.0.0.1:8100/health >/dev/null && echo "  mock APIs OK"

echo
echo "Deployed. Open ${PUBLIC_BASE_URL}  (make sure GCP firewall allows HTTP/80)"
echo "Demo logins: editor/editor123, approver/approver123 — change data/users.json for real use."
