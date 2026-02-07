#!/bin/bash
set -e

DEPLOY_LOG="$APP_DIR/deploy.log"
GUNI_ERR="$APP_DIR/gunicorn-error.log"
GUNI_ACC="$APP_DIR/gunicorn-access.log"

echo "=====================================" | tee -a "$DEPLOY_LOG"
echo "🚀 Starting deployment..." | tee -a "$DEPLOY_LOG"
echo "Time: $(date)" | tee -a "$DEPLOY_LOG"
echo "=====================================" | tee -a "$DEPLOY_LOG"

cd /root/app/visualflow

echo "📥 Pulling latest code from GitHub..." | tee -a "$DEPLOY_LOG"
git pull origin main 2>&1 | tee -a "$DEPLOY_LOG"

echo "📦 Installing / updating dependencies..." | tee -a "$DEPLOY_LOG"
/root/.local/share/mise/installs/python/3.14.2/bin/pip install -r requirements.txt 2>&1 | tee -a "$DEPLOY_LOG"

echo "🔄 Restarting Gunicorn..." | tee -a "$DEPLOY_LOG"

# Kill old gunicorn safely
pkill /root/.local/share/mise/installs/python/3.14.2/bin/gunicorn || true
sleep 1

# Start fresh instance
/root/.local/share/mise/installs/python/3.14.2/bin/gunicorn visualflow.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 2 \
  --timeout 120 \
  --daemon \
  --error-logfile "$GUNI_ERR" \
  --access-logfile "$GUNI_ACC"

echo "✅ Deployment completed successfully!" | tee -a "$DEPLOY_LOG"
