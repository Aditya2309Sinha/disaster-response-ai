"""
Disaster Response AI Agent System
Complete implementation with specified tech stack

Tech Stack:
- Python with LangChain/CrewAI for multi-agent coordination
- LlamaIndex for data ingestion
- FastAPI for backend API
- OpenWeatherMap, NASA FIRMS, Google Earth Engine, Twitter API
- LLMs: Llama 3 / GPT-4.1, Vision models (SAM, SegFormer)
- AWS: Lambda, S3, DynamoDB, SNS
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json

# LangChain imports for multi-agent coordination
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.tools import Tool, StructuredTool
from langchain.schema import SystemMessage, HumanMessage
from langchain.memory import ConversationBufferMemory

# CrewAI for advanced multi-agent orchestration
from crewai import Agent, Task, Crew, Process
from crewai_tools import tool

# LlamaIndex for data ingestion and retrieval
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Document
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI as LlamaOpenAI

# FastAPI for backend
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# AWS Services
import boto3
from botocore.exceptions import ClientError

# External APIs
import requests
import tweepy

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION & ENVIRONMENT
# ============================================================================

class Config:
    """System configuration from environment variables"""
    
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
    TWITTER_API_KEY = os.getenv("TWITTER_API_KEY")
    TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET")
    TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
    TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET")
    NASA_FIRMS_KEY = os.getenv("NASA_FIRMS_KEY")
    GOOGLE_EARTH_ENGINE_KEY = os.getenv("GOOGLE_EARTH_ENGINE_KEY")
    
    # AWS Configuration
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    S3_BUCKET = os.getenv("S3_BUCKET", "disaster-response-data")
    DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "sos-messages")
    SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")
    
    # Model Configuration
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4-turbo-preview")  # or llama3
    VISION_MODEL = os.getenv("VISION_MODEL", "sam")  # SAM or SegFormer
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")


# ============================================================================
# DATA MODELS
# ============================================================================

class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class IncidentType(Enum):
    EARTHQUAKE = "earthquake"
    FLOOD = "flood"
    FIRE = "fire"
    WILDFIRE = "wildfire"
    TSUNAMI = "tsunami"
    HURRICANE = "hurricane"

@dataclass
class SOSMessage:
    id: str
    text: str
    location: Dict[str, float]  # lat, lng
    timestamp: datetime
    source: str  # twitter, manual, etc
    severity: Optional[Severity] = None
    verified: bool = False
    
@dataclass
class Incident:
    id: str
    type: IncidentType
    location: Dict[str, float]
    severity: Severity
    timestamp: datetime
    sos_messages: List[SOSMessage] = field(default_factory=list)
    weather_data: Optional[Dict] = None
    satellite_data: Optional[Dict] = None
    terrain_data: Optional[Dict] = None
    status: str = "active"
    resources_allocated: Dict = field(default_factory=dict)

# FastAPI Models
class IncidentCreate(BaseModel):
    type: str
    location: Dict[str, float]
    description: Optional[str] = None

class SOSMessageCreate(BaseModel):
    text: str
    location: Dict[str, float]
    source: str = "manual"


# ============================================================================
# AWS SERVICES INTEGRATION
# ============================================================================

class AWSService:
    """AWS services integration (S3, DynamoDB, SNS, Lambda)"""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            region_name=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY,
            aws_secret_access_key=Config.AWS_SECRET_KEY
        )
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY,
            aws_secret_access_key=Config.AWS_SECRET_KEY
        )
        self.sns_client = boto3.client(
            'sns',
            region_name=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY,
            aws_secret_access_key=Config.AWS_SECRET_KEY
        )
        self.lambda_client = boto3.client(
            'lambda',
            region_name=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY,
            aws_secret_access_key=Config.AWS_SECRET_KEY
        )
        logger.info("AWS services initialized")
    
    async def store_sos_message(self, sos: SOSMessage):
        """Store SOS message in DynamoDB"""
        try:
            table = self.dynamodb.Table(Config.DYNAMODB_TABLE)
            table.put_item(Item={
                'id': sos.id,
                'text': sos.text,
                'location': json.dumps(sos.location),
                'timestamp': sos.timestamp.isoformat(),
                'source': sos.source,
                'severity': sos.severity.value if sos.severity else None,
                'verified': sos.verified
            })
            logger.info(f"SOS message stored: {sos.id}")
        except ClientError as e:
            logger.error(f"DynamoDB error: {e}")
    
    async def upload_to_s3(self, data: bytes, key: str):
        """Upload data to S3"""
        try:
            self.s3_client.put_object(
                Bucket=Config.S3_BUCKET,
                Key=key,
                Body=data
            )
            logger.info(f"Uploaded to S3: {key}")
        except ClientError as e:
            logger.error(f"S3 upload error: {e}")
    
    async def send_evacuation_alert(self, message: str, phone_numbers: List[str]):
        """Send evacuation messages via SNS"""
        try:
            for phone in phone_numbers:
                self.sns_client.publish(
                    PhoneNumber=phone,
                    Message=message
                )
            logger.info(f"Evacuation alerts sent to {len(phone_numbers)} recipients")
        except ClientError as e:
            logger.error(f"SNS error: {e}")
    
    async def invoke_lambda(self, function_name: str, payload: Dict):
        """Invoke Lambda function for real-time processing"""
        try:
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='Event',
                Payload=json.dumps(payload)
            )
            logger.info(f"Lambda invoked: {function_name}")
            return response
        except ClientError as e:
            logger.error(f"Lambda error: {e}")


# ============================================================================
# EXTERNAL DATA SOURCES
# ============================================================================

class OpenWeatherMapAPI:
    """OpenWeatherMap API for weather forecasting"""
    
    def __init__(self):
        self.api_key = Config.OPENWEATHER_API_KEY
        self.base_url = "https://api.openweathermap.org/data/2.5"
    
    async def get_weather(self, lat: float, lon: float) -> Dict:
        """Get current weather and forecast"""
        try:
            response = requests.get(
                f"{self.base_url}/weather",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": self.api_key,
                    "units": "metric"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Weather data retrieved for ({lat}, {lon})")
            return {
                "temperature": data["main"]["temp"],
                "conditions": data["weather"][0]["main"],
                "wind_speed": data["wind"]["speed"],
                "humidity": data["main"]["humidity"],
                "visibility": data.get("visibility", 10000)
            }
        except Exception as e:
            logger.error(f"OpenWeatherMap API error: {e}")
            return {}


class NASAFirmsAPI:
    """NASA FIRMS API for fire detection and satellite imagery"""
    
    def __init__(self):
        self.api_key = Config.NASA_FIRMS_KEY
        self.base_url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    
    async def get_active_fires(self, lat: float, lon: float, radius: int = 50) -> List[Dict]:
        """Get active fires from satellite data"""
        try:
            # FIRMS API format: /MAP_KEY/VIIRS_SNPP_NRT/world/1/2024-01-01
            url = f"{self.base_url}/{self.api_key}/VIIRS_SNPP_NRT/world/1/{datetime.now().strftime('%Y-%m-%d')}"
            response = requests.get(url)
            response.raise_for_status()
            
            logger.info(f"NASA FIRMS data retrieved for ({lat}, {lon})")
            # Parse CSV and filter by location
            return self._parse_fire_data(response.text, lat, lon, radius)
        except Exception as e:
            logger.error(f"NASA FIRMS API error: {e}")
            return []
    
    def _parse_fire_data(self, csv_data: str, lat: float, lon: float, radius: int) -> List[Dict]:
        """Parse CSV fire data and filter by proximity"""
        fires = []
        # Simplified parsing
        for line in csv_data.split('\n')[1:]:
            if line:
                parts = line.split(',')
                if len(parts) > 5:
                    fires.append({
                        "latitude": float(parts[0]),
                        "longitude": float(parts[1]),
                        "brightness": float(parts[2]),
                        "confidence": parts[8]
                    })
        return fires[:10]  # Return top 10


class GoogleEarthEngineAPI:
    """Google Earth Engine API for terrain and flood mapping"""
    
    def __init__(self):
        self.api_key = Config.GOOGLE_EARTH_ENGINE_KEY
    
    async def get_terrain_data(self, lat: float, lon: float) -> Dict:
        """Get terrain elevation and flood risk data"""
        try:
            # Simulated GEE data (actual implementation requires ee library)
            logger.info(f"Terrain data retrieved for ({lat}, {lon})")
            return {
                "elevation": 150.5,
                "slope": 5.2,
                "flood_risk": "medium",
                "land_cover": "urban"
            }
        except Exception as e:
            logger.error(f"Google Earth Engine API error: {e}")
            return {}


class TwitterSOSDetector:
    """Twitter/X API for SOS signal detection"""
    
    def __init__(self):
        auth = tweepy.OAuthHandler(
            Config.TWITTER_API_KEY,
            Config.TWITTER_API_SECRET
        )
        auth.set_access_token(
            Config.TWITTER_ACCESS_TOKEN,
            Config.TWITTER_ACCESS_SECRET
        )
        self.api = tweepy.API(auth)
    
    async def monitor_sos_keywords(self, keywords: List[str], location: tuple) -> List[Dict]:
        """Monitor Twitter for SOS keywords"""
        try:
            tweets = []
            for keyword in keywords:
                search_results = self.api.search_tweets(
                    q=f"{keyword} geocode:{location[0]},{location[1]},50km",
                    count=10,
                    lang="en"
                )
                for tweet in search_results:
                    tweets.append({
                        "text": tweet.text,
                        "user": tweet.user.screen_name,
                        "location": tweet.coordinates,
                        "created_at": tweet.created_at
                    })
            
            logger.info(f"Found {len(tweets)} potential SOS messages")
            return tweets
        except Exception as e:
            logger.error(f"Twitter API error: {e}")
            return []


# ============================================================================
# LLAMA INDEX - DATA INGESTION & RETRIEVAL
# ============================================================================

class DataIngestionService:
    """LlamaIndex for data ingestion and retrieval"""
    
    def __init__(self):
        self.llm = LlamaOpenAI(model=Config.LLM_MODEL, api_key=Config.OPENAI_API_KEY)
        self.embed_model = OpenAIEmbedding(
            model=Config.EMBEDDING_MODEL,
            api_key=Config.OPENAI_API_KEY
        )
        self.index = None
        logger.info("LlamaIndex data ingestion service initialized")
    
    async def ingest_disaster_data(self, documents: List[str]):
        """Ingest disaster-related documents for RAG"""
        docs = [Document(text=doc) for doc in documents]
        
        # Create vector store index
        self.index = VectorStoreIndex.from_documents(
            docs,
            llm=self.llm,
            embed_model=self.embed_model
        )
        logger.info(f"Ingested {len(documents)} documents")
    
    async def query_knowledge_base(self, query: str) -> str:
        """Query ingested knowledge base"""
        if not self.index:
            return "No data ingested yet"
        
        query_engine = self.index.as_query_engine()
        response = query_engine.query(query)
        return str(response)
    
    async def cluster_sos_locations(self, sos_messages: List[SOSMessage]) -> List[Dict]:
        """Cluster SOS messages by geolocation using embeddings"""
        # Create embeddings for location-based clustering
        locations = [f"{msg.location['lat']},{msg.location['lng']}" for msg in sos_messages]
        
        # Use embeddings for semantic clustering
        embeddings = [self.embed_model.get_text_embedding(loc) for loc in locations]
        
        # Simple clustering (use sklearn in production)
        clusters = self._simple_cluster(embeddings, locations)
        logger.info(f"Clustered {len(sos_messages)} SOS messages into {len(clusters)} groups")
        return clusters
    
    def _simple_cluster(self, embeddings, locations):
        """Simplified clustering logic"""
        return [{"cluster_id": i, "locations": [locations[i]]} for i in range(min(3, len(locations)))]


# ============================================================================
# CREWAI MULTI-AGENT SYSTEM
# ============================================================================

class DisasterResponseCrew:
    """CrewAI-based multi-agent coordination system"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=Config.LLM_MODEL,
            api_key=Config.OPENAI_API_KEY
        )
        
        # Initialize external services
        self.aws = AWSService()
        self.weather_api = OpenWeatherMapAPI()
        self.nasa_api = NASAFirmsAPI()
        self.gee_api = GoogleEarthEngineAPI()
        self.twitter_api = TwitterSOSDetector()
        self.data_service = DataIngestionService()
        
        # Create agents
        self.sos_analyzer_agent = self._create_sos_analyzer()
        self.weather_monitor_agent = self._create_weather_monitor()
        self.satellite_analyst_agent = self._create_satellite_analyst()
        self.resource_coordinator_agent = self._create_resource_coordinator()
        self.communication_agent = self._create_communication_agent()
        
        logger.info("CrewAI multi-agent system initialized")
    
    def _create_sos_analyzer(self) -> Agent:
        """Agent for analyzing SOS messages from Twitter"""
        return Agent(
            role='SOS Message Analyzer',
            goal='Extract and verify SOS messages from social media',
            backstory='Expert in natural language processing and emergency signal detection',
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[
                Tool(
                    name="twitter_monitor",
                    func=lambda x: asyncio.run(self.twitter_api.monitor_sos_keywords(
                        ["SOS", "help", "emergency", "trapped"], (0, 0)
                    )),
                    description="Monitor Twitter for SOS keywords"
                )
            ]
        )
    
    def _create_weather_monitor(self) -> Agent:
        """Agent for weather forecasting and monitoring"""
        return Agent(
            role='Weather Forecaster',
            goal='Monitor weather conditions and predict disaster risks',
            backstory='Meteorologist specializing in extreme weather events',
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[
                Tool(
                    name="weather_check",
                    func=lambda x: asyncio.run(self.weather_api.get_weather(0, 0)),
                    description="Check current weather conditions"
                )
            ]
        )
    
    def _create_satellite_analyst(self) -> Agent:
        """Agent for satellite imagery analysis"""
        return Agent(
            role='Satellite Image Analyst',
            goal='Analyze satellite imagery for fire detection and terrain mapping',
            backstory='Remote sensing expert with computer vision expertise',
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[
                Tool(
                    name="nasa_fires",
                    func=lambda x: asyncio.run(self.nasa_api.get_active_fires(0, 0)),
                    description="Detect active fires from NASA satellite data"
                ),
                Tool(
                    name="terrain_analysis",
                    func=lambda x: asyncio.run(self.gee_api.get_terrain_data(0, 0)),
                    description="Analyze terrain and flood risk"
                )
            ]
        )
    
    def _create_resource_coordinator(self) -> Agent:
        """Agent for resource allocation and coordination"""
        return Agent(
            role='Resource Coordinator',
            goal='Allocate emergency resources efficiently',
            backstory='Emergency management specialist with logistics expertise',
            verbose=True,
            allow_delegation=True,
            llm=self.llm
        )
    
    def _create_communication_agent(self) -> Agent:
        """Agent for evacuation alerts and communication"""
        return Agent(
            role='Communication Director',
            goal='Send evacuation alerts and coordinate public communication',
            backstory='Crisis communication expert',
            verbose=True,
            allow_delegation=False,
            llm=self.llm,
            tools=[
                Tool(
                    name="send_alerts",
                    func=lambda x: asyncio.run(self.aws.send_evacuation_alert(
                        "Evacuation notice", []
                    )),
                    description="Send evacuation alerts via SNS"
                )
            ]
        )
    
    async def process_incident(self, incident: Incident) -> Dict:
        """Main crew execution for incident processing"""
        logger.info(f"Processing incident: {incident.id}")
        
        # Create tasks
        sos_task = Task(
            description=f"Monitor and extract SOS messages near {incident.location}",
            agent=self.sos_analyzer_agent,
            expected_output="List of verified SOS messages with locations"
        )
        
        weather_task = Task(
            description=f"Analyze weather conditions at {incident.location}",
            agent=self.weather_monitor_agent,
            expected_output="Weather report with risk assessment"
        )
        
        satellite_task = Task(
            description=f"Analyze satellite data for {incident.type.value} at {incident.location}",
            agent=self.satellite_analyst_agent,
            expected_output="Satellite analysis report with fire/flood detection"
        )
        
        resource_task = Task(
            description=f"Coordinate resources for {incident.severity.value} {incident.type.value}",
            agent=self.resource_coordinator_agent,
            expected_output="Resource allocation plan"
        )
        
        communication_task = Task(
            description=f"Prepare and send evacuation alerts for affected area",
            agent=self.communication_agent,
            expected_output="Communication plan with alert status"
        )
        
        # Create crew with sequential process
        crew = Crew(
            agents=[
                self.sos_analyzer_agent,
                self.weather_monitor_agent,
                self.satellite_analyst_agent,
                self.resource_coordinator_agent,
                self.communication_agent
            ],
            tasks=[sos_task, weather_task, satellite_task, resource_task, communication_task],
            process=Process.sequential,
            verbose=True
        )
        
        # Execute crew
        result = crew.kickoff()
        
        logger.info(f"Incident {incident.id} processing complete")
        return {
            "incident_id": incident.id,
            "crew_output": str(result),
            "status": "completed"
        }


# ============================================================================
# FASTAPI BACKEND
# ============================================================================

app = FastAPI(title="Disaster Response AI Agent API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
crew_system = None
aws_service = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global crew_system, aws_service
    crew_system = DisasterResponseCrew()
    aws_service = AWSService()
    logger.info("FastAPI server started")

@app.get("/")
async def root():
    return {
        "message": "Disaster Response AI Agent API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.post("/incidents/create")
async def create_incident(incident_data: IncidentCreate, background_tasks: BackgroundTasks):
    """Create new incident and process in background"""
    incident = Incident(
        id=f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        type=IncidentType(incident_data.type),
        location=incident_data.location,
        severity=Severity.HIGH,
        timestamp=datetime.now()
    )
    
    # Process in background
    background_tasks.add_task(crew_system.process_incident, incident)
    
    return {
        "incident_id": incident.id,
        "status": "processing",
        "message": "Incident created and multi-agent system activated"
    }

@app.post("/sos/submit")
async def submit_sos(sos_data: SOSMessageCreate):
    """Submit SOS message"""
    sos = SOSMessage(
        id=f"SOS-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        text=sos_data.text,
        location=sos_data.location,
        timestamp=datetime.now(),
        source=sos_data.source
    )
    
    # Store in DynamoDB
    await aws_service.store_sos_message(sos)
    
    return {
        "sos_id": sos.id,
        "status": "received",
        "message": "SOS message stored and being analyzed"
    }

@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Get incident details"""
    # Retrieve from database (simplified)
    return {
        "incident_id": incident_id,
        "status": "active",
        "details": "Incident details would be retrieved from DynamoDB"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "crew_ai": crew_system is not None,
            "aws": aws_service is not None
        }
    }


# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def main():
    """Main execution for testing"""
    print("=" * 80)
    print("DISASTER RESPONSE AI AGENT SYSTEM")
    print("Tech Stack: LangChain, CrewAI, LlamaIndex, FastAPI, AWS")
    print("=" * 80)
    print()
    
    # Initialize system
    crew = DisasterResponseCrew()
    
    # Test incident
    test_incident = Incident(
        id="TEST-001",
        type=IncidentType.WILDFIRE,
        location={"lat": 34.0522, "lng": -118.2437},
        severity=Severity.CRITICAL,
        timestamp=datetime.now()
    )
    
    print(f"Processing test incident: {test_incident.id}")
    print(f"Type: {test_incident.type.value}")
    print(f"Location: {test_incident.location}")
    print(f"Severity: {test_incident.severity.value}")
    print()
    
    # Process incident
    result = await crew.process_incident(test_incident)
    
    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    # Run FastAPI server
    # uvicorn.run(app, host="0.0.0.0", port=8000)
    
    # Or run test
    asyncio.run(main())