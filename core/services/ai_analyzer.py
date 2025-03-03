import openai
import json
from typing import Dict, Any
from django.conf import settings

class AIAnalyzer:
    """Service for analyzing pitch deck content using GPT."""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def analyze_section(self, text: str, section: str) -> Dict[str, Any]:
        """Analyze a section of the pitch deck using GPT."""
        prompts = {
            'technical': """Analyze this technical section of a pitch deck and return a JSON object with:
                {
                    "feasibility": "detailed feasibility assessment",
                    "stack": "technology stack evaluation",
                    "timeline": "development timeline analysis",
                    "feasibility_score": numeric_score_between_0_and_100
                }""",
                
            'market': """Analyze this market section of a pitch deck and return a JSON object with:
                {
                    "market_size": "market size assessment",
                    "growth": "growth potential analysis",
                    "competition": "competition evaluation",
                    "potential_score": numeric_score_between_0_and_100
                }""",
                
            'team': """Analyze this team section of a pitch deck and return a JSON object with:
                {
                    "composition": "team composition assessment",
                    "expertise": "expertise evaluation",
                    "completeness": "completeness analysis",
                    "capability_score": numeric_score_between_0_and_100
                }""",
                
            'financial': """Analyze this financial section of a pitch deck and return a JSON object with:
                {
                    "revenue_model": "revenue model assessment",
                    "projections": "financial projections analysis",
                    "funding": "funding requirements evaluation",
                    "viability_score": numeric_score_between_0_and_100
                }""",
                
            'risks': """Analyze this risk section of a pitch deck and return a JSON object with:
                {
                    "technical_risks": ["risk1", "risk2"],
                    "market_risks": ["risk1", "risk2"],
                    "operational_risks": ["risk1", "risk2"],
                    "risk_score": numeric_score_between_0_and_100
                }"""
        }
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert AI pitch deck analyzer. Analyze the provided content and return a valid JSON object based on the prompt structure. Ensure all scores are numeric values between 0 and 100."},
                    {"role": "user", "content": f"{prompts[section]}\n\nContent to analyze:\n{text}"}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            # Parse the JSON response
            try:
                result = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError as e:
                print(f"JSON Parse Error: {str(e)}")
                print(f"Raw Response: {response.choices[0].message.content}")
                # Return a default structure if parsing fails
                return self._get_default_structure(section)
            
            # Ensure scores are numeric
            score_keys = {
                'technical': 'feasibility_score',
                'market': 'potential_score',
                'team': 'capability_score',
                'financial': 'viability_score',
                'risks': 'risk_score'
            }
            
            if section in score_keys:
                score_key = score_keys[section]
                if score_key in result:
                    try:
                        result[score_key] = float(result[score_key])
                    except (ValueError, TypeError):
                        result[score_key] = 50.0  # Default score if conversion fails
            
            return result
            
        except Exception as e:
            print(f"Analysis Error: {str(e)}")
            return self._get_default_structure(section)
    
    def _get_default_structure(self, section: str) -> Dict[str, Any]:
        """Return a default structure for a section if analysis fails."""
        default_structures = {
            'technical': {
                'feasibility': 'Analysis failed',
                'stack': 'Analysis failed',
                'timeline': 'Analysis failed',
                'feasibility_score': 50.0
            },
            'market': {
                'market_size': 'Analysis failed',
                'growth': 'Analysis failed',
                'competition': 'Analysis failed',
                'potential_score': 50.0
            },
            'team': {
                'composition': 'Analysis failed',
                'expertise': 'Analysis failed',
                'completeness': 'Analysis failed',
                'capability_score': 50.0
            },
            'financial': {
                'revenue_model': 'Analysis failed',
                'projections': 'Analysis failed',
                'funding': 'Analysis failed',
                'viability_score': 50.0
            },
            'risks': {
                'technical_risks': ['Analysis failed'],
                'market_risks': ['Analysis failed'],
                'operational_risks': ['Analysis failed'],
                'risk_score': 50.0
            }
        }
        return default_structures.get(section, {'error': 'Invalid section', 'score': 50.0})
    
    def calculate_overall_score(self, analyses: Dict[str, Dict]) -> float:
        """Calculate overall score based on individual section scores."""
        weights = {
            'technical': 0.25,  # Technical feasibility
            'market': 0.25,     # Market potential
            'team': 0.2,        # Execution capability
            'financial': 0.2,   # Financial viability
            'risks': 0.1        # Risk assessment
        }
        
        scores = {
            'technical': analyses['technical'].get('feasibility_score', 0),
            'market': analyses['market'].get('potential_score', 0),
            'team': analyses['team'].get('capability_score', 0),
            'financial': analyses['financial'].get('viability_score', 0),
            'risks': analyses['risks'].get('risk_score', 0)
        }
        
        overall_score = sum(scores[section] * weights[section] for section in weights)
        return round(overall_score, 2)
    
    def generate_insights(self, analyses: Dict[str, Dict]) -> str:
        """Generate overall insights and recommendations based on the analyses."""
        try:
            insights_prompt = f"""Based on the following pitch deck analysis, provide key insights and recommendations:
            Technical Analysis: {analyses['technical']}
            Market Analysis: {analyses['market']}
            Team Analysis: {analyses['team']}
            Financial Analysis: {analyses['financial']}
            Risk Analysis: {analyses['risks']}
            
            Format your response as a concise summary with:
            1. Key strengths
            2. Areas for improvement
            3. Strategic recommendations"""
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert startup advisor. Provide clear, actionable insights based on the pitch deck analysis."},
                    {"role": "user", "content": insights_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            raise Exception(f"Error generating insights: {str(e)}") 