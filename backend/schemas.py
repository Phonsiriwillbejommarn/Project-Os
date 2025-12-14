from pydantic import BaseModel
from typing import Optional
from models import Gender, ActivityLevel, Goal, MessageRole


# User Profile Schemas
class UserProfileCreate(BaseModel):
    username: str
    password: str
    name: str
    age: int
    gender: Gender
    weight: float
    height: float
    activity_level: ActivityLevel
    goal: Goal
    conditions: str = ""
    dietary_restrictions: str = ""
    target_timeline: Optional[str] = None


class UserProfileResponse(UserProfileCreate):
    id: int
    ai_assessment: Optional[str] = None
    target_calories: Optional[float] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fat: Optional[float] = None
    daily_tips: Optional[str] = None

    class Config:
        from_attributes = True


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[Gender] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    activity_level: Optional[ActivityLevel] = None
    goal: Optional[Goal] = None
    conditions: Optional[str] = None
    dietary_restrictions: Optional[str] = None
    target_timeline: Optional[str] = None
    target_calories: Optional[float] = None
    target_protein: Optional[float] = None
    target_carbs: Optional[float] = None
    target_fat: Optional[float] = None
    daily_tips: Optional[str] = None


# Food Item Schemas
class FoodItemCreate(BaseModel):
    id: str
    name: str
    calories: float
    protein: float
    carbs: float
    fat: float
    date: str
    timestamp: int


class FoodItemResponse(FoodItemCreate):
    user_id: int

    class Config:
        from_attributes = True


# Message Schemas
class MessageCreate(BaseModel):
    id: str
    role: MessageRole
    text: str
    image: Optional[str] = None
    timestamp: int


class MessageResponse(MessageCreate):
    user_id: int

    class Config:
        from_attributes = True


# Daily Stats Schema
class DailyStats(BaseModel):
    calories: float
    protein: float
    carbs: float
    fat: float
