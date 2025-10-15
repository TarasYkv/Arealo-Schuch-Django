#!/bin/bash
# MySQL Deployment Script für PythonAnywhere

set -e  # Stop on error

echo "🚀 Starting MySQL Deployment..."

# Pfade
PROJECT_DIR="/home/TarasYuzkiv/Arealo-Schuch-Django"
VENV="/home/TarasYuzkiv/.virtualenvs/arealo-venv"

cd "$PROJECT_DIR"

# 1. Git Pull
echo "📥 Pulling latest code from GitHub..."
git pull origin master

# 2. Activate virtualenv
source "$VENV/bin/activate"

# 3. Install mysqlclient if needed
echo "📦 Installing mysqlclient..."
pip install mysqlclient --quiet

# 4. Run Migrations
echo "🔄 Running migrations..."
python manage.py migrate --noinput

# 5. Collect Static Files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Deployment completed successfully!"
echo ""
echo "⚠️  Next steps:"
echo "1. Import data: python manage.py loaddata data_backup_final.json"
echo "2. Reload web app"
