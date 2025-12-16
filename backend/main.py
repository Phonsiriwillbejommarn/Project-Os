from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import os
import json
import re
import time
import hashlib
from collections import defaultdict, deque
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from google import genai
from google.genai import types
from google.genai.errors import ServerError

from models import init_db, get_db, UserProfile, FoodItem, Message
from schemas import (
    UserProfileCreate, UserProfileResponse, UserProfileUpdate,
    FoodItemCreate, FoodItemResponse,
    MessageCreate, MessageResponse,
    DailyStats
)

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
# Gemini helper: retry/backoff + map 503 properly
# ============================================================
def gemini_generate_with_backoff(model: str, contents, max_tries: int = 4) -> str:
    delay = 1.0
    for attempt in range(1, max_tries + 1):
        try:
            resp = client.models.generate_content(model=model, contents=contents)
            return (resp.text or "").strip()

        except ServerError as e:
            msg = str(e)
            # 503 overloaded
            if "503" in msg:
                if attempt < max_tries:
                    time.sleep(delay)
                    delay = min(delay * 2, 8.0)
                    continue
                raise HTTPException(status_code=503, detail="AI model overloaded. Please try again later.")

            # other server-side errors
            raise HTTPException(status_code=502, detail=f"Upstream error: {msg}")

        except Exception:
            raise HTTPException(status_code=500, detail="AI request failed.")


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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to SmartFood Analyzer API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}


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
วิเคราะห์ข้อมูลผู้ใช้และสร้างแผนโภชนาการเบื้องต้น:
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

คำสั่ง:
1. ให้ใช้เกณฑ์ปริมาณสารอาหารที่แนะนำสำหรับคนไทย (Thai RDI) จากกรมอนามัย กระทรวงสาธารณสุข
2. อ้างอิงฐานข้อมูลสารอาหารไทยจากสถาบันโภชนาการ มหาวิทยาลัยมหิดล (INMUCAL)
3. สำหรับผู้ที่มีโรคประจำตัว ให้อ้างอิงแนวทางเวชปฏิบัติจากคณะแพทยศาสตร์ศิริราชพยาบาล หรือโรงพยาบาลรามาธิบดี

กรุณาให้คำแนะนำและคำนวณเป้าหมายโภชนาการ:
1. การประเมินสุขภาพเบื้องต้น (BMI, BMR, TDEE)
2. คำแนะนำแคลอรี่และสารอาหารที่ควรได้รับต่อวัน
3. แนวทางการทานอาหารเพื่อให้บรรลุเป้าหมายในระยะเวลาที่กำหนด
4. ข้อควรระวัง
5. สร้าง "เคล็ดลับสุขภาพประจำวัน" จำนวน 7 ข้อ (สำหรับ 7 วัน)

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
                    result_text = gemini_generate_with_backoff("gemini-2.5-flash", [prompt])
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
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


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
                    "gemini-2.5-flash",
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
async def chat_with_ai(request: ChatRequest, req: Request):
    if not client:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")

    ip = req.client.host if req.client else "unknown"
    rate_limit(ip, "chat")

    profile = request.profile
    food_logs = request.foodLogs

    context = f"""คุณเป็นผู้เชี่ยวชาญด้านโภชนาการชื่อ NutriFriend AI

ข้อมูลผู้ใช้:
- ชื่อ: {profile.get('name', 'ไม่ระบุ')}
- อายุ: {profile.get('age', 'ไม่ระบุ')} ปี
- เพศ: {profile.get('gender', 'ไม่ระบุ')}
- น้ำหนัก: {profile.get('weight', 'ไม่ระบุ')} kg
- ส่วนสูง: {profile.get('height', 'ไม่ระบุ')} cm
- ระดับกิจกรรม: {profile.get('activityLevel', 'ไม่ระบุ')}
- เป้าหมาย: {profile.get('goal', 'ไม่ระบุ')}
- โรคประจำตัว: {profile.get('conditions', 'ไม่มี')}
- ข้อจำกัดด้านอาหาร: {profile.get('dietaryRestrictions', 'ไม่มี')}

อาหารที่ทานวันนี้: {len(food_logs)} รายการ
แคลอรี่รวม: {sum(f.get('calories', 0) for f in food_logs)} kcal

กรุณาตอบคำถามหรือให้คำแนะนำด้านโภชนาการอย่างเป็นกันเองและเป็นประโยชน์
โดยอ้างอิงหลักการแพทย์จากคณะแพทยศาสตร์ศิริราชพยาบาล, โรงพยาบาลรามาธิบดี และกรมอนามัย"""

    contents = [context, f"\nคำถาม: {request.message}"]

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
        text = gemini_generate_with_backoff("gemini-2.5-flash", contents)
        cache_set(key, text)
        return ChatResponse(response=text)
    finally:
        inflight_release(key)

# ============================================================
# Serve Frontend (Static Files) - MUST BE LAST
# ============================================================

# Mount static files (JS, CSS, Images)
# Check if dist folder exists (it should be in ../frontend/dist relative to backend)
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

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
