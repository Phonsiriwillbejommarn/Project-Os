from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import os
import json
import re
from datetime import datetime
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from google import genai
from google.genai import types

from models import init_db, get_db, UserProfile, FoodItem, Message
from schemas import (
    UserProfileCreate, UserProfileResponse, UserProfileUpdate,
    FoodItemCreate, FoodItemResponse,
    MessageCreate, MessageResponse,
    DailyStats
)

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


# ==================== User Profile Endpoints ====================

@app.post("/users", response_model=UserProfileResponse)
def create_user(user: UserProfileCreate, db: Session = Depends(get_db)):
    # Generate AI Assessment
    # Generate AI Assessment
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
            5. สร้าง "เคล็ดลับสุขภาพประจำวัน" จำนวน 7 ข้อ (สำหรับ 7 วัน) ที่เหมาะกับผู้ใช้นี้โดยเฉพาะ (เช่น เตือนเรื่องน้ำตาล, การกินผัก, การออกกำลังกาย)
            
            ตอบเป็น JSON เท่านั้น ในรูปแบบ:
            {{
                "assessment": "เนื้อหาคำแนะนำในรูปแบบ Markdown",
                "targets": {{
                    "calories": ตัวเลข (kcal),
                    "protein": ตัวเลข (g),
                    "carbs": ตัวเลข (g),
                    "fat": ตัวเลข (g)
                }},
                "daily_tips": ["เคล็ดลับวันที่ 1", "เคล็ดลับวันที่ 2", ..., "เคล็ดลับวันที่ 7"]
            }}
            """
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt]
            )
            
            result_text = response.text.strip()
            # Extract JSON
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
                ai_assessment = response.text # Fallback if not JSON

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
        timestamp=message.timestamp
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message


@app.get("/users/{user_id}/messages", response_model=List[MessageResponse])
def get_messages(user_id: int, limit: int = 50, db: Session = Depends(get_db)):
    return db.query(Message).filter(
        Message.user_id == user_id
    ).order_by(Message.timestamp.desc()).limit(limit).all()


@app.delete("/users/{user_id}/messages")
def clear_messages(user_id: int, db: Session = Depends(get_db)):
    db.query(Message).filter(Message.user_id == user_id).delete()
    db.commit()
    return {"message": "All messages cleared"}


# ==================== AI Analysis Endpoints ====================

# Initialize Gemini client
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
async def analyze_food(request: AnalyzeFoodRequest):
    """Analyze food from image and return nutritional information"""
    if not client:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")
    
    try:
        # Remove base64 prefix if present
        image_data = request.image
        if "," in image_data:
            image_data = image_data.split(",")[1]
        
        import base64
        image_bytes = base64.b64decode(image_data)
        
        prompt = """วิเคราะห์อาหารในรูปภาพนี้และให้ข้อมูลโภชนาการโดยประมาณ
        - อ้างอิงฐานข้อมูลสารอาหารไทยจากสถาบันโภชนาการ มหาวิทยาลัยมหิดล (INMUCAL) สำหรับอาหารไทย
        
        ตอบเป็น JSON เท่านั้น ในรูปแบบ:
        {"name": "ชื่ออาหาร", "calories": ตัวเลข, "protein": ตัวเลข, "carbs": ตัวเลข, "fat": ตัวเลข}
        - calories เป็น kcal
        - protein, carbs, fat เป็นกรัม
        ตอบเฉพาะ JSON ไม่ต้องมีข้อความอื่น"""
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt
            ]
        )
        
        result_text = response.text.strip()
        # Extract JSON from response
        json_match = re.search(r'\{[^}]+\}', result_text)
        if json_match:
            result = json.loads(json_match.group())
            return AnalyzeFoodResponse(
                name=result.get("name", "Unknown Food"),
                calories=float(result.get("calories", 0)),
                protein=float(result.get("protein", 0)),
                carbs=float(result.get("carbs", 0)),
                fat=float(result.get("fat", 0))
            )
        else:
            raise HTTPException(status_code=500, detail="Could not parse AI response")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat_with_ai(request: ChatRequest):
    """Chat with AI nutritionist"""
    if not client:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")
    
    try:
        profile = request.profile
        food_logs = request.foodLogs
        
        # Build context
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
        
        # Add image if present
        if request.image:
            image_data = request.image
            if "," in image_data:
                image_data = image_data.split(",")[1]
            import base64
            image_bytes = base64.b64decode(image_data)
            contents = [
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                context,
                f"\nคำถาม: {request.message}"
            ]
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents
        )
        
        return ChatResponse(response=response.text)
        
    except Exception as e:
        print(f"[DEBUG] Chat error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

