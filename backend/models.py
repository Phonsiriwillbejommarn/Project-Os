from sqlalchemy import Column, Integer, String, Float, Text, Enum as SQLEnum, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import enum

Base = declarative_base()


# Enums
class Gender(str, enum.Enum):
    Male = "Male"
    Female = "Female"


class ActivityLevel(str, enum.Enum):
    Sedentary = "Sedentary"
    LightlyActive = "LightlyActive"
    ModeratelyActive = "ModeratelyActive"
    VeryActive = "VeryActive"
    ExtraActive = "ExtraActive"


class Goal(str, enum.Enum):
    LoseWeight = "LoseWeight"
    MaintainWeight = "MaintainWeight"
    GainMuscle = "GainMuscle"


class MessageRole(str, enum.Enum):
    user = "user"
    model = "model"


# Models
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(50), nullable=False)  # plain text (ตามที่ส้มทำไว้)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(SQLEnum(Gender), nullable=False)
    weight = Column(Float, nullable=False)  # kg
    height = Column(Float, nullable=False)  # cm
    activity_level = Column(SQLEnum(ActivityLevel), nullable=False)
    goal = Column(SQLEnum(Goal), nullable=False)
    conditions = Column(Text, default="")
    dietary_restrictions = Column(Text, default="")
    target_timeline = Column(String(50), nullable=True)
    ai_assessment = Column(Text, nullable=True)
    target_calories = Column(Float, nullable=True)
    target_protein = Column(Float, nullable=True)
    target_carbs = Column(Float, nullable=True)
    target_fat = Column(Float, nullable=True)
    daily_tips = Column(Text, default="[]")  # JSON string


class FoodItem(Base):
    __tablename__ = "food_items"

    id = Column(String(50), primary_key=True)
    user_id = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    calories = Column(Float, nullable=False)
    protein = Column(Float, nullable=False)
    carbs = Column(Float, nullable=False)
    fat = Column(Float, nullable=False)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    timestamp = Column(Integer, nullable=False)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(50), primary_key=True)
    user_id = Column(Integer, nullable=False)
    role = Column(SQLEnum(MessageRole), nullable=False)
    text = Column(Text, nullable=False)
    image = Column(Text, nullable=True)
    timestamp = Column(Integer, nullable=False)
    date = Column(String(10), nullable=False)  # ✅ YYYY-MM-DD


class NutritionPlan(Base):
    """ตารางเก็บแผนโภชนาการที่ AI วางไว้"""
    __tablename__ = "nutrition_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    
    # ข้อมูลแผน
    plan_type = Column(String(50), nullable=False)  # weekly, daily, custom
    week_start_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    week_end_date = Column(String(10), nullable=False)    # YYYY-MM-DD
    
    # เป้าหมายที่ AI กำหนด
    target_calories = Column(Float, nullable=True)
    target_protein = Column(Float, nullable=True)
    target_carbs = Column(Float, nullable=True)
    target_fat = Column(Float, nullable=True)
    
    # แผนรายละเอียด (JSON)
    daily_plan = Column(Text, nullable=True)       # แผนรายวัน (JSON array)
    meal_suggestions = Column(Text, nullable=True)  # แนะนำเมนู (JSON)
    
    # การวิเคราะห์
    analysis = Column(Text, nullable=True)          # วิเคราะห์จาก AI
    motivation = Column(Text, nullable=True)        # ข้อความให้กำลังใจ
    
    # สถานะการทำตาม
    adherence_rate = Column(Float, nullable=True)   # อัตราทำตามแผน (%)
    can_follow = Column(Integer, default=1)         # 1=ทำตามได้, 0=ปรับแผนแล้ว
    
    # Timestamps
    created_at = Column(Integer, nullable=False)    # Unix timestamp
    updated_at = Column(Integer, nullable=True)     # Unix timestamp


# ============================================================
# Health Monitoring Models (Pi Health Coach)
# ============================================================

class HealthMetric(Base):
    """เก็บข้อมูลสุขภาพแบบ Real-time จากนาฬิกา Aolon"""
    __tablename__ = "health_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    timestamp = Column(Integer, nullable=False)  # Unix timestamp
    date = Column(String(10), nullable=False)    # YYYY-MM-DD
    
    # Vital Signs
    heart_rate = Column(Integer, nullable=True)      # BPM
    spo2 = Column(Integer, nullable=True)            # Blood oxygen %
    blood_pressure_sys = Column(Integer, nullable=True)
    blood_pressure_dia = Column(Integer, nullable=True)
    
    # Activity
    steps = Column(Integer, default=0)
    calories_burned = Column(Float, default=0)
    distance = Column(Float, default=0)              # meters
    activity_type = Column(String(50), nullable=True)  # walking, running, etc.
    
    # Sleep (if available)
    sleep_quality = Column(Integer, nullable=True)   # 0-100
    
    # HRV Analysis (Pi คำนวณ)
    hrv_sdnn = Column(Float, nullable=True)
    hrv_rmssd = Column(Float, nullable=True)
    stress_index = Column(Float, nullable=True)
    
    # ML Predictions (Pi คำนวณ)
    fatigue_score = Column(Float, nullable=True)
    vo2_max = Column(Float, nullable=True)
    health_risk_level = Column(String(20), nullable=True)  # LOW, MODERATE, HIGH


class WorkoutSession(Base):
    """เก็บ session การออกกำลังกาย"""
    __tablename__ = "workout_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    date = Column(String(10), nullable=False)        # YYYY-MM-DD
    start_time = Column(Integer, nullable=False)     # Unix timestamp
    end_time = Column(Integer, nullable=True)        # Unix timestamp
    duration_minutes = Column(Integer, nullable=True)
    
    # Workout details
    activity_type = Column(String(50), nullable=False)  # running, walking, cycling, etc.
    
    # Heart rate stats
    avg_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    min_heart_rate = Column(Integer, nullable=True)
    
    # Performance metrics (Pi คำนวณ)
    calories_burned = Column(Float, nullable=True)
    distance = Column(Float, nullable=True)          # meters
    steps = Column(Integer, nullable=True)
    vo2_max = Column(Float, nullable=True)
    fatigue_score = Column(Float, nullable=True)
    
    # HRV during workout
    avg_hrv_rmssd = Column(Float, nullable=True)
    
    # Summary from AI
    ai_summary = Column(Text, nullable=True)


class HealthAlert(Base):
    """เก็บ Alert/Notification ที่ Pi สร้าง"""
    __tablename__ = "health_alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    timestamp = Column(Integer, nullable=False)      # Unix timestamp
    date = Column(String(10), nullable=False)        # YYYY-MM-DD
    
    # Alert details
    alert_type = Column(String(50), nullable=False)  # ANOMALY, FATIGUE, RECOMMENDATION, NUTRITION
    priority = Column(String(20), default="NORMAL")  # LOW, NORMAL, HIGH, CRITICAL
    message = Column(Text, nullable=False)           # Thai message
    message_en = Column(Text, nullable=True)         # English message
    
    # Related data (JSON)
    data = Column(Text, nullable=True)
    
    # Status
    acknowledged = Column(Integer, default=0)        # 0=unread, 1=read
    acknowledged_at = Column(Integer, nullable=True) # Unix timestamp


# Database setup
DATABASE_URL = "sqlite:///./nutrifriend.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
