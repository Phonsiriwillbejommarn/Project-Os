export enum Gender {
  Male = "Male",
  Female = "Female",
}

export enum ActivityLevel {
  Sedentary = "Sedentary",
  LightlyActive = "LightlyActive",
  ModeratelyActive = "ModeratelyActive",
  VeryActive = "VeryActive",
  ExtraActive = "ExtraActive",
}

export enum Goal {
  LoseWeight = "LoseWeight",
  MaintainWeight = "MaintainWeight",
  GainMuscle = "GainMuscle",
}

export interface UserProfile {
  id?: number;
  username?: string;
  password?: string;
  name: string;
  age: number;
  gender: Gender;
  weight: number;
  height: number;
  activityLevel: ActivityLevel;
  goal: Goal;
  conditions: string;
  dietaryRestrictions: string;
  targetTimeline?: string;
  aiAssessment?: string;
  targetCalories?: number;
  targetProtein?: number;
  targetCarbs?: number;
  targetFat?: number;
  dailyTips?: string[];
}

export interface FoodItem {
  id: string;
  name: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  date: string; // YYYY-MM-DD
  timestamp: number;
}

export interface Message {
  id: string;
  role: "user" | "model";
  text: string;
  image?: string; // base64
  timestamp: number;
  date?: string; // ✅ เพิ่ม (ใช้ตอนส่งเข้า DB)
}

export interface DailyStats {
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}
