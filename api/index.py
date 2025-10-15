import os
import sys
import json
import logging
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from dotenv import load_dotenv

# Add the api directory to the python path for Vercel
sys.path.append(os.path.dirname(os.path.realpath(__file__)))

# Import our modules - use absolute imports for Vercel compatibility
from trakt_auth import TraktAuth
from history_fetcher import HistoryFetcher
from recommendation_engine import RecommendationEngine
from tmdb_client import TMDBClient
from trakt_list import TraktListManager
from update_lists import handle_cron_update

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Initialize components
trakt_auth = TraktAuth()
history_fetcher = HistoryFetcher()
recommendation_engine = RecommendationEngine()
tmdb_client = TMDBClient()
list_manager = TraktListManager()

@app.route('/')
def index():
    """Main page - show form if authenticated, login prompt if not"""
    return render_template('index.html')

@app.route('/login')
def login():
    """Redirect to Trakt OAuth"""
    auth_url = trakt_auth.get_auth_url()
    return render_template('login.html', auth_url=auth_url)

@app.route('/oauth/callback')
def oauth_callback():
    """Handle OAuth callback from Trakt"""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        return render_template('callback.html', success=False, error=error)
    
    if not code:
        return render_template('callback.html', success=False, error="No authorization code received")
    
    # Exchange code for tokens
    tokens = trakt_auth.exchange_code_for_tokens(code)
    if not tokens:
        return render_template('callback.html', success=False, error="Failed to get access tokens")
    
    # Get user info
    user_info = trakt_auth.get_user_info(tokens['access_token'])
    if not user_info:
        return render_template('callback.html', success=False, error="Failed to get user information")
    
    username = user_info.get('user', {}).get('username')
    if not username:
        return render_template('callback.html', success=False, error="No username found")
    
    # Store tokens
    trakt_auth.store_tokens(username, tokens)
    
    # Set session
    session['username'] = username
    
    return render_template('callback.html', success=True, username=username)

@app.route('/api/generate-list', methods=['POST'])
def generate_list():
    """Generate AI recommendations and create/update Trakt list"""
    if 'username' not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
    try:
        data = request.get_json()
        username = session['username']
        
        # Extract parameters
        time_period = data.get('time_period', '1 month')
        selected_genres = data.get('genres', [])
        list_name = data.get('list_name', 'AI Recommendations')
        
        print(f"🎯 Generating recommendations for {username}")
        
        # Fetch watch history
        history = history_fetcher.get_filtered_history(username, time_period)
        
        if not history:
            return jsonify({
                "success": False, 
                "error": f"No watch history found for the selected time period ({time_period}). Please watch some movies first!"
            }), 400
        
        # Generate AI recommendations
        recommendations = recommendation_engine.analyze_watch_history(
            history, time_period, selected_genres
        )
        
        if not recommendations:
            return jsonify({
                "success": False,
                "error": "Failed to generate recommendations. Please try again."
            }), 500
        
        # Get watched movie IDs to filter out
        watched_movie_ids = history_fetcher.get_watched_movie_ids(history)
        
        # Enrich with TMDB data and filter out watched movies
        enriched_movies = tmdb_client.enrich_movie_list(recommendations, selected_genres, watched_movie_ids)
        
        if not enriched_movies:
            return jsonify({
                "success": False,
                "error": "Failed to find movie information. Please try again."
            }), 500
        
        # Create/update Trakt list
        list_url = list_manager.create_or_update_list(username, list_name, enriched_movies)
        
        if not list_url:
            return jsonify({
                "success": False,
                "error": "Failed to create/update list on Trakt. Please try again."
            }), 500
        
        # Store user configuration for nightly updates
        config = {
            'time_period': time_period,
            'genres': selected_genres,
            'list_name': list_name
        }
        list_manager.store_user_config(username, config)
        
        print(f"🎉 List generation completed successfully!")
        
        return jsonify({
            "success": True,
            "list_url": list_url,
            "list_name": list_name,
            "movies_count": len(enriched_movies)
        })
        
    except Exception as e:
        logger.error(f"Error generating list: {e}")
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred. Please try again."
        }), 500

@app.route('/api/update-lists', methods=['GET', 'POST'])
def update_lists():
    """Cron job endpoint for nightly list updates"""
    # Verify this is a cron request (you might want to add authentication here)
    return handle_cron_update()

@app.route('/logout')
def logout():
    """Clear session and logout"""
    if 'username' in session:
        username = session['username']
        # Optionally delete stored tokens
        session.clear()
        logger.info(f"User {username} logged out")
    
    return redirect(url_for('index'))

@app.route('/api/refresh-token', methods=['POST'])
def refresh_token():
    """Manual token refresh endpoint for testing"""
    if 'username' not in session:
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    
    username = session['username']
    access_token = trakt_auth.get_valid_access_token(username)
    
    if access_token:
        return jsonify({"success": True, "message": "Token is valid"})
    else:
        return jsonify({"success": False, "error": "Token refresh failed"}), 401

@app.errorhandler(404)
def not_found(error):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500

# For local development
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
