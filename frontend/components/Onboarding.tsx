import React, { useState } from 'react';
import { UserProfile, Gender, ActivityLevel, Goal } from '../types';
import { User, Activity, Target, AlertCircle, Loader2, ArrowRight, ArrowLeft, Check, Heart, Scale, Calendar } from 'lucide-react';

interface OnboardingProps {
  onComplete: (profile: UserProfile) => void;
  onLoginClick: () => void;
}

const Onboarding: React.FC<OnboardingProps> = ({ onComplete, onLoginClick }) => {
  const [step, setStep] = useState(1);
  const totalSteps = 4;

  const [formData, setFormData] = useState<UserProfile>({
    username: '',
    password: '',
    name: '',
    age: '' as any,
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

  // Helper to check if current step is valid
  const isStepValid = () => {
    switch (step) {
      case 1:
        return formData.username.trim() !== '' && formData.password.length >= 4 && formData.name.trim() !== '';
      case 2:
        return formData.age > 0 && formData.weight > 0 && formData.height > 0;
      case 3:
        return true; // Selects always have value
      case 4:
        return true; // Optional fields
      default:
        return false;
    }
  };

  const nextStep = () => {
    if (isStepValid()) {
      setStep(prev => Math.min(prev + 1, totalSteps));
    }
  };

  const prevStep = () => {
    setStep(prev => Math.max(prev - 1, 1));
  };

  const handleChange = (field: keyof UserProfile, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const calculateBMI = () => {
    if (formData.weight > 0 && formData.height > 0) {
      const h = formData.height / 100;
      return (formData.weight / (h * h)).toFixed(1);
    }
    return null;
  };

  const handleSubmit = async () => {
    setIsLoading(true);
    try {
      const apiData = {
        username: formData.username,
        password: formData.password,
        name: formData.name,
        age: formData.age,
        gender: formData.gender,
        weight: formData.weight,
        height: formData.height,
        activity_level: formData.activityLevel,
        goal: formData.goal,
        conditions: formData.conditions,
        dietary_restrictions: formData.dietaryRestrictions,
        target_timeline: formData.targetTimeline
      };

      const response = await fetch('/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(apiData),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Server Error Response:", errorText);

        let errorMessage = 'การลงทะเบียนล้มเหลว';
        try {
          const errorData = JSON.parse(errorText);
          errorMessage = errorData.detail || errorMessage;
        } catch (e) {
          errorMessage = `Server Error (${response.status}): ${errorText.substring(0, 100)}`;
        }
        throw new Error(errorMessage);
      }

      const responseText = await response.text();
      console.log("Raw Server Response:", responseText);

      let newUser;
      try {
        newUser = JSON.parse(responseText);
      } catch (e) {
        console.error("JSON Parse Error:", e);
        throw new Error(`Invalid JSON response: ${responseText.substring(0, 100)}...`);
      }

      onComplete({ ...formData, id: newUser.id });
    } catch (error: any) {
      console.error("Registration Error:", error);
      // Show detailed error for debugging
      const errorMsg = error?.message || 'Unknown error';
      const errorStack = error?.stack || '';
      const errorName = error?.name || 'Error';

      alert(`Error: ${errorName}\nMessage: ${errorMsg}\n\n(Please verify backend connection)`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-green-50 to-emerald-100 p-4 font-sans">
      <div className="bg-white rounded-3xl shadow-xl w-full max-w-4xl overflow-hidden flex flex-col md:flex-row h-auto md:h-[600px]">

        {/* Sidebar Summary (Desktop) */}
        <div className="hidden md:flex flex-col bg-emerald-600 text-white w-1/3 p-8 justify-between relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-full opacity-10">
            <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
              <path fill="#FFFFFF" d="M42.7,-62.9C50.9,-52.8,50.1,-34.4,51.7,-19.2C53.4,-4,57.4,8,54,18.7C50.6,29.4,39.8,38.8,28,46.6C16.2,54.4,3.4,60.6,-10.1,61.8C-23.6,63,-37.8,59.3,-48.6,50.5C-59.4,41.7,-66.8,27.9,-68.8,13.4C-70.8,-1.1,-67.4,-16.3,-58.5,-28.9C-49.6,-41.5,-35.1,-51.5,-21.3,-58.5C-7.5,-65.5,5.6,-69.5,17.9,-68.4L30.2,-67.3Z" transform="translate(100 100)" />
            </svg>
          </div>

          <div className="relative z-10">
            <h1 className="text-3xl font-bold mb-4 flex items-center gap-2">
              <Heart className="fill-emerald-400 text-emerald-100" /> Health Pi Friend
            </h1>
            <p className="text-emerald-100 mb-8 opacity-90 leading-relaxed">
              ดูแลสุขภาพผ่าน AI ผู้ช่วยส่วนตัวของคุณ เริ่มต้นง่ายๆ เพียงไม่กี่ขั้นตอน
            </p>

            <div className="space-y-4">
              {[
                { id: 1, label: 'สร้างบัญชี', icon: User },
                { id: 2, label: 'ข้อมูลส่วนตัว', icon: Scale },
                { id: 3, label: 'เป้าหมาย', icon: Target },
                { id: 4, label: 'สุขภาพ', icon: Activity },
              ].map((s) => (
                <div key={s.id} className={`flex items-center gap-3 p-3 rounded-xl transition-all ${step === s.id ? 'bg-white/20 translate-x-2' : 'opacity-60'}`}>
                  <div className={`p-2 rounded-full ${step === s.id ? 'bg-white text-emerald-600' : 'bg-emerald-800 text-emerald-200'}`}>
                    {step > s.id ? <Check size={16} /> : <s.icon size={16} />}
                  </div>
                  <span className="font-medium">{s.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="relative z-10 text-xs text-emerald-200 text-center">
            © 2024 Health Pi Friend
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 p-6 md:p-10 flex flex-col relative bg-slate-50">
          {/* Mobile Progress Bar */}
          <div className="md:hidden mb-6">
            <div className="flex justify-between mb-2 text-xs font-medium text-gray-500">
              <span>ต้อนรับ</span>
              <span>{Math.round((step / totalSteps) * 100)}%</span>
            </div>
            <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500 transition-all duration-300" style={{ width: `${(step / totalSteps) * 100}%` }}></div>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">

            {step === 1 && (
              <div className="animate-in fade-in slide-in-from-right duration-300">
                <h2 className="text-2xl font-bold text-gray-800 mb-6">เริ่มสร้างบัญชีของคุณ</h2>
                <div className="space-y-5">
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">Username</label>
                    <input
                      type="text"
                      value={formData.username}
                      onChange={(e) => handleChange('username', e.target.value)}
                      className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 focus:ring-2 focus:ring-emerald-500 outline-none transition-all shadow-sm"
                      placeholder="ชื่อผู้ใช้สำหรับเข้าสู่ระบบ"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">Password</label>
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => handleChange('password', e.target.value)}
                      className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 focus:ring-2 focus:ring-emerald-500 outline-none transition-all shadow-sm"
                      placeholder="รหัสผ่านอย่างน้อย 4 ตัวอักษร"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">ชื่อเล่น</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => handleChange('name', e.target.value)}
                      className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 focus:ring-2 focus:ring-emerald-500 outline-none transition-all shadow-sm"
                      placeholder="เช่น มิ้นท์, บอล"
                    />
                  </div>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="animate-in fade-in slide-in-from-right duration-300">
                <h2 className="text-2xl font-bold text-gray-800 mb-6">ข้อมูลร่างกาย</h2>
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-3">เพศ</label>
                    <div className="grid grid-cols-2 gap-4">
                      {[Gender.Male, Gender.Female].map((g) => (
                        <button
                          key={g}
                          type="button"
                          onClick={() => handleChange('gender', g)}
                          className={`py-4 rounded-xl border-2 font-medium transition-all ${formData.gender === g
                            ? 'border-emerald-500 bg-emerald-50 text-emerald-700 shadow-md transform scale-[1.02]'
                            : 'border-gray-100 bg-white text-gray-500 hover:border-gray-200'
                            }`}
                        >
                          {g === Gender.Male ? 'ชาย' : 'หญิง'}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">น้ำหนัก (kg)</label>
                      <input
                        type="number"
                        value={formData.weight}
                        onChange={(e) => handleChange('weight', parseFloat(e.target.value))}
                        className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 focus:ring-2 focus:ring-emerald-500 outline-none text-center text-lg font-medium"
                        placeholder="0.0"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">ส่วนสูง (cm)</label>
                      <input
                        type="number"
                        value={formData.height}
                        onChange={(e) => handleChange('height', parseFloat(e.target.value))}
                        className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 focus:ring-2 focus:ring-emerald-500 outline-none text-center text-lg font-medium"
                        placeholder="0"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">อายุ (ปี)</label>
                    <input
                      type="number"
                      value={formData.age}
                      onChange={(e) => handleChange('age', parseInt(e.target.value))}
                      className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 focus:ring-2 focus:ring-emerald-500 outline-none text-lg"
                      placeholder="ระบุอายุ"
                    />
                  </div>

                  {calculateBMI() && (
                    <div className="bg-blue-50 text-blue-800 px-4 py-3 rounded-xl flex justify-between items-center text-sm">
                      <span className="font-medium">ดัชนีมวลกาย (BMI) เบื้องต้น:</span>
                      <span className="text-xl font-bold">{calculateBMI()}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="animate-in fade-in slide-in-from-right duration-300">
                <h2 className="text-2xl font-bold text-gray-800 mb-6">ไลฟ์สไตล์และเป้าหมาย</h2>
                <div className="space-y-6">
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-3">ระดับกิจกรรมประจำวัน</label>
                    <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar p-1">
                      {[
                        { val: ActivityLevel.Sedentary, label: 'นั่งทำงาน (Sedentary)', desc: 'ไม่ออกกำลังกายเลย หรือน้อยมาก' },
                        { val: ActivityLevel.LightlyActive, label: 'เล็กน้อย (Lightly Active)', desc: 'ออกกำลังกาย 1-3 วัน/สัปดาห์' },
                        { val: ActivityLevel.ModeratelyActive, label: 'ปานกลาง (Moderately Active)', desc: 'ออกกำลังกาย 3-5 วัน/สัปดาห์' },
                        { val: ActivityLevel.VeryActive, label: 'หนัก (Very Active)', desc: 'ออกกำลังกาย 6-7 วัน/สัปดาห์' },
                        { val: ActivityLevel.ExtraActive, label: 'หนักมาก (Extra Active)', desc: 'งานใช้แรง หรือนักกีฬาอาชีพ' },
                      ].map((opt) => (
                        <div
                          key={opt.val}
                          onClick={() => handleChange('activityLevel', opt.val)}
                          className={`p-3 rounded-xl border cursor-pointer transition-all flex items-center gap-3 ${formData.activityLevel === opt.val
                            ? 'border-emerald-500 bg-emerald-50 shadow-sm'
                            : 'border-gray-200 hover:bg-gray-50 bg-white'
                            }`}
                        >
                          <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${formData.activityLevel === opt.val ? 'border-emerald-500' : 'border-gray-300'}`}>
                            {formData.activityLevel === opt.val && <div className="w-2 h-2 rounded-full bg-emerald-500" />}
                          </div>
                          <div>
                            <div className="font-medium text-gray-800 text-sm">{opt.label}</div>
                            <div className="text-xs text-gray-500">{opt.desc}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">เป้าหมายหลัก</label>
                      <select
                        value={formData.goal}
                        onChange={(e) => handleChange('goal', e.target.value as Goal)}
                        className="w-full bg-white border border-gray-200 rounded-xl px-3 py-3 focus:ring-2 focus:ring-emerald-500 outline-none"
                      >
                        <option value={Goal.LoseWeight}>ลดน้ำหนัก</option>
                        <option value={Goal.MaintainWeight}>รักษาน้ำหนัก</option>
                        <option value={Goal.GainMuscle}>เพิ่มกล้ามเนื้อ</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-semibold text-gray-700 mb-2">ระยะเวลา</label>
                      <select
                        value={formData.targetTimeline}
                        onChange={(e) => handleChange('targetTimeline', e.target.value)}
                        className="w-full bg-white border border-gray-200 rounded-xl px-3 py-3 focus:ring-2 focus:ring-emerald-500 outline-none"
                      >
                        <option value="1 Month">1 เดือน</option>
                        <option value="3 Months">3 เดือน</option>
                        <option value="6 Months">6 เดือน</option>
                        <option value="1 Year">1 ปี</option>
                      </select>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="animate-in fade-in slide-in-from-right duration-300">
                <h2 className="text-2xl font-bold text-gray-800 mb-6">ข้อมูลสุขภาพเพิ่มเติม</h2>
                <div className="space-y-5">
                  <div className="bg-orange-50 p-4 rounded-xl border border-orange-100 flex gap-3 text-orange-800 text-sm mb-4">
                    <AlertCircle className="w-5 h-5 flex-shrink-0 text-orange-500" />
                    <p>ข้อมูลนี้สำคัญมาก เพื่อให้ AI ประเมินและแนะนำโภชนาการได้อย่างปลอดภัย โปรดระบุตามความเป็นจริง</p>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">โรคประจำตัว</label>
                    <textarea
                      value={formData.conditions}
                      onChange={(e) => handleChange('conditions', e.target.value)}
                      className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 focus:ring-2 focus:ring-emerald-500 outline-none transition-all shadow-sm h-24 resize-none"
                      placeholder="เช่น เบาหวาน, ความดันโลหิตสูง, ไตเรื้อรัง (หากไม่มีให้เว้นว่าง)"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">ข้อจำกัดอาหาร / การแพ้</label>
                    <textarea
                      value={formData.dietaryRestrictions}
                      onChange={(e) => handleChange('dietaryRestrictions', e.target.value)}
                      className="w-full bg-white border border-gray-200 rounded-xl px-4 py-3 focus:ring-2 focus:ring-emerald-500 outline-none transition-all shadow-sm h-24 resize-none"
                      placeholder="เช่น แพ้ถั่วลิสง, แพ้นมวัว, ทานเจ, อิสลาม (หากไม่มีให้เว้นว่าง)"
                    />
                  </div>
                </div>
              </div>
            )}

          </div>

          {/* Actions */}
          <div className="pt-6 mt-2 border-t border-gray-100 flex justify-between items-center">
            {step > 1 ? (
              <button
                onClick={prevStep}
                className="text-gray-500 hover:text-gray-800 font-medium px-4 py-2 rounded-lg hover:bg-gray-100 transition-colors flex items-center"
              >
                <ArrowLeft size={18} className="mr-2" /> ย้อนกลับ
              </button>
            ) : (
              <button
                onClick={onLoginClick}
                className="text-emerald-600 font-medium px-4 py-2 hover:bg-emerald-50 rounded-lg transition-colors"
              >
                เข้าสู่ระบบ
              </button>
            )}

            {step < totalSteps ? (
              <button
                onClick={nextStep}
                disabled={!isStepValid()}
                className={`bg-emerald-600 text-white px-6 py-3 rounded-xl font-semibold shadow-lg shadow-emerald-200 flex items-center transition-all ${!isStepValid() ? 'opacity-50 cursor-not-allowed' : 'hover:bg-emerald-700 hover:scale-105 filter'}`}
              >
                ถัดไป <ArrowRight size={18} className="ml-2" />
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={isLoading}
                className="bg-emerald-600 text-white px-8 py-3 rounded-xl font-bold shadow-lg shadow-emerald-200 flex items-center transition-all hover:bg-emerald-700 hover:shadow-xl hover:scale-105"
              >
                {isLoading ? <Loader2 className="animate-spin mr-2" /> : <Check className="mr-2" />}
                วิเคราะห์และเริ่มต้น
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Loading Overlay */}
      {isLoading && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="bg-white p-10 rounded-3xl shadow-2xl flex flex-col items-center max-w-sm text-center relative overflow-hidden">

            <div className="absolute top-0 w-full h-1 bg-gradient-to-r from-emerald-400 to-green-500"></div>

            <div className="relative mb-8">
              <div className="absolute inset-0 bg-emerald-100 rounded-full animate-ping opacity-75"></div>
              <div className="relative bg-emerald-50 p-5 rounded-full ring-4 ring-emerald-50">
                <Loader2 className="w-12 h-12 text-emerald-600 animate-spin" />
              </div>
            </div>
            <h3 className="text-2xl font-bold text-gray-800 mb-3">กำลังประมวลผล...</h3>
            <p className="text-gray-500 leading-relaxed">
              AI Nutritionist กำลังวิเคราะห์ข้อมูลสุขภาพของคุณเพื่อสร้างแผนโภชนาการส่วนบุคคล
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default Onboarding;