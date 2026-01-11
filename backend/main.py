from fastapi import FastAPI, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict
import uuid
import os
import json
import re
import time
import hashlib
import sys
import io
import asyncio

# Force UTF-8 encoding for stdout/stderr to prevent crashes on some terminals
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from collections import defaultdict, deque
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
#AIzaSyCtjpIF9-GFkJboudELV6ycE6IWZ5ROBns

from google import genai
from google.genai import types

from google.genai.errors import ServerError
from duckduckgo_search import DDGS

from models import (
    init_db, get_db, UserProfile, FoodItem, Message, MessageRole, NutritionPlan,
    HealthMetric, WorkoutSession, HealthAlert
)
from schemas import (
    UserProfileCreate, UserProfileResponse, UserProfileUpdate,
    FoodItemCreate, FoodItemResponse,
    MessageCreate, MessageResponse,
    DailyStats
)

# Health Coach Integration - Pi เป็นสมองหลัก
from health_ai_engine import HealthAIEngine
from health_coach import HealthCoachEngine
from mqtt_handler import MQTTHealthHandler, AlertType, AlertPriority

# ============================================================
# Stronger Rate limit (per-endpoint) + cache + in-flight lock
# ============================================================

# --- Per-endpoint limits (ต่อ IP) ---
RATE_LIMITS = {
    "users": {"window": 60, "max": 3},          # สมัคร/สร้างโปรไฟล์ (หนัก) 3 ครั้ง/นาที
    "analyze_food": {"window": 60, "max": 5},   # วิเคราะห์รูป (หนัก) 5 ครั้ง/นาที
    "chat": {"window": 60, "max": 10},          # แชท 10 ครั้ง/นาที
}

# hits: (ip, bucket) -> deque[timestamps]
_hits = defaultdict(deque)

def rate_limit(ip: str, bucket: str):
    cfg = RATE_LIMITS.get(bucket, {"window": 60, "max": 10})
    window = cfg["window"]
    max_req = cfg["max"]

    now = time.time()
    q = _hits[(ip, bucket)]
    while q and q[0] <= now - window:
        q.popleft()

    if len(q) >= max_req:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests for {bucket}. Please slow down."
        )
    q.append(now)

# --- Cache (กันกดส่งซ้ำ / รูปเดิมซ้ำ) ---
CACHE_TTL = 30
_cache = {}  # key -> (expire_ts, value)

def cache_key(*parts: str) -> str:
    raw = "|".join(parts).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()

def cache_get(key: str):
    now = time.time()
    item = _cache.get(key)
    if not item:
        return None
    exp, val = item
    if exp < now:
        _cache.pop(key, None)
        return None
    return val

def cache_set(key: str, val: str, ttl: int = CACHE_TTL):
    _cache[key] = (time.time() + ttl, val)

# --- In-flight lock (กันเรียก Gemini ซ้อนคำถาม/รูปเดิม) ---
# inflight: key -> expire_ts
_INFLIGHT_TTL = 25  # กันค้าง (เผื่อ request ตาย)
_inflight = {}

def inflight_acquire(key: str):
    now = time.time()
    expired = [k for k, exp in _inflight.items() if exp < now]
    for k in expired:
        _inflight.pop(k, None)

    if key in _inflight:
        raise HTTPException(status_code=409, detail="Same request is in progress. Please wait a moment.")

    _inflight[key] = now + _INFLIGHT_TTL

def inflight_release(key: str):
    _inflight.pop(key, None)

# ============================================================
# Smart API Cooldown System - ประหยัด API calls เมื่อ rate limited
# ============================================================

# Track API cooldown per model
_api_cooldown = {}  # model_name -> cooldown_until_timestamp
_API_COOLDOWN_DURATION = 300  # หยุดยิง 5 นาทีเมื่อโดน 429
_api_stats = {
    "total_calls": 0,
    "rate_limited": 0,
    "saved_calls": 0,  # จำนวน calls ที่ประหยัดได้
    "last_429_time": None
}

def is_api_on_cooldown(model_name: str) -> bool:
    """ตรวจสอบว่า model นี้อยู่ในช่วง cooldown หรือไม่"""
    now = time.time()
    cooldown_until = _api_cooldown.get(model_name, 0)
    if cooldown_until > now:
        remaining = int(cooldown_until - now)
        print(f"[COOLDOWN] Model {model_name} is on cooldown for {remaining}s more. Skipping to save resources.")
        _api_stats["saved_calls"] += 1
        return True
    return False

def set_api_cooldown(model_name: str, duration: int = _API_COOLDOWN_DURATION):
    """ตั้ง cooldown สำหรับ model ที่โดน rate limit"""
    _api_cooldown[model_name] = time.time() + duration
    _api_stats["rate_limited"] += 1
    _api_stats["last_429_time"] = time.time()
    print(f"[COOLDOWN] Model {model_name} rate limited. Cooling down for {duration}s.")

def get_api_stats():
    """ดึงสถิติการใช้ API"""
    return {
        **_api_stats,
        "cooldown_models": {k: int(v - time.time()) for k, v in _api_cooldown.items() if v > time.time()},
        "efficiency": f"{(_api_stats['saved_calls'] / max(_api_stats['total_calls'], 1)) * 100:.1f}%" if _api_stats['total_calls'] > 0 else "N/A"
    }

# ============================================================
# Gemini helper: retry/backoff + map 503 properly
# ============================================================
# Fallback chain as requested
FALLBACK_CHAIN = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemma-3-27b-it"
]

def gemini_generate_with_backoff(model: str, contents, config: Optional[types.GenerateContentConfig] = None, max_tries: int = 2, force_model: str = None) -> str:
    # Track total calls for stats
    _api_stats["total_calls"] += 1
    
    # Decide which models to try
    if force_model:
        models_to_try = [force_model]
        print(f"[DEBUG] Forcing usage of model: {force_model}")
    else:
        # Build fallback chain
        models_to_try = [model]
        for m in FALLBACK_CHAIN:
            if m != model and m not in models_to_try:
                models_to_try.append(m)

    # Filter out cooldown models (unless forced)
    available_models = []
    for m in models_to_try:
        if force_model or not is_api_on_cooldown(m):
            available_models.append(m)
        else:
            print(f"[COOLDOWN] Model {m} is skipping due to cooldown.")

    if not available_models:
        print("[COOLDOWN] All models turned down. Waiting resources.")
        raise HTTPException(status_code=503, detail="AI Service temporarily on cooldown.")

    last_error = None

    for model_name in available_models:
        print(f"[DEBUG] Attempting AI generation with model: {model_name}")
        delay = 1.0
        
        for attempt in range(1, max_tries + 1):
            try:
                # Special handling for Gemma
                current_config = config
                if "gemma" in model_name.lower():
                    current_config = None

                resp = client.models.generate_content(model=model_name, contents=contents, config=current_config)

                if resp.candidates and resp.candidates[0].grounding_metadata and resp.candidates[0].grounding_metadata.search_entry_point:
                    print(f"[DEBUG] Google Search used by model: {model_name}")
                
                return (resp.text or "").strip()

            except Exception as e:
                last_error = e
                error_str = str(e)
                print(f"[WARN] Model {model_name} (Attempt {attempt}/{max_tries}) failed: {error_str}")

                if "429" in error_str or "Resource has been exhausted" in error_str:
                    set_api_cooldown(model_name, _API_COOLDOWN_DURATION)
                    break # Rate limit -> Next model

                is_fatal = any(x in error_str for x in ["404", "400", "Not Found", "Invalid Argument"])
                if is_fatal:
                    break 

                if "503" in error_str:
                    if attempt < max_tries:
                        time.sleep(delay)
                        delay = min(delay * 2, 5.0)
                        continue
                
                break # Unknown error -> Next model

    # If forced model failed, we should probably let caller know specifically
    if force_model:
        raise HTTPException(status_code=503, detail=f"Forced model {force_model} failed: {last_error}")

    raise HTTPException(status_code=500, detail=f"AI Service Temporarily Unavailable. Last error: {last_error}")


# ============================================================
# App
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str

app = FastAPI(title="SmartFood Analyzer API", version="1.0.0")

# Initialize database on startup
@app.on_event("startup")
def startup():
    init_db()
    
    # Start Watch Service Auto-connect
    if WATCH_SERVICE_AVAILABLE:
        try:
            service = get_watch_service()
            service.start_auto_connect(interval=5.0)
            print("✅ Watch service auto-connect started on boot")
        except Exception as e:
            print(f"⚠️ Failed to start watch service: {e}")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Health Coach Integration - Pi เป็นสมองหลัก
# ============================================================

# Initialize MQTT handler (mock mode for development)
mqtt_handler = MQTTHealthHandler(broker="localhost", port=1883, mock_mode=True)

# Initialize Health AI Engine (per-user instances will be created as needed)
health_engines: Dict[int, HealthAIEngine] = {}

# Initialize Health Coach
health_coach = HealthCoachEngine(mqtt_handler=mqtt_handler, enable_mqtt=True)

# Real Watch Service (imported separately for optional BLE connection)
try:
    from watch_service import AolonRealTimeService, get_watch_service
    WATCH_SERVICE_AVAILABLE = True
    print("✅ Watch service available")
except ImportError:
    WATCH_SERVICE_AVAILABLE = False
    print("⚠️ Watch service not available")


class WebSocketConnectionManager:
    """จัดการ WebSocket connections สำหรับ real-time health data"""
    
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"🔌 WebSocket connected: user {user_id}")
    
    def disconnect(self, user_id: int):
        self.active_connections.pop(user_id, None)
        print(f"🔌 WebSocket disconnected: user {user_id}")
    
    async def send_health_data(self, user_id: int, data: dict):
        """ส่งข้อมูลสุขภาพแบบ real-time ไปยัง client"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(data)
            except Exception as e:
                print(f"Failed to send to user {user_id}: {e}")
                self.disconnect(user_id)
    
    async def broadcast_alert(self, user_id: int, alert: dict):
        """ส่ง alert ไปยัง user"""
        await self.send_health_data(user_id, {"type": "alert", "data": alert})


ws_manager = WebSocketConnectionManager()


def get_health_engine(user_id: int, db: Session) -> HealthAIEngine:
    """Get or create Health AI Engine for a user"""
    if user_id not in health_engines:
        # Load user info from DB
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if user:
            engine = HealthAIEngine(user_age=user.age, user_weight=user.weight)
            health_engines[user_id] = engine
        else:
            # Default engine
            health_engines[user_id] = HealthAIEngine()
    return health_engines[user_id]


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ============================================================
# Real Watch API Endpoints (Aolon Curve)
# ============================================================

@app.get("/watch/status")
async def get_watch_status():
    """Get current watch connection status and data"""
    if not WATCH_SERVICE_AVAILABLE:
        return {"available": False, "error": "Watch service not installed"}
    
    service = get_watch_service()
    data = service.get_current_data()
    
    return {
        "available": True,
        "connected": service.connected,
        "hr": data["hr"],
        "steps": data["steps"],
        "battery": data["battery"],
        "last_update": data["last_update"]
    }


class WatchDataInput(BaseModel):
    """Input model for watch data from crontab script"""
    hr: int = 0
    steps: int = 0
    battery: int = 0
    timestamp: int = 0
    connected: bool = False


@app.post("/watch/data")
async def receive_watch_data(data: WatchDataInput, db: Session = Depends(get_db)):
    """Receive watch data from crontab script (read_watch.py) and save to database"""
    if not WATCH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Watch service not available")
    
    service = get_watch_service()
    
    # Update service data from crontab script
    if data.hr > 0:
        service.current_hr = data.hr
    if data.steps > 0:
        service.steps = data.steps
    if data.battery > 0:
        service.battery = data.battery
    
    service.last_update = data.timestamp or time.time()
    service.connected = data.connected
    
    # Auto-save to database (HealthMetric)
    if data.connected and (data.steps > 0 or data.hr > 0):
        try:
            from datetime import datetime
            now = datetime.now()
            
            # Calculate activity type from HR
            if data.hr < 80:
                activity = "resting"
            elif data.hr < 100:
                activity = "walking"
            elif data.hr < 120:
                activity = "light_exercise"
            else:
                activity = "moderate_exercise"
            
            # Calculate calories
            calories = data.steps * 0.04 if data.steps > 0 else 0
            
            # Calculate health risk
            risk = "HIGH" if data.hr > 150 else ("MODERATE" if data.hr > 120 else "LOW")
            
            health_metric = HealthMetric(
                user_id=1,  # Default user
                timestamp=int(data.timestamp or time.time()),
                date=now.strftime("%Y-%m-%d"),
                heart_rate=data.hr if data.hr > 0 else None,
                steps=data.steps,
                calories_burned=calories,
                activity_type=activity,
                health_risk_level=risk
            )
            db.add(health_metric)
            db.commit()
            print(f"💾 Health log saved: HR={data.hr} Steps={data.steps}")
        except Exception as e:
            print(f"⚠️ Failed to save health log: {e}")
    
    print(f"📡 Crontab data received: HR={data.hr} Steps={data.steps} Battery={data.battery}%")
    
    return {"status": "ok", "message": "Data updated from crontab", "saved_to_db": True}


@app.post("/watch/connect")
async def connect_watch(background_tasks: BackgroundTasks):
    """Connect to Aolon watch (runs in background)"""
    if not WATCH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Watch service not available")
    
    service = get_watch_service()
    
    if service.connected:
        return {"status": "already_connected", "data": service.get_current_data()}
    
    # Start auto-connect service
    service.start_auto_connect(interval=5.0)
    
    return {"status": "connecting", "message": "Watch auto-connect service started"}


@app.post("/watch/disconnect")
async def disconnect_watch():
    """Disconnect from watch"""
    if not WATCH_SERVICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Watch service not available")
    
    service = get_watch_service()
    
    # Stop auto-connect service
    service.stop_auto_connect()
    
    async def do_disconnect():
        await service.disconnect()
    
    asyncio.create_task(do_disconnect())
    
    return {"status": "disconnecting", "message": "Watch disconnecting..."}


# ============================================================
# WebSocket for Real-time Watch Data
# ============================================================

class WatchWebSocketManager:
    """จัดการ WebSocket connections สำหรับ watch data real-time"""
    
    def __init__(self):
        self.connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        print(f"📡 Watch WebSocket connected. Total: {len(self.connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
        print(f"📡 Watch WebSocket disconnected. Total: {len(self.connections)}")
    
    async def broadcast(self, data: dict):
        """Broadcast watch data to all connected clients"""
        disconnected = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.disconnect(ws)


watch_ws_manager = WatchWebSocketManager()


@app.websocket("/ws/watch")
async def websocket_watch_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint สำหรับ real-time watch data
    Server จะ push updates ทุก 2 วินาที
    """
    await watch_ws_manager.connect(websocket)
    
    try:
        while True:
            # Get current watch data
            if WATCH_SERVICE_AVAILABLE:
                service = get_watch_service()
                data = service.get_current_data()
                
                watch_data = {
                    "type": "watch_update",
                    "connected": service.connected,
                    "hr": data["hr"],
                    "steps": data["steps"],
                    "battery": data["battery"],
                    "last_update": data["last_update"],
                    "timestamp": time.time()
                }
            else:
                watch_data = {
                    "type": "watch_update",
                    "connected": False,
                    "hr": 0,
                    "steps": 0,
                    "battery": 0,
                    "last_update": 0,
                    "timestamp": time.time()
                }
            
            # Send to this client
            await websocket.send_json(watch_data)
            
            # Wait 2 seconds before next update
            await asyncio.sleep(2)
            
    except WebSocketDisconnect:
        watch_ws_manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        watch_ws_manager.disconnect(websocket)


@app.get("/api-stats")
async def api_statistics():
    """ดูสถิติการใช้ API และ cooldown status เพื่อประหยัด resources"""
    stats = get_api_stats()
    return {
        "total_api_calls": stats["total_calls"],
        "rate_limited_count": stats["rate_limited"],
        "saved_calls": stats["saved_calls"],
        "efficiency": stats["efficiency"],
        "cooldown_models": stats["cooldown_models"],
        "last_rate_limit": stats["last_429_time"],
        "message": "Models on cooldown will be skipped to save resources"
    }


