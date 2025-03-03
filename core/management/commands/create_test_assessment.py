from django.core.management.base import BaseCommand
from core.models import AppListing, AIAssessment
import json

class Command(BaseCommand):
    help = 'Creates a test AI assessment for a specified app'

    def add_arguments(self, parser):
        parser.add_argument('app_id', type=int, help='The ID of the app to assess')

    def handle(self, *args, **options):
        app_id = options['app_id']
        
        try:
            app = AppListing.objects.get(id=app_id)
        except AppListing.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'App with ID {app_id} does not exist'))
            return

        # Delete existing assessment if any
        AIAssessment.objects.filter(app=app).delete()

        # Create new assessment
        assessment = AIAssessment.objects.create(
            app=app,
            
            # Technical Assessment
            tech_stack_details=json.dumps({
                "frontend": "React 18",
                "backend": "Django 4.2",
                "ai_framework": "TensorFlow 2.0",
                "database": "PostgreSQL",
                "deployment": "AWS",
                "version_control": "Git",
                "ci_cd": "GitHub Actions"
            }),
            
            ai_features_details=json.dumps({
                "natural_language_processing": {
                    "algorithm": "BERT",
                    "purpose": "Text Classification",
                    "training_data": "100k samples",
                    "accuracy": "92%"
                },
                "computer_vision": {
                    "algorithm": "YOLOv5",
                    "purpose": "Object Detection",
                    "training_data": "50k images",
                    "accuracy": "89%"
                }
            }),
            
            development_progress=80,
            
            # Market Assessment
            target_market="GLOBAL",
            
            competitor_analysis=json.dumps({
                "competitor1": {
                    "market_share": "20%",
                    "strengths": ["established brand", "large user base"],
                    "weaknesses": ["outdated technology", "high prices"]
                },
                "competitor2": {
                    "market_share": "15%",
                    "strengths": ["innovative features", "good pricing"],
                    "weaknesses": ["limited market reach", "poor support"]
                }
            }),
            
            revenue_model=json.dumps({
                "subscription": 60,
                "advertising": 20,
                "premium_features": 20,
                "projected_monthly_revenue": "$50,000"
            }),
            
            # Team Assessment
            team_experience=json.dumps([
                {
                    "role": "AI Engineer",
                    "years": 5,
                    "expertise": ["Machine Learning", "NLP", "Computer Vision"],
                    "previous_companies": ["Google", "Microsoft"]
                },
                {
                    "role": "Full Stack Developer",
                    "years": 8,
                    "expertise": ["React", "Django", "AWS"],
                    "previous_companies": ["Amazon", "Meta"]
                }
            ]),
            
            previous_projects=json.dumps([
                {
                    "name": "AI Chat Assistant",
                    "success_metrics": {
                        "users": 100000,
                        "revenue": "$1M",
                        "satisfaction": "4.8/5"
                    }
                },
                {
                    "name": "Computer Vision Security System",
                    "success_metrics": {
                        "deployments": 500,
                        "revenue": "$2M",
                        "accuracy": "99.9%"
                    }
                }
            ]),
            
            # Additional Metrics
            scalability_plan="Our infrastructure is built on AWS with auto-scaling capabilities. We use microservices architecture for better scalability and maintenance. Our database is sharded for handling large amounts of data.",
            
            innovation_factors=json.dumps({
                "unique_features": [
                    "Real-time AI processing",
                    "Hybrid cloud architecture",
                    "Advanced security measures"
                ],
                "patents": [
                    "AI Algorithm Patent #12345",
                    "System Architecture Patent #67890"
                ],
                "research_papers": [
                    "Efficient Large Scale AI Deployment",
                    "Novel Approach to Secure AI Systems"
                ]
            }),
            
            risk_factors=json.dumps({
                "technical": [
                    "AI model accuracy degradation",
                    "System scalability challenges"
                ],
                "market": [
                    "New competitors",
                    "Market saturation"
                ],
                "operational": [
                    "Team expansion needs",
                    "Infrastructure costs"
                ],
                "mitigation": {
                    "AI model accuracy degradation": "Continuous model retraining",
                    "System scalability challenges": "Cloud-native architecture",
                    "New competitors": "Rapid innovation cycle",
                    "Market saturation": "Market differentiation strategy",
                    "Team expansion needs": "Talent pipeline program",
                    "Infrastructure costs": "Resource optimization"
                }
            })
        )

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created AI assessment for app "{app.name}"')
        ) 