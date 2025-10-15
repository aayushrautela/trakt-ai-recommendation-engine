# Deployment Guide

## Quick Deployment to Vercel

### 1. Prepare Your Repository

1. Fork this repository
2. Update the `TRAKT_REDIRECT_URI` in your environment variables to match your deployment URL

### 2. Deploy to Vercel

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click "New Project"
3. Import your forked repository
4. Configure environment variables during import

### 3. Required Environment Variables

Add these in your Vercel project settings:

```bash
TRAKT_CLIENT_ID=your_trakt_client_id_here
TRAKT_CLIENT_SECRET=your_trakt_client_secret_here
TRAKT_REDIRECT_URI=https://your-app-name.vercel.app/oauth/callback
GEMINI_API_KEY=your_gemini_api_key_here
TMDB_API_KEY=your_tmdb_api_key_here
```

### 4. Set Up Redis Storage

1. In your Vercel project dashboard
2. Go to the "Storage" tab
3. Click "Create Database"
4. Select "Upstash Redis"
5. Follow the setup wizard
6. Vercel will automatically add the Redis environment variables

### 5. Update Trakt App Settings

1. Go to your [Trakt API Applications](https://trakt.tv/oauth/applications)
2. Edit your application
3. Update the Redirect URI to: `https://your-app-name.vercel.app/oauth/callback`

### 6. Test Your Deployment

1. Visit your deployed app URL
2. Click "Login with Trakt"
3. Complete the OAuth flow
4. Generate your first recommendation list

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `TRAKT_CLIENT_ID` | Your Trakt API application client ID | Yes |
| `TRAKT_CLIENT_SECRET` | Your Trakt API application client secret | Yes |
| `TRAKT_REDIRECT_URI` | OAuth callback URL (must match Trakt app settings) | Yes |
| `GEMINI_API_KEY` | Google Gemini AI API key | Yes |
| `TMDB_API_KEY` | The Movie Database API key | Yes |
| `REDIS_URL` | Redis connection URL (auto-added by Vercel) | Auto |
| `KV_REST_API_TOKEN` | Redis API token (auto-added by Vercel) | Auto |

## API Setup Instructions

### Trakt API Setup

1. Visit [Trakt API Applications](https://trakt.tv/oauth/applications)
2. Click "New Application"
3. Fill in:
   - **Name**: "AI Movie Recommendations" (or any name you prefer)
   - **Redirect URI**: `https://your-app-name.vercel.app/oauth/callback`
   - **Description**: "AI-powered movie recommendations based on watch history"
4. Save and note your Client ID and Client Secret

### Google Gemini API Setup

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy your API key
4. Note: Free tier has usage limits, monitor your usage

### TMDB API Setup

1. Visit [TMDB API Settings](https://www.themoviedb.org/settings/api)
2. Click "Request an API Key"
3. Fill out the application form
4. Once approved, copy your API key

## Troubleshooting Deployment

### Common Issues

**OAuth Redirect URI Mismatch**
- Ensure the URI in Trakt app settings exactly matches your deployment URL
- Include the full path: `/oauth/callback`

**Environment Variables Not Loading**
- Double-check variable names (case-sensitive)
- Redeploy after adding new variables
- Check Vercel function logs for errors

**Redis Connection Issues**
- Ensure Upstash Redis is properly set up
- Check that Redis environment variables are automatically added
- Verify Redis database is active

**Cron Job Not Running**
- Cron jobs run on UTC time
- Check Vercel function logs at 2 AM UTC
- Verify the cron schedule in `vercel.json`

### Monitoring Your Deployment

1. **Vercel Dashboard**: Monitor function logs and performance
2. **Redis Dashboard**: Check stored data and connections
3. **API Usage**: Monitor your API quotas for Gemini and TMDB

### Scaling Considerations

- **Gemini API**: Free tier has rate limits, consider upgrading for heavy usage
- **TMDB API**: Free tier should be sufficient for most use cases
- **Redis**: Upstash free tier includes 10,000 requests per day
- **Vercel**: Free tier includes 100GB-hours of serverless function execution

## Security Best Practices

1. **Environment Variables**: Never commit API keys to your repository
2. **Redis Access**: Use Vercel's built-in Redis integration
3. **OAuth Tokens**: Tokens are automatically refreshed and stored securely
4. **User Data**: Only necessary data is stored (configuration and tokens)

## Maintenance

### Regular Tasks

1. **Monitor API Usage**: Check quotas monthly
2. **Update Dependencies**: Keep packages updated for security
3. **Check Logs**: Review error logs weekly
4. **User Feedback**: Monitor for recommendation quality issues

### Backup Strategy

- **Redis Data**: Upstash provides automatic backups
- **Code**: Your repository serves as code backup
- **Configuration**: Environment variables are stored in Vercel
