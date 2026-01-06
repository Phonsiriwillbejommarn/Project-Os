from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
import uuid
import os
import json
import re
import time
import hashlib
import sys
import io

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

from models import init_db, get_db, UserProfile, FoodItem, Message, MessageRole
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
# Fallback chain as requested
FALLBACK_CHAIN = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemma-3-27b-it"
]

def gemini_generate_with_backoff(model: str, contents, config: Optional[types.GenerateContentConfig] = None, max_tries: int = 2) -> str:
    # Build list of models to try: requested model first, then the rest of the chain
    models_to_try = [model]
    for m in FALLBACK_CHAIN:
        if m != model and m not in models_to_try:
            models_to_try.append(m)

    last_error = None

    for model_name in models_to_try:
        print(f"[DEBUG] Attempting AI generation with model: {model_name}")
        delay = 1.0
        
        # Try up to max_tries for EACH model (mainly for 503s)
        for attempt in range(1, max_tries + 1):
            try:
                # Special handling for Gemma: Does NOT support Search Tool
                current_config = config
                if "gemma" in model_name.lower():
                    # Remove search config for Gemma to avoid 400 INVALID_ARGUMENT
                    current_config = None

                resp = client.models.generate_content(model=model_name, contents=contents, config=current_config)

                # Check if search was used
                if resp.candidates and resp.candidates[0].grounding_metadata and resp.candidates[0].grounding_metadata.search_entry_point:
                    print(f"[DEBUG] 🔍 Google Search used by model: {model_name}")
                
                return (resp.text or "").strip()

            except Exception as e:
                last_error = e
                error_str = str(e)
                print(f"[WARN] Model {model_name} (Attempt {attempt}/{max_tries}) failed: {error_str}")

                # Check for fatal errors that suggest "Move to next model immediately"
                # 429 = Quota exceeded / Too many requests
                # 404 = Model not found
                # 400 = Bad Request (Invalid Argument) -> e.g. model doesn't support search tools
                is_fatal = any(x in error_str for x in ["429", "404", "400", "Resource has been exhausted", "Not Found", "Invalid Argument"])
                
                if is_fatal:
                    # If this model is broken/full/incompatible, don't retry IT. Move to NEXT model in chain.
                    break 

                # If it's a 503 (Overloaded) -> Wait and retry THIS model
                if "503" in error_str:
                    if attempt < max_tries:
                        time.sleep(delay)
                        delay = min(delay * 2, 5.0)
                        continue
                
                # For safety, if we hit other unknown errors, we also break to try the next model
                break

    # If we exit the loop, all models failed
    import traceback
    traceback.print_exc()
    print(f"!!! ALL FALLBACK MODELS FAILED. Last error: {last_error}")
    raise HTTPException(status_code=500, detail=f"AI Service Temporarily Unavailable. All models failed. Last error: {last_error}")


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
def refresh_daily_tips(user_id: int, db: Session = Depends(get_db)):
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

        result_text = gemini_generate_with_backoff("gemini-3-flash-preview", [prompt])
        
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
def generate_adaptive_plan(user_id: int, db: Session = Depends(get_db)):
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

        result_text = gemini_generate_with_backoff("gemini-3-flash-preview", [prompt], config=SEARCH_CONFIG)
        
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
            db.commit()
            
            return {
                "status": "success",
                "can_follow": can_follow,
                "adherence_rate": round(overall_adherence, 1),
                "new_targets": new_targets,
                "analysis": analysis,
                "motivation": motivation
            }
        else:
            return {"status": "error", "reason": "Could not parse AI response"}

    except Exception as e:
        print(f"[ERROR] Adaptive plan failed: {e}")
        return {"status": "error", "reason": str(e)}


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

    context = f"""บทบาท: คุณคือ "NutriFriend" เพื่อนซี้โภชนาการของคุณ {profile.get('name', 'เพื่อน')}
บุคลิก: คุยสนุก เป็นกันเอง เหมือนเพื่อนสนิทที่หวังดี (แต่มีความรู้แน่นปึ้ก!)
สไตล์การตอบ: 
- ใช้ภาษาพูดที่เป็นธรรมชาติ (เช่น "นะครับ/คะ", "ลองแบบนี้ดูมั้ย", "ดีเลยครับ")
- หลีกเลี่ยงคำทางการน่าเบื่อ (เช่น "จากข้อมูลข้างต้น", "จึงเรียนมาเพื่อทราบ")
- ถ้าข้อมูลวิชาการยากๆ ให้เปรียบเทียบหรือเล่าให้เห็นภาพง่ายๆ
- ให้กำลังใจและชื่นชมเสมอเมื่อเพื่อนทำดี
- ถ้าหากเป็นข้อมูลที่ซับซ้อน เเละต้องการข้อมูลที่เเม่นยำ เเละละเอียดอ่อน ให้เรียกใช้ฟังก์ชั่นเสิชทันที

ข้อมูลโปรไฟล์เพื่อน:
- ชื่อ: {profile.get('name', 'ไม่ระบุ')}
- อายุ: {profile.get('age', 'ไม่ระบุ')} ปี
- สัดส่วน: หนัก {profile.get('weight', 'ไม่ระบุ')} kg / สูง {profile.get('height', 'ไม่ระบุ')} cm
- กิจกรรม: {profile.get('activityLevel', 'ไม่ระบุ')}
- เป้าหมาย: {profile.get('goal', 'ไม่ระบุ')}
- เงื่อนไขร่างกาย: {profile.get('conditions', 'แข็งแรงดี')} / {profile.get('dietaryRestrictions', 'ทานได้ทุกอย่าง')}

อาหารวันนี้: {len(food_logs)} เมนู (แคลรวม: {sum(f.get('calories', 0) for f in food_logs)} kcal)
{history_text}
คำแนะนำเพิ่มเติม:
- ถ้าเพื่อนถามเรื่องป่วย ให้แนะนำให้ปรึกษาหมอด้วยความเป็นห่วงเสมอ
- "Google Search" จะช่วยหาข้อมูลล่าสุดให้คุณ อย่าลืมใช้ข้อมูลนั้นมาเล่าต่อเพื่อนนะ"""

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
