from typing import Dict, List, Optional
import numpy as np
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Avg, Count, Q

class AIInsightService:
    """Service for generating AI-powered insights about apps"""
    
    def __init__(self):
        self.confidence_threshold = 0.7
    
    def generate_app_insights(self, app) -> Dict:
        """
        Generate insights for a specific app
        """
        from core.models import AppListing  # Import here to avoid circular import
        
        insights = {
            'valuation': self._calculate_valuation(app),
            'risk_assessment': self._assess_risk(app),
            'growth_potential': self._analyze_growth_potential(app),
            'market_analysis': self._analyze_market(app)
        }
        
        return insights
    
    def _calculate_valuation(self, app) -> Dict:
        """Calculate app valuation"""
        # Basic valuation metrics
        metrics = {
            'funding_goal': float(app.funding_goal),
            'total_investment': self._get_total_investment(app),
            'monthly_revenue': self._get_monthly_revenue(app),
            'user_growth': self._get_user_growth_rate(app),
            'market_size': self._get_market_size(app.category)
        }
        
        # Calculate valuation using multiple methods
        valuations = {
            'revenue_multiple': metrics['monthly_revenue'] * 12 * 5,  # 5x annual revenue
            'market_share': metrics['market_size'] * 0.01,  # Assume 1% market capture
            'investment_based': metrics['total_investment'] * 1.5  # 50% premium on investment
        }
        
        # Weighted average of different valuation methods
        weights = {'revenue_multiple': 0.4, 'market_share': 0.3, 'investment_based': 0.3}
        final_valuation = sum(val * weights[key] for key, val in valuations.items())
        
        return {
            'value': final_valuation,
            'confidence': 0.85,
            'metrics': metrics,
            'methods': valuations
        }
    
    def _assess_risk(self, app) -> Dict:
        """Assess app risk factors"""
        risk_factors = {
            'market_volatility': self._get_market_volatility(app.category),
            'competition_level': self._get_competition_level(app.category),
            'tech_complexity': self._get_tech_complexity(app),
            'team_experience': self._get_team_experience(app),
            'regulatory_risk': self._get_regulatory_risk(app.category)
        }
        
        # Calculate overall risk score (0-10, lower is better)
        weights = {
            'market_volatility': 0.25,
            'competition_level': 0.2,
            'tech_complexity': 0.2,
            'team_experience': 0.25,
            'regulatory_risk': 0.1
        }
        
        risk_score = sum(score * weights[factor] for factor, score in risk_factors.items())
        
        return {
            'score': risk_score,
            'confidence': 0.8,
            'factors': risk_factors
        }
    
    def _analyze_growth_potential(self, app) -> Dict:
        """Analyze growth potential"""
        growth_factors = {
            'market_opportunity': self._get_market_opportunity(app.category),
            'competitive_advantage': self._get_competitive_advantage(app),
            'scalability': self._get_scalability_score(app),
            'innovation_level': self._get_innovation_score(app),
            'team_capability': self._get_team_capability(app)
        }
        
        # Calculate growth potential score (0-10)
        weights = {
            'market_opportunity': 0.3,
            'competitive_advantage': 0.2,
            'scalability': 0.2,
            'innovation_level': 0.15,
            'team_capability': 0.15
        }
        
        growth_score = sum(score * weights[factor] for factor, score in growth_factors.items())
        
        return {
            'score': growth_score,
            'confidence': 0.75,
            'factors': growth_factors
        }
    
    def _analyze_market(self, app) -> Dict:
        """Analyze market conditions"""
        market_metrics = {
            'total_size': self._get_market_size(app.category),
            'growth_rate': self._get_market_growth_rate(app.category),
            'competition': self._get_competition_analysis(app.category),
            'barriers_to_entry': self._get_entry_barriers(app.category),
            'market_trends': self._get_market_trends(app.category)
        }
        
        return {
            'metrics': market_metrics,
            'confidence': 0.8,
            'summary': self._generate_market_summary(market_metrics)
        }
    
    # Helper methods
    def _get_total_investment(self, app) -> float:
        return sum(float(inv.amount_paid) for inv in app.investment_set.all())
    
    def _get_monthly_revenue(self, app) -> float:
        last_month = timezone.now() - timedelta(days=30)
        return sum(float(rev.amount) for rev in app.revenues.filter(created_at__gte=last_month))
    
    def _get_user_growth_rate(self, app) -> float:
        # Implement user growth calculation
        return 0.15  # Placeholder
    
    def _get_market_size(self, category: str) -> float:
        # Market size estimation logic
        base_sizes = {
            'CHATBOT': 1e9,  # $1B
            'VISION': 5e8,   # $500M
            'NLP': 7e8,      # $700M
            'ANALYTICS': 3e8, # $300M
            'OTHER': 2e8     # $200M
        }
        return base_sizes.get(category, 2e8)
    
    def _get_market_volatility(self, category: str) -> float:
        # Implement market volatility calculation
        return 5.0  # Placeholder
    
    def _get_competition_level(self, category: str) -> float:
        from core.models import AppListing  # Import here to avoid circular import
        return AppListing.objects.filter(category=category).count() / 10
    
    def _get_tech_complexity(self, app) -> float:
        # Analyze technical complexity
        return 6.0  # Placeholder
    
    def _get_team_experience(self, app) -> float:
        # Analyze team experience
        return 7.0  # Placeholder
    
    def _get_regulatory_risk(self, category: str) -> float:
        # Assess regulatory risk
        risk_levels = {
            'CHATBOT': 4.0,
            'VISION': 5.0,
            'NLP': 4.0,
            'ANALYTICS': 3.0,
            'OTHER': 3.0
        }
        return risk_levels.get(category, 3.0)
    
    def _get_market_opportunity(self, category: str) -> float:
        # Assess market opportunity
        return 7.5  # Placeholder
    
    def _get_competitive_advantage(self, app) -> float:
        # Analyze competitive advantages
        return 6.5  # Placeholder
    
    def _get_scalability_score(self, app) -> float:
        # Assess scalability
        return 8.0  # Placeholder
    
    def _get_innovation_score(self, app) -> float:
        # Assess innovation level
        return 7.0  # Placeholder
    
    def _get_team_capability(self, app) -> float:
        # Assess team capabilities
        return 7.5  # Placeholder
    
    def _get_market_growth_rate(self, category: str) -> float:
        # Calculate market growth rate
        return 0.12  # Placeholder
    
    def _get_competition_analysis(self, category: str) -> Dict:
        # Analyze competition
        return {
            'total_competitors': 15,
            'market_leaders': 3,
            'average_market_share': 0.07
        }
    
    def _get_entry_barriers(self, category: str) -> List[str]:
        # Identify entry barriers
        return [
            'Technical expertise required',
            'High initial investment',
            'Strong incumbent players'
        ]
    
    def _get_market_trends(self, category: str) -> List[str]:
        # Identify market trends
        return [
            'Increasing adoption of AI',
            'Focus on privacy and security',
            'Integration with existing systems'
        ]
    
    def _generate_market_summary(self, metrics: Dict) -> str:
        # Generate market summary
        return "Market shows strong growth potential with moderate competition."

    def get_detailed_risk_analysis(self, app) -> Dict:
        """Get detailed risk analysis for an app"""
        risk_assessment = self._assess_risk(app)
        return {
            'risk_score': risk_assessment['score'],
            'confidence': risk_assessment['confidence'],
            'risk_factors': risk_assessment['factors'],
            'recommendations': self._generate_risk_recommendations(risk_assessment)
        }

    def evaluate_technology(self, app) -> Dict:
        """Evaluate app's technology stack and implementation"""
        return {
            'tech_score': self._get_tech_complexity(app),
            'scalability': self._get_scalability_score(app),
            'innovation': self._get_innovation_score(app),
            'tech_stack': self._analyze_tech_stack(app),
            'architecture': self._analyze_architecture(app),
            'best_practices': self._evaluate_best_practices(app)
        }

    def analyze_portfolio(self, user) -> Dict:
        """Analyze user's investment portfolio"""
        portfolio = user.investments.all()
        return {
            'portfolio_score': self._calculate_portfolio_score(portfolio),
            'diversification': self._analyze_diversification(portfolio),
            'risk_exposure': self._calculate_risk_exposure(portfolio),
            'performance_metrics': self._get_performance_metrics(portfolio),
            'recommendations': self._generate_portfolio_recommendations(portfolio)
        }

    def _generate_risk_recommendations(self, risk_assessment: Dict) -> List[str]:
        """Generate risk mitigation recommendations"""
        recommendations = []
        factors = risk_assessment['factors']
        
        if factors['market_volatility'] > 7:
            recommendations.append("Consider implementing market hedging strategies")
        if factors['tech_complexity'] > 7:
            recommendations.append("Review and simplify technical architecture")
        if factors['team_experience'] < 5:
            recommendations.append("Consider bringing in experienced advisors")
            
        return recommendations

    def _analyze_tech_stack(self, app) -> Dict:
        """Analyze app's technology stack"""
        return {
            'languages': ['Python', 'JavaScript'],  # Placeholder
            'frameworks': ['Django', 'React'],  # Placeholder
            'databases': ['PostgreSQL'],  # Placeholder
            'infrastructure': ['AWS'],  # Placeholder
            'score': 8.5  # Placeholder
        }

    def _analyze_architecture(self, app) -> Dict:
        """Analyze app's architecture"""
        return {
            'scalability': 8.0,  # Placeholder
            'maintainability': 7.5,  # Placeholder
            'security': 8.5,  # Placeholder
            'performance': 7.8  # Placeholder
        }

    def _evaluate_best_practices(self, app) -> Dict:
        """Evaluate adherence to best practices"""
        return {
            'code_quality': 8.0,  # Placeholder
            'testing': 7.5,  # Placeholder
            'documentation': 7.0,  # Placeholder
            'ci_cd': 8.5  # Placeholder
        }

    def _calculate_portfolio_score(self, portfolio) -> float:
        """Calculate overall portfolio score"""
        return 8.5  # Placeholder

    def _analyze_diversification(self, portfolio) -> Dict:
        """Analyze portfolio diversification"""
        return {
            'category_distribution': {
                'CHATBOT': 0.3,
                'VISION': 0.2,
                'NLP': 0.25,
                'ANALYTICS': 0.25
            },
            'risk_distribution': {
                'low': 0.3,
                'medium': 0.5,
                'high': 0.2
            },
            'score': 8.0
        }

    def _calculate_risk_exposure(self, portfolio) -> Dict:
        """Calculate portfolio risk exposure"""
        return {
            'total_risk_score': 6.5,
            'risk_factors': {
                'market_risk': 6.0,
                'tech_risk': 7.0,
                'operational_risk': 5.5
            }
        }

    def _get_performance_metrics(self, portfolio) -> Dict:
        """Get portfolio performance metrics"""
        return {
            'total_return': 0.15,  # Placeholder
            'monthly_growth': 0.02,  # Placeholder
            'volatility': 0.08,  # Placeholder
            'sharpe_ratio': 1.5  # Placeholder
        }

    def _generate_portfolio_recommendations(self, portfolio) -> List[str]:
        """Generate portfolio optimization recommendations"""
        return [
            "Consider increasing exposure to NLP applications",
            "Rebalance portfolio to reduce high-risk investments",
            "Look for opportunities in emerging AI categories"
        ] 