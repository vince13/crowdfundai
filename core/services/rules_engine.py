from django.core.cache import cache
from django.conf import settings
from ..models import BusinessRule
import json
import logging
from datetime import datetime

logger = logging.getLogger('core.rules')

class RulesEngine:
    CACHE_KEY = 'business_rules'
    
    @classmethod
    def load_rules(cls):
        """Load rules from cache or database"""
        rules = cache.get(cls.CACHE_KEY)
        if not rules:
            # Load from database
            rules = {}
            for rule_type, _ in BusinessRule.RULE_TYPES:
                rules[rule_type] = {
                    rule['name']: rule['value'] 
                    for rule in BusinessRule.get_rules_by_type(rule_type)
                }
            cache.set(cls.CACHE_KEY, rules, timeout=3600)  # Cache for 1 hour
        return rules

    @classmethod
    def evaluate(cls, rule_type, context):
        """Evaluate business rules for a given context"""
        rules = cls.load_rules()
        if rule_type not in rules:
            logger.error(f"Unknown rule type: {rule_type}")
            return False, "Invalid rule type"

        try:
            if rule_type == 'investment':
                return cls._evaluate_investment_rules(rules[rule_type], context)
            elif rule_type == 'app_submission':
                return cls._evaluate_app_rules(rules[rule_type], context)
            elif rule_type == 'user':
                return cls._evaluate_user_rules(rules[rule_type], context)
            elif rule_type == 'moderation':
                return cls._evaluate_moderation_rules(rules[rule_type], context)
            
        except Exception as e:
            logger.error(f"Error evaluating rules: {str(e)}")
            return False, str(e)

    @classmethod
    def _evaluate_investment_rules(cls, rules, context):
        """Evaluate investment-related rules"""
        amount = context.get('amount', 0)
        user = context.get('user')
        
        if amount < rules['min_amount']:
            return False, f"Investment amount below minimum ({rules['min_amount']})"
            
        if amount > rules['max_amount']:
            return False, f"Investment amount exceeds maximum ({rules['max_amount']})"
            
        # Check daily limit
        daily_total = cls._get_user_daily_investment_total(user)
        if daily_total + amount > rules['daily_limit']:
            return False, f"Daily investment limit exceeded"
            
        # Check monthly limit
        monthly_total = cls._get_user_monthly_investment_total(user)
        if monthly_total + amount > rules['monthly_limit']:
            return False, f"Monthly investment limit exceeded"
            
        return True, "Investment rules passed"

    @classmethod
    def _evaluate_app_rules(cls, rules, context):
        """Evaluate app submission rules"""
        user = context.get('user')
        app_data = context.get('app_data', {})
        
        # Check number of apps per user
        user_apps_count = cls._get_user_apps_count(user)
        if user_apps_count >= rules['max_apps_per_user']:
            return False, f"Maximum apps per user ({rules['max_apps_per_user']}) exceeded"
            
        # Check required fields
        for field in rules['required_fields']:
            if field not in app_data or not app_data[field]:
                return False, f"Missing required field: {field}"
                
        # Check description length
        if len(app_data.get('description', '')) < rules['min_description_length']:
            return False, f"Description too short (minimum {rules['min_description_length']} characters)"
            
        # Check category
        if app_data.get('category') not in rules['allowed_categories']:
            return False, f"Invalid category. Allowed: {', '.join(rules['allowed_categories'])}"
            
        return True, "App submission rules passed"

    @classmethod
    def _evaluate_user_rules(cls, rules, context):
        """Evaluate user-related rules"""
        user_data = context.get('user_data', {})
        
        # Check age requirement
        if user_data.get('age', 0) < rules['min_age']:
            return False, f"User must be at least {rules['min_age']} years old"
            
        # Check verification requirement
        if rules['required_verification'] and not user_data.get('is_verified'):
            return False, "User verification required"
            
        # Check password expiry
        last_password_change = user_data.get('last_password_change')
        if last_password_change:
            days_since_change = (datetime.now() - last_password_change).days
            if days_since_change > rules['password_expiry_days']:
                return False, "Password expired"
                
        return True, "User rules passed"

    @classmethod
    def _evaluate_moderation_rules(cls, rules, context):
        """Evaluate moderation rules"""
        content = context.get('content', '').lower()
        reports = context.get('reports', [])
        
        # Check for flagged keywords
        for keyword in rules['auto_flag_keywords']:
            if keyword in content:
                return False, f"Content contains flagged keyword: {keyword}"
                
        # Check report threshold
        if len(reports) >= rules['report_threshold']:
            return False, f"Content exceeded report threshold"
            
        return True, "Moderation rules passed"

    @classmethod
    def update_rules(cls, rule_type, new_rules):
        """Update business rules"""
        rules = cls.load_rules()
        if rule_type not in rules:
            logger.error(f"Unknown rule type: {rule_type}")
            return False, "Invalid rule type"
            
        rules[rule_type].update(new_rules)
        cache.set(cls.CACHE_KEY, rules)
        return True, "Rules updated successfully"

    # Helper methods for rule evaluation
    @staticmethod
    def _get_user_daily_investment_total(user):
        """Get user's total investments for current day"""
        # Implementation depends on your investment model
        return 0.0

    @staticmethod
    def _get_user_monthly_investment_total(user):
        """Get user's total investments for current month"""
        # Implementation depends on your investment model
        return 0.0

    @staticmethod
    def _get_user_apps_count(user):
        """Get number of apps submitted by user"""
        # Implementation depends on your app model
        return 0 