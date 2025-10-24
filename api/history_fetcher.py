import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from trakt_auth import TraktAuth

logger = logging.getLogger(__name__)

class HistoryFetcher:
    def __init__(self):
        self.trakt_auth = TraktAuth()
    
    def get_days_back(self, time_period: str) -> int:
        """Convert time period string to number of days"""
        period_map = {
            '1 day': 1,
            '1 week': 7,
            '1 month': 30,
            '3 months': 90
        }
        return period_map.get(time_period, 30)  # Default to 1 month
    
    def fetch_watch_history(self, username: str, time_period: str = '1 month') -> List[Dict]:
        """Fetch user's movie watch history for the specified time period"""
        
        days_back = self.get_days_back(time_period)
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        # Fetch movie history with pagination
        all_history = []
        page = 1
        limit = 100
        
        while True:
            endpoint = f'/users/{username}/history/movies'
            params = f'?start_date={start_date}&page={page}&limit={limit}'
            
            history_data = self.trakt_auth.make_authenticated_request(
                username, 
                f'{endpoint}{params}'
            )
            
            if not history_data:
                break
            
            if not history_data:  # Empty response
                break
            
            all_history.extend(history_data)
            
            # If we got fewer items than the limit, we've reached the end
            if len(history_data) < limit:
                break
            
            page += 1
            
            # Safety check to prevent infinite loops
            if page > 50:  # Max 5000 items
                break
        
        # Fetched movies from history
        return all_history
    
    def fetch_complete_watch_history(self, username: str) -> List[Dict]:
        """Fetch user's complete movie watch history (no date filtering) for filtering purposes"""
        
        # Fetch movie history with pagination (no start_date filter)
        all_history = []
        page = 1
        limit = 100
        
        while True:
            endpoint = f'/users/{username}/history/movies'
            params = f'?page={page}&limit={limit}'
            
            history_data = self.trakt_auth.make_authenticated_request(
                username, 
                f'{endpoint}{params}'
            )
            
            if not history_data:
                break
            
            if not history_data:  # Empty response
                break
            
            all_history.extend(history_data)
            
            # If we got fewer items than the limit, we've reached the end
            if len(history_data) < limit:
                break
            
            page += 1
            
            # Safety check to prevent infinite loops
            if page > 50:  # Max 5000 items
                break
        
        # Fetched movies from complete history
        return all_history
    
    def extract_movie_info(self, history_item: Dict) -> Dict:
        """Extract relevant movie information from history item"""
        movie_data = history_item.get('movie', {})
        
        return {
            'title': movie_data.get('title', ''),
            'year': movie_data.get('year', 0),
            'genres': movie_data.get('genres', []),
            'watched_at': history_item.get('watched_at', ''),
            'trakt_id': movie_data.get('ids', {}).get('trakt', 0),
            'imdb_id': movie_data.get('ids', {}).get('imdb', ''),
            'tmdb_id': movie_data.get('ids', {}).get('tmdb', 0),
            'slug': movie_data.get('ids', {}).get('slug', ''),
            'overview': movie_data.get('overview', ''),
            'rating': movie_data.get('rating', 0)
        }
    
    def get_filtered_history(self, username: str, time_period: str = '1 month') -> List[Dict]:
        """Get filtered and processed watch history with caching"""
        # Try to get cached history first
        cached_history = self._get_cached_history(username, time_period)
        if cached_history:
            logger.info(f"Using cached history for {username}: {len(cached_history)} movies")
            return cached_history
        
        # Fetch fresh history if no cache
        raw_history = self.fetch_watch_history(username, time_period)
        
        # Extract and clean movie information
        processed_history = []
        seen_movies = set()  # Avoid duplicates
        
        for item in raw_history:
            movie_info = self.extract_movie_info(item)
            
            # Create unique identifier for deduplication
            movie_key = f"{movie_info['title']}_{movie_info['year']}"
            
            if movie_key not in seen_movies and movie_info['title']:
                processed_history.append(item)  # Keep original structure for compatibility
                seen_movies.add(movie_key)
        
        # Cache the processed history
        self._cache_history(username, processed_history, time_period)
        
        return processed_history
    
    def get_complete_cached_history(self, username: str) -> List[Dict]:
        """Get complete cached history for filtering purposes with incremental updates"""
        # Try to get from cache first
        cache_data = self.trakt_auth.redis_client.get(f'{self.trakt_auth.namespace}:user_history:{username}')
        if cache_data:
            import json
            cached_data = json.loads(cache_data)
            cached_history = cached_data.get('history', [])
            last_fetch_time = cached_data.get('last_fetch_time')
            
            # ALWAYS check for new movies and update cache
            if last_fetch_time:
                logger.info(f"Checking for new movies for {username} since {last_fetch_time}")
                new_movies = self._fetch_history_since(username, last_fetch_time)
                if new_movies:
                    logger.info(f"Found {len(new_movies)} new movies for {username}, updating cache")
                    # Update cache with new movies
                    self._update_cache_with_new_history(username, new_movies)
                    # Get updated cache
                    cache_data = self.trakt_auth.redis_client.get(f'{self.trakt_auth.namespace}:user_history:{username}')
                    cached_data = json.loads(cache_data)
                    cached_history = cached_data.get('history', [])
                else:
                    logger.info(f"No new movies found for {username}")
            
            logger.info(f"Using cached complete history for {username}: {len(cached_history)} movies")
            return cached_history
        
        # If no cache, fetch complete history
        logger.info(f"No cached history found for {username}, fetching complete history")
        return self.fetch_complete_watch_history(username)
    
    def _get_cached_history(self, username: str, time_period: str) -> Optional[List[Dict]]:
        """Get cached history and update with new movies"""
        try:
            cache_data = self.trakt_auth.redis_client.get(f'{self.trakt_auth.namespace}:user_history:{username}')
            if not cache_data:
                return None
            
            import json
            cached_data = json.loads(cache_data)
            cached_history = cached_data.get('history', [])
            last_fetch_time = cached_data.get('last_fetch_time')
            
            if not cached_history:
                return None
            
            # ALWAYS check for new movies and update cache
            if last_fetch_time:
                logger.info(f"Checking for new movies for {username} since {last_fetch_time}")
                new_movies = self._fetch_history_since(username, last_fetch_time)
                if new_movies:
                    logger.info(f"Found {len(new_movies)} new movies for {username}, updating cache")
                    # Update cache with new movies
                    self._update_cache_with_new_history(username, new_movies)
                    # Get updated cache
                    cache_data = self.trakt_auth.redis_client.get(f'{self.trakt_auth.namespace}:user_history:{username}')
                    cached_data = json.loads(cache_data)
                    cached_history = cached_data.get('history', [])
                else:
                    logger.info(f"No new movies found for {username}")
            
            # Filter cached history by time period
            days_back = self.get_days_back(time_period)
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            filtered_history = []
            for item in cached_history:
                watched_at = item.get('watched_at', '')
                if watched_at:
                    try:
                        # Parse watched_at timestamp
                        watched_date = datetime.fromisoformat(watched_at.replace('Z', '+00:00'))
                        if watched_date >= cutoff_date:
                            filtered_history.append(item)
                    except ValueError:
                        # If we can't parse the date, include it to be safe
                        filtered_history.append(item)
            
            logger.info(f"Using cached history for {username}: {len(filtered_history)} movies in {time_period}")
            return filtered_history
            
        except Exception as e:
            logger.error(f"Error getting cached history for {username}: {e}")
            return None
    
    def _cache_history(self, username: str, history: List[Dict], time_period: str) -> bool:
        """Cache the processed history"""
        try:
            # Get the most recent watched_at timestamp
            last_fetch_time = None
            for item in history:
                watched_at = item.get('watched_at', '')
                if watched_at and (not last_fetch_time or watched_at > last_fetch_time):
                    last_fetch_time = watched_at
            
            if not last_fetch_time:
                last_fetch_time = datetime.now().isoformat()
            
            # Store in cache
            cache_data = {
                'history': history,
                'last_fetch_time': last_fetch_time,
                'cached_at': time.time()
            }
            
            cache_key = f'{self.trakt_auth.namespace}:user_history:{username}'
            self.trakt_auth.redis_client.setex(cache_key, 86400 * 7, json.dumps(cache_data))  # 7 days
            
            logger.info(f"Cached history for {username}: {len(history)} movies")
            return True
            
        except Exception as e:
            logger.error(f"Error caching history for {username}: {e}")
            return False
    
    def get_genre_stats(self, history: List[Dict]) -> Dict[str, int]:
        """Get genre statistics from watch history"""
        genre_counts = {}
        
        for item in history:
            genres = item.get('movie', {}).get('genres', [])
            for genre in genres:
                genre_name = genre.get('name', 'Unknown')
                genre_counts[genre_name] = genre_counts.get(genre_name, 0) + 1
        
        return genre_counts
    
    def get_top_genres(self, history: List[Dict], top_n: int = 5) -> List[str]:
        """Get top N genres from watch history"""
        genre_stats = self.get_genre_stats(history)
        
        # Sort by count and return genre names
        sorted_genres = sorted(genre_stats.items(), key=lambda x: x[1], reverse=True)
        return [genre[0] for genre in sorted_genres[:top_n]]
    
    def get_watched_movie_ids(self, history: List[Dict]) -> set:
        """Extract TMDB IDs of watched movies to filter out from recommendations"""
        watched_ids = set()
        
        for item in history:
            movie_data = item.get('movie', {})
            tmdb_id = movie_data.get('ids', {}).get('tmdb')
            if tmdb_id:
                watched_ids.add(tmdb_id)
        
        # DEBUG: Log watched movie IDs count and sample
        logger.info(f"DEBUG: Extracted {len(watched_ids)} watched TMDB IDs. Sample: {list(watched_ids)[:5]}")
        
        return watched_ids
    
    def update_history_incrementally(self, username: str) -> bool:
        """Update cached history with only new entries since last fetch"""
        try:
            # Get current cache
            cache_data = self.trakt_auth.redis_client.get(f'{self.trakt_auth.namespace}:user_history:{username}')
            if not cache_data:
                # No cache, fetch complete history
                logger.info(f"No cache found for {username}, fetching complete history")
                complete_history = self.fetch_complete_watch_history(username)
                if complete_history:
                    self._cache_history(username, complete_history, "all_time")
                return True
            
            import json
            cached_data = json.loads(cache_data)
            last_fetch_time = cached_data.get('last_fetch_time')
            
            if not last_fetch_time:
                # No timestamp, fetch complete history
                complete_history = self.fetch_complete_watch_history(username)
                if complete_history:
                    self._cache_history(username, complete_history, "all_time")
                return True
            
            # Fetch only new history since last fetch
            logger.info(f"Fetching incremental history for {username} since {last_fetch_time}")
            new_history = self._fetch_history_since(username, last_fetch_time)
            
            if new_history:
                # Update cache with new entries
                self._update_cache_with_new_history(username, new_history)
                logger.info(f"Updated cache for {username} with {len(new_history)} new movies")
            else:
                logger.info(f"No new history found for {username}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating incremental history for {username}: {e}")
            return False
    
    def _fetch_history_since(self, username: str, since_time: str) -> List[Dict]:
        """Fetch history entries since a specific timestamp"""
        try:
            # Convert since_time to datetime
            since_date = datetime.fromisoformat(since_time.replace('Z', '+00:00'))
            start_date = since_date.strftime('%Y-%m-%d')
            
            # Fetch movie history with pagination
            all_history = []
            page = 1
            limit = 100
            
            while True:
                endpoint = f'/users/{username}/history/movies'
                params = f'?start_date={start_date}&page={page}&limit={limit}'
                
                history_data = self.trakt_auth.make_authenticated_request(
                    username, 
                    f'{endpoint}{params}'
                )
                
                if not history_data:
                    break
                
                all_history.extend(history_data)
                
                # If we got fewer items than the limit, we've reached the end
                if len(history_data) < limit:
                    break
                
                page += 1
                
                # Safety check to prevent infinite loops
                if page > 10:  # Max 1000 new items
                    break
            
            return all_history
            
        except Exception as e:
            logger.error(f"Error fetching history since {since_time} for {username}: {e}")
            return []
    
    def _update_cache_with_new_history(self, username: str, new_history: List[Dict]) -> bool:
        """Update cache with new history entries"""
        try:
            # Get existing cache
            cache_data = self.trakt_auth.redis_client.get(f'{self.trakt_auth.namespace}:user_history:{username}')
            if not cache_data:
                # No existing cache, store new history
                return self._cache_history(username, new_history, "all_time")
            
            import json
            cached_data = json.loads(cache_data)
            existing_history = cached_data.get('history', [])
            
            # Create set of existing movie IDs for deduplication
            existing_movie_ids = set()
            for item in existing_history:
                movie_id = item.get('movie', {}).get('ids', {}).get('trakt')
                if movie_id:
                    existing_movie_ids.add(movie_id)
            
            # Add only new movies
            updated_history = existing_history.copy()
            for new_item in new_history:
                movie_id = new_item.get('movie', {}).get('ids', {}).get('trakt')
                if movie_id and movie_id not in existing_movie_ids:
                    updated_history.append(new_item)
            
            # Update cache with merged history
            return self._cache_history(username, updated_history, "all_time")
            
        except Exception as e:
            logger.error(f"Error updating cache with new history for {username}: {e}")
            return False
