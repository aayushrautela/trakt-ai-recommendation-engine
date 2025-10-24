import logging
from typing import List, Dict, Optional, Tuple
from history_fetcher import HistoryFetcher
from recommendation_engine import RecommendationEngine
from tmdb_client import TMDBClient

logger = logging.getLogger(__name__)

class RecommendationService:
    """
    Service class that handles the sophisticated logic for generating movie recommendations.
    
    This class encapsulates the complex retry mechanism that:
    1. Generates AI recommendations based on recent watch history
    2. Filters out already watched movies from complete history
    3. Retries with updated history if not enough unique movies are found
    4. Prevents duplicate recommendations across retry attempts
    """
    
    def __init__(self):
        self.history_fetcher = HistoryFetcher()
        self.recommendation_engine = RecommendationEngine()
        self.tmdb_client = TMDBClient()
    
    def generate_recommendations(
        self, 
        username: str, 
        time_period: str, 
        selected_genres: List[str] = None,
        target_count: int = 20,
        max_retries: int = 3,
        min_quality_score: float = 5.0
    ) -> Tuple[List[Dict], Dict]:
        """
        Generate movie recommendations with sophisticated retry logic.
        
        Args:
            username: Trakt username
            time_period: Time period for AI analysis ('1 day', '1 week', etc.)
            selected_genres: Optional list of genres to filter by
            target_count: Target number of recommendations (default: 20)
            max_retries: Maximum number of retry attempts (default: 3)
            min_quality_score: Minimum quality score threshold (default: 5.0)
            
        Returns:
            Tuple of (enriched_movies, metadata)
            metadata contains: {
                'total_attempts': int,
                'total_generated': int,
                'total_filtered_watched': int,
                'total_filtered_duplicates': int,
                'total_filtered_quality': int,
                'success': bool
            }
        """
        
        # Fetch histories
        analysis_history = self.history_fetcher.get_filtered_history(username, time_period)
        if not analysis_history:
            return [], {
                'total_attempts': 0,
                'total_generated': 0,
                'total_filtered_watched': 0,
                'total_filtered_duplicates': 0,
                'success': False,
                'error': f"No watch history found for {time_period}"
            }
        
        complete_history = self.history_fetcher.get_complete_cached_history(username)
        watched_movie_ids = self.history_fetcher.get_watched_movie_ids(complete_history)
        
        # Initialize tracking variables
        all_enriched_movies = []
        used_movie_ids = set()
        current_history = analysis_history.copy()
        
        metadata = {
            'total_attempts': 0,
            'total_generated': 0,
            'total_filtered_watched': 0,
            'total_filtered_duplicates': 0,
            'total_filtered_quality': 0,
            'success': False
        }
        
        logger.info(f"Starting recommendation generation for {username}. Target: {target_count} movies")
        
        for attempt in range(max_retries):
            metadata['total_attempts'] += 1
            
            # Generate AI recommendations
            recommendations = self.recommendation_engine.analyze_watch_history(
                current_history, time_period, selected_genres
            )
            
            if not recommendations:
                logger.warning(f"Attempt {attempt + 1}: No recommendations generated")
                if attempt == max_retries - 1:
                    metadata['error'] = "Failed to generate recommendations after multiple attempts"
                    return [], metadata
                continue
            
            metadata['total_generated'] += len(recommendations)
            logger.info(f"Attempt {attempt + 1}: Generated {len(recommendations)} AI recommendations")
            
            # Enrich and filter recommendations
            new_enriched_movies = self._enrich_and_filter_recommendations(
                recommendations, selected_genres, watched_movie_ids, used_movie_ids, min_quality_score
            )
            
            if new_enriched_movies:
                # Track statistics
                metadata['total_filtered_duplicates'] += len(new_enriched_movies)
                
                # Add unique movies to our collection
                for movie in new_enriched_movies:
                    movie_id = movie.get('id')
                    if movie_id and movie_id not in used_movie_ids:
                        all_enriched_movies.append(movie)
                        used_movie_ids.add(movie_id)
                
                logger.info(f"Attempt {attempt + 1}: Added {len(new_enriched_movies)} new movies. Total: {len(all_enriched_movies)}")
            
            # Check if we have enough movies
            if len(all_enriched_movies) >= target_count:
                logger.info(f"Successfully generated {len(all_enriched_movies)} movies in {attempt + 1} attempts")
                metadata['success'] = True
                break
            
            # If we need more movies and have retries left, update history
            if attempt < max_retries - 1:
                self._update_history_for_retry(current_history, recommendations)
                logger.info(f"Attempt {attempt + 1}: Updated history for retry. Need {target_count - len(all_enriched_movies)} more movies")
        
        # Return results
        final_movies = all_enriched_movies[:target_count]
        metadata['final_count'] = len(final_movies)
        
        if not final_movies:
            metadata['error'] = "Failed to generate any recommendations"
        
        return final_movies, metadata
    
    def _enrich_and_filter_recommendations(
        self, 
        recommendations: List[str], 
        selected_genres: List[str], 
        watched_movie_ids: set,
        used_movie_ids: set,
        min_quality_score: float = 5.0
    ) -> List[Dict]:
        """
        Enrich recommendations with TMDB data and filter out watched/duplicate/low-quality movies.
        
        This is a critical method that handles the sophisticated filtering logic.
        """
        enriched_movies = []
        filtered_out_watched = 0
        filtered_out_duplicates = 0
        filtered_out_quality = 0
        
        for title in recommendations:
            # Try to extract year from title if present
            year = None
            if '(' in title and ')' in title:
                try:
                    year_str = title.split('(')[-1].split(')')[0]
                    year = int(year_str)
                    title = title.split('(')[0].strip()
                except ValueError:
                    pass
            
            # Search for movie in TMDB
            movie_data = self.tmdb_client.search_movie(title, year)
            if not movie_data:
                continue
            
            movie_id = movie_data.get('id')
            
            # Filter out already watched movies
            if watched_movie_ids and movie_id in watched_movie_ids:
                filtered_out_watched += 1
                continue
            
            # Filter out already used movies (from previous attempts)
            if movie_id in used_movie_ids:
                filtered_out_duplicates += 1
                continue
            
            # Filter out low-quality movies
            quality_score = self._calculate_quality_score(movie_data)
            if quality_score < min_quality_score:
                filtered_out_quality += 1
                continue
            
            enriched_movies.append(movie_data)
        
        # Apply genre filtering if specified
        if selected_genres:
            enriched_movies = self.tmdb_client.filter_movies_by_genres(enriched_movies, selected_genres)
        
        # No sorting - keep diversity by returning movies in order they were found
        logger.info(f"Enriched {len(enriched_movies)} movies. Filtered out {filtered_out_watched} watched, {filtered_out_duplicates} duplicates, {filtered_out_quality} low-quality")
        
        return enriched_movies
    
    def _update_history_for_retry(self, current_history: List[Dict], recommendations: List[str]) -> None:
        """
        Update the analysis history with AI recommendations to prevent suggesting them again.
        
        This is a sophisticated technique that helps the AI learn from its previous attempts.
        """
        for recommendation in recommendations:
            # Parse the recommendation to extract title and year
            if '(' in recommendation and ')' in recommendation:
                title = recommendation.split('(')[0].strip()
                year = recommendation.split('(')[1].split(')')[0].strip()
                
                # Create a fake history item to prevent re-suggestion
                fake_history_item = {
                    'movie': {
                        'title': title,
                        'year': year,
                        'ids': {'tmdb': None},  # No TMDB ID since it wasn't found
                        'genres': []  # No genre info from raw text
                    }
                }
                current_history.append(fake_history_item)
        
        logger.info(f"Added {len(recommendations)} fake history items to prevent re-suggestion")
    
    def _calculate_quality_score(self, movie: Dict) -> float:
        """
        Calculate a quality score to filter out bad movies.
        
        Uses weighted scoring based on:
        - 40% popularity (indicates mainstream appeal)
        - 40% vote average (quality rating)
        - 20% vote count credibility (more votes = more reliable)
        """
        popularity = movie.get('popularity', 0)
        vote_average = movie.get('vote_average', 0)
        vote_count = movie.get('vote_count', 0)
        
        # Weighted quality score
        quality_score = (
            popularity * 0.4 +           # 40% popularity
            vote_average * 10 * 0.4 +    # 40% quality (TMDB rating out of 10)
            min(vote_count / 1000, 1) * 0.2  # 20% credibility (more votes = more reliable)
        )
        
        return quality_score
    
    def generate_fallback_recommendations(self, selected_genres: List[str] = None) -> List[Dict]:
        """
        Generate fallback recommendations when no watch history is available.
        """
        fallback_movies = [
            "The Dark Knight (2008)",
            "Inception (2010)",
            "Pulp Fiction (1994)",
            "The Shawshank Redemption (1994)",
            "Forrest Gump (1994)",
            "The Matrix (1999)",
            "Goodfellas (1990)",
            "The Lord of the Rings: The Fellowship of the Ring (2001)",
            "Star Wars: Episode IV - A New Hope (1977)",
            "The Godfather (1972)",
            "Fight Club (1999)",
            "Interstellar (2014)",
            "The Lion King (1994)",
            "Toy Story (1995)",
            "Jurassic Park (1993)",
            "Back to the Future (1985)",
            "E.T. the Extra-Terrestrial (1982)",
            "Indiana Jones: Raiders of the Lost Ark (1981)",
            "Terminator 2: Judgment Day (1991)",
            "Alien (1979)"
        ]
        
        # Enrich fallback recommendations
        enriched_movies = self.tmdb_client.enrich_movie_list(fallback_movies, selected_genres)
        
        # Apply quality filtering to fallback recommendations too
        quality_movies = []
        for movie in enriched_movies:
            quality_score = self._calculate_quality_score(movie)
            if quality_score >= 5.0:  # Same quality threshold
                quality_movies.append(movie)
        
        return quality_movies[:20]  # Return up to 20 quality movies
