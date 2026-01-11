import React, { useState, useEffect } from 'react';
import { UserProfile, FoodItem, DailyStats } from './types';
import Onboarding from './components/Onboarding';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import ChatAssistant from './components/ChatAssistant';
import HealthDashboard from './components/HealthDashboard';
import OverviewDashboard from './components/OverviewDashboard';
import {
  LayoutDashboard,
  MessageSquare,
  Leaf,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Lightbulb,
  Heart,
  Home
} from 'lucide-react';

const App: React.FC = () => {
  // --- State ---
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [foodLogs, setFoodLogs] = useState<FoodItem[]>([]);
  const [currentTab, setCurrentTab] = useState<'overview' | 'dashboard' | 'health' | 'chat'>('overview');
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login');
  const [isLoading, setIsLoading] = useState(true);

  // Date State for History
  const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split('T')[0]);

  // Health Data State (from watch)
  const [healthData, setHealthData] = useState<{
    heart_rate: number;
    steps: number;
    calories_burned: number;
    activity: string;
    battery: number;
    health_risk_level: string;
  } | null>(null);

  // --- Effects ---
  useEffect(() => {
    const checkAuth = async () => {
      const storedUserId = localStorage.getItem('nutrifriend_user_id');
      if (storedUserId) {
        try {
          const userRes = await fetch(`/users/${storedUserId}`);
          if (userRes.ok) {
            const userData = await userRes.json();

            const profile: UserProfile = {
              id: userData.id,
              username: userData.username,
              name: userData.name,
              age: userData.age,
              gender: userData.gender,
              weight: userData.weight,
              height: userData.height,
              activityLevel: userData.activity_level,
              goal: userData.goal,
              conditions: userData.conditions,
              dietaryRestrictions: userData.dietary_restrictions,
              targetTimeline: userData.target_timeline,
              aiAssessment: userData.ai_assessment,
              targetCalories: userData.target_calories,
              targetProtein: userData.target_protein,
              targetCarbs: userData.target_carbs,
              targetFat: userData.target_fat,
              dailyTips: userData.daily_tips ? JSON.parse(userData.daily_tips) : []
            };

            setUserProfile(profile);

            const foodRes = await fetch(`/users/${storedUserId}/foods`);
            if (foodRes.ok) {
              const foodData = await foodRes.json();
              setFoodLogs(foodData);
            }
          } else {
            localStorage.removeItem('nutrifriend_user_id');
          }
        } catch (error) {
          console.error("Failed to fetch user data", error);
        }
      }
      setIsLoading(false);
    };

    checkAuth();
  }, []);

  // Fetch health data from watch (every 5 seconds)
  useEffect(() => {
    const fetchHealthData = async () => {
      try {
        const res = await fetch('/watch/status');
        if (res.ok) {
          const data = await res.json();
          if (data.connected && (data.steps > 0 || data.battery > 0)) {
            setHealthData({
              heart_rate: data.hr || 0,
              steps: data.steps || 0,
              calories_burned: (data.steps || 0) * 0.04,
              activity: data.hr < 80 ? 'resting' : data.hr < 100 ? 'walking' : 'light_exercise',
              battery: data.battery || 0,
              health_risk_level: data.hr > 150 ? 'MODERATE' : 'LOW'
            });
          }
        }
      } catch (e) {
        // Ignore errors - watch may not be connected
      }
    };

    fetchHealthData();
    const interval = setInterval(fetchHealthData, 5000);
    return () => clearInterval(interval);
  }, []);

  // --- Handlers ---
  const handleLogin = async (user: UserProfile) => {
    const profile: UserProfile = {
      id: user.id,
      username: user.username,
      name: user.name,
      age: user.age,
      gender: user.gender,
      weight: user.weight,
      height: user.height,
      activityLevel: (user as any).activity_level || user.activityLevel,
      goal: user.goal,
      conditions: user.conditions,
      dietaryRestrictions: (user as any).dietary_restrictions || user.dietaryRestrictions,
      targetTimeline: (user as any).target_timeline || user.targetTimeline,
      aiAssessment: (user as any).ai_assessment || user.aiAssessment,
      targetCalories: (user as any).target_calories || user.targetCalories,
      targetProtein: (user as any).target_protein || user.targetProtein,
      targetCarbs: (user as any).target_carbs || user.targetCarbs,
      targetFat: (user as any).target_fat || user.targetFat,
      stepGoal: (user as any).step_goal || user.stepGoal || 10000,
      dailyTips: (user as any).daily_tips ? JSON.parse((user as any).daily_tips) : []
    };

    setUserProfile(profile);

    if (profile.id) {
      localStorage.setItem('nutrifriend_user_id', profile.id.toString());

      try {
        const foodRes = await fetch(`/users/${profile.id}/foods`);
        if (foodRes.ok) {
          const foodData = await foodRes.json();
          setFoodLogs(foodData);
        }
      } catch (e) {
        console.error("Error fetching logs", e);
      }
    }

    setCurrentTab('dashboard');
  };

  const handleLogout = () => {
    localStorage.removeItem('nutrifriend_user_id');
    setUserProfile(null);
    setFoodLogs([]);
    setAuthMode('login');
  };

  const handleOnboardingComplete = () => {
    alert("ลงทะเบียนสำเร็จ! กรุณาเข้าสู่ระบบ");
    setAuthMode('login');
  };

  const handleAddFoodLog = async (log: FoodItem) => {
    if (!userProfile?.id) return;

    try {
      const response = await fetch(`/users/${userProfile.id}/foods`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(log),
      });

      if (response.ok) {
        const newLog = await response.json();
        setFoodLogs(prev => [newLog, ...prev]);
      }
    } catch (error) {
      console.error("Failed to add log", error);
      setFoodLogs(prev => [log, ...prev]);
    }
  };

  const handleRemoveFoodLog = async (id: string) => {
    if (!userProfile?.id) return;

    try {
      await fetch(`/users/${userProfile.id}/foods/${id}`, {
        method: 'DELETE',
      });
      setFoodLogs(prev => prev.filter(item => item.id !== id));
    } catch (error) {
      console.error("Failed to delete log", error);
    }
  };

  const changeDate = (offset: number) => {
    const date = new Date(selectedDate);
    date.setDate(date.getDate() + offset);
    setSelectedDate(date.toISOString().split('T')[0]);
  };

  // --- Computed Stats ---
  const currentLogs = foodLogs.filter(log => log.date === selectedDate);

  const dailyStats: DailyStats = currentLogs.reduce((acc, curr) => ({
    calories: acc.calories + curr.calories,
    protein: acc.protein + curr.protein,
    carbs: acc.carbs + curr.carbs,
    fat: acc.fat + curr.fat,
  }), { calories: 0, protein: 0, carbs: 0, fat: 0 });

  // --- Render ---
  if (isLoading) {
    return <div className="min-h-screen flex items-center justify-center bg-slate-50">Loading...</div>;
  }

  if (!userProfile) {
    if (authMode === 'login') {
      return <Login onLogin={handleLogin} onRegisterClick={() => setAuthMode('register')} />;
    }
    return <Onboarding onComplete={handleOnboardingComplete} onLoginClick={() => setAuthMode('login')} />;
  }

  return (
    // ✅ เพิ่ม min-h-0 เพื่อให้ flex children คำนวณความสูง/scroll ได้ถูกต้อง
    <div className="h-screen bg-slate-50 flex flex-col md:flex-row overflow-hidden min-h-0 font-['Prompt']">

      {/* Sidebar / Mobile Nav */}
      <nav className="md:w-64 bg-white shadow-lg z-10 flex flex-col fixed md:relative bottom-0 w-full md:h-screen h-16 md:border-r border-t md:border-t-0 border-gray-100">
        <div className="hidden md:block p-6">
          <h1 className="text-2xl font-bold text-emerald-600 flex items-center">
            <Leaf className="w-8 h-8 mr-2" />
            Health Pi Friend
          </h1>
          <p className="text-sm text-gray-500 mt-2">สวัสดี, {userProfile.name}</p>
        </div>

        <div className="flex md:flex-col justify-around md:justify-start md:px-4 md:space-y-2 w-full h-full md:h-auto items-center md:items-stretch">
          <button
            onClick={() => setCurrentTab('overview')}
            className={`flex flex-col md:flex-row items-center p-2 md:p-3 rounded-lg transition-colors ${currentTab === 'overview' ? 'text-emerald-600 md:bg-emerald-50' : 'text-gray-400 hover:text-emerald-500'}`}
          >
            <Home className="w-6 h-6 md:mr-3" />
            <span className="text-xs md:text-sm font-medium mt-1 md:mt-0">ภาพรวม</span>
          </button>

          <button
            onClick={() => setCurrentTab('dashboard')}
            className={`flex flex-col md:flex-row items-center p-2 md:p-3 rounded-lg transition-colors ${currentTab === 'dashboard' ? 'text-emerald-600 md:bg-emerald-50' : 'text-gray-400 hover:text-emerald-500'}`}
          >
            <LayoutDashboard className="w-6 h-6 md:mr-3" />
            <span className="text-xs md:text-sm font-medium mt-1 md:mt-0">โภชนาการ</span>
          </button>

          <button
            onClick={() => setCurrentTab('health')}
            className={`flex flex-col md:flex-row items-center p-2 md:p-3 rounded-lg transition-colors ${currentTab === 'health' ? 'text-emerald-600 md:bg-emerald-50' : 'text-gray-400 hover:text-emerald-500'}`}
          >
            <Heart className="w-6 h-6 md:mr-3" />
            <span className="text-xs md:text-sm font-medium mt-1 md:mt-0">สุขภาพ</span>
          </button>

          <button
            onClick={() => setCurrentTab('chat')}
            className={`flex flex-col md:flex-row items-center p-2 md:p-3 rounded-lg transition-colors ${currentTab === 'chat' ? 'text-emerald-600 md:bg-emerald-50' : 'text-gray-400 hover:text-emerald-500'}`}
          >
            <MessageSquare className="w-6 h-6 md:mr-3" />
            <span className="text-xs md:text-sm font-medium mt-1 md:mt-0">ผู้ช่วยส่วนตัว</span>
          </button>
        </div>

        <div className="hidden md:block p-6 mt-auto">
          <div className="bg-emerald-50 p-4 rounded-xl text-xs text-emerald-800 mb-4">
            <p className="font-semibold mb-1 flex items-center">
              <Lightbulb className="w-3 h-3 mr-1" />
              เคล็ดลับวันนี้
            </p>
            {userProfile.dailyTips && userProfile.dailyTips.length > 0 ? (
              <p>{userProfile.dailyTips[new Date().getDay() % userProfile.dailyTips.length]}</p>
            ) : (
              <p>อย่าลืมดื่มน้ำให้เพียงพอ อย่างน้อยวันละ 8 แก้วนะครับ!</p>
            )}
          </div>
          <button
            onClick={handleLogout}
            className="w-full text-left text-sm text-red-500 hover:text-red-600 font-medium"
          >
            ออกจากระบบ
          </button>
        </div>
      </nav>

      {/* Main Content */}
      {/* ✅ เพิ่ม min-h-0 เพื่อให้ Dashboard ใช้ flex-1 / overflow ได้ถูกต้อง */}
      <main className="flex-1 min-h-0 p-4 md:p-8 overflow-y-auto mb-16 md:mb-0 max-w-7xl mx-auto w-full">
        {/* Date Navigator Header */}
        <div className="flex flex-col sm:flex-row justify-between items-center mb-6 gap-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-800">
              {currentTab === 'overview' ? 'ภาพรวมวันนี้' : currentTab === 'dashboard' ? 'โภชนาการวันนี้' : currentTab === 'health' ? 'สุขภาพของคุณ' : 'ผู้ช่วยส่วนตัว'}
            </h2>
            <p className="text-gray-500 text-sm hidden sm:block">ดูแลสุขภาพของคุณในทุกๆ วัน</p>
          </div>

          <div className="flex items-center bg-white rounded-lg shadow-sm border border-gray-200 p-1">
            <button onClick={() => changeDate(-1)} className="p-2 hover:bg-gray-100 rounded-md text-gray-600">
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center px-4 border-x border-gray-100">
              <Calendar className="w-4 h-4 text-emerald-500 mr-2" />
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="text-sm font-medium text-gray-700 focus:outline-none bg-transparent"
              />
            </div>
            <button onClick={() => changeDate(1)} className="p-2 hover:bg-gray-100 rounded-md text-gray-600">
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>

        {currentTab === 'overview' ? (
          <OverviewDashboard
            user={userProfile}
            stats={dailyStats}
            healthData={healthData}
            stepGoal={userProfile.stepGoal || 10000}
            navigateToNutrition={() => setCurrentTab('dashboard')}
            navigateToHealth={() => setCurrentTab('health')}
          />
        ) : currentTab === 'dashboard' ? (
          <Dashboard
            user={userProfile}
            stats={dailyStats}
            allLogs={foodLogs}
            selectedDate={selectedDate}
            currentLogs={currentLogs}
            onAddLog={handleAddFoodLog}
            onRemoveLog={handleRemoveFoodLog}
            navigateToChat={() => setCurrentTab('chat')}
          />
        ) : currentTab === 'health' ? (
          <HealthDashboard
            userId={userProfile.id!}
            stepGoal={userProfile.stepGoal || 10000}
            onStepGoalChange={async (newGoal) => {
              // Update local state
              setUserProfile({ ...userProfile, stepGoal: newGoal });
              // Save to backend
              try {
                await fetch(`/users/${userProfile.id}`, {
                  method: 'PUT',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ step_goal: newGoal })
                });
              } catch (e) {
                console.error('Failed to save step goal:', e);
              }
            }}
          />
        ) : (
          <div className="h-full flex flex-col">
            <ChatAssistant
              userProfile={userProfile}
              foodLogs={currentLogs}
              selectedDate={selectedDate}
              healthData={healthData || undefined}
            />
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
