# Trakt AI List Generator

An intelligent movie recommendation system that analyzes your Trakt.tv watch history and generates personalized movie lists using AI. The system automatically updates your recommendations nightly and creates curated lists of 20 movies based on your viewing patterns.

## Features

- **🤖 AI-Powered Recommendations**: Uses Google's Gemini AI to analyze your watch history and suggest similar and slightly different content
- **📊 Flexible Time Periods**: Choose from 1 day, 1 week, 1 month, or 3 months of watch history
- **🎭 Genre Filtering**: Filter recommendations by specific genres
- **🔄 Automatic Updates**: Lists are refreshed nightly with fresh recommendations
- **🔐 Secure Authentication**: Persistent OAuth with Trakt using Redis token storage
- **🎨 Beautiful Web Interface**: Clean, responsive design for easy configuration

## How It Works

1. **Authentication**: Connect your Trakt account via OAuth
2. **History Analysis**: The system fetches your watch history for the selected time period
3. **AI Analysis**: Gemini AI analyzes your viewing patterns and preferences
4. **Recommendation Generation**: Creates a mix of 70% similar content and 30% slightly different movies
5. **TMDB Enrichment**: Enriches recommendations with metadata and filters by selected genres
6. **List Creation**: Creates or updates your Trakt list with 20 curated movies
7. **Nightly Updates**: Automatically refreshes your list every night

## Setup Instructions

### 1. Create Required API Accounts

#### Trakt API App
- Go to [Trakt API Applications](https://trakt.tv/oauth/applications)
- Click "New Application"
- Set Redirect URI to: `https://your-app-name.vercel.app/oauth/callback`
- Save your Client ID and Client Secret

#### Google Gemini API
- Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
- Create a new API key
- Save your API key

#### TMDB API
- Go to [TMDB API](https://www.themoviedb.org/settings/api)
- Request an API key
- Save your API key

### 2. Deploy to Vercel

1. Fork this repository
2. Deploy to Vercel
3. Add environment variables:
   - `TRAKT_CLIENT_ID`
   - `TRAKT_CLIENT_SECRET`
   - `TRAKT_REDIRECT_URI`
   - `GEMINI_API_KEY`
   - `TMDB_API_KEY`

### 3. Set Up Redis Storage

1. In your Vercel project dashboard
2. Go to Storage tab
3. Create Upstash Redis database
4. Vercel will automatically add `REDIS_URL` and `KV_REST_API_TOKEN`

### 4. Update Trakt App Settings

1. Update your Trakt app's redirect URI with your actual Vercel URL
2. Update the `TRAKT_REDIRECT_URI` environment variable

## Usage

1. Visit your deployed application
2. Click "Login with Trakt" to authenticate
3. Configure your preferences:
   - **Time Period**: How far back to analyze your watch history
   - **Genres**: Optional genre filtering
   - **List Name**: Name for your recommendation list (default: "AI Recommendations")
4. Click "Generate Recommendations"
5. Your personalized list will be created on Trakt
6. The list will automatically update every night at 2 AM UTC

## API Endpoints

- `GET /` - Main application interface
- `GET /login` - Initiate Trakt OAuth
- `GET /oauth/callback` - Handle OAuth callback
- `POST /api/generate-list` - Generate new recommendations
- `POST /api/update-lists` - Nightly cron job endpoint
- `GET /logout` - Clear session and logout

## Configuration Options

### Time Periods
- **1 day**: Recent movies only
- **1 week**: Past week's viewing
- **1 month**: Past month (default)
- **3 months**: Extended history analysis

### Supported Genres
- Action, Adventure, Animation, Comedy
- Crime, Documentary, Drama, Family
- Fantasy, History, Horror, Music
- Mystery, Romance, Science Fiction
- Thriller, War, Western

## Technical Architecture

### Components
- **Flask Web App**: Main application server
- **Trakt Auth**: OAuth flow with token management
- **History Fetcher**: Retrieves and processes watch history
- **Recommendation Engine**: Gemini AI integration
- **TMDB Client**: Movie metadata and genre filtering
- **List Manager**: Trakt list creation and updates
- **Redis Storage**: Persistent token and configuration storage

### Data Flow
1. User authenticates via Trakt OAuth
2. System fetches watch history for specified period
3. Gemini AI analyzes patterns and generates recommendations
4. TMDB enriches recommendations with metadata
5. Movies are filtered by selected genres
6. Top 20 movies are added to Trakt list
7. Configuration is stored for nightly updates

## Environment Variables

```bash
# Required
TRAKT_CLIENT_ID=your_trakt_client_id
TRAKT_CLIENT_SECRET=your_trakt_client_secret
TRAKT_REDIRECT_URI=https://your-app.vercel.app/oauth/callback
GEMINI_API_KEY=your_gemini_api_key
TMDB_API_KEY=your_tmdb_api_key

# Auto-added by Vercel Upstash
REDIS_URL=your_redis_url
KV_REST_API_TOKEN=your_kv_token
```

## Local Development

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables in `.env` file
4. Run Redis locally: `redis-server`
5. Start the application: `python api/index.py`

## Troubleshooting

### Common Issues

**"No watch history found"**
- Ensure you've watched movies in the selected time period
- Check that your Trakt account has viewing history

**"Failed to generate recommendations"**
- Verify your Gemini API key is correct
- Check API quota limits

**"Failed to create list on Trakt"**
- Ensure your Trakt tokens are valid
- Check Trakt API rate limits

**Authentication issues**
- Verify your Trakt app settings match your deployment URL
- Check that all environment variables are set correctly

### Logs and Monitoring

- Check Vercel function logs for detailed error information
- Monitor Redis storage for token and configuration data
- Use the `/api/refresh-token` endpoint to test authentication

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Trakt.tv](https://trakt.tv/) for the movie tracking API
- [Google Gemini](https://ai.google.dev/) for AI recommendations
- [TMDB](https://www.themoviedb.org/) for movie metadata
- [Vercel](https://vercel.com/) for hosting and serverless functions
- [Upstash](https://upstash.com/) for Redis storage