@app.post("/ai/overview-summary")
async def generate_overview_summary(data: dict):
    """
    AI สรุปภาพรวมโภชนาการ + สุขภาพ
    ใช้ Gemini สร้างสรุปแบบ personalized
    """
    try:
        nutrition = data.get("nutrition", {})
        health = data.get("health", {})
        user_info = data.get("user", {})
        
        # Check if we have valid data
        has_nutrition = nutrition.get("calories_eaten", 0) > 0
        has_health = health.get("steps", 0) > 0 or health.get("heart_rate", 0) > 0
        
        if not has_nutrition and not has_health:
            return {"summary": "ยังไม่มีข้อมูลเพียงพอ กรุณาบันทึกอาหารหรือเชื่อมต่อนาฬิกาก่อน"}
        
        # Build prompt for AI
        prompt = f"""คุณเป็น AI นักโภชนาการและโค้ชสุขภาพส่วนตัว สรุปภาพรวมสุขภาพวันนี้ให้สั้นกระชับ เป็นภาษาไทย เข้าใจง่าย

ข้อมูลผู้ใช้: {user_info.get('name', 'ผู้ใช้')} 
เป้าหมาย: {user_info.get('goal', 'MaintainWeight')}

📊 โภชนาการวันนี้:
- กินไปแล้ว: {nutrition.get('calories_eaten', 0)} kcal (เป้า {nutrition.get('target_calories', 2000)} kcal, {nutrition.get('percentage', 0)}%)
- คงเหลือ: {nutrition.get('remaining', 0)} kcal
- โปรตีน: {nutrition.get('protein', 0)}g | คาร์บ: {nutrition.get('carbs', 0)}g | ไขมัน: {nutrition.get('fat', 0)}g

💪 ข้อมูลสุขภาพ:
- Heart Rate: {health.get('heart_rate', 0)} BPM
- ก้าววันนี้: {health.get('steps', 0)}/10,000
- แคลอรี่เบิร์น: {health.get('calories_burned', 0)} kcal
- กิจกรรม: {health.get('activity', 'unknown')}
- ความเหนื่อยล้า: {health.get('fatigue', 0)}%

สรุปให้เป็น bullet points สั้นๆ 3-4 ข้อ พร้อม emoji ที่เหมาะสม เน้นให้กำลังใจและคำแนะนำที่ปฏิบัติได้จริง
ห้ามใช้ markdown headers (#) หรือ *** ให้ใช้ emoji และตัวหนา **text** แทน"""

        # Try to use Gemini
        if client:
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=prompt
                )
                if response and response.text:
                    return {"summary": response.text.strip()}
            except Exception as e:
                print(f"Gemini error: {e}")
        
        # Fallback to local summary
        nutrition_status = ""
        if nutrition.get('remaining', 0) > 0:
            nutrition_status = f"✅ **ดีมาก!** ยังทานได้อีก {nutrition.get('remaining', 0)} kcal"
        else:
            nutrition_status = f"⚠️ ทานเกินเป้า {abs(nutrition.get('remaining', 0))} kcal ลองออกกำลังกายเพิ่มนะ"
        
        steps = health.get('steps', 0)
        if steps >= 10000:
            steps_status = "🎉 **ยอดเยี่ยม!** เดินครบ 10,000 ก้าวแล้ว!"
        elif steps >= 5000:
            steps_status = f"👍 เดินได้ดี! อีก {(10000 - steps):,} ก้าวจะถึงเป้า"
        else:
            steps_status = f"🚶 ลองเดินเพิ่มอีกนะ อีก {(10000 - steps):,} ก้าว"
        
        fatigue = health.get('fatigue', 0)
        if fatigue > 70:
            energy_status = "😓 ความเหนื่อยล้าสูง ควรพักผ่อนให้เพียงพอ"
        elif fatigue > 40:
            energy_status = "⚡ พลังงานปานกลาง ลองออกกำลังกายเบาๆ"
        else:
            energy_status = "💪 สบายดี! พร้อมลุยกิจกรรมได้เลย"
        
        summary = f"""📊 **สรุปภาพรวมวันนี้**

🍽️ **โภชนาการ:** {nutrition_status}

👟 **การเดิน:** {steps_status}

{energy_status}

💡 **คำแนะนำ:** ดื่มน้ำให้เพียงพอและพักผ่อนอย่างน้อย 7-8 ชั่วโมง"""
        
        return {"summary": summary}
        
    except Exception as e:
        print(f"Overview summary error: {e}")
        return {"summary": "ไม่สามารถสร้างสรุปได้ กรุณาลองใหม่อีกครั้ง"}


# ============================================================
# Initialize Gemini client
# ============================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
print(f"[DEBUG] GEMINI_API_KEY loaded: {'YES' if GEMINI_API_KEY else 'NO'}")
print(f"[DEBUG] API Key length: {len(GEMINI_API_KEY)}" if GEMINI_API_KEY else "[DEBUG] No API key found")

client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        print("[DEBUG] Gemini client initialized successfully")
    except Exception as e:
        print(f"[DEBUG] Failed to initialize Gemini client: {e}")


# ============================================================
# Search Tool Config
# ============================================================
SEARCH_CONFIG = types.GenerateContentConfig(
    tools=[types.Tool(google_search=types.GoogleSearch())],
    response_mime_type="text/plain" 
)

def perform_duckduckgo_search(query: str) -> str:
    try:
        print(f"[DEBUG] Performing DuckDuckGo search for: {query}")
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No search results found."
        summary = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        return summary
    except Exception as e:
        print(f"DuckDuckGo Search failed: {e}")
        return "Search unavailable."

# ==================== User Profile Endpoints ====================

@app.post("/users", response_model=UserProfileResponse)
def create_user(user: UserProfileCreate, db: Session = Depends(get_db), req: Request = None):
    # per-endpoint limit
    if req and req.client:
        rate_limit(req.client.host, "users")

    ai_assessment = "AI Analysis unavailable (API Key missing)"
    target_calories = None
    target_protein = None
    target_carbs = None
    target_fat = None
    daily_tips = "[]"

    if client:
        try:
            prompt = f"""
บทบาท: คุณคือ "NutriFriend" เพื่อนซี้ที่มีความรู้ลึกรู้จริงด้านโภชนาการและสุขภาพ
บุคลิก: เป็นกันเอง, เข้าถึงง่าย, จริงใจ, หวังดี, และคอยให้กำลังใจ (Supportive)
สไตล์การเขียน: เล่าเรื่องเหมือนเพื่อนคุยกับเพื่อน ใช้ภาษาพูดที่เป็นธรรมชาติ (Spoken Language) ไม่ใช้คำศัพท์ทางการหรือวิชาการที่เข้าใจยาก

ข้อมูลเพื่อนของคุณ:
ชื่อ: {user.name}
อายุ: {user.age}
เพศ: {user.gender}
น้ำหนัก: {user.weight} kg
ส่วนสูง: {user.height} cm
ระดับกิจกรรม: {user.activity_level}
เป้าหมาย: {user.goal}
ระยะเวลาเป้าหมาย: {user.target_timeline or 'ไม่ระบุ'}
โรคประจำตัว: {user.conditions}
ข้อจำกัดอาหาร: {user.dietary_restrictions}

ภารกิจของคุณ:
ช่วยวิเคราะห์และวางแผนการกินให้เพื่อนหน่อย โดยอ้างอิงหลักการแพทย์ที่น่าเชื่อถือ (เช่น กรมอนามัย, INMUCAL, รพ.ศิริราช/รามา) แต่ให้เรียบเรียงใหม่เป็นคำพูดของคุณเองที่ชวนอ่าน

หัวข้อที่ต้องตอบ:
1. เช็คสุขภาพกันหน่อย (ประเมิน BMI, BMR แบบเข้าใจง่ายๆ ว่าตอนนี้หุ่นเป็นไง)
2. ควรกินยังไงดี? (แนะนำแคลอรี่และสารอาหารแบบไม่ต้องเครียดมาก)
3. How-to พิชิตเป้าหมาย (ขอคำแนะนำที่ทำได้จริง ไม่ขายฝัน)
4. เรื่องที่ต้องระวัง (เตือนด้วยความเป็นห่วง)
5. 7 วัน 7 เคล็ดลับ (ทริคเล็กๆ น้อยๆ ในการดูแลตัวเอง)

ตอบเป็น JSON เท่านั้น ในรูปแบบ:
{{
  "assessment": "เนื้อหาคำแนะนำในรูปแบบ Markdown",
  "targets": {{
    "calories": ตัวเลข,
    "protein": ตัวเลข,
    "carbs": ตัวเลข,
    "fat": ตัวเลข
  }},
  "daily_tips": ["...7 items..."]
}}
"""
            # cache กันสมัครซ้ำ
            key = cache_key(
                "create_user",
                user.username,
                user.name,
                str(user.age),
                str(user.weight),
                str(user.height),
                str(user.goal),
                str(user.activity_level),
                str(user.gender),
            )
            cached = cache_get(key)
            if cached:
                result_text = cached
            else:
                # inflight กัน request ซ้อน
                inflight_acquire(key)
                try:
                    # Enable search for profile assessment to find medical info
                    result_text = gemini_generate_with_backoff(
                        "gemini-3-flash-preview", 
                        [prompt],
                        config=SEARCH_CONFIG
                    )
                    cache_set(key, result_text, ttl=60)
                finally:
                    inflight_release(key)

            json_match = re.search(r'\{[\s\S]*\}', result_text)
            if json_match:
                result = json.loads(json_match.group())
                ai_assessment = result.get("assessment", "ไม่สามารถดึงข้อมูลคำแนะนำได้")
                targets = result.get("targets", {})
                target_calories = targets.get("calories")
                target_protein = targets.get("protein")
                target_carbs = targets.get("carbs")
                target_fat = targets.get("fat")
                daily_tips_list = result.get("daily_tips", [])
                daily_tips = json.dumps(daily_tips_list, ensure_ascii=False)
            else:
                ai_assessment = result_text

        except HTTPException:
            ai_assessment = "ขออภัย ไม่สามารถวิเคราะห์ข้อมูลได้ในขณะนี้"
        except Exception as e:
            print(f"AI Assessment failed: {e}")
            ai_assessment = "ขออภัย ไม่สามารถวิเคราะห์ข้อมูลได้ในขณะนี้"

    db_user = UserProfile(
        username=user.username,
        password=user.password,
        name=user.name,
        age=user.age,
        gender=user.gender,
        weight=user.weight,
        height=user.height,
        activity_level=user.activity_level,
        goal=user.goal,
        conditions=user.conditions,
        dietary_restrictions=user.dietary_restrictions,
        target_timeline=user.target_timeline,
        ai_assessment=ai_assessment,
        target_calories=target_calories,
        target_protein=target_protein,
        target_carbs=target_carbs,
        target_fat=target_fat,
        daily_tips=daily_tips
    )
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")


