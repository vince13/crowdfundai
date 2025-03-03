"""
Test configuration for load tests
"""

# Test Users
TEST_USERS = {
    "investor": {
        "email": "test_investor@example.com",
        "password": "testpassword123",
        "role": "INVESTOR"
    },
    "developer": {
        "email": "test_developer@example.com",
        "password": "testpassword123",
        "role": "DEVELOPER"
    }
}

# Test Apps
TEST_APPS = [
    {
        "name": "Test App 1",
        "description": "A test AI application for load testing",
        "ai_features": "Natural language processing, machine learning models",
        "category": "CHATBOT",
        "funding_goal": "1000000.00",
        "currency": "NGN",
        "available_percentage": "30.00",
        "min_investment_percentage": "1.00",
        "price_per_percentage": "33333.33",
        "equity_percentage": "30.00",
        "funding_round": "PRESEED",
        "round_number": 1,
        "lock_in_period": 180,
        "use_of_funds": {"development": 40, "marketing": 30, "operations": 30},
        "github_url": "https://github.com/test/app1",
        "demo_url": "https://demo.test.app1",
        "funding_end_date": "2025-12-31T23:59:59Z",
        "status": "PENDING",
        "development_stage": "MVP",
        "listing_type": "LISTED"
    },
    {
        "name": "Test App 2",
        "description": "Another test AI application for load testing",
        "ai_features": "Computer vision, object detection",
        "category": "COMPUTER_VISION",
        "funding_goal": "2000000.00",
        "currency": "NGN",
        "available_percentage": "25.00",
        "min_investment_percentage": "1.00",
        "price_per_percentage": "80000.00",
        "equity_percentage": "25.00",
        "funding_round": "PRESEED",
        "round_number": 1,
        "lock_in_period": 180,
        "use_of_funds": {"development": 50, "marketing": 25, "operations": 25},
        "github_url": "https://github.com/test/app2",
        "demo_url": "https://demo.test.app2",
        "funding_end_date": "2025-12-31T23:59:59Z",
        "status": "PENDING",
        "development_stage": "MVP",
        "listing_type": "LISTED"
    }
]

# Test Scenarios
SCENARIOS = {
    "light_load": {
        "users": 100,
        "spawn_rate": 10,
        "run_time": "10m"
    },
    "medium_load": {
        "users": 500,
        "spawn_rate": 20,
        "run_time": "15m"
    },
    "heavy_load": {
        "users": 1000,
        "spawn_rate": 30,
        "run_time": "20m"
    }
}

# Performance Thresholds
THRESHOLDS = {
    "response_time": {
        "median": 200,  # milliseconds
        "95th_percentile": 500,
        "99th_percentile": 1000
    },
    "error_rate": {
        "maximum": 1.0,  # percentage
        "target": 0.1
    },
    "throughput": {
        "minimum": 10,  # requests per second
        "target": 50
    }
}

# API Endpoints
ENDPOINTS = {
    "auth": {
        "login": "/api/v1/auth/login/",
        "register": "/api/v1/auth/register/"
    },
    "apps": {
        "list": "/api/v1/apps/",
        "detail": "/api/v1/apps/{id}/",
        "create": "/api/v1/apps/"
    },
    "investments": {
        "create": "/api/v1/investments/",
        "list": "/api/v1/investments/",
        "detail": "/api/v1/investments/{id}/"
    },
    "payments": {
        "webhook": "/api/v1/payments/paystack-webhook/",
        "verify": "/api/v1/payments/verify/{reference}/"
    },
    "certificates": {
        "list": "/api/v1/certificates/",
        "generate": "/api/v1/certificates/generate/",
        "verify": "/api/v1/certificates/{id}/verify/"
    }
}

# Test Environment Settings
ENVIRONMENT = {
    "development": {
        "host": "http://localhost:8000",
        "debug": True,
        "verify_ssl": False
    },
    "staging": {
        "host": "https://staging.crowdfundai.com",
        "debug": False,
        "verify_ssl": True
    },
    "production": {
        "host": "https://api.crowdfundai.com",
        "debug": False,
        "verify_ssl": True
    }
}

# Monitoring Configuration
MONITORING = {
    "prometheus": {
        "enabled": True,
        "port": 9090
    },
    "grafana": {
        "enabled": True,
        "port": 3000
    },
    "logging": {
        "level": "INFO",
        "file": "load_test.log"
    }
}

# Database Test Data
DB_TEST_DATA = {
    "min_investments": 100,
    "min_apps": 10,
    "min_users": 50
}

# Test Run Settings
RUN_SETTINGS = {
    "reset_database": False,
    "generate_test_data": True,
    "cleanup_after": True,
    "save_reports": True,
    "report_format": ["json", "html"],
    "screenshots": True
} 