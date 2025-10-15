# Trakt AI List Generator

An intelligent movie recommendation system that analyzes your Trakt.tv watch history and generates personalized movie lists using AI. The system automatically updates your recommendations nightly and creates curated lists of 20 movies based on your viewing patterns.

## Features

- **🤖 AI-Powered Recommendations**: Uses Google's Gemini AI to analyze your watch history and suggest similar and slightly different content
- **📊 Flexible Time Periods**: Choose from 1 day, 1 week, 1 month, or 3 months of watch history
- **🎭 Genre Filtering**: Filter recommendations by specific genres
- **🔄 Automatic Updates**: Lists are refreshed nightly with fresh recommendations
- **🔐 Secure Authentication**: Persistent OAuth with Trakt using Redis token storage

## How It Works

1. **Authentication**: Connect your Trakt account via OAuth
2. **History Analysis**: Fetches your watch history for the selected time period
3. **AI Analysis**: Gemini AI analyzes your viewing patterns and generates 50 recommendations
4. **Smart Filtering**: Filters out watched movies and duplicates, enriches with TMDB metadata
5. **List Creation**: Creates or updates your Trakt list with 20 curated movies
6. **Nightly Updates**: Automatically refreshes your list every night

## Quick Setup

### 1. Create API Accounts
- **Trakt API**: [Create app](https://trakt.tv/oauth/applications) with redirect URI `https://your-app.vercel.app/oauth/callback`
- **Google Gemini**: [Get API key](https://makersuite.google.com/app/apikey)
- **TMDB**: [Get API key](https://www.themoviedb.org/settings/api)

### 2. Deploy to Vercel
1. Fork this repository
2. Deploy to Vercel
3. Add environment variables:
   ```
   TRAKT_CLIENT_ID=your_client_id
   TRAKT_CLIENT_SECRET=your_client_secret
   TRAKT_REDIRECT_URI=https://your-app.vercel.app/oauth/callback
   GEMINI_API_KEY=your_gemini_key
   TMDB_API_KEY=your_tmdb_key
   ```

### 3. Set Up Redis
1. In Vercel dashboard → Storage tab
2. Create Upstash Redis database
3. Vercel auto-adds `REDIS_URL` and `KV_REST_API_TOKEN`

## Usage

1. Visit your deployed application
2. Click "Login with Trakt" to authenticate
3. Configure preferences:
   - **Time Period**: How far back to analyze (1 day to 3 months)
   - **Genres**: Optional genre filtering
   - **List Name**: Name for your list (default: "AI Recommendations")
4. Click "Generate Recommendations"
5. Your personalized list is created on Trakt
6. List automatically updates every night at 2 AM UTC

## Technical Details

### API Endpoints
- `GET /` - Main interface
- `GET /login` - Trakt OAuth
- `POST /api/generate-list` - Generate recommendations
- `POST /api/update-lists` - Nightly cron job

### Environment Variables
```bash
TRAKT_CLIENT_ID=your_trakt_client_id
TRAKT_CLIENT_SECRET=your_trakt_client_secret
TRAKT_REDIRECT_URI=https://your-app.vercel.app/oauth/callback
GEMINI_API_KEY=your_gemini_api_key
TMDB_API_KEY=your_tmdb_api_key
REDIS_URL=your_redis_url
KV_REST_API_TOKEN=your_kv_token
```

## Troubleshooting

**"No watch history found"**
- Ensure you've watched movies in the selected time period

**"Failed to generate recommendations"**
- Check your Gemini API key and quota

**"Failed to create list on Trakt"**
- Verify Trakt tokens are valid
- Check Trakt API rate limits

**Authentication issues**
- Ensure Trakt app redirect URI matches your Vercel URL
- Verify all environment variables are set

## Local Development

```bash
git clone <repository>
cd trakt_ai_gen
pip install -r requirements.txt
# Set up .env file with your API keys
redis-server
python api/index.py
```

## License

MIT License - see LICENSE file for details.