import os
import json
import time
import redis
import requests
from datetime import datetime, timedelta
from flask import session, redirect, url_for, request
import logging

logger = logging.getLogger(__name__)

class TraktAuth:
    def __init__(self):
        self.client_id = os.getenv('TRAKT_CLIENT_ID')
        self.client_secret = os.getenv('TRAKT_CLIENT_SECRET')
        self.redirect_uri = os.getenv('TRAKT_REDIRECT_URI')
        self.base_url = 'https://api.trakt.tv'
        self.namespace = os.getenv('REDIS_NAMESPACE', 'trakt_ai_gen')
        
        # Redis connection
        redis_url = os.getenv('REDIS_URL')
        if redis_url:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
        else:
            # Fallback for local development
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    def get_auth_url(self):
        """Generate Trakt OAuth authorization URL"""
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri
        }
        
        auth_url = 'https://trakt.tv/oauth/authorize?' + '&'.join([f'{k}={v}' for k, v in params.items()])
        return auth_url
    
    def exchange_code_for_tokens(self, code):
        """Exchange authorization code for access and refresh tokens"""
        data = {
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/oauth/token',
                json=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Token exchange failed: {e}")
            return None
    
    def refresh_access_token(self, refresh_token):
        """Refresh access token using refresh token"""
        data = {
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'refresh_token'
        }
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/oauth/token',
                json=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Token refresh failed: {e}")
            return None
    
    def store_tokens(self, username, tokens):
        """Store tokens in Redis with expiration"""
        token_data = {
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token'],
            'expires_in': tokens['expires_in'],
            'created_at': time.time(),
            'scope': tokens.get('scope', '')
        }
        
        # Store with expiration (subtract 5 minutes for safety)
        expires_at = time.time() + tokens['expires_in'] - 300
        self.redis_client.setex(
            f'{self.namespace}:trakt_tokens:{username}',
            int(expires_at - time.time()),
            json.dumps(token_data)
        )
    
    def get_tokens(self, username):
        """Get tokens from Redis"""
        try:
            token_data = self.redis_client.get(f'{self.namespace}:trakt_tokens:{username}')
            if token_data:
                return json.loads(token_data)
        except Exception as e:
            logger.error(f"Failed to get tokens for {username}: {e}")
        return None
    
    def get_valid_access_token(self, username):
        """Get valid access token, refreshing if necessary"""
        tokens = self.get_tokens(username)
        if not tokens:
            return None
        
        # Check if token is expired (with 5 minute buffer)
        current_time = time.time()
        token_age = current_time - tokens['created_at']
        
        if token_age >= tokens['expires_in'] - 300:  # 5 minute buffer
            # Token is expired, try to refresh
            new_tokens = self.refresh_access_token(tokens['refresh_token'])
            if new_tokens:
                self.store_tokens(username, new_tokens)
                return new_tokens['access_token']
            else:
                # Refresh failed, user needs to re-authenticate
                return None
        
        return tokens['access_token']
    
    def get_user_info(self, access_token):
        """Get user information from Trakt"""
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': self.client_id
        }
        
        try:
            response = requests.get(
                f'{self.base_url}/users/settings',
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to get user info: {e}")
            return None
    
    def make_authenticated_request(self, username, endpoint, method='GET', data=None):
        """Make authenticated request to Trakt API"""
        access_token = self.get_valid_access_token(username)
        if not access_token:
            return None
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'trakt-api-version': '2',
            'trakt-api-key': self.client_id
        }
        
        try:
            if method == 'GET':
                response = requests.get(f'{self.base_url}{endpoint}', headers=headers)
            elif method == 'POST':
                response = requests.post(f'{self.base_url}{endpoint}', json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(f'{self.base_url}{endpoint}', headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
