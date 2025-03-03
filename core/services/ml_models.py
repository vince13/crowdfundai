from sklearn.ensemble import RandomForestRegressor, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import numpy as np
import joblib
import os

class AIModelService:
    def __init__(self):
        self.models = {
            'valuation': self._load_or_create_model('valuation'),
            'risk': self._load_or_create_model('risk'),
            'growth': self._load_or_create_model('growth')
        }
        self.scaler = StandardScaler()

    def _load_or_create_model(self, model_type: str):
        """Load existing model or create new one"""
        model_path = f'models/{model_type}_model.joblib'
        if os.path.exists(model_path):
            return joblib.load(model_path)
        else:
            if model_type == 'valuation':
                return RandomForestRegressor(
                    n_estimators=200,
                    max_depth=10,
                    random_state=42
                )
            elif model_type == 'risk':
                return GradientBoostingClassifier(
                    n_estimators=150,
                    learning_rate=0.1,
                    random_state=42
                )
            else:
                return RandomForestRegressor(
                    n_estimators=150,
                    max_depth=8,
                    random_state=42
                )

    def prepare_features(self, app, market_data):
        """Prepare features for ML models"""
        features = {
            # App-specific features
            'funding_goal': float(app.funding_goal),
            'price_per_percentage': float(app.price_per_percentage),
            'total_shares': app.total_shares,
            'available_shares': app.available_shares,
            'development_stage': self._encode_stage(app.status),
            'team_size': app.team_members.count() + 1,
            'days_since_creation': (datetime.now() - app.created_at).days,
            
            # Market features
            'market_volatility': self._calculate_volatility(market_data),
            'market_trend': self._calculate_market_trend(market_data),
            'market_volume': self._calculate_volume_trend(market_data),
            
            # Category features
            'category_score': self._get_category_score(app.category),
            'competition_level': self._get_competition_level(app),
            
            # Technical features
            'tech_complexity': self._calculate_tech_complexity(app),
            'innovation_score': self._calculate_innovation_score(app)
        }
        return features

    def predict_valuation(self, features):
        """Predict app valuation"""
        scaled_features = self.scaler.fit_transform([list(features.values())])
        return self.models['valuation'].predict(scaled_features)[0]

    def predict_risk_level(self, features):
        """Predict risk level"""
        scaled_features = self.scaler.fit_transform([list(features.values())])
        return self.models['risk'].predict_proba(scaled_features)[0]

    def predict_growth_potential(self, features):
        """Predict growth potential"""
        scaled_features = self.scaler.fit_transform([list(features.values())])
        return self.models['growth'].predict(scaled_features)[0] 