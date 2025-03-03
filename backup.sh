#!/bin/bash

set -e  # Exit on error

# Load environment variables if they exist
if [ -f .env ]; then
    source .env
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Get timestamp for report
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "Starting backup process..."

# Run Django backup command (using BackupService)
python manage.py backup --type=full --quiet

# Create a simple backup report
if [ $? -eq 0 ]; then
    # Create backup report
    BACKUP_DIR=${BACKUP_DIR:-backups}
    mkdir -p "${BACKUP_DIR}"
    
    echo "Creating backup report..."
    cat > "${BACKUP_DIR}/backup_report_${TIMESTAMP}.txt" << EOL
Backup Report - ${TIMESTAMP}
=========================
Status: Success
Backup Location: ${BACKUP_DIR}
EOL

    echo "Backup completed successfully!"
else
    echo "Backup failed! Check the application logs for details."
    exit 1
fi 