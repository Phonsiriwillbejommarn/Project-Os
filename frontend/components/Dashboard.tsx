import React from 'react';
import { UserProfile, DailyStats, Goal, Gender, ActivityLevel, FoodItem } from '../types';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, BarChart, Bar, XAxis, YAxis, CartesianGrid, ReferenceLine } from 'recharts';
import { Target, Utensils, CheckCircle, CalendarDays, Sparkles } from 'lucide-react';
import FoodLogger from './FoodLogger';
import ReactMarkdown from 'react-markdown';

interface DashboardProps {
  user: UserProfile;
  stats: DailyStats;
  allLogs: FoodItem[];
  selectedDate: string;
  // Props for FoodLogger integration
  currentLogs: FoodItem[];
  onAddLog: (log: FoodItem) => void;
  onRemoveLog: (id: string) => void;
  navigateToChat: () => void;
}

const Dashboard: React.FC<DashboardProps> = ({
  user, stats, allLogs, selectedDate,
  currentLogs, onAddLog, onRemoveLog, navigateToChat
}) => {

  // Calculate BMR & TDEE (Target)
  const calculateBMR = () => {
    let bmr = (10 * user.weight) + (6.25 * user.height) - (5 * user.age);
    return user.gender === Gender.Male ? bmr + 5 : bmr - 161;
  };

  const calculateTDEE = (bmr: number) => {
    const multipliers: Record<ActivityLevel, number> = {
      [ActivityLevel.Sedentary]: 1.2,
      [ActivityLevel.LightlyActive]: 1.375,
      [ActivityLevel.ModeratelyActive]: 1.55,
      [ActivityLevel.VeryActive]: 1.725,
      [ActivityLevel.ExtraActive]: 1.9,
    };
    return Math.round(bmr * multipliers[user.activityLevel]);
  };

  const bmr = calculateBMR();
  const tdee = calculateTDEE(bmr);

  // Adjust goal calories
  let calculatedTarget = tdee;
  if (user.goal === Goal.LoseWeight) calculatedTarget -= 500;
  else if (user.goal === Goal.GainMuscle) calculatedTarget += 300;

  // Use AI target if available, otherwise fallback to calculation
  const targetCalories = user.targetCalories || calculatedTarget;

  const remainingCalories = targetCalories - stats.calories;

  // --- Weekly Data Calculation ---
  const getLast7DaysData = () => {
    const data = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(selectedDate);
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];

      // Filter logs for this specific date
      const dayLogs = allLogs.filter(log => log.date === dateStr);
      const totalCals = dayLogs.reduce((sum, item) => sum + item.calories, 0);

      // Format day name (e.g., Mon, Tue)
      const dayName = d.toLocaleDateString('th-TH', { weekday: 'short' });

      data.push({
        date: dateStr,
        name: dayName,
        calories: totalCals,
        target: targetCalories
      });
    }
    return data;
  };

  const weeklyData = getLast7DaysData();
  const avgWeeklyCalories = Math.round(weeklyData.reduce((sum, d) => sum + d.calories, 0) / 7);

  // --- Pie Chart Data ---
  const data = [
    { name: 'Carbs', value: stats.carbs, color: '#FBBF24' },    // Amber
    { name: 'Protein', value: stats.protein, color: '#34D399' }, // Emerald
    { name: 'Fat', value: stats.fat, color: '#F87171' },        // Red
  ];

  const calPercentage = Math.min(100, (stats.calories / targetCalories) * 100);

  return (
    <div className="space-y-4 animate-fade-in">
      {/* 1. Header Stats - Daily Budget */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500">เป้าหมาย (Goal)</p>
            <h3 className="text-3xl font-bold text-slate-700">{targetCalories.toLocaleString()}</h3>
            <p className="text-xs text-gray-400">kcal / วัน</p>
          </div>
          <Target className="w-10 h-10 text-blue-400 bg-blue-50 p-2 rounded-full" />
        </div>

        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500">กินไปแล้ว (Food)</p>
            <h3 className="text-3xl font-bold text-emerald-600">{stats.calories.toLocaleString()}</h3>
            <p className="text-xs text-gray-400">kcal</p>
          </div>
          <Utensils className="w-10 h-10 text-emerald-400 bg-emerald-50 p-2 rounded-full" />
        </div>

        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500">ทานได้อีก (Remaining)</p>
            <h3 className={`text-3xl font-bold ${remainingCalories < 0 ? 'text-red-500' : 'text-slate-700'}`}>
              {remainingCalories.toLocaleString()}
            </h3>
            <p className="text-xs text-gray-400">kcal</p>
          </div>
          <div className={`w-10 h-10 p-2 rounded-full flex items-center justify-center font-bold text-lg ${remainingCalories < 0 ? 'bg-red-50 text-red-500' : 'bg-gray-100 text-gray-500'}`}>
            {remainingCalories < 0 ? '!' : '+'}
          </div>
        </div>
      </div>

      {/* 2. Main Content Grid: Food Logger & Daily Nutrition */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Left Column: Food Logger */}
        <div className="lg:col-span-2 space-y-6">
          <FoodLogger
            logs={currentLogs}
            onAddLog={onAddLog}
            onRemoveLog={onRemoveLog}
            selectedDate={selectedDate}
          />

          {/* Weekly Summary (Bar Chart) */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-gray-700 flex items-center">
                <CalendarDays className="w-5 h-5 mr-2 text-indigo-500" />
                สรุป 7 วันย้อนหลัง
              </h3>
              <span className="text-xs bg-indigo-50 text-indigo-600 px-2 py-1 rounded-full">
                เฉลี่ย {avgWeeklyCalories} kcal/วัน
              </span>
            </div>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={weeklyData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis
                    dataKey="name"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 12, fill: '#94a3b8' }}
                    dy={10}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fontSize: 12, fill: '#94a3b8' }}
                  />
                  <Tooltip
                    cursor={{ fill: '#f8fafc' }}
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  />
                  <ReferenceLine y={targetCalories} stroke="#3b82f6" strokeDasharray="3 3" />
                  <Bar dataKey="calories" radius={[4, 4, 0, 0]}>
                    {weeklyData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.calories > entry.target ? '#f87171' : '#10b981'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 flex justify-center gap-4 text-xs text-gray-500">
              <div className="flex items-center"><span className="w-3 h-3 bg-emerald-500 rounded-sm mr-1"></span> ตามเกณฑ์</div>
              <div className="flex items-center"><span className="w-3 h-3 bg-red-400 rounded-sm mr-1"></span> เกินเป้าหมาย</div>
              <div className="flex items-center"><span className="w-3 h-1 border-t border-dashed border-blue-500 mr-1"></span> เป้าหมาย ({targetCalories})</div>
            </div>
          </div>
        </div>

        {/* Right Column: Daily Stats & Chat CTA */}
        <div className="lg:col-span-1 space-y-6">
          {/* AI Assessment Card */}
          {user.aiAssessment && (
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-emerald-100 overflow-hidden">
              <h3 className="text-lg font-semibold text-emerald-700 mb-4 flex items-center">
                <Sparkles className="w-5 h-5 mr-2" />
                แผนโภชนาการส่วนตัว
              </h3>

              {/* ✅ ลดความสูง: max-h-96 -> max-h-56 เพื่อให้การ์ดถัดไปแสดงโดยไม่ต้องเลื่อน */}
              <div className="text-sm text-gray-600 whitespace-pre-wrap leading-relaxed max-h-20 overflow-y-auto prose prose-emerald prose-sm">
                <ReactMarkdown>{user.aiAssessment}</ReactMarkdown>
              </div>
            </div>
          )}

          {/* Daily Nutrition Card (Pie Chart) */}
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col h-fit">
            <h3 className="text-lg font-semibold text-gray-700 mb-4 flex items-center">
              <CheckCircle className="w-5 h-5 mr-2 text-emerald-500" />
              โภชนาการวันนี้
            </h3>

            {/* Progress Bar */}
            <div className="mb-6">
              <div className="flex mb-2 items-center justify-between">
                <span className="text-xs font-semibold uppercase text-emerald-600">Calories Progress</span>
                <span className="text-xs font-semibold text-emerald-600">{Math.round(calPercentage)}%</span>
              </div>
              <div className="overflow-hidden h-3 mb-2 text-xs flex rounded-full bg-emerald-100">
                <div
                  style={{ width: `${calPercentage}%` }}
                  className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center transition-all duration-500 ${remainingCalories < 0 ? 'bg-red-500' : 'bg-emerald-500'}`}
                ></div>
              </div>
            </div>

            {/* Pie Chart */}
            <div className="h-[200px] relative">
              {stats.calories === 0 ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 border-2 border-dashed border-gray-100 rounded-xl">
                  <Utensils className="w-8 h-8 mb-2 opacity-20" />
                  <p className="text-sm">ไม่มีข้อมูลวันนี้</p>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={data}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={70}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {data.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value: number) => `${value}g`} />
                    <Legend verticalAlign="bottom" height={36} />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

        </div>
      </div>

    </div>
  );
};

export default Dashboard;
