from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.services.ai_insights import AIInsightService
from django.core.exceptions import ObjectDoesNotExist

class AppInsightViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    insight_service = AIInsightService()

    @action(detail=True, methods=['get'])
    def insights(self, request, pk=None):
        """Get AI-powered insights for an app"""
        try:
            app = self.get_object()
            insights = self.insight_service.generate_app_insights(app)
            return Response(insights)
        except ObjectDoesNotExist:
            return Response(
                {"error": "App not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def risk_analysis(self, request, pk=None):
        """Get detailed risk analysis"""
        try:
            app = self.get_object()
            risk_score = self.insight_service.calculate_risk_score(app)
            risk_analysis = {
                'risk_score': risk_score,
                'risk_factors': {
                    'development_stage': app.development_stage,
                    'team_experience': self._get_team_experience_details(app),
                    'market_competition': self._get_competition_analysis(app),
                    'funding_progress': self._get_funding_progress(app),
                    'technology_maturity': self._get_tech_analysis(app),
                    'market_volatility': self._get_market_volatility(app),
                    'historical_performance': self._get_historical_performance(app)
                }
            }
            return Response(risk_analysis)
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_team_experience_details(self, app):
        """Get detailed team experience analysis"""
        return {
            'score': self.insight_service._analyze_team_experience(app),
            'details': 'Detailed team background and experience analysis'
        }

    def _get_competition_analysis(self, app):
        """Get detailed competition analysis"""
        return {
            'score': self.insight_service._analyze_competition(app),
            'details': 'Market competition analysis and positioning'
        }

    def _get_funding_progress(self, app):
        """Get funding progress details"""
        try:
            progress = (app.funded_amount / app.funding_goal) * 100
            return {
                'percentage': f"{progress:.1f}%",
                'amount_raised': app.funded_amount,
                'goal': app.funding_goal
            }
        except (AttributeError, ZeroDivisionError):
            return {
                'percentage': '0%',
                'amount_raised': 0,
                'goal': 0
            }

    @action(detail=True, methods=['get'])
    def investment_recommendation(self, request, pk=None):
        """Get personalized investment recommendation"""
        app = self.get_object()
        recommendation = self.insight_service.get_investment_recommendation(app)
        return Response(recommendation) 