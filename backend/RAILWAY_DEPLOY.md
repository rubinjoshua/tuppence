# Railway Deployment Guide

Step-by-step guide to deploy Tuppence backend to Railway.

## Prerequisites

- GitHub account (to connect repository)
- OpenAI API key (from https://platform.openai.com/api-keys)

## Step 1: Create Railway Account

1. Go to https://railway.app
2. Click "Start a New Project" or "Login with GitHub"
3. Sign up/login with your GitHub account

## Step 2: Create New Project from GitHub

1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Authorize Railway to access your GitHub repositories
4. Select the `tuppence` repository
5. Railway will detect the backend automatically

## Step 3: Add PostgreSQL Database

1. In your Railway project, click "New"
2. Select "Database"
3. Choose "PostgreSQL"
4. Railway will automatically:
   - Provision a PostgreSQL instance
   - Set the `DATABASE_URL` environment variable
   - Link it to your backend service

## Step 4: Configure Environment Variables

1. Click on your backend service (not the database)
2. Go to "Variables" tab
3. Click "New Variable"
4. Add the following:

   ```
   OPENAI_API_KEY=sk-your-actual-openai-api-key-here
   ```

5. The `DATABASE_URL` is already set automatically by Railway

## Step 5: Configure Build Settings

1. In your backend service, go to "Settings"
2. Under "Build Command", ensure it's empty (Railway auto-detects)
3. Under "Start Command", set to:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

## Step 6: Deploy

1. Railway will automatically deploy on git push
2. Monitor deployment in the "Deployments" tab
3. Wait for deployment to complete (usually 2-3 minutes)

## Step 7: Get Public URL

1. Go to "Settings" tab in your backend service
2. Scroll to "Networking" section
3. Click "Generate Domain"
4. Railway will create a public URL like:
   ```
   https://tuppence-backend-production.up.railway.app
   ```
5. Copy this URL for your iOS app configuration

## Step 8: Verify Deployment

Test your backend with curl:

```bash
# Health check
curl https://your-railway-url.railway.app/health

# Root endpoint
curl https://your-railway-url.railway.app/

# API docs (open in browser)
open https://your-railway-url.railway.app/docs
```

## Step 9: Initialize Database

The database will be automatically initialized on first request (the `init_db()` function runs on startup).

You can verify by checking:
```bash
curl https://your-railway-url.railway.app/monthly_budgets
```

Should return: `{"budgets": []}`

## Ongoing Deployment

Every time you push to GitHub, Railway will automatically:
1. Detect changes
2. Build new version
3. Deploy seamlessly with zero downtime

## Monitoring

Railway provides:
- **Logs**: Real-time application logs in "Deployments" tab
- **Metrics**: CPU, memory, network usage in "Metrics" tab
- **Variables**: Environment variable management in "Variables" tab

## Troubleshooting

### Database Connection Issues

Check that `DATABASE_URL` is set:
1. Go to Variables tab
2. Verify `DATABASE_URL` exists and starts with `postgresql://`

### OpenAI API Errors

Check that `OPENAI_API_KEY` is set:
1. Go to Variables tab
2. Verify `OPENAI_API_KEY` is set
3. Test API key at https://platform.openai.com/api-keys

### Application Won't Start

Check logs:
1. Go to "Deployments" tab
2. Click latest deployment
3. View logs for errors
4. Common issues:
   - Missing dependencies in requirements.txt
   - Syntax errors (check locally first)
   - Database connection timeout

## Free Tier Limits

Railway free tier includes:
- 500 hours of usage per month
- $5 worth of resources
- Enough for personal projects and development

For production use, consider upgrading to Railway Pro.

## Cost Optimization

To minimize costs:
1. Use `gpt-4o-mini` (already configured) instead of larger models
2. Caching is implemented to reduce API calls
3. Database connection pooling is enabled
4. Consider adding rate limiting if needed

## Next Steps

After deployment:
1. Test all endpoints using the API docs
2. Configure your iOS app with the Railway URL
3. Test the full workflow from iOS app
4. Monitor logs for any issues

## Updating Deployment

To update your backend:

```bash
# Make changes locally
git add .
git commit -m "Update backend"
git push

# Railway will automatically deploy the new version
```

## Support

- Railway docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Railway status: https://status.railway.app
