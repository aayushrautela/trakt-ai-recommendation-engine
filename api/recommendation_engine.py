import os
import sys
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# Suppress Google AI library warnings during import
stderr_original = sys.stderr
sys.stderr = open(os.devnull, 'w')

try:
    import google.generativeai as genai
finally:
    # Restore stderr to its original state
    sys.stderr = stderr_original

logger = logging.getLogger(__name__)

class RecommendationEngine:
    def __init__(self):
        self.api_key = os.getenv('GEMINI_API_KEY')
        if self.api_key:
            # Suppress warnings during model initialization
            stderr_original = sys.stderr
            sys.stderr = open(os.devnull, 'w')
            
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-2.5-flash')
            finally:
                # Restore stderr to its original state
                sys.stderr = stderr_original
        else:
            self.model = None
            logger.error("GEMINI_API_KEY not found")
    
    def analyze_watch_history(self, watch_history: List[Dict], time_period: str, selected_genres: List[str] = None) -> List[str]:
        """Analyze watch history and generate movie recommendations using Gemini AI"""
        if not self.model:
            logger.error("Gemini model not initialized")
            return []
        
        try:
            # Prepare history data for analysis
            history_summary = self._prepare_history_summary(watch_history)
            
            # Create the prompt
            prompt = self._create_recommendation_prompt(history_summary, time_period, selected_genres)
            
            # Generate recommendations
            response = self.model.generate_content(prompt)
            
            # Parse the response to extract movie titles
            recommendations = self._parse_gemini_response(response.text)
            
            return recommendations
            
        except Exception as e:
            print(f"ERROR: Gemini AI failed: {e}", file=sys.stderr)
            return []
    
    def _prepare_history_summary(self, watch_history: List[Dict]) -> str:
        """Prepare a summary of watch history for AI analysis"""
        if not watch_history:
            return "No watch history available."
        
        # Group movies by genre and extract key information
        movies_by_genre = {}
        total_movies = len(watch_history)
        
        for movie in watch_history:
            genres = movie.get('movie', {}).get('genres', [])
            title = movie.get('movie', {}).get('title', 'Unknown')
            year = movie.get('movie', {}).get('year', 'Unknown')
            
            for genre in genres:
                genre_name = genre.get('name', 'Unknown')
                if genre_name not in movies_by_genre:
                    movies_by_genre[genre_name] = []
                movies_by_genre[genre_name].append(f"{title} ({year})")
        
        # Create summary
        summary = f"User has watched {total_movies} movies recently. "
        summary += "Genre breakdown:\n"
        
        for genre, movies in movies_by_genre.items():
            summary += f"- {genre}: {len(movies)} movies (e.g., {', '.join(movies[:3])})\n"
        
        return summary
    
    def _create_recommendation_prompt(self, history_summary: str, time_period: str, selected_genres: List[str] = None) -> str:
        """Create a detailed prompt for Gemini AI"""
        
        genre_constraint = ""
        if selected_genres:
            genre_constraint = f"\nIMPORTANT: Only suggest movies from these genres: {', '.join(selected_genres)}"
        
        prompt = f"""
You are a movie recommendation expert. Based on the user's recent watch history, provide 50 movie recommendations.

User's watch history ({time_period}):
{history_summary}

Instructions:
1. Analyze their viewing patterns and preferences
2. Suggest 50 movies total with the following mix:
   - 70% similar to what they've watched (same genres, themes, directors, or similar appeal)
   - 30% slightly different to help them discover new content (different but complementary genres or styles)
3. Focus on well-known, popular movies that are likely to be in movie databases
4. Include movies from different decades (not just recent releases)
5. Avoid suggesting movies they've already watched
6. Ensure recommendations are accessible and mainstream enough to be found in databases{genre_constraint}

Please respond with ONLY the movie titles, one per line, in this format:
Movie Title (Year)

Example:
The Dark Knight (2008)
Inception (2010)
Pulp Fiction (1994)

Do not include any explanations, introductions, or additional text. Just the movie titles with years.
"""
        
        return prompt
    
    def _parse_gemini_response(self, response_text: str) -> List[str]:
        """Parse Gemini response to extract movie titles"""
        recommendations = []
        
        try:
            lines = response_text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                
                # Skip empty lines and lines that don't look like movie titles
                if not line or line.startswith('#') or line.startswith('*'):
                    continue
                
                # Remove numbering if present (e.g., "1. Movie Title (Year)")
                if '. ' in line and line.split('. ')[0].isdigit():
                    line = line.split('. ', 1)[1]
                
                # Basic validation - should contain a year in parentheses
                if '(' in line and ')' in line and any(c.isdigit() for c in line):
                    recommendations.append(line)
            
            # Generated AI recommendations
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            return []
    
    def validate_recommendations(self, recommendations: List[str]) -> List[str]:
        """Basic validation of movie recommendations"""
        validated = []
        
        for rec in recommendations:
            # Check if it has a reasonable format
            if len(rec) > 5 and '(' in rec and ')' in rec:
                # Check if year looks reasonable (1900-2030)
                try:
                    year_part = rec.split('(')[-1].split(')')[0]
                    year = int(year_part)
                    if 1900 <= year <= 2030:
                        validated.append(rec)
                except ValueError:
                    continue
        
        return validated
