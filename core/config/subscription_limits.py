"""Configuration for subscription feature limits and usage tracking."""

from datetime import timedelta

FEATURE_LIMITS = {
    'FREE': {
        'basic_ai_insights': {'daily': 5, 'monthly': 50},
        'basic_portfolio': {'daily': 10, 'monthly': 100},
        'standard_transactions': {'daily': 10, 'monthly': 100},
    },
    'DEV_PRO': {
        'advanced_ai_assessment': {'daily': 50, 'monthly': 500},
        'market_analysis': {'daily': 20, 'monthly': 200},
        'tech_evaluation': {'daily': 30, 'monthly': 300},
        'priority_listing': {'daily': float('inf'), 'monthly': float('inf')},
        'api_access': {'daily': 1000, 'monthly': 10000},
        'custom_branding': {'daily': float('inf'), 'monthly': float('inf')},
        'priority_support': {'daily': 10, 'monthly': 100},
        'marketing_tools': {'daily': 50, 'monthly': 500},
    },
    'INV_PRO': {
        'detailed_risk_analysis': {'daily': 30, 'monthly': 300},
        'portfolio_optimization': {'daily': 20, 'monthly': 200},
        'market_trends': {'daily': 50, 'monthly': 500},
        'investment_alerts': {'daily': 100, 'monthly': 1000},
        'due_diligence_tools': {'daily': 30, 'monthly': 300},
        'early_access': {'daily': float('inf'), 'monthly': float('inf')},
        'priority_processing': {'daily': float('inf'), 'monthly': float('inf')},
        'exclusive_events': {'daily': 5, 'monthly': 50},
    }
}

# Reset periods for different tracking intervals
RESET_PERIODS = {
    'daily': timedelta(days=1),
    'monthly': timedelta(days=30),
}

# Grace percentage before sending usage limit warnings
WARNING_THRESHOLD = 0.85  # 85% of limit 