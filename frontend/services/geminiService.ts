import { UserProfile, FoodItem } from "../types";

const API_URL = '';

export const startChatSession = (profile: UserProfile) => {
  // No longer needed on frontend, handled by backend statelessly or via session
  console.log("Chat session initialized on backend");
};

export const sendMessageToGemini = async (
  message: string,
  image: string | undefined,
  profile: UserProfile,
  foodLogs: FoodItem[]
): Promise<string> => {
  try {
    const response = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        image,
        profile,
        foodLogs
      }),
    });

    if (!response.ok) {
      throw new Error(`Server responded with ${response.status}`);
    }

    const data = await response.json();
    return data.response;
  } catch (error) {
    console.error("Backend API Error:", error);
    return "ไม่สามารถเชื่อมต่อกับระบบ AI ได้ (Backend Error)\n1. กรุณาตรวจสอบว่ารันไฟล์ `main.py` แล้วหรือยัง\n2. ตรวจสอบ API Key ใน Backend";
  }
};

export const analyzeFoodFromImage = async (imageBase64: string): Promise<{ name: string, calories: number, protein: number, carbs: number, fat: number } | null> => {
  try {
    const response = await fetch(`${API_URL}/analyze-food`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        image: imageBase64
      }),
    });

    if (!response.ok) {
      throw new Error(`Server responded with ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Backend Analysis Error:", error);
    alert("ไม่สามารถเชื่อมต่อกับ Backend ได้ กรุณาตรวจสอบ Server");
    return null;
  }
};