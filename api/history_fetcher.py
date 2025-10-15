import logging
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
        
        logger.info(f"Fetching watch history for {username} from {start_date}")
        
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
                logger.error(f"Failed to fetch history page {page} for {username}")
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
                logger.warning(f"Reached maximum page limit for {username}")
                break
        
        logger.info(f"Fetched {len(all_history)} movies for {username}")
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
        """Get filtered and processed watch history"""
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
        
        logger.info(f"Processed {len(processed_history)} unique movies for {username}")
        return processed_history
    
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
        
        logger.info(f"Found {len(watched_ids)} unique watched movie TMDB IDs")
        return watched_ids
