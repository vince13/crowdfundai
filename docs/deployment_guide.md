
at /var/log/codewithvince.pythonanywhere.com.error.log | tail -n 50

# Deployment Guide - Crowdfund AI Platform

## Table of Contents
1. [Production Requirements](#production-requirements)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Deployment Process](#deployment-process)
4. [Configuration](#configuration)
5. [Monitoring](#monitoring)
6. [Backup & Recovery](#backup--recovery)
7. [Maintenance](#maintenance)

## Production Requirements

### Hardware Requirements
- Minimum 2 CPU cores
- 4GB RAM (8GB recommended)
- 50GB SSD storage
- Scalable based on traffic

### Software Requirements
- Ubuntu 20.04 LTS or newer
- Python 3.13+
- PostgreSQL 13+
- Redis 6+
- Nginx
- Gunicorn
- Supervisor
- Let's Encrypt SSL

## Infrastructure Setup

### Server Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3-pip python3-venv postgresql nginx redis-server supervisor -y

# Create application user
sudo useradd -m -s /bin/bash crowdfund
sudo usermod -aG sudo crowdfund
```

### Database Setup
```bash
# Create database user and database
sudo -u postgres psql
postgres=# CREATE USER crowdfund WITH PASSWORD 'secure_password';
postgres=# CREATE DATABASE crowdfund_ai OWNER crowdfund;
postgres=# \q

# Configure PostgreSQL for remote access (if needed)
sudo nano /etc/postgresql/13/main/postgresql.conf
# listen_addresses = '*'

sudo nano /etc/postgresql/13/main/pg_hba.conf
# Add: host crowdfund_ai crowdfund 0.0.0.0/0 md5
```

### Redis Setup
```bash
# Configure Redis
sudo nano /etc/redis/redis.conf
# bind 127.0.0.1
# requirepass your_redis_password

# Restart Redis
sudo systemctl restart redis
```

## Deployment Process

### Application Setup
```bash
# Clone repository
git clone [repository-url] /home/crowdfund/app
cd /home/crowdfund/app

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
pip install gunicorn

# Create environment file
cp .env.example .env
nano .env  # Configure environment variables
```

### Gunicorn Configuration
```bash
# Create Gunicorn config
sudo nano /etc/supervisor/conf.d/crowdfund.conf

[program:crowdfund]
command=/home/crowdfund/app/venv/bin/gunicorn crowdfund_ai.wsgi:application -w 4 -b 127.0.0.1:8000
directory=/home/crowdfund/app
user=crowdfund
autostart=true
autorestart=true
stderr_logfile=/var/log/crowdfund/gunicorn.err.log
stdout_logfile=/var/log/crowdfund/gunicorn.out.log
```

### Nginx Configuration
```nginx
# Create Nginx config
sudo nano /etc/nginx/sites-available/crowdfund

server {
    listen 80;
    server_name your-domain.com;

    location = /favicon.ico { access_log off; log_not_found off; }
    
    location /static/ {
        root /home/crowdfund/app;
    }

    location /media/ {
        root /home/crowdfund/app;
    }

    location / {
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://127.0.0.1:8000;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/crowdfund /etc/nginx/sites-enabled
```

### SSL Configuration
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com
```

## Configuration

### Environment Variables
Critical production settings:
```
DJANGO_SETTINGS_MODULE=crowdfund_ai.settings.production
DJANGO_SECRET_KEY=your-secure-secret-key
ALLOWED_HOSTS=your-domain.com
DATABASE_URL=postgres://user:password@localhost:5432/crowdfund_ai
REDIS_URL=redis://:password@localhost:6379/0
PAYSTACK_SECRET_KEY=your-paystack-key
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
```

### Security Settings
- Enable CSRF protection
- Set secure cookie settings
- Configure security headers
- Enable rate limiting
- Set up firewall rules

## Monitoring

### Application Monitoring
```bash
# Install monitoring tools
pip install sentry-sdk newrelic

# Configure Sentry
export SENTRY_DSN=your-sentry-dsn

# Set up New Relic
newrelic-admin generate-config your-key newrelic.ini
```

### System Monitoring
- Set up Prometheus for metrics
- Configure Grafana dashboards
- Enable error alerting
- Monitor system resources

## Backup & Recovery

### Database Backups
```bash
# Create backup script
#!/bin/bash
BACKUP_DIR="/backup/postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
pg_dump crowdfund_ai > "$BACKUP_DIR/backup_$TIMESTAMP.sql"

# Schedule daily backups
0 2 * * * /path/to/backup-script.sh
```

### Media Backups
- Configure AWS S3 for media storage
- Set up regular S3 bucket backups
- Implement backup rotation policy

## Maintenance

### Regular Tasks
- Monitor log files
- Update system packages
- Rotate log files
- Check disk usage
- Review security updates

### Scaling
- Configure load balancer
- Set up read replicas
- Implement caching strategy
- Use CDN for static files

### Troubleshooting
- Check application logs
- Monitor error rates
- Review system metrics
- Inspect database performance

### Updates
```bash
# Update application
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo supervisorctl restart crowdfund
``` 