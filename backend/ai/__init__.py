"""
AI分析模块
DeepSeek-powered stock analysis, news sentiment, and anomaly detection
"""
from backend.ai.client import get_deepseek_client
from backend.ai.analyst import generate_market_summary, analyze_stock_deep, detect_anomalies
from backend.ai.news_sentiment import analyze_news_with_ai, batch_ai_sentiment
from backend.ai.cache import ai_cache
