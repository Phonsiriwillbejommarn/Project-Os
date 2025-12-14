
export enum Gender {
  Male = 'Male',
  Female = 'Female'
}

export enum ActivityLevel {
  Sedentary = 'Sedentary', // Little or no exercise
  LightlyActive = 'LightlyActive', // Light exercise 1-3 days/week
  ModeratelyActive = 'ModeratelyActive', // Moderate exercise 3-5 days/week
  VeryActive = 'VeryActive', // Hard exercise 6-7 days/week
  ExtraActive = 'ExtraActive' // Very hard exercise & physical job
}

export enum Goal {
  LoseWeight = 'LoseWeight',
  MaintainWeight = 'MaintainWeight',
  GainMuscle = 'GainMuscle'
}

export interface UserProfile {
  id?: number;
  username?: string;
  password?: string;
  name: string;
  age: number;
  gender: Gender;
  weight: number; // kg
  height: number; // cm
  activityLevel: ActivityLevel;
  goal: Goal;
  conditions: string; // Comma separated string of medical conditions
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
  date: string; // ISO Date string YYYY-MM-DD
  timestamp: number;
}

export interface Message {
  id: string;
  role: 'user' | 'model';
  text: string;
  image?: string; // Base64 string of the uploaded image
  timestamp: number;
}

export interface DailyStats {
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}
