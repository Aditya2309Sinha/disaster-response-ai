# Disaster Response AI Agent System - Setup Guide

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Detailed Installation](#detailed-installation)
4. [API Keys Setup](#api-keys-setup)
5. [AWS Configuration](#aws-configuration)
6. [Running the Application](#running-the-application)
7. [Troubleshooting](#troubleshooting)

---

## 🔧 Prerequisites

### System Requirements
- **Python**: 3.9 or higher
- **pip**: Latest version
- **Virtual Environment**: venv or conda
- **AWS Account**: For S3, DynamoDB, SNS, Lambda
- **RAM**: Minimum 8GB (16GB recommended for vision models)
- **Disk Space**: 5GB for models and dependencies

### Required Accounts & API Keys
1. **OpenAI** - For GPT-4.1 and embeddings
2. **OpenWeatherMap** - For weather data
3. **NASA FIRMS** - For fire detection
4. **Google Earth Engine** - For terrain mapping
5. **Twitter/X Developer** - For SOS detection
6. **AWS** - For cloud infrastructure

---

## ⚡ Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/disaster-response-ai.git
cd disaster-response-ai

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Run the application
python disaster_response.py

# Or start the FastAPI server
uvicorn disaster_response:app --reload
```

---

## 📦 Detailed Installation

### Step 1: Python Environment

```bash
# Check Python version
python --version  # Should be 3.9+

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### Step 2: Install Dependencies

```bash
# Install all requirements
pip install -r requirements.txt

# Verify installations
pip list | grep -E "(langchain|crewai|llama-index|fastapi)"
```

### Step 3: Install Vision Models (Optional)

```bash
# Install PyTorch with CUDA (for GPU support)
# For CUDA 11.8:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# For CPU only:
pip install torch torchvision

# Download SAM model weights
mkdir -p models
cd models
wget https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth
cd ..
```

---

## 🔑 API Keys Setup

### 1. OpenAI API Key

```bash
# Visit: https://platform.openai.com/api-keys
# 1. Sign up or log in
# 2. Create new secret key
# 3. Add to .env:
OPENAI_API_KEY=sk-...
```

### 2. OpenWeatherMap API Key

```bash
# Visit: https://openweathermap.org/api
# 1. Sign up for free account
# 2. Go to API keys section
# 3. Generate new key
# 4. Add to .env:
OPENWEATHER_API_KEY=your_key_here
```

### 3. NASA FIRMS API Key

```bash
# Visit: https://firms.modaps.eosdis.nasa.gov/api/
# 1. Request API access
# 2. Receive MAP_KEY via email
# 3. Add to .env:
NASA_FIRMS_KEY=your_map_key
```

### 4. Google Earth Engine

```bash
# Visit: https://earthengine.google.com/
# 1. Sign up for GEE access
# 2. Authenticate:
earthengine authenticate

# 3. Add service account key to .env
GOOGLE_EARTH_ENGINE_KEY=your_key_here
```

### 5. Twitter/X API

```bash
# Visit: https://developer.twitter.com/
# 1. Apply for developer account
# 2. Create new app
# 3. Generate API keys and access tokens
# 4. Add to .env:
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
```

---

## ☁️ AWS Configuration

### Step 1: AWS Account Setup

```bash
# Install AWS CLI
pip install awscli

# Configure AWS credentials
aws configure
# Enter:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region (e.g., us-east-1)
# - Default output format (json)
```

### Step 2: Create S3 Bucket

```bash
# Create bucket for data storage
aws s3 mb s3://disaster-response-data --region us-east-1

# Set bucket policy (optional)
aws s3api put-bucket-policy --bucket disaster-response-data --policy file://bucket-policy.json
```

### Step 3: Create DynamoDB Tables

```bash
# SOS Messages table
aws dynamodb create-table \
    --table-name sos-messages \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Incidents table
aws dynamodb create-table \
    --table-name incidents \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

### Step 4: Create SNS Topic

```bash
# Create topic for evacuation alerts
aws sns create-topic --name disaster-alerts --region us-east-1

# Get the Topic ARN (add to .env)
aws sns list-topics --region us-east-1
```

### Step 5: Deploy Lambda Function (Optional)

```bash
# Package Lambda function
cd lambda
zip -r function.zip .
cd ..

# Create Lambda function
aws lambda create-function \
    --function-name disaster-response-processor \
    --runtime python3.11 \
    --role arn:aws:iam::ACCOUNT_ID:role/lambda-execution-role \
    --handler lambda_function.lambda_handler \
    --zip-file fileb://lambda/function.zip \
    --timeout 300 \
    --memory-size 1024 \
    --region us-east-1
```

### Step 6: IAM Permissions

Create IAM policy with required permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::disaster-response-data",
        "arn:aws:s3:::disaster-response-data/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/sos-messages",
        "arn:aws:dynamodb:*:*:table/incidents"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:*:*:disaster-alerts"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": "arn:aws:lambda:*:*:function:disaster-response-processor"
    }
  ]
}
```

---

## 🚀 Running the Application

### Option 1: Run FastAPI Server

```bash
# Start development server
uvicorn disaster_response:app --reload --host 0.0.0.0 --port 8000

# Or with Gunicorn for production
gunicorn disaster_response:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Access API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Option 2: Run Test Script

```bash
# Run the main test script
python disaster_response.py
```

### Option 3: Run with Docker

```bash
# Build Docker image
docker build -t disaster-response-ai .

# Run container
docker run -p 8000:8000 --env-file .env disaster-response-ai
```

### Option 4: Deploy to AWS Lambda

```bash
# Using Serverless Framework
serverless deploy

# Or using AWS SAM
sam build
sam deploy --guided
```

---

## 🧪 Testing the System

### Test API Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Create incident
curl -X POST http://localhost:8000/incidents/create \
  -H "Content-Type: application/json" \
  -d '{
    "type": "wildfire",
    "location": {"lat": 34.0522, "lng": -118.2437},
    "description": "Wildfire reported in Los Angeles area"
  }'

# Submit SOS message
curl -X POST http://localhost:8000/sos/submit \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Trapped in flood waters, need immediate help!",
    "location": {"lat": 34.0522, "lng": -118.2437},
    "source": "twitter"
  }'
```

### Run Unit Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=disaster_response --cov-report=html
```

---

## 🔍 Monitoring & Observability

### View Logs

```bash
# View application logs
tail -f logs/disaster_response.log

# View AWS CloudWatch logs
aws logs tail /aws/lambda/disaster-response-processor --follow

# View DynamoDB metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=sos-messages \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z \
  --period 3600 \
  --statistics Sum
```

---

## 🐛 Troubleshooting

### Issue: ModuleNotFoundError

```bash
# Solution: Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

### Issue: AWS Credentials Error

```bash
# Solution: Reconfigure AWS CLI
aws configure
# Or set environment variables:
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

### Issue: OpenAI Rate Limit

```bash
# Solution: Implement retry logic or upgrade plan
# Add to code:
from tenacity import retry, wait_exponential

@retry(wait=wait_exponential(multiplier=1, min=4, max=10))
async def call_openai_api():
    # API call here
```

### Issue: Twitter API Authentication Failed

```bash
# Solution: Regenerate tokens
# 1. Go to Twitter Developer Portal
# 2. Regenerate access tokens
# 3. Update .env file
# 4. Restart application
```

### Issue: Lambda Timeout

```bash
# Solution: Increase timeout
aws lambda update-function-configuration \
  --function-name disaster-response-processor \
  --timeout 900  # 15 minutes
```

### Issue: DynamoDB Capacity Exceeded

```bash
# Solution: Switch to on-demand billing
aws dynamodb update-table \
  --table-name sos-messages \
  --billing-mode PAY_PER_REQUEST
```

---

## 📊 Performance Optimization

### 1. Enable Caching

```python
# Install Redis
pip install redis

# Add to code:
import redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)
```

### 2. Parallel Processing

```python
# Already implemented with asyncio
# Increase max parallel agents in .env:
MAX_PARALLEL_AGENTS=10
```

### 3. Database Indexing

```bash
# Add GSI to DynamoDB for faster queries
aws dynamodb update-table \
  --table-name sos-messages \
  --attribute-definitions AttributeName=location,AttributeType=S \
  --global-secondary-index-updates file://gsi.json
```

---

## 🔒 Security Best Practices

1. **Never commit .env files** - Add to .gitignore
2. **Use AWS Secrets Manager** for production keys
3. **Enable API authentication** - Set API_KEY_ENABLED=true
4. **Use HTTPS** in production
5. **Implement rate limiting** - Prevent API abuse
6. **Regular security audits** - Check dependencies

```bash
# Check for vulnerabilities
pip install safety
safety check

# Update dependencies
pip list --outdated
pip install -U package_name
```

---

## 📚 Additional Resources

- **LangChain Docs**: https://python.langchain.com/docs
- **CrewAI Docs**: https://docs.crewai.com
- **LlamaIndex Docs**: https://docs.llamaindex.ai
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **AWS SDK**: https://boto3.amazonaws.com/v1/documentation/api/latest/index.html

---

## 🆘 Support

For issues and questions:
1. Check [GitHub Issues](https://github.com/yourusername/disaster-response-ai/issues)
2. Read the [FAQ](docs/FAQ.md)
3. Contact: support@disaster-response-ai.com

---

**Last Updated**: 2024  
**Version**: 1.0.0