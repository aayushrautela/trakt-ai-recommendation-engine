import os
import json
import logging
from datetime import datetime
from trakt_list import TraktListManager
from history_fetcher import HistoryFetcher
from recommendation_engine import RecommendationEngine
from tmdb_client import TMDBClient
from recommendation_service import RecommendationService

logger = logging.getLogger(__name__)

class ListUpdater:
    def __init__(self):
        self.list_manager = TraktListManager()
        self.history_fetcher = HistoryFetcher()
        self.recommendation_engine = RecommendationEngine()
        self.tmdb_client = TMDBClient()
        self.recommendation_service = RecommendationService()
    
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
            
            # Generate recommendations using the sophisticated service
            enriched_movies, metadata = self.recommendation_service.generate_recommendations(
                username=username,
                time_period=time_period,
                selected_genres=selected_genres,
                target_count=20,
                max_retries=3
            )
            
            if not enriched_movies:
                logger.warning(f"No recommendations generated for {username}: {metadata.get('error', 'Unknown error')}")
                # Try fallback recommendations
                enriched_movies = self.recommendation_service.generate_fallback_recommendations(selected_genres)
                if not enriched_movies:
                    logger.error(f"Even fallback recommendations failed for {username}")
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