@app.post("/login", response_model=UserProfileResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(
        UserProfile.username == login_data.username,
        UserProfile.password == login_data.password
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return user


@app.get("/users/{user_id}", response_model=UserProfileResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.put("/users/{user_id}", response_model=UserProfileResponse)
def update_user(user_id: int, user_update: UserProfileUpdate, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


# ==================== Refresh Plan & Tips Endpoints ====================

@app.post("/users/{user_id}/refresh-plan")
def refresh_nutrition_plan(user_id: int, db: Session = Depends(get_db)):
    """Refresh AI nutrition plan based on current food logs"""
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not client:
        return {"status": "skipped", "reason": "AI not available"}

    # Get recent food logs (last 7 days)
    from datetime import datetime, timedelta
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)
    
    foods = db.query(FoodItem).filter(
        FoodItem.user_id == user_id,
        FoodItem.date >= start_date.isoformat(),
        FoodItem.date <= end_date.isoformat()
    ).all()

    # Calculate current intake
    total_calories = sum(f.calories for f in foods)
    total_protein = sum(f.protein for f in foods)
    total_carbs = sum(f.carbs for f in foods)
    total_fat = sum(f.fat for f in foods)
    avg_calories = round(total_calories / 7, 0) if foods else 0

    food_summary = ", ".join([f.name for f in foods[:10]]) if foods else "ยังไม่มีข้อมูล"

    try:
        prompt = f"""บทบาท: คุณคือ "NutriFriend" เพื่อนซี้โภชนาการ
        
ข้อมูลเพื่อน {user.name}:
- อายุ: {user.age} ปี | เพศ: {user.gender}
- น้ำหนัก: {user.weight} kg | ส่วนสูง: {user.height} cm
- เป้าหมาย: {user.goal}
- โรคประจำตัว: {user.conditions or 'ไม่มี'}

สรุปอาหาร 7 วันที่ผ่านมา:
- แคลอรี่รวม: {total_calories:.0f} kcal (เฉลี่ย {avg_calories:.0f}/วัน)
- โปรตีน: {total_protein:.0f}g | คาร์บ: {total_carbs:.0f}g | ไขมัน: {total_fat:.0f}g
- อาหารที่กิน: {food_summary}

ช่วยวิเคราะห์และให้คำแนะนำสั้นๆ (2-3 ย่อหน้า) ว่าเพื่อนกินตามเป้าหมายไหม และควรปรับอะไรบ้าง
ใช้ภาษาเป็นกันเอง เหมือนเพื่อนคุยกัน ตอบเป็น Markdown"""

        result_text = gemini_generate_with_backoff("gemini-3-flash-preview", [prompt])
        
        # Update user's ai_assessment
        user.ai_assessment = result_text
        db.commit()
        
        return {"status": "success", "assessment": result_text}

    except Exception as e:
        print(f"[ERROR] Refresh plan failed: {e}")
        return {"status": "error", "reason": str(e)}


@app.post("/users/{user_id}/refresh-tips")
def refresh_daily_tips(user_id: int, model: Optional[str] = None, db: Session = Depends(get_db)):
    """Generate new daily tips for user"""
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not client:
        return {"status": "skipped", "reason": "AI not available"}

    try:
        prompt = f"""บทบาท: คุณคือ "NutriFriend" เพื่อนซี้โภชนาการ

สร้างเคล็ดลับดูแลสุขภาพ 7 ข้อ สำหรับเพื่อน {user.name}
- เป้าหมาย: {user.goal}
- โรคประจำตัว: {user.conditions or 'ไม่มี'}
- ข้อจำกัดอาหาร: {user.dietary_restrictions or 'ไม่มี'}

ให้เคล็ดลับที่ทำได้จริง สั้นกระชับ 1 ประโยค เป็นกันเอง
ตอบเป็น JSON array เท่านั้น: ["tip1", "tip2", ...]"""

        result_text = gemini_generate_with_backoff("gemini-3-flash-preview", [prompt], force_model=model)
        
        # Parse JSON array
        json_match = re.search(r'\[[\s\S]*\]', result_text)
        if json_match:
            tips = json.loads(json_match.group())
            user.daily_tips = json.dumps(tips, ensure_ascii=False)
            db.commit()
            return {"status": "success", "tips": tips}
        else:
            return {"status": "error", "reason": "Could not parse tips"}

    except Exception as e:
        print(f"[ERROR] Refresh tips failed: {e}")
        return {"status": "error", "reason": str(e)}


@app.post("/users/{user_id}/adaptive-plan")
def generate_adaptive_plan(user_id: int, model: Optional[str] = None, db: Session = Depends(get_db)):
    """Generate adaptive nutrition plan based on user adherence analysis"""
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not client:
        return {"status": "skipped", "reason": "AI not available"}

    # Get food logs for last 7 days
    from datetime import datetime, timedelta
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)
    
    foods = db.query(FoodItem).filter(
        FoodItem.user_id == user_id,
        FoodItem.date >= start_date.isoformat(),
        FoodItem.date <= end_date.isoformat()
    ).all()

    # Calculate actual intake
    total_calories = sum(f.calories for f in foods)
    total_protein = sum(f.protein for f in foods)
    total_carbs = sum(f.carbs for f in foods)
    total_fat = sum(f.fat for f in foods)
    
    # Calculate days with data
    unique_days = len(set(f.date for f in foods))
    avg_calories = round(total_calories / max(unique_days, 1), 0)
    
    # Get target values
    target_cal = user.target_calories or 2000
    target_protein = user.target_protein or 60
    target_carbs = user.target_carbs or 250
    target_fat = user.target_fat or 65

    # Calculate adherence rates
    cal_adherence = min(100, (avg_calories / target_cal) * 100) if target_cal > 0 else 0
    protein_adherence = min(100, ((total_protein / max(unique_days, 1)) / target_protein) * 100) if target_protein > 0 else 0
    
    # Determine if user can follow the plan
    overall_adherence = (cal_adherence + protein_adherence) / 2
    can_follow = overall_adherence >= 70  # 70% threshold
    
    # Get food patterns
    food_names = [f.name for f in foods]
    food_summary = ", ".join(food_names[:15]) if food_names else "ไม่มีข้อมูล"
    
    try:
        prompt = f"""บทบาท: คุณคือ "NutriFriend" เพื่อนซี้โภชนาการที่เข้าใจผู้ใช้

ข้อมูลเพื่อน {user.name}:
- อายุ: {user.age} ปี | เพศ: {user.gender}
- น้ำหนัก: {user.weight} kg | ส่วนสูง: {user.height} cm
- เป้าหมาย: {user.goal}
- โรคประจำตัว: {user.conditions or 'ไม่มี'}
- ข้อจำกัดอาหาร: {user.dietary_restrictions or 'ไม่มี'}

เป้าหมายปัจจุบัน:
- แคลอรี่: {target_cal} kcal/วัน
- โปรตีน: {target_protein}g | คาร์บ: {target_carbs}g | ไขมัน: {target_fat}g

ผลการปฏิบัติ 7 วันที่ผ่านมา:
- วันที่มีข้อมูล: {unique_days}/7 วัน
- แคลอรี่เฉลี่ย: {avg_calories:.0f} kcal/วัน (เป้า {target_cal})
- อัตราทำตามแผน: {overall_adherence:.0f}%
- สามารถทำตามแผนได้: {"ได้" if can_follow else "ยังไม่ได้"}
- อาหารที่กินบ่อย: {food_summary}

ภารกิจ:
{"เพื่อนทำได้ดี! ให้กำลังใจและปรับเป้าหมายให้ท้าทายขึ้นเล็กน้อย" if can_follow else "เพื่อนยังทำตามแผนไม่ค่อยได้ ช่วยปรับแผนให้ง่ายขึ้น เข้าถึงง่ายขึ้น และเป็นไปได้จริงในชีวิตประจำวัน"}

ตอบเป็น JSON ในรูปแบบ:
{{
  "analysis": "วิเคราะห์สั้นๆ 2-3 ประโยค ว่าเพื่อนทำได้ไหม อะไรดี อะไรควรปรับ",
  "can_follow": {"true" if can_follow else "false"},
  "new_targets": {{
    "calories": ตัวเลขใหม่ที่ปรับแล้ว,
    "protein": ตัวเลขใหม่,
    "carbs": ตัวเลขใหม่,
    "fat": ตัวเลขใหม่
  }},
  "weekly_plan": "แผนการกินสัปดาห์นี้แบบสั้นๆ ที่ทำได้จริง",
  "motivation": "ข้อความให้กำลังใจเพื่อน 1 ประโยค"
}}"""

        result_text = gemini_generate_with_backoff("gemini-3-flash-preview", [prompt], config=SEARCH_CONFIG, force_model=model)
        
        # Parse JSON response
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            result = json.loads(json_match.group())
            
            # Update user targets with new adaptive values
            new_targets = result.get("new_targets", {})
            if new_targets:
                user.target_calories = new_targets.get("calories", target_cal)
                user.target_protein = new_targets.get("protein", target_protein)
                user.target_carbs = new_targets.get("carbs", target_carbs)
                user.target_fat = new_targets.get("fat", target_fat)
            
            # Update assessment with new plan
            weekly_plan = result.get("weekly_plan", "")
            analysis = result.get("analysis", "")
            motivation = result.get("motivation", "")
            
            new_assessment = f"""## แผนโภชนาการสัปดาห์นี้

{analysis}

### เป้าหมายใหม่ที่ปรับแล้ว:
- แคลอรี่: {user.target_calories} kcal/วัน
- โปรตีน: {user.target_protein}g | คาร์บ: {user.target_carbs}g | ไขมัน: {user.target_fat}g

### แผนการกิน:
{weekly_plan}

---
💪 {motivation}"""
            
            user.ai_assessment = new_assessment
            
            # ==================== บันทึกลงตาราง nutrition_plans ====================
            from datetime import datetime, timedelta
            
            # คำนวณวันเริ่มและสิ้นสุดของแผน
            plan_start = datetime.now().date()
            plan_end = plan_start + timedelta(days=6)
            
            # สร้างแผนใหม่
            new_plan = NutritionPlan(
                user_id=user_id,
                plan_type="weekly",
                week_start_date=plan_start.isoformat(),
                week_end_date=plan_end.isoformat(),
                target_calories=user.target_calories,
                target_protein=user.target_protein,
                target_carbs=user.target_carbs,
                target_fat=user.target_fat,
                daily_plan=json.dumps({"plan": weekly_plan}, ensure_ascii=False),
                meal_suggestions=None,
                analysis=analysis,
                motivation=motivation,
                adherence_rate=round(overall_adherence, 1),
                can_follow=1 if can_follow else 0,
                created_at=int(time.time()),
                updated_at=None
            )
            db.add(new_plan)
            
            db.commit()
            
            return {
                "status": "success",
                "can_follow": can_follow,
                "adherence_rate": round(overall_adherence, 1),
                "new_targets": new_targets,
                "analysis": analysis,
                "motivation": motivation,
                "plan_id": new_plan.id
            }
        else:
            return {"status": "error", "reason": "Could not parse AI response"}

    except Exception as e:
        print(f"[ERROR] Adaptive plan failed: {e}")
        return {"status": "error", "reason": str(e)}


# ==================== Nutrition Plan Endpoints ====================

class NutritionPlanCreate(BaseModel):
    plan_type: str = "weekly"
    week_start_date: str
    week_end_date: str
    target_calories: Optional[float] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fat: Optional[float] = None
    daily_plan: Optional[str] = None
    meal_suggestions: Optional[str] = None
    analysis: Optional[str] = None
    motivation: Optional[str] = None


class NutritionPlanResponse(BaseModel):
    id: int
    user_id: int
    plan_type: str
    week_start_date: str
    week_end_date: str
    target_calories: Optional[float]
    target_protein: Optional[float]
    target_carbs: Optional[float]
    target_fat: Optional[float]
    daily_plan: Optional[str]
    meal_suggestions: Optional[str]
    analysis: Optional[str]
    motivation: Optional[str]
    adherence_rate: Optional[float]
    can_follow: int
    created_at: int
    updated_at: Optional[int]

    class Config:
        from_attributes = True


@app.post("/users/{user_id}/nutrition-plans", response_model=NutritionPlanResponse)
def create_nutrition_plan(user_id: int, plan: NutritionPlanCreate, db: Session = Depends(get_db)):
    """สร้างแผนโภชนาการใหม่"""
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db_plan = NutritionPlan(
        user_id=user_id,
        plan_type=plan.plan_type,
        week_start_date=plan.week_start_date,
        week_end_date=plan.week_end_date,
        target_calories=plan.target_calories or user.target_calories,
        target_protein=plan.target_protein or user.target_protein,
        target_carbs=plan.target_carbs or user.target_carbs,
        target_fat=plan.target_fat or user.target_fat,
        daily_plan=plan.daily_plan,
        meal_suggestions=plan.meal_suggestions,
        analysis=plan.analysis,
        motivation=plan.motivation,
        adherence_rate=None,
        can_follow=1,
        created_at=int(time.time()),
        updated_at=None
    )
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan


@app.get("/users/{user_id}/nutrition-plans", response_model=List[NutritionPlanResponse])
def get_nutrition_plans(user_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """ดึงแผนโภชนาการทั้งหมดของผู้ใช้"""
    plans = db.query(NutritionPlan).filter(
        NutritionPlan.user_id == user_id
    ).order_by(NutritionPlan.created_at.desc()).limit(limit).all()
    return plans


@app.get("/users/{user_id}/nutrition-plans/current", response_model=NutritionPlanResponse)
def get_current_plan(user_id: int, db: Session = Depends(get_db)):
    """ดึงแผนโภชนาการปัจจุบัน (ล่าสุด)"""
    plan = db.query(NutritionPlan).filter(
        NutritionPlan.user_id == user_id
    ).order_by(NutritionPlan.created_at.desc()).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="No nutrition plan found")
    return plan


@app.put("/users/{user_id}/nutrition-plans/{plan_id}")
def update_nutrition_plan(user_id: int, plan_id: int, adherence_rate: float = None, can_follow: int = None, db: Session = Depends(get_db)):
    """อัปเดตสถานะแผน (adherence rate, can_follow)"""
    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == plan_id,
        NutritionPlan.user_id == user_id
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    if adherence_rate is not None:
        plan.adherence_rate = adherence_rate
    if can_follow is not None:
        plan.can_follow = can_follow
    plan.updated_at = int(time.time())
    
    db.commit()
    return {"status": "success", "message": "Plan updated"}


@app.delete("/users/{user_id}/nutrition-plans/{plan_id}")
def delete_nutrition_plan(user_id: int, plan_id: int, db: Session = Depends(get_db)):
    """ลบแผนโภชนาการ"""
    plan = db.query(NutritionPlan).filter(
        NutritionPlan.id == plan_id,
        NutritionPlan.user_id == user_id
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    db.delete(plan)
    db.commit()
    return {"status": "success", "message": "Plan deleted"}


# ==================== Food Item Endpoints ====================

@app.post("/users/{user_id}/foods", response_model=FoodItemResponse)
def add_food_item(user_id: int, food: FoodItemCreate, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db_food = FoodItem(
        id=food.id or str(uuid.uuid4()),
        user_id=user_id,
        name=food.name,
        calories=food.calories,
        protein=food.protein,
        carbs=food.carbs,
        fat=food.fat,
        date=food.date,
        timestamp=food.timestamp
    )
    db.add(db_food)
    db.commit()
    db.refresh(db_food)

    # Trigger refresh-plan in background (non-blocking)
    import threading
    def background_refresh():
        try:
            from models import SessionLocal
            bg_db = SessionLocal()
            refresh_nutrition_plan(user_id, bg_db)
            bg_db.close()
        except Exception as e:
            print(f"[WARN] Background refresh failed: {e}")

    thread = threading.Thread(target=background_refresh)
    thread.start()

    return db_food


@app.get("/users/{user_id}/foods", response_model=List[FoodItemResponse])
def get_food_items(user_id: int, date: str = None, db: Session = Depends(get_db)):
    query = db.query(FoodItem).filter(FoodItem.user_id == user_id)
    if date:
        query = query.filter(FoodItem.date == date)
    return query.order_by(FoodItem.timestamp.desc()).all()


@app.get("/users/{user_id}/foods/{food_id}", response_model=FoodItemResponse)
def get_food_item(user_id: int, food_id: str, db: Session = Depends(get_db)):
    food = db.query(FoodItem).filter(
        FoodItem.id == food_id,
        FoodItem.user_id == user_id
    ).first()
    if not food:
        raise HTTPException(status_code=404, detail="Food item not found")
    return food


@app.delete("/users/{user_id}/foods/{food_id}")
def delete_food_item(user_id: int, food_id: str, db: Session = Depends(get_db)):
    food = db.query(FoodItem).filter(
        FoodItem.id == food_id,
        FoodItem.user_id == user_id
    ).first()
    if not food:
        raise HTTPException(status_code=404, detail="Food item not found")
    db.delete(food)
    db.commit()
    return {"message": "Food item deleted successfully"}


# ==================== Daily Stats Endpoint ====================

@app.get("/users/{user_id}/stats/{date}", response_model=DailyStats)
def get_daily_stats(user_id: int, date: str, db: Session = Depends(get_db)):
    foods = db.query(FoodItem).filter(
        FoodItem.user_id == user_id,
        FoodItem.date == date
    ).all()

    stats = DailyStats(
        calories=sum(f.calories for f in foods),
        protein=sum(f.protein for f in foods),
        carbs=sum(f.carbs for f in foods),
        fat=sum(f.fat for f in foods)
    )
    return stats


# ==================== Weekly Report Endpoint ====================

class WeeklyReportResponse(BaseModel):
    period_start: str
    period_end: str
    total_meals: int
    total_calories: float
    avg_calories: float
    total_protein: float
    total_carbs: float
    total_fat: float
    target_calories: Optional[float]
    status: str  # "on_track", "under", "over"
    daily_breakdown: list


@app.get("/users/{user_id}/weekly-report", response_model=WeeklyReportResponse)
def get_weekly_report(user_id: int, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Calculate date range (last 7 days)
    from datetime import datetime, timedelta
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=6)

    # Get all food items in the date range
    foods = db.query(FoodItem).filter(
        FoodItem.user_id == user_id,
        FoodItem.date >= start_date.isoformat(),
        FoodItem.date <= end_date.isoformat()
    ).all()

    # Calculate totals
    total_calories = sum(f.calories for f in foods)
    total_protein = sum(f.protein for f in foods)
    total_carbs = sum(f.carbs for f in foods)
    total_fat = sum(f.fat for f in foods)
    total_meals = len(foods)
    avg_calories = round(total_calories / 7, 0) if total_calories > 0 else 0

    # Get target calories
    target_calories = user.target_calories

    # Determine status
    if target_calories:
        weekly_target = target_calories * 7
        diff_percent = ((total_calories - weekly_target) / weekly_target) * 100 if weekly_target > 0 else 0
        if abs(diff_percent) <= 10:
            status = "on_track"
        elif total_calories < weekly_target:
            status = "under"
        else:
            status = "over"
    else:
        status = "on_track"

    # Build daily breakdown
    daily_breakdown = []
    for i in range(7):
        day = start_date + timedelta(days=i)
        day_str = day.isoformat()
        day_foods = [f for f in foods if f.date == day_str]
        daily_breakdown.append({
            "date": day_str,
            "meals": len(day_foods),
            "calories": round(sum(f.calories for f in day_foods), 0),
            "protein": round(sum(f.protein for f in day_foods), 1),
            "carbs": round(sum(f.carbs for f in day_foods), 1),
            "fat": round(sum(f.fat for f in day_foods), 1)
        })

    return WeeklyReportResponse(
        period_start=start_date.isoformat(),
        period_end=end_date.isoformat(),
        total_meals=total_meals,
        total_calories=round(total_calories, 0),
        avg_calories=avg_calories,
        total_protein=round(total_protein, 1),
        total_carbs=round(total_carbs, 1),
        total_fat=round(total_fat, 1),
        target_calories=target_calories,
        status=status,
        daily_breakdown=daily_breakdown
    )


# ==================== Message Endpoints ====================

@app.post("/users/{user_id}/messages", response_model=MessageResponse)
def add_message(user_id: int, message: MessageCreate, db: Session = Depends(get_db)):
    user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db_message = Message(
        id=message.id or str(uuid.uuid4()),
        user_id=user_id,
        role=message.role,
        text=message.text,
        image=message.image,
        timestamp=message.timestamp,
        date=message.date,
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


@app.get("/users/{user_id}/messages", response_model=List[MessageResponse])
def get_messages(user_id: int, date: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Message).filter(Message.user_id == user_id)
    if date:
        query = query.filter(Message.date == date)
    return query.order_by(Message.timestamp.asc()).all()


@app.delete("/users/{user_id}/messages")
def clear_messages(user_id: int, date: str, db: Session = Depends(get_db)):
    db.query(Message).filter(
        Message.user_id == user_id,
        Message.date == date
    ).delete()
    db.commit()
    return {"message": "Messages cleared"}


# ==================== AI Analysis Endpoints ====================

class AnalyzeFoodRequest(BaseModel):
    image: str  # Base64 image

class AnalyzeFoodResponse(BaseModel):
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float

class ChatRequest(BaseModel):
    message: str
    image: Optional[str] = None
    profile: dict
    foodLogs: list
    healthData: Optional[dict] = None  # ข้อมูลสุขภาพจากนาฬิกา (HR, Steps, Calories)

class ChatResponse(BaseModel):
    response: str


@app.post("/analyze-food", response_model=AnalyzeFoodResponse)
async def analyze_food(request: AnalyzeFoodRequest, req: Request):
    if not client:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")

    ip = req.client.host if req.client else "unknown"
    rate_limit(ip, "analyze_food")

    try:
        image_data = request.image.split(",")[1] if "," in request.image else request.image
        import base64
        image_bytes = base64.b64decode(image_data)

        prompt = """วิเคราะห์อาหารในรูปภาพนี้และให้ข้อมูลโภชนาการโดยประมาณ
- อ้างอิงฐานข้อมูลสารอาหารไทยจากสถาบันโภชนาการ มหาวิทยาลัยมหิดล (INMUCAL) สำหรับอาหารไทย

ตอบเป็น JSON เท่านั้น ในรูปแบบ:
{"name": "ชื่ออาหาร", "calories": ตัวเลข, "protein": ตัวเลข, "carbs": ตัวเลข, "fat": ตัวเลข}
- calories เป็น kcal
- protein, carbs, fat เป็นกรัม
ตอบเฉพาะ JSON ไม่ต้องมีข้อความอื่น"""

        img_hash = hashlib.sha256(image_bytes).hexdigest()
        key = cache_key("analyze_food", img_hash)

        cached = cache_get(key)
        if cached:
            result_text = cached
        else:
            inflight_acquire(key)
            try:
                result_text = gemini_generate_with_backoff(
                    "gemini-3-flash-preview",
                    [types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"), prompt]
                )
                cache_set(key, result_text, ttl=120)
            finally:
                inflight_release(key)

        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if not json_match:
            raise HTTPException(status_code=500, detail="Could not parse AI response")

        result = json.loads(json_match.group())
        return AnalyzeFoodResponse(
            name=result.get("name", "Unknown Food"),
            calories=float(result.get("calories", 0)),
            protein=float(result.get("protein", 0)),
            carbs=float(result.get("carbs", 0)),
            fat=float(result.get("fat", 0))
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest, req: Request, db: Session = Depends(get_db)):
    if not client:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")

    ip = req.client.host if req.client else "unknown"
    rate_limit(ip, "chat")

    profile = request.profile
    food_logs = request.foodLogs
    health_data = request.healthData

    # --- Fetch Chat History ---
    user_id = profile.get('id')
    history_text = ""
    if user_id:
        # Get last 15 messages (excluding current one if it was already saved - though usually frontend calls chat api separately)
        # We want context of previous conversation.
        previous_msgs = db.query(Message).filter(Message.user_id == user_id).order_by(Message.timestamp.desc()).limit(15).all()
        previous_msgs.reverse() # Sort chronological: Old -> New

        if previous_msgs:
            history_text = "\n\n=== ประวัติการสนทนาล่าสุด (Context) ===\n"
            for msg in previous_msgs:
                role_label = "เพื่อน (User)" if msg.role == MessageRole.user else "NutriFriend (AI)"
                history_text += f"{role_label}: {msg.text}\n"
            history_text += "========================================\n"

    # สร้าง health context ถ้ามีข้อมูลจากนาฬิกา
    health_context = ""
    if health_data:
        health_context = f"""
ข้อมูลสุขภาพจากนาฬิกา (Real-time):
- ❤️ Heart Rate: {health_data.get('heart_rate', 0)} BPM
- 👟 Steps วันนี้: {health_data.get('steps', 0):,} ก้าว
- 🔥 Calories เผาผลาญ: {health_data.get('calories_burned', 0):.0f} kcal
- 🏃 กิจกรรม: {health_data.get('activity', 'ไม่ทราบ')}
- 🔋 Battery นาฬิกา: {health_data.get('battery', 0)}%
- ⚠️ ระดับความเสี่ยง: {health_data.get('health_risk_level', 'LOW')}
"""

    context = f"""บทบาท: คุณคือ "NutriFriend" เพื่อนซี้โภชนาการและสุขภาพของคุณ {profile.get('name', 'เพื่อน')}
บุคลิก: คุยสนุก เป็นกันเอง เหมือนเพื่อนสนิทที่หวังดี (แต่มีความรู้แน่นปึ้ก!)
สไตล์การตอบ: 
- ใช้ภาษาพูดที่เป็นธรรมชาติ (เช่น "นะครับ/คะ", "ลองแบบนี้ดูมั้ย", "ดีเลยครับ")
- หลีกเลี่ยงคำทางการน่าเบื่อ (เช่น "จากข้อมูลข้างต้น", "จึงเรียนมาเพื่อทราบ")
- ถ้าข้อมูลวิชาการยากๆ ให้เปรียบเทียบหรือเล่าให้เห็นภาพง่ายๆ
- ให้กำลังใจและชื่นชมเสมอเมื่อเพื่อนทำดี
- ถ้าหากเป็นข้อมูลที่ซับซ้อน เเละต้องการข้อมูลที่เเม่นยำ เเละละเอียดอ่อน ให้เรียกใช้ฟังก์ชั่นเสิชทันที
- วิเคราะห์ความสัมพันธ์ระหว่างอาหารที่กินกับสุขภาพร่างกาย เช่น "กินหนักไป ควรเดินออกกำลังกาย" หรือ "ออกกำลังเยอะ กินเพิ่มได้"

ข้อมูลโปรไฟล์เพื่อน:
- ชื่อ: {profile.get('name', 'ไม่ระบุ')}
- อายุ: {profile.get('age', 'ไม่ระบุ')} ปี
- สัดส่วน: หนัก {profile.get('weight', 'ไม่ระบุ')} kg / สูง {profile.get('height', 'ไม่ระบุ')} cm
- กิจกรรม: {profile.get('activityLevel', 'ไม่ระบุ')}
- เป้าหมาย: {profile.get('goal', 'ไม่ระบุ')}
- เงื่อนไขร่างกาย: {profile.get('conditions', 'แข็งแรงดี')} / {profile.get('dietaryRestrictions', 'ทานได้ทุกอย่าง')}

อาหารวันนี้: {len(food_logs)} เมนู (แคลรวม: {sum(f.get('calories', 0) for f in food_logs)} kcal)
{health_context}
{history_text}
คำแนะนำเพิ่มเติม:
- ถ้าเพื่อนถามเรื่องป่วย ให้แนะนำให้ปรึกษาหมอด้วยความเป็นห่วงเสมอ
- "Google Search" จะช่วยหาข้อมูลล่าสุดให้คุณ อย่าลืมใช้ข้อมูลนั้นมาเล่าต่อเพื่อนนะ
- ถ้ามีข้อมูลสุขภาพจากนาฬิกา ให้วิเคราะห์ร่วมกับอาหารด้วย เช่น "วันนี้เดินไป X ก้าว เผาผลาญไป Y แคล กินได้อีก Z แคล" """

    # Perform DuckDuckGo search to augment context for ALL models (including Gemma)
    search_context = ""
    try:
        # Simple heuristic: if message is short or looks like a question, search.
        # For now, let's search for everything to be safe as requested.
        search_results = perform_duckduckgo_search(request.message)
        if search_results and "Search unavailable" not in search_results:
            search_context = f"\n\n=== ข้อมูลเพิ่มเติมจาก DuckDuckGo ===\n{search_results}\n=====================================\n"
    except Exception as e:
        print(f"[WARN] DDG Search injection failed: {e}")

    contents = [context + search_context, f"\nเพื่อนถามว่า: {request.message}"]

    img_sig = ""
    if request.image:
        image_data = request.image.split(",")[1] if "," in request.image else request.image
        import base64
        image_bytes = base64.b64decode(image_data)
        img_sig = hashlib.sha256(image_bytes).hexdigest()
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            context,
            f"\nคำถาม: {request.message}",
        ]

    key = cache_key(
        "chat",
        str(profile.get("id", "")),
        request.message.strip(),
        img_sig,
        str(len(food_logs)),
        str(sum(f.get("calories", 0) for f in food_logs)),
    )

    cached = cache_get(key)
    if cached is not None:
        return ChatResponse(response=cached)

    inflight_acquire(key)
    try:
        # Enable search for chat
        text = gemini_generate_with_backoff(
            "gemini-3-flash-preview", 
            contents,
            config=SEARCH_CONFIG
        )
        cache_set(key, text)
        return ChatResponse(response=text)
    finally:
        inflight_release(key)


# ============================================================
# Health Coach WebSocket & API Endpoints
# ============================================================

@app.websocket("/ws/health/{user_id}")
async def websocket_health_endpoint(websocket: WebSocket, user_id: int):
    """
    WebSocket endpoint สำหรับ real-time health data
    
    Client ส่ง data:
    {
        "hr": 75,           # Heart rate
        "steps": 5432,      # Step count
        "accel_x": 0.1,     # Accelerometer
        "accel_y": 0.2,
        "accel_z": 9.8,
        "spo2": 98          # Optional: Blood oxygen
    }
    
    Server ตอบกลับ:
    {
        "health_data": { ... processed data ... },
        "decisions": [ ... AI decisions/alerts ... ]
    }
    """
    db = next(get_db())
    
    try:
        await ws_manager.connect(websocket, user_id)
        
        # Get or create health engine for this user
        health_engine = get_health_engine(user_id, db)
        
        # Get user info for decisions
        user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
        if user:
            health_coach.set_user_baseline(user_id, {
                "resting_hr": 70,  # Could be personalized
                "max_hr": 220 - user.age,
                "vo2_max": None
            })
        
        while True:
            # Receive sensor data from watch/client
            raw_data = await websocket.receive_json()
            
            # Process with AI Engine
            processed = health_engine.process_realtime(
                hr=raw_data.get("hr", 70),
                steps=raw_data.get("steps", 0),
                accel_x=raw_data.get("accel_x", 0),
                accel_y=raw_data.get("accel_y", 0),
                accel_z=raw_data.get("accel_z", 9.8),
                spo2=raw_data.get("spo2")
            )
            
            # Make decisions with Health Coach
            decisions = health_coach.make_decisions(processed.to_dict(), user_id)
            
            # Save to database (every minute or when anomaly)
            if processed.anomaly_detected or int(time.time()) % 60 == 0:
                health_metric = HealthMetric(
                    user_id=user_id,
                    timestamp=processed.timestamp,
                    date=time.strftime("%Y-%m-%d"),
                    heart_rate=processed.heart_rate,
                    steps=processed.steps,
                    spo2=raw_data.get("spo2"),
                    activity_type=processed.activity,
                    calories_burned=processed.calories_burned,
                    hrv_sdnn=processed.hrv.get("sdnn") if processed.hrv else None,
                    hrv_rmssd=processed.hrv.get("rmssd") if processed.hrv else None,
                    stress_index=processed.hrv.get("stress_index") if processed.hrv else None,
                    fatigue_score=processed.fatigue_score,
                    vo2_max=processed.vo2_max,
                    health_risk_level=processed.health_risk_level
                )
                db.add(health_metric)
                db.commit()
            
            # Save alerts to database
            for decision in decisions:
                if decision.action.value == "ALERT":
                    alert = HealthAlert(
                        user_id=user_id,
                        timestamp=decision.timestamp,
                        date=time.strftime("%Y-%m-%d"),
                        alert_type=decision.action.value,
                        priority=decision.priority,
                        message=decision.message,
                        message_en=decision.message_en,
                        data=json.dumps(decision.data) if decision.data else None
                    )
                    db.add(alert)
                    db.commit()
            
            # Send response back to client
            response = {
                "health_data": processed.to_dict(),
                "decisions": [d.to_dict() for d in decisions]
            }
            await websocket.send_json(response)
            
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
        ws_manager.disconnect(user_id)
    finally:
        db.close()


@app.get("/users/{user_id}/health/today")
def get_today_health(user_id: int, db: Session = Depends(get_db)):
    """ดึงข้อมูลสุขภาพวันนี้"""
    today = time.strftime("%Y-%m-%d")
    
    metrics = db.query(HealthMetric).filter(
        HealthMetric.user_id == user_id,
        HealthMetric.date == today
    ).order_by(HealthMetric.timestamp.desc()).limit(100).all()
    
    if not metrics:
        return {"date": today, "metrics": [], "summary": None}
    
    # Calculate summary
    heart_rates = [m.heart_rate for m in metrics if m.heart_rate]
    steps_list = [m.steps for m in metrics if m.steps]
    calories_list = [m.calories_burned for m in metrics if m.calories_burned]
    
    summary = {
        "avg_heart_rate": round(sum(heart_rates) / len(heart_rates)) if heart_rates else None,
        "max_heart_rate": max(heart_rates) if heart_rates else None,
        "min_heart_rate": min(heart_rates) if heart_rates else None,
        "total_steps": max(steps_list) if steps_list else 0,
        "total_calories": round(sum(calories_list), 1) if calories_list else 0,
        "last_activity": metrics[0].activity_type if metrics else None,
        "last_update": metrics[0].timestamp if metrics else None
    }
    
    return {
        "date": today,
        "metrics": [
            {
                "timestamp": m.timestamp,
                "heart_rate": m.heart_rate,
                "steps": m.steps,
                "activity_type": m.activity_type,
                "stress_index": m.stress_index,
                "fatigue_score": m.fatigue_score
            }
            for m in metrics[:20]  # Limit to last 20 for response size
        ],
        "summary": summary
    }


@app.get("/users/{user_id}/health/alerts")
def get_health_alerts(user_id: int, unread_only: bool = True, db: Session = Depends(get_db)):
    """ดึง health alerts"""
    query = db.query(HealthAlert).filter(HealthAlert.user_id == user_id)
    
    if unread_only:
        query = query.filter(HealthAlert.acknowledged == 0)
    
    alerts = query.order_by(HealthAlert.timestamp.desc()).limit(20).all()
    
    return {
        "alerts": [
            {
                "id": a.id,
                "timestamp": a.timestamp,
                "alert_type": a.alert_type,
                "priority": a.priority,
                "message": a.message,
                "acknowledged": a.acknowledged == 1
            }
            for a in alerts
        ]
    }


@app.put("/users/{user_id}/health/alerts/{alert_id}/acknowledge")
def acknowledge_alert(user_id: int, alert_id: int, db: Session = Depends(get_db)):
    """Mark alert as acknowledged"""
    alert = db.query(HealthAlert).filter(
        HealthAlert.id == alert_id,
        HealthAlert.user_id == user_id
    ).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.acknowledged = 1
    alert.acknowledged_at = int(time.time())
    db.commit()
    
    return {"status": "acknowledged", "alert_id": alert_id}


@app.get("/users/{user_id}/health/workouts")
def get_workout_sessions(user_id: int, limit: int = 10, db: Session = Depends(get_db)):
    """ดึง workout sessions"""
    sessions = db.query(WorkoutSession).filter(
        WorkoutSession.user_id == user_id
    ).order_by(WorkoutSession.start_time.desc()).limit(limit).all()
    
    return {
        "workouts": [
            {
                "id": s.id,
                "date": s.date,
                "activity_type": s.activity_type,
                "duration_minutes": s.duration_minutes,
                "avg_heart_rate": s.avg_heart_rate,
                "calories_burned": s.calories_burned,
                "vo2_max": s.vo2_max
            }
            for s in sessions
        ]
    }


@app.get("/users/{user_id}/health/stats")
def get_health_stats(user_id: int, db: Session = Depends(get_db)):
    """ดึงสถิติสุขภาพรวม"""
    # Get engine stats
    engine_stats = {}
    if user_id in health_engines:
        engine_stats = health_engines[user_id].get_stats()
    
    # Get today's metrics count
    today = time.strftime("%Y-%m-%d")
    today_count = db.query(HealthMetric).filter(
        HealthMetric.user_id == user_id,
        HealthMetric.date == today
    ).count()
    
    # Get unread alerts count
    unread_alerts = db.query(HealthAlert).filter(
        HealthAlert.user_id == user_id,
        HealthAlert.acknowledged == 0
    ).count()
    
    return {
        "user_id": user_id,
        "today_metrics_count": today_count,
        "unread_alerts": unread_alerts,
        "engine_stats": engine_stats,
        "connection_status": "connected" if user_id in ws_manager.active_connections else "disconnected"
    }

# ============================================================
# Serve Frontend (Static Files) - MUST BE LAST
# ============================================================

# Mount static files (JS, CSS, Images)
# Check if dist folder exists (it should be in ../frontend/dist relative to backend)
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if not os.path.exists(FRONTEND_DIST):
    BACKEND_DIST = os.path.join(os.path.dirname(__file__), "dist")
    if os.path.exists(BACKEND_DIST):
        FRONTEND_DIST = BACKEND_DIST

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    # Serve root index.html
    @app.get("/")
    async def serve_root():
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    # Catch-all route for SPA (React Router)
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # API routes are already handled above because they are defined first
        # If path is a file in dist, serve it
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Otherwise serve index.html (for client-side routing)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
else:
    print(f"WARNING: Frontend dist folder not found at {FRONTEND_DIST}")
