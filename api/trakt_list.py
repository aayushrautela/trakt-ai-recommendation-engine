import os
import json
import redis
import logging
from typing import List, Dict, Optional
from trakt_auth import TraktAuth
from tmdb_client import TMDBClient

logger = logging.getLogger(__name__)

class TraktListManager:
    def __init__(self):
        self.trakt_auth = TraktAuth()
        self.tmdb_client = TMDBClient()
        self.namespace = os.getenv('REDIS_NAMESPACE', 'trakt_ai_gen')
        
        # Redis connection
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
        else:
            # Fallback for local development
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    def create_or_update_list(self, username: str, list_name: str, movies: List[Dict]) -> Optional[str]:
        """Create a new list or update existing one with movies"""
        
        # First, check if list exists
        list_id = self._find_list_by_name(username, list_name)
        
        if list_id:
            # Clear existing list completely
            logger.info(f"Found existing list '{list_name}' (ID: {list_id}) - clearing all items")
            clear_success = self._clear_list(username, list_id)
            if not clear_success:
                logger.warning(f"Failed to clear existing list, but continuing...")
        else:
            # Create new list
            list_id = self._create_list(username, list_name)
            if not list_id:
                logger.error(f"Failed to create list '{list_name}' for {username}")
                return None
            logger.info(f"Created new list '{list_name}' for {username}")
        
        # Add movies to list
        success = self._add_movies_to_list(username, list_id, movies)
        
        if success:
            list_url = f"https://trakt.tv/users/{username}/lists/{list_id}"
            logger.info(f"Successfully added {len(movies)} movies to list for {username}")
            return list_url
        else:
            logger.error(f"Failed to add movies to list for {username}")
            return None
    
    def _find_list_by_name(self, username: str, list_name: str) -> Optional[str]:
        """Find list ID by name"""
        endpoint = f'/users/{username}/lists'
        
        lists_data = self.trakt_auth.make_authenticated_request(username, endpoint)
        if not lists_data:
            return None
        
        for list_item in lists_data:
            if list_item.get('name') == list_name:
                return str(list_item.get('ids', {}).get('trakt', ''))
        
        return None
    
    def _create_list(self, username: str, list_name: str) -> Optional[str]:
        """Create a new list"""
        list_data = {
            'name': list_name,
            'description': 'AI-generated movie recommendations based on your watch history',
            'privacy': 'private',
            'display_numbers': True,
            'allow_comments': False,
            'sort_by': 'rank',
            'sort_how': 'asc'
        }
        
        endpoint = f'/users/{username}/lists'
        result = self.trakt_auth.make_authenticated_request(username, endpoint, 'POST', list_data)
        
        if result and result.get('ids', {}).get('trakt'):
            return str(result['ids']['trakt'])
        
        return None
    
    def _clear_list(self, username: str, list_id: str) -> bool:
        """Clear all items from a list"""
        endpoint = f'/users/{username}/lists/{list_id}/items'
        
        logger.info(f"Clearing list {list_id} for {username}")
        result = self.trakt_auth.make_authenticated_request(username, endpoint, 'DELETE')
        
        if result is not None:
            logger.info(f"Successfully cleared list {list_id}")
            return True
        else:
            logger.warning(f"Failed to clear list {list_id} - continuing anyway")
            return True  # Continue even if clear fails
    
    def _add_movies_to_list(self, username: str, list_id: str, movies: List[Dict]) -> bool:
        """Add movies to a list"""
        # Prepare movies data for Trakt API - correct format
        movies_data = {
            'movies': []
        }
        
        for movie in movies:
            # Convert TMDB data to Trakt format
            movie_item = {
                'ids': {
                    'tmdb': movie.get('id')
                }
            }
            movies_data['movies'].append(movie_item)
        
        endpoint = f'/users/{username}/lists/{list_id}/items'
        
        # Debug logging
        logger.info(f"Sending {len(movies_data['movies'])} movies to Trakt API")
        logger.info(f"Sample movie data: {movies_data['movies'][:2] if movies_data['movies'] else 'No movies'}")
        
        # Try the request with retry logic for rate limiting
        max_retries = 3
        for attempt in range(max_retries):
            result = self.trakt_auth.make_authenticated_request(username, endpoint, 'POST', movies_data)
            
            if result:
                logger.info(f"Trakt API response: {result}")
                return True
            else:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
                    logger.warning(f"Trakt API failed, retrying in {wait_time} seconds (attempt {attempt + 1}/{max_retries})")
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error("Trakt API returned no result after all retries")
                    return False
        
        return False
    
    def store_user_config(self, username: str, config: Dict) -> bool:
        """Store user configuration in Redis for nightly updates"""
        try:
            config_key = f'{self.namespace}:user_config:{username}'
            self.redis_client.setex(config_key, 86400 * 30, json.dumps(config))  # 30 days expiry
            logger.info(f"Stored config for {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to store config for {username}: {e}")
            return False
    
    def get_user_config(self, username: str) -> Optional[Dict]:
        """Get user configuration from Redis"""
        try:
            config_key = f'{self.namespace}:user_config:{username}'
            config_data = self.redis_client.get(config_key)
            if config_data:
                return json.loads(config_data)
        except Exception as e:
            logger.error(f"Failed to get config for {username}: {e}")
        return None
    
    def get_all_user_configs(self) -> Dict[str, Dict]:
        """Get all user configurations for nightly updates"""
        try:
            configs = {}
            pattern = f'{self.namespace}:user_config:*'
            
            for key in self.redis_client.scan_iter(match=pattern):
                username = key.replace(f'{self.namespace}:user_config:', '')
                config_data = self.redis_client.get(key)
                if config_data:
                    configs[username] = json.loads(config_data)
            
            return configs
        except Exception as e:
            logger.error(f"Failed to get all user configs: {e}")
            return {}
    
    def delete_user_config(self, username: str) -> bool:
        """Delete user configuration"""
        try:
            config_key = f'{self.namespace}:user_config:{username}'
            self.redis_client.delete(config_key)
            logger.info(f"Deleted config for {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete config for {username}: {e}")
            return False
    
    def convert_tmdb_to_trakt_items(self, movies: List[Dict]) -> List[Dict]:
        """Convert TMDB movie data to Trakt API format"""
        trakt_items = []
        
        for movie in movies:
            # Use TMDB ID as the primary identifier
            item = {
                'movies': [{
                    'ids': {
                        'tmdb': movie.get('id')
                    }
                }]
            }
            trakt_items.append(item)
        
        return trakt_items
