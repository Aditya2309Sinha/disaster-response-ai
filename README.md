# Disaster Response AI Agent System

An autonomous multi-agent system for coordinating emergency response during natural disasters.

## 🎯 Features

- Multi-agent coordination using LangChain & CrewAI
- Real-time SOS detection from Twitter/X
- Weather monitoring via OpenWeatherMap
- Satellite imagery analysis (NASA FIRMS)
- Terrain mapping with Google Earth Engine
- AWS cloud infrastructure (S3, DynamoDB, SNS, Lambda)
- FastAPI REST API backend

## 🚀 Tech Stack

- **Python** - Core language
- **LangChain/CrewAI** - Multi-agent coordination
- **LlamaIndex** - Data ingestion & RAG
- **FastAPI** - Backend API
- **AWS Services** - Cloud infrastructure
- **AI Models** - GPT-4.1, SAM, SegFormer

## 📦 Installation
```bash
pip install -r requirements.txt
```

## ⚙️ Configuration

1. Copy `.env.example` to `.env`
2. Add your API keys
3. Configure AWS credentials

## 🏃 Running
```bash
# Start FastAPI server
uvicorn disaster_response:app --reload

# Or run test
python disaster_response.py
```

## 📚 Documentation

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions.

## 🎓 Course Project

This project demonstrates:
- ✅ Multi-agent systems (LLM, Parallel, Sequential, Loop agents)
- ✅ Tools integration (MCP, Custom, Built-in)
- ✅ Sessions & Memory management
- ✅ Context engineering
- ✅ Observability (Logging, Tracing, Metrics)

## 📄 License

MIT License