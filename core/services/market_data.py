from typing import Dict, List, Optional
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import requests
import logging

logger = logging.getLogger(__name__)

class MarketDataService:
    def __init__(self):
        self.cache = {}
        self.cache_timeout = 3600  # 1 hour

    def get_market_data(self, category: str) -> Dict:
        """Get market data for a specific category"""
        try:
            # Map categories to relevant stock symbols/indices
            category_symbols = {
                'AI_CHATBOT': ['MSFT', 'GOOGL', 'META'],  # Companies with chatbot products
                'COMPUTER_VISION': ['NVDA', 'INTC', 'AMD'],  # Hardware/CV companies
                'NLP': ['GOOGL', 'META', 'BIDU'],  # NLP-focused companies
                'ML_ANALYTICS': ['CRM', 'PLTR', 'SNOW'],  # Data analytics companies
                'OTHER': ['^GSPC']  # S&P 500 as fallback
            }

            symbols = category_symbols.get(category, ['^GSPC'])
            data = self._fetch_stock_data(symbols)
            sentiment = self._fetch_market_sentiment(category)
            news = self._fetch_industry_news(category)

            return {
                'market_data': data,
                'sentiment': sentiment,
                'news': news,
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return None

    def _fetch_stock_data(self, symbols: List[str]) -> Dict:
        """Fetch stock data for given symbols"""
        data = {}
        for symbol in symbols:
            try:
                stock = yf.Ticker(symbol)
                hist = stock.history(period="6mo")
                data[symbol] = {
                    'prices': hist['Close'].tolist(),
                    'volumes': hist['Volume'].tolist(),
                    'dates': hist.index.strftime('%Y-%m-%d').tolist()
                }
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
        return data

    def _fetch_market_sentiment(self, category: str) -> Dict:
        """Fetch market sentiment from various sources"""
        try:
            # Placeholder implementation
            return {
                'sentiment': 'positive',
                'score': 0.75,
                'confidence': 0.8
            }
        except Exception as e:
            logger.error(f"Error fetching market sentiment: {e}")
            return {
                'sentiment': 'neutral',
                'score': 0.5,
                'confidence': 0.5
            }

    def _fetch_industry_news(self, category: str) -> List[Dict]:
        """Fetch relevant industry news"""
        try:
            # Placeholder implementation
            return [{
                'title': 'AI Industry Growth Continues',
                'summary': 'The AI industry shows strong growth in Q3 2023',
                'sentiment': 'positive',
                'date': datetime.now().strftime('%Y-%m-%d')
            }]
        except Exception as e:
            logger.error(f"Error fetching industry news: {e}")
            return [] 