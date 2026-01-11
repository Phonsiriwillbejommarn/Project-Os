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

// ============================================================
// Health Coach Types (Pi เป็นสมองหลัก)
// ============================================================

export interface HealthData {
  timestamp: number;
  heart_rate: number;
  steps: number;
  activity: string;
  hrv?: {
    sdnn: number;
    rmssd: number;
    pnn50: number;
    lf_hf_ratio?: number;
    stress_index: number;
  };
  anomaly_detected: boolean;
  fatigue_score: number;
  vo2_max?: number;
  calories_burned: number;
  hr_zone: {
    zone: number;
    name: string;
    hr_percent: number;
  };
  health_risk_level: string;
  processing_time_ms: number;
}

export interface HealthAlert {
  id: number;
  timestamp: number;
  alert_type: 'ALERT' | 'RECOMMENDATION' | 'ADJUST_PLAN' | 'NUTRITION';
  priority: 'LOW' | 'NORMAL' | 'HIGH' | 'CRITICAL';
  message: string;
  message_en?: string;
  acknowledged: boolean;
}

export interface HealthDecision {
  action: string;
  priority: string;
  message: string;
  message_en?: string;
  data?: Record<string, any>;
  notification_channels: string[];
  timestamp: number;
}

export interface WebSocketHealthMessage {
  health_data: HealthData;
  decisions: HealthDecision[];
}

export interface HealthSummary {
  avg_heart_rate?: number;
  max_heart_rate?: number;
  min_heart_rate?: number;
  total_steps: number;
  total_calories: number;
  last_activity?: string;
  last_update?: number;
}

export interface WorkoutSession {
  id: number;
  date: string;
  activity_type: string;
  duration_minutes?: number;
  avg_heart_rate?: number;
  calories_burned?: number;
  vo2_max?: number;
}
