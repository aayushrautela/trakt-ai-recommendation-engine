import os
import sys
import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class TMDBClient:
    def __init__(self):
        self.api_key = os.getenv('TMDB_API_KEY')
        self.base_url = 'https://api.themoviedb.org/3'
        self.image_base_url = 'https://image.tmdb.org/t/p/w500'
        
        # TMDB genre mapping (common genres)
        self.genre_map = {
            'action': 28,
            'adventure': 12,
            'animation': 16,
            'comedy': 35,
            'crime': 80,
            'documentary': 99,
            'drama': 18,
            'family': 10751,
            'fantasy': 14,
            'history': 36,
            'horror': 27,
            'music': 10402,
            'mystery': 9648,
            'romance': 10749,
            'science fiction': 878,
            'thriller': 53,
            'war': 10752,
            'western': 37
        }
    
    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search for a movie by title"""
        params = {
            'api_key': self.api_key,
            'query': title,
            'language': 'en-US',
            'include_adult': False
        }
        
        if year:
            params['year'] = year
        
        try:
            response = requests.get(
                f'{self.base_url}/search/movie',
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            if data['results']:
                # Return the first result
                movie = data['results'][0]
                return {
                    'id': movie['id'],
                    'title': movie['title'],
                    'original_title': movie.get('original_title'),
                    'release_date': movie.get('release_date'),
                    'genre_ids': movie.get('genre_ids', []),
                    'overview': movie.get('overview'),
                    'poster_path': movie.get('poster_path'),
                    'vote_average': movie.get('vote_average'),
                    'popularity': movie.get('popularity')
                }
        except requests.RequestException as e:
            logger.error(f"TMDB search failed for '{title}': {e}")
        
        return None
    
    def get_movie_details(self, movie_id: int) -> Optional[Dict]:
        """Get detailed information about a movie"""
        params = {
            'api_key': self.api_key,
            'language': 'en-US'
        }
        
        try:
            response = requests.get(
                f'{self.base_url}/movie/{movie_id}',
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"TMDB movie details failed for ID {movie_id}: {e}")
            return None
    
    def get_genre_id(self, genre_name: str) -> Optional[int]:
        """Convert genre name to TMDB genre ID"""
        genre_lower = genre_name.lower().strip()
        return self.genre_map.get(genre_lower)
    
    def get_genre_name(self, genre_id: int) -> Optional[str]:
        """Convert TMDB genre ID to genre name"""
        for name, gid in self.genre_map.items():
            if gid == genre_id:
                return name
        return None
    
    def filter_movies_by_genres(self, movies: List[Dict], selected_genres: List[str]) -> List[Dict]:
        """Filter movies by selected genres"""
        if not selected_genres:
            return movies
        
        # Convert genre names to IDs
        genre_ids = []
        for genre in selected_genres:
            genre_id = self.get_genre_id(genre)
            if genre_id:
                genre_ids.append(genre_id)
        
        if not genre_ids:
            return movies
        
        # Filter movies that have at least one of the selected genres
        filtered_movies = []
        for movie in movies:
            if movie.get('genre_ids'):
                if any(genre_id in movie['genre_ids'] for genre_id in genre_ids):
                    filtered_movies.append(movie)
        
        return filtered_movies
    
    def enrich_movie_list(self, movie_titles: List[str], selected_genres: List[str] = None, watched_movie_ids: set = None) -> List[Dict]:
        """Enrich a list of movie titles with TMDB data and filter by genres and watched status"""
        enriched_movies = []
        
        for title in movie_titles:
            # Try to extract year from title if present
            year = None
            if '(' in title and ')' in title:
                try:
                    year_str = title.split('(')[-1].split(')')[0]
                    year = int(year_str)
                    title = title.split('(')[0].strip()
                except ValueError:
                    pass
            
            movie_data = self.search_movie(title, year)
            if movie_data:
                # Check if this movie is already watched
                if watched_movie_ids and movie_data.get('id') in watched_movie_ids:
                    continue
                
                enriched_movies.append(movie_data)
        
        # Filter by genres if specified
        if selected_genres:
            enriched_movies = self.filter_movies_by_genres(enriched_movies, selected_genres)
        
        # Sort by popularity and return top 20
        enriched_movies.sort(key=lambda x: x.get('popularity', 0), reverse=True)
        final_movies = enriched_movies[:20]
        
        # Found movies after filtering
        return final_movies
    
    def convert_to_trakt_slug(self, movie_data: Dict) -> str:
        """Convert TMDB movie data to Trakt slug format"""
        title = movie_data['title']
        year = movie_data.get('release_date', '').split('-')[0] if movie_data.get('release_date') else ''
        
        # Create slug: lowercase, replace spaces with hyphens, remove special chars
        slug = title.lower()
        slug = slug.replace(' ', '-')
        slug = ''.join(c for c in slug if c.isalnum() or c == '-')
        
        if year:
            return f"{slug}-{year}"
        return slug
