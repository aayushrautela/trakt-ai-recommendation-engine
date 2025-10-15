import os
import sys
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
            # For existing lists, we'll replace all items in one operation
            print(f"Updating existing list '{list_name}'")
            success = self._replace_list_items(username, list_id, movies)
        else:
            # Create new list
            list_id = self._create_list(username, list_name)
            if not list_id:
                print(f"ERROR: Failed to create list '{list_name}'", file=sys.stderr)
                return None
            print(f"Created new list '{list_name}'")
            success = self._add_movies_to_list(username, list_id, movies)
        
        if success:
            list_url = f"https://trakt.tv/users/{username}/lists/{list_id}"
            print(f"Successfully updated list with {len(movies)} movies")
            return list_url
        else:
            print(f"ERROR: Failed to update Trakt list", file=sys.stderr)
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
    
    def _replace_list_items(self, username: str, list_id: str, movies: List[Dict]) -> bool:
        """Replace all items in a list with new movies in one operation"""
        try:
            # First, get current items to remove
            items_endpoint = f'/users/{username}/lists/{list_id}/items'
            current_items = self.trakt_auth.make_authenticated_request(username, items_endpoint, 'GET')
            
            # Prepare removal data
            movies_to_remove = []
            if current_items:
                for item in current_items:
                    if item.get('type') == 'movie':
                        movie_data = item.get('movie', {})
                        if movie_data.get('ids', {}).get('trakt'):
                            movies_to_remove.append({
                                'ids': {'trakt': movie_data['ids']['trakt']}
                            })
                        elif movie_data.get('ids', {}).get('tmdb'):
                            movies_to_remove.append({
                                'ids': {'tmdb': movie_data['ids']['tmdb']}
                            })
                        elif movie_data.get('ids', {}).get('imdb'):
                            movies_to_remove.append({
                                'ids': {'imdb': movie_data['ids']['imdb']}
                            })
            
            # Prepare new movies data with deduplication
            movies_data = {
                'movies': []
            }
            
            # Track TMDB IDs to prevent duplicates
            used_tmdb_ids = set()
            
            for movie in movies:
                movie_id = movie.get('id')
                if movie_id and movie_id not in used_tmdb_ids:
                    movie_item = {
                        'ids': {
                            'tmdb': movie_id
                        }
                    }
                    movies_data['movies'].append(movie_item)
                    used_tmdb_ids.add(movie_id)
            
            # Debug: Show sample of what we're sending
            print(f"Sending {len(movies_data['movies'])} movies to Trakt")
            if movies_data['movies']:
                sample_movie = movies_data['movies'][0]
                print(f"Sample movie data: {sample_movie}")
            
            # If there are items to remove, do it first
            if movies_to_remove:
                remove_data = {'movies': movies_to_remove}
                remove_endpoint = f'/users/{username}/lists/{list_id}/items/remove'
                remove_result = self.trakt_auth.make_authenticated_request(
                    username, remove_endpoint, 'POST', remove_data
                )
                
                if not remove_result:
                    print(f"WARNING: Failed to clear existing items, but continuing...", file=sys.stderr)
            
            # Add new movies
            add_endpoint = f'/users/{username}/lists/{list_id}/items'
            add_result = self.trakt_auth.make_authenticated_request(username, add_endpoint, 'POST', movies_data)
            
            if add_result:
                # Check the actual response to see how many movies were added
                added_count = add_result.get('added', {}).get('movies', 0)
                existing_count = add_result.get('existing', {}).get('movies', 0)
                not_found_count = len(add_result.get('not_found', {}).get('movies', []))
                total_in_list = add_result.get('list', {}).get('item_count', 0)
                
                print(f"Added {added_count} new movies, {existing_count} already existed, {not_found_count} not found")
                print(f"Total movies in list: {total_in_list}")
                
                # Consider it successful if we added at least some movies
                if added_count > 0 or existing_count > 0:
                    return True
                else:
                    print(f"ERROR: No movies were successfully added to the list", file=sys.stderr)
                    return False
            else:
                print(f"ERROR: Failed to add new movies", file=sys.stderr)
                return False
                
        except Exception as e:
            print(f"ERROR: Failed to replace list items: {e}", file=sys.stderr)
            return False
    
    def _delete_list(self, username: str, list_id: str) -> bool:
        """Delete an entire list"""
        endpoint = f'/users/{username}/lists/{list_id}'
        
        logger.info(f"Deleting list {list_id} for {username}")
        result = self.trakt_auth.make_authenticated_request(username, endpoint, 'DELETE')
        
        if result is not None:
            logger.info(f"Successfully deleted list {list_id}")
            return True
        else:
            logger.warning(f"Failed to delete list {list_id}")
            return False
    
    def _clear_list_items(self, username: str, list_id: str) -> bool:
        """Clear all items from a list by using the correct Trakt API /items/remove endpoint"""
        try:
            # First, get all current items in the list
            items_endpoint = f'/users/{username}/lists/{list_id}/items'
            current_items = self.trakt_auth.make_authenticated_request(username, items_endpoint, 'GET')
            
            if not current_items:
                return True
            
            # Prepare removal data using the correct format
            movies_to_remove = []
            shows_to_remove = []
            
            for item in current_items:
                if item.get('type') == 'movie':
                    movie_data = item.get('movie', {})
                    # Try different ID types that might be available
                    if movie_data.get('ids', {}).get('trakt'):
                        movies_to_remove.append({
                            'ids': {'trakt': movie_data['ids']['trakt']}
                        })
                    elif movie_data.get('ids', {}).get('tmdb'):
                        movies_to_remove.append({
                            'ids': {'tmdb': movie_data['ids']['tmdb']}
                        })
                    elif movie_data.get('ids', {}).get('imdb'):
                        movies_to_remove.append({
                            'ids': {'imdb': movie_data['ids']['imdb']}
                        })
                elif item.get('type') == 'show':
                    show_data = item.get('show', {})
                    if show_data.get('ids', {}).get('trakt'):
                        shows_to_remove.append({
                            'ids': {'trakt': show_data['ids']['trakt']}
                        })
                    elif show_data.get('ids', {}).get('tmdb'):
                        shows_to_remove.append({
                            'ids': {'tmdb': show_data['ids']['tmdb']}
                        })
            
            # Use the /items/remove endpoint
            if movies_to_remove or shows_to_remove:
                remove_data = {}
                if movies_to_remove:
                    remove_data['movies'] = movies_to_remove
                if shows_to_remove:
                    remove_data['shows'] = shows_to_remove
                
                # Use the correct /items/remove endpoint
                remove_endpoint = f'/users/{username}/lists/{list_id}/items/remove'
                remove_result = self.trakt_auth.make_authenticated_request(
                    username, remove_endpoint, 'POST', remove_data
                )
                
                if remove_result:
                    print(f"Cleared {len(movies_to_remove)} movies from list")
                    return True
                else:
                    print(f"WARNING: Failed to clear list items", file=sys.stderr)
            
            return True
            
        except Exception as e:
            print(f"ERROR: Error clearing list: {e}", file=sys.stderr)
            return True  # Continue even if clear fails
    
    def _clear_list_items_individually(self, username: str, list_id: str) -> bool:
        """Fallback method to clear items individually"""
        try:
            # Get all current items
            endpoint = f'/users/{username}/lists/{list_id}/items'
            current_items = self.trakt_auth.make_authenticated_request(username, endpoint, 'GET')
            
            if not current_items:
                logger.info(f"List {list_id} is already empty")
                return True
            
            logger.info(f"Found {len(current_items)} items to remove individually")
            
            # Remove items one by one (this is slower but more reliable)
            removed_count = 0
            for item in current_items:
                try:
                    # Get the item ID from the response
                    item_id = item.get('id')
                    if item_id:
                        # Use the specific item endpoint to remove
                        item_endpoint = f'/users/{username}/lists/{list_id}/items/{item_id}'
                        result = self.trakt_auth.make_authenticated_request(username, item_endpoint, 'DELETE')
                        if result is not None:
                            removed_count += 1
                        else:
                            logger.warning(f"Failed to remove item {item_id}")
                except Exception as e:
                    logger.warning(f"Error removing individual item: {e}")
                    continue
            
            logger.info(f"Removed {removed_count} out of {len(current_items)} items")
            return True
            
        except Exception as e:
            logger.error(f"Error in individual removal: {e}")
            return True
    
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
        
        # Try the request with retry logic for rate limiting
        max_retries = 3
        for attempt in range(max_retries):
            result = self.trakt_auth.make_authenticated_request(username, endpoint, 'POST', movies_data)
            
            if result:
                return True
            else:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
                    print(f"Rate limited, retrying in {wait_time}s...", file=sys.stderr)
                    import time
                    time.sleep(wait_time)
                else:
                    print(f"ERROR: Trakt API failed after {max_retries} attempts", file=sys.stderr)
                    return False
        
        return False
    
    def store_user_config(self, username: str, config: Dict) -> bool:
        """Store user configuration in Redis for nightly updates"""
        try:
            config_key = f'{self.namespace}:user_config:{username}'
            self.redis_client.setex(config_key, 86400 * 30, json.dumps(config))  # 30 days expiry
            return True
        except Exception as e:
            print(f"❌ Failed to store config: {e}", file=sys.stderr)
            return False
    
    def get_user_config(self, username: str) -> Optional[Dict]:
        """Get user configuration from Redis"""
        try:
            config_key = f'{self.namespace}:user_config:{username}'
            config_data = self.redis_client.get(config_key)
            if config_data:
                return json.loads(config_data)
        except Exception as e:
            print(f"❌ Failed to get config: {e}", file=sys.stderr)
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
            print(f"❌ Failed to get user configs: {e}", file=sys.stderr)
            return {}
    
    def delete_user_config(self, username: str) -> bool:
        """Delete user configuration"""
        try:
            config_key = f'{self.namespace}:user_config:{username}'
            self.redis_client.delete(config_key)
            return True
        except Exception as e:
            print(f"❌ Failed to delete config: {e}", file=sys.stderr)
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
