#!/bin/bash

echo "Starting PythonAnywhere refresh..."

# Navigate to project directory
cd /home/codewithvince/crowdfund_ai || exit

# Activate virtual environment
if [ -f "/home/codewithvince/.virtualenvs/django-venv/bin/activate" ]; then
    source /home/codewithvince/.virtualenvs/django-venv/bin/activate
else
    echo "Error: Virtual environment not found at /home/codewithvince/.virtualenvs/django-venv"
    exit 1
fi

# Pull latest changes from GitHub
echo "Pulling latest changes from GitHub..."
git pull origin main

# Install/update requirements
echo "Updating dependencies..."
pip install -r requirements.txt

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Update environment file
echo "Updating environment file..."
if [ -f ".env.production" ]; then
    cp .env.production .env
    chmod 600 .env
else
    echo "Warning: .env.production not found"
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p media
mkdir -p staticfiles
mkdir -p logs

# Set proper permissions
echo "Setting permissions..."
chmod -R 755 media staticfiles logs

# Reload the web app
echo "Reloading web app..."
touch /var/www/codewithvince_pythonanywhere_com_wsgi.py

echo "Refresh completed successfully!"

# Show current git status
git status 