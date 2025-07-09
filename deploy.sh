#!/bin/bash
# Deployment Script für Production

echo "🚀 Starting deployment..."

# 1. Pull latest code
git pull origin main

# 2. Install/update dependencies
pip install -r requirements.txt

# 3. Run migrations
python manage.py migrate

# 4. Collect static files
python manage.py collectstatic --noinput

# 5. Create superuser if needed
python create_superuser_if_needed.py

# 6. Restart services (adjust according to your setup)
# systemctl restart gunicorn
# systemctl restart nginx

echo "✅ Deployment completed!"