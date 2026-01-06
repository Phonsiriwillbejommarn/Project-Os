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
