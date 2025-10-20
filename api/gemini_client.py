import os
import json
import requests
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class GeminiClient:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
        
    def generate_content(self, prompt: str) -> str:
        """Generate content using Gemini API via HTTP requests"""
        if not self.api_key:
            logger.error("GEMINI_API_KEY not found")
            return ""
        
        try:
            headers = {
                'Content-Type': 'application/json',
            }
            
            data = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 2048,
                }
            }
            
            response = requests.post(
                f"{self.base_url}?key={self.api_key}",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    content = result['candidates'][0]['content']['parts'][0]['text']
                    return content
                else:
                    logger.error(f"No content in Gemini response: {result}")
                    return ""
            else:
                logger.error(f"Gemini API error: {response.status_code} - {response.text}")
                return ""
                
        except Exception as e:
            logger.error(f"Failed to call Gemini API: {e}")
            return ""
