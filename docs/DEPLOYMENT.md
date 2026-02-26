# DossieClean Deployment Guide

This guide covers deploying DossieClean in various environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development](#local-development)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [Environment Configuration](#environment-configuration)
- [Scaling Considerations](#scaling-considerations)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying DossieClean, ensure you have:

1. **Azure Blob Storage Account**
   - Create at [portal.azure.com](https://portal.azure.com)
   - Create a container for PDF storage
   - Note the connection string

2. **Qdrant Vector Database**
   - Sign up at [cloud.qdrant.io](https://cloud.qdrant.io)
   - Create a cluster (free tier available)
   - Note the URL and API key

3. **OpenAI API Key**
   - Get from [platform.openai.com](https://platform.openai.com/api-keys)
   - Ensure sufficient credits for your usage

## Local Development

### Quick Start

```bash
# Clone repository
git clone https://github.com/yourusername/dossieclean.git
cd dossieclean

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run application
python app.py
```

Access at: http://localhost:5000

### Development with Hot Reload

```bash
export FLASK_DEBUG=True
export FLASK_ENV=development
python app.py
```

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

## Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Manual Docker Build

```bash
# Build image
docker build -t dossieclean:latest .

# Run container
docker run -d \
  --name dossieclean \
  -p 5000:5000 \
  --env-file .env \
  dossieclean:latest
```

### Docker Environment Variables

Pass environment variables via `--env-file` or `-e`:

```bash
docker run -d \
  -p 5000:5000 \
  -e OPENAI_API_KEY=sk-xxx \
  -e AZURE_STORAGE_CONNECTION_STRING="..." \
  -e AZURE_CONTAINER_NAME=pdf-documents \
  -e QDRANT_URL=https://xxx.qdrant.io \
  -e QDRANT_API_KEY=xxx \
  dossieclean:latest
```

## Cloud Deployment

### Heroku

1. **Install Heroku CLI** and login:
   ```bash
   heroku login
   ```

2. **Create Heroku app**:
   ```bash
   heroku create dossieclean-app
   ```

3. **Set environment variables**:
   ```bash
   heroku config:set OPENAI_API_KEY=sk-xxx
   heroku config:set AZURE_STORAGE_CONNECTION_STRING="..."
   heroku config:set AZURE_CONTAINER_NAME=pdf-documents
   heroku config:set QDRANT_URL=https://xxx.qdrant.io
   heroku config:set QDRANT_API_KEY=xxx
   heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
   ```

4. **Create Procfile**:
   ```
   web: python app.py
   ```

5. **Deploy**:
   ```bash
   git push heroku main
   ```

### AWS (Elastic Beanstalk)

1. **Install EB CLI**:
   ```bash
   pip install awsebcli
   ```

2. **Initialize EB**:
   ```bash
   eb init -p python-3.11 dossieclean
   ```

3. **Create environment**:
   ```bash
   eb create dossieclean-env
   ```

4. **Set environment variables**:
   ```bash
   eb setenv OPENAI_API_KEY=sk-xxx \
             AZURE_STORAGE_CONNECTION_STRING="..." \
             QDRANT_URL=https://xxx.qdrant.io
   ```

5. **Deploy**:
   ```bash
   eb deploy
   ```

### Azure App Service

1. **Create App Service**:
   ```bash
   az webapp create \
     --resource-group myResourceGroup \
     --plan myAppServicePlan \
     --name dossieclean \
     --runtime "PYTHON:3.11"
   ```

2. **Configure settings**:
   ```bash
   az webapp config appsettings set \
     --resource-group myResourceGroup \
     --name dossieclean \
     --settings \
       OPENAI_API_KEY=sk-xxx \
       AZURE_STORAGE_CONNECTION_STRING="..." \
       QDRANT_URL=https://xxx.qdrant.io
   ```

3. **Deploy**:
   ```bash
   az webapp deployment source config-local-git \
     --resource-group myResourceGroup \
     --name dossieclean
   git push azure main
   ```

### Google Cloud Run

1. **Build and push image**:
   ```bash
   gcloud builds submit --tag gcr.io/PROJECT_ID/dossieclean
   ```

2. **Deploy**:
   ```bash
   gcloud run deploy dossieclean \
     --image gcr.io/PROJECT_ID/dossieclean \
     --platform managed \
     --allow-unauthenticated \
     --set-env-vars "OPENAI_API_KEY=sk-xxx,QDRANT_URL=https://xxx"
   ```

## Environment Configuration

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | `sk-proj-xxx` |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure connection string | `DefaultEndpointsProtocol=https;...` |
| `AZURE_CONTAINER_NAME` | Blob container name | `pdf-documents` |
| `QDRANT_URL` | Qdrant instance URL | `https://xxx.qdrant.io:6333` |
| `QDRANT_API_KEY` | Qdrant API key | `xxx` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | auto-generated per process | Flask session key (set explicitly in production) |
| `COLLECTION_NAME` | `AAU_PDF` | Qdrant collection name |
| `CHUNK_SIZE` | `512` | Text chunk size (tokens) |
| `CHUNK_OVERLAP` | `50` | Chunk overlap (tokens) |
| `MAX_UPLOAD_SIZE_MB` | `100` | Maximum upload size (MB) |
| `FLASK_DEBUG` | `False` | Enable debug mode |
| `PORT` | `5000` | Application port |
| `DOSSIECLEAN_INIT_STORAGE` | `true` | Set `false` to skip storage init during tests/CI |

### Production Checklist

- [ ] Set strong `SECRET_KEY` (64+ characters)
- [ ] Set `FLASK_DEBUG=False`
- [ ] Set `FLASK_ENV=production`
- [ ] Enable HTTPS
- [ ] Configure proper CORS
- [ ] Set up monitoring/logging
- [ ] Configure rate limiting
- [ ] Set up backups for Qdrant

## Scaling Considerations

### Horizontal Scaling

DossieClean can be scaled horizontally with some considerations:

1. **Stateless Design**: The app is mostly stateless
2. **Session Storage**: Use Redis for sessions in multi-instance deployments
3. **File Uploads**: Temporary files are cleaned up after processing
4. **Batch Processing**: Status files stored locally - consider shared storage

### Recommended Architecture for Scale

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  DossieClean    │ │  DossieClean    │ │  DossieClean    │
│  Instance 1     │ │  Instance 2     │ │  Instance 3     │
└────────┬────────┘ └────────┬────────┘ └────────┬────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│     Redis       │ │  Azure Blob     │ │     Qdrant      │
│   (Sessions)    │ │   Storage       │ │   (Vectors)     │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Performance Tuning

1. **Gunicorn Workers**: Use multiple workers in production
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

2. **Nginx Reverse Proxy**: Add nginx for static files and SSL
   ```nginx
   server {
       listen 80;
       server_name dossieclean.example.com;

       location /static {
           alias /app/static;
       }

       location / {
           proxy_pass http://localhost:5000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

3. **Connection Pooling**: Qdrant client maintains connections

## Troubleshooting

### Common Issues

**1. Azure Connection Failed**
```
Error: Azure container client is not properly initialized
```
- Check `AZURE_STORAGE_CONNECTION_STRING` format
- Verify container exists
- Check network connectivity

**2. Qdrant Connection Failed**
```
Error: Error connecting to Qdrant
```
- Verify `QDRANT_URL` includes port (`:6333`)
- Check API key is correct
- Ensure collection exists or can be created

**3. OpenAI API Errors**
```
Error: Error extracting metadata from PDF
```
- Verify API key is valid
- Check API quota/credits
- Ensure model access (`gpt-4o-mini`)

**4. Large File Upload Timeout**
```
Error: Request timeout
```
- Increase server timeout settings
- Check `MAX_CONTENT_LENGTH` in Flask config
- Use chunked upload for files >10MB

### Logging

View application logs:

```bash
# Local
tail -f dossieclean.log

# Docker
docker logs -f dossieclean

# Heroku
heroku logs --tail
```

### Health Check

Test application health:

```bash
curl http://localhost:5000/
```

### Debug Mode

Enable detailed logging:

```bash
export FLASK_DEBUG=True
python app.py
```

## Backup and Recovery

### Qdrant Backup

```bash
# Create snapshot
curl -X POST "https://your-qdrant-url/collections/AAU_PDF/snapshots"

# List snapshots
curl "https://your-qdrant-url/collections/AAU_PDF/snapshots"
```

### Azure Blob Backup

Use Azure's built-in backup features or:

```bash
# Using azcopy
azcopy copy "https://account.blob.core.windows.net/container" \
  "https://backup-account.blob.core.windows.net/backup" \
  --recursive
```

## Support

For deployment issues:
1. Check the [GitHub Issues](https://github.com/yourusername/dossieclean/issues)
2. Review logs for error messages
3. Open a new issue with environment details
