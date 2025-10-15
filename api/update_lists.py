import os
import json
import logging
from datetime import datetime
from trakt_list import TraktListManager
from history_fetcher import HistoryFetcher
from recommendation_engine import RecommendationEngine
from tmdb_client import TMDBClient

logger = logging.getLogger(__name__)

class ListUpdater:
    def __init__(self):
        self.list_manager = TraktListManager()
        self.history_fetcher = HistoryFetcher()
        self.recommendation_engine = RecommendationEngine()
        self.tmdb_client = TMDBClient()
    
    def update_all_lists(self) -> dict:
        """Update all user lists based on stored configurations"""
        logger.info("Starting nightly list update process")
        
        # Get all user configurations
        user_configs = self.list_manager.get_all_user_configs()
        
        if not user_configs:
            logger.info("No user configurations found for update")
            return {"status": "success", "message": "No users to update", "updated": 0}
        
        results = {
            "status": "success",
            "updated": 0,
            "failed": 0,
            "errors": []
        }
        
        for username, config in user_configs.items():
            try:
                logger.info(f"Updating list for user: {username}")
                
                # Update single user's list
                success = self.update_user_list(username, config)
                
                if success:
                    results["updated"] += 1
                    logger.info(f"Successfully updated list for {username}")
                else:
                    results["failed"] += 1
                    results["errors"].append(f"Failed to update list for {username}")
                    logger.error(f"Failed to update list for {username}")
                    
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Error updating {username}: {str(e)}")
                logger.error(f"Exception updating {username}: {e}")
        
        logger.info(f"Update process completed. Updated: {results['updated']}, Failed: {results['failed']}")
        return results
    
    def update_user_list(self, username: str, config: dict) -> bool:
        """Update a single user's list based on their configuration"""
        try:
            # Extract configuration
            time_period = config.get('time_period', '1 month')
            selected_genres = config.get('genres', [])
            list_name = config.get('list_name', 'AI Recommendations')
            
            logger.info(f"Processing {username}: {time_period}, genres: {selected_genres}")
            
            # Fetch watch history
            history = self.history_fetcher.get_filtered_history(username, time_period)
            
            if not history:
                logger.warning(f"No watch history found for {username} in {time_period}")
                # Still create a list with general recommendations
                recommendations = self._get_fallback_recommendations(selected_genres)
            else:
                # Generate AI recommendations
                recommendations = self.recommendation_engine.analyze_watch_history(
                    history, time_period, selected_genres
                )
            
            if not recommendations:
                logger.warning(f"No recommendations generated for {username}")
                return False
            
            # Get watched movie IDs to filter out
            watched_movie_ids = self.history_fetcher.get_watched_movie_ids(history)
            
            # Enrich with TMDB data and filter out watched movies
            enriched_movies = self.tmdb_client.enrich_movie_list(recommendations, selected_genres, watched_movie_ids)
            
            if not enriched_movies:
                logger.warning(f"No enriched movies for {username}")
                return False
            
            # Update/create Trakt list
            list_url = self.list_manager.create_or_update_list(username, list_name, enriched_movies)
            
            if list_url:
                logger.info(f"Successfully updated list for {username}: {list_url}")
                return True
            else:
                logger.error(f"Failed to update list for {username}")
                return False
                
        except Exception as e:
            logger.error(f"Exception in update_user_list for {username}: {e}")
            return False
    
    def _get_fallback_recommendations(self, selected_genres: list = None) -> list:
        """Get fallback recommendations when no history is available"""
        # Popular movies from different genres as fallback
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
        
        return fallback_movies[:20]  # Return 20 fallback recommendations

def handle_cron_update():
    """Handler function for the cron job endpoint"""
    try:
        updater = ListUpdater()
        results = updater.update_all_lists()
        
        return {
            "statusCode": 200,
            "body": json.dumps(results)
        }
    except Exception as e:
        logger.error(f"Cron job failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": str(e)
            })
        }
