#!/bin/bash

echo "Starting deep cleanup process..."

# Remove all Python cache files
find . -type f -name "*.pyc" -delete
find . -type d -name "__pycache__" -exec rm -rf {} +

# Clean pip cache
rm -rf ~/.cache/pip

# Remove old log files
find . -name "*.log" -type f -delete

# Clean temporary files
rm -rf /tmp/*

# Clean old virtualenv if exists
rm -rf ~/.virtualenvs/myenv

# Remove old static files
rm -rf ~/crowdfund_ai/staticfiles/*

# Remove old media files (be careful with this if you have user uploads)
# rm -rf ~/crowdfund_ai/media/*

# Clean package caches
pip cache purge

# Remove old wheels
rm -rf ~/.cache/pip/wheels/*

# Show current disk usage
echo "Current disk usage:"
du -sh ~/*

echo "Cleanup completed! Please check disk usage above." 