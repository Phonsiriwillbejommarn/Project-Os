import React, { useState } from 'react';
import { UserProfile, Gender, ActivityLevel, Goal } from '../types';
import { User, Activity, Target, AlertCircle, Loader2 } from 'lucide-react';

interface OnboardingProps {
  onComplete: (profile: UserProfile) => void;
  onLoginClick: () => void;
}

const Onboarding: React.FC<OnboardingProps> = ({ onComplete, onLoginClick }) => {
  const [formData, setFormData] = useState<UserProfile>({
    username: '',
    password: '',
    name: '',
    age: '' as any, // Initialize as empty string for UI, will be parsed as number
    gender: Gender.Male,
    weight: '' as any,
    height: '' as any,
    activityLevel: ActivityLevel.ModeratelyActive,
    goal: Goal.LoseWeight,
    conditions: '',
    dietaryRestrictions: '',
    targetTimeline: '3 Months'
  });
  const [isLoading, setIsLoading] = useState(false);

  const handleChange = (field: keyof UserProfile, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.username && formData.password && formData.name && formData.weight > 0 && formData.height > 0) {
      setIsLoading(true);
      try {
        // Map frontend camelCase to backend snake_case expected by API
        const apiData = {
          username: formData.username,
          password: formData.password,
          name: formData.name,
          age: formData.age,
          gender: formData.gender,
          weight: formData.weight,
          height: formData.height,
          activity_level: formData.activityLevel, // Note snake_case
          goal: formData.goal,
          conditions: formData.conditions,
          dietary_restrictions: formData.dietaryRestrictions, // Note snake_case
          target_timeline: formData.targetTimeline
        };

        const response = await fetch('http://localhost:8000/users', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(apiData),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'การลงทะเบียนล้มเหลว');
        }

        const newUser = await response.json();
        // Convert back to frontend format if needed, but for now just pass formData + id
        onComplete({ ...formData, id: newUser.id });
      } catch (error) {
        alert(error instanceof Error ? error.message : 'เกิดข้อผิดพลาดในการลงทะเบียน');
      } finally {
        setIsLoading(false);
      }
    } else {
      alert('กรุณากรอกข้อมูลที่จำเป็นให้ครบถ้วน');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-emerald-100 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden">
        <div className="bg-emerald-600 p-6 text-white text-center">
          <h1 className="text-3xl font-bold mb-2">ยินดีต้อนรับสู่ NutriFriend AI</h1>
          <p className="text-emerald-100">เราจะช่วยดูแลสุขภาพของคุณให้ดีที่สุด กรุณาให้ข้อมูลเบื้องต้น</p>
        </div>

        <form onSubmit={handleSubmit} className="p-8 space-y-6" autoComplete="off">

          {/* Personal Info */}
          <div className="space-y-4">
            <h2 className="flex items-center text-xl font-semibold text-gray-700 border-b pb-2">
              <User className="w-5 h-5 mr-2 text-emerald-500" /> ข้อมูลบัญชีและส่วนตัว
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="md:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4 bg-emerald-50 p-4 rounded-lg">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">ชื่อผู้ใช้ (Username)</label>
                  <input
                    type="text"
                    value={formData.username}
                    onChange={(e) => handleChange('username', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                    placeholder="สำหรับเข้าสู่ระบบ"
                    required
                    autoComplete="off"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">รหัสผ่าน (Password)</label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => handleChange('password', e.target.value)}
                    className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                    placeholder="รหัสผ่านของคุณ"
                    required
                    autoComplete="new-password"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">ชื่อเล่น</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleChange('name', e.target.value)}
                  className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  placeholder="เช่น มิ้นท์"
                  required
                  autoComplete="off"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">อายุ (ปี)</label>
                <input
                  type="number"
                  value={formData.age}
                  onChange={(e) => handleChange('age', e.target.value === '' ? '' : parseInt(e.target.value))}
                  className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  placeholder="ระบุอายุ"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">น้ำหนัก (กก.)</label>
                <input
                  type="number"
                  value={formData.weight}
                  onChange={(e) => handleChange('weight', e.target.value === '' ? '' : parseFloat(e.target.value))}
                  className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  placeholder="ระบุน้ำหนัก"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">ส่วนสูง (ซม.)</label>
                <input
                  type="number"
                  value={formData.height}
                  onChange={(e) => handleChange('height', e.target.value === '' ? '' : parseFloat(e.target.value))}
                  className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  placeholder="ระบุส่วนสูง"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">เพศ</label>
                <select
                  value={formData.gender}
                  onChange={(e) => handleChange('gender', e.target.value as Gender)}
                  className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                >
                  <option value={Gender.Male}>ชาย</option>
                  <option value={Gender.Female}>หญิง</option>
                </select>
              </div>
            </div>
          </div>

          {/* Activity & Goal */}
          <div className="space-y-4">
            <h2 className="flex items-center text-xl font-semibold text-gray-700 border-b pb-2">
              <Activity className="w-5 h-5 mr-2 text-emerald-500" /> กิจกรรมและเป้าหมาย
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">ระดับกิจกรรม</label>
                <select
                  value={formData.activityLevel}
                  onChange={(e) => handleChange('activityLevel', e.target.value as ActivityLevel)}
                  className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                >
                  <option value={ActivityLevel.Sedentary}>ไม่ออกกำลังกาย (นั่งทำงาน)</option>
                  <option value={ActivityLevel.LightlyActive}>ออกกำลังกายเล็กน้อย (1-3 วัน/สัปดาห์)</option>
                  <option value={ActivityLevel.ModeratelyActive}>ปานกลาง (3-5 วัน/สัปดาห์)</option>
                  <option value={ActivityLevel.VeryActive}>หนัก (6-7 วัน/สัปดาห์)</option>
                  <option value={ActivityLevel.ExtraActive}>หนักมาก (นักกีฬา/งานใช้แรง)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">เป้าหมาย</label>
                <select
                  value={formData.goal}
                  onChange={(e) => handleChange('goal', e.target.value as Goal)}
                  className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                >
                  <option value={Goal.LoseWeight}>ลดน้ำหนัก</option>
                  <option value={Goal.MaintainWeight}>รักษาน้ำหนัก</option>
                  <option value={Goal.GainMuscle}>เพิ่มกล้ามเนื้อ</option>
                </select>
              </div>
            </div>
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">ระยะเวลาเป้าหมาย</label>
              <select
                value={formData.targetTimeline}
                onChange={(e) => handleChange('targetTimeline', e.target.value)}
                className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              >
                <option value="1 Month">1 เดือน</option>
                <option value="3 Months">3 เดือน</option>
                <option value="6 Months">6 เดือน</option>
                <option value="1 Year">1 ปี</option>
              </select>
            </div>
          </div>

          {/* Health Conditions */}
          <div className="space-y-4">
            <h2 className="flex items-center text-xl font-semibold text-gray-700 border-b pb-2">
              <AlertCircle className="w-5 h-5 mr-2 text-emerald-500" /> ข้อมูลสุขภาพ
            </h2>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">โรคประจำตัว (ถ้ามี)</label>
              <input
                type="text"
                value={formData.conditions}
                onChange={(e) => handleChange('conditions', e.target.value)}
                className="w-full border border-gray-300 rounded-lg p-2 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                placeholder="เช่น เบาหวาน, ความดันโลหิตสูง (สำคัญมากสำหรับการประมวลผลของ AI)"
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-3 rounded-lg shadow-lg transition transform hover:scale-[1.02] flex items-center justify-center text-lg"
          >
            <Target className="w-6 h-6 mr-2" /> เริ่มต้นใช้งาน
          </button>

        </form>

        <div className="bg-gray-50 p-4 text-center border-t border-gray-100">
          <p className="text-sm text-gray-600">
            มีบัญชีอยู่แล้ว?{' '}
            <button
              onClick={onLoginClick}
              className="text-emerald-600 font-semibold hover:underline"
            >
              เข้าสู่ระบบ
            </button>
          </p>
        </div>
      </div >

      {/* Loading Overlay */}
      {isLoading && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-white p-8 rounded-2xl shadow-2xl flex flex-col items-center max-w-sm text-center animate-in fade-in zoom-in duration-300">
            <div className="relative mb-6">
              <div className="absolute inset-0 bg-emerald-100 rounded-full animate-ping opacity-75"></div>
              <div className="relative bg-emerald-50 p-4 rounded-full">
                <Loader2 className="w-10 h-10 text-emerald-600 animate-spin" />
              </div>
            </div>
            <h3 className="text-xl font-bold text-gray-800 mb-2">กำลังวิเคราะห์ข้อมูล...</h3>
            <p className="text-gray-500 text-sm">
              AI Nutritionist กำลังประเมินสุขภาพและสร้างแผนโภชนาการที่เหมาะสมที่สุดสำหรับคุณ
            </p>
          </div>
        </div>
      )}
    </div >
  );
};

export default Onboarding;