import React, { useState, useRef, useEffect } from "react";
import { Message, UserProfile, FoodItem } from "../types";
import { Send, Bot, User as UserIcon, Loader2, Image as ImageIcon, X, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface ChatAssistantProps {
  userProfile: UserProfile;
  foodLogs: FoodItem[];
  selectedDate: string;
}

const API_BASE = "http://localhost:8000";

const ChatAssistant: React.FC<ChatAssistantProps> = ({ userProfile, foodLogs, selectedDate }) => {
  const userId = userProfile.id;

  const INITIAL_MESSAGE: Message = {
    id: "welcome",
    role: "model",
    text: `สวัสดีครับคุณ ${userProfile.name}! 👋
ผมคือ NutriFriend เพื่อนคู่คิดด้านโภชนาการของคุณ

📸 ส่งรูปอาหารให้ผมช่วยวิเคราะห์ได้
📊 ผมดูข้อมูลอาหารที่คุณบันทึกวันนี้เพื่อแนะนำเพิ่มเติมได้ครับ`,
    timestamp: Date.now(),
    date: selectedDate,
  };

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");

  // แยก preview กับ base64
  const [selectedImagePreview, setSelectedImagePreview] = useState<string | null>(null);
  const [selectedImageBase64, setSelectedImageBase64] = useState<string | null>(null);

  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* ---------------- Load messages from DB (by date) ---------------- */
  useEffect(() => {
    const loadMessages = async () => {
      if (!userId) return;

      try {
        const res = await fetch(`${API_BASE}/users/${userId}/messages?date=${selectedDate}`);
        if (!res.ok) throw new Error("load failed");

        const data: Message[] = await res.json();
        setMessages(data && data.length ? data : [INITIAL_MESSAGE]);
      } catch {
        setMessages([INITIAL_MESSAGE]);
      }
    };

    loadMessages();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, selectedDate]);

  /* ---------------- Auto scroll ---------------- */
  useEffect(() => {
    // ใช้ scrollTop แทน scrollIntoView เพื่อไม่ให้กระทบหน้าหลัก
    if (messagesEndRef.current?.parentElement) {
      const container = messagesEndRef.current.parentElement;
      container.scrollTop = container.scrollHeight;
    }
  }, [messages]);

  /* ---------------- Clear chat (this date only) ---------------- */
  const handleClearHistory = async () => {
    if (!userId) return;
    if (!window.confirm(`ลบประวัติแชทวันที่ ${selectedDate} ใช่หรือไม่?`)) return;

    try {
      await fetch(`${API_BASE}/users/${userId}/messages?date=${selectedDate}`, { method: "DELETE" });
    } catch { }

    setMessages([INITIAL_MESSAGE]);
  };

  /* ---------------- Image handling ---------------- */
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // preview ทันที
    const previewUrl = URL.createObjectURL(file);
    setSelectedImagePreview(previewUrl);

    // base64 สำหรับส่ง backend
    const reader = new FileReader();
    reader.onloadend = () => setSelectedImageBase64(reader.result as string);
    reader.readAsDataURL(file);

    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleRemoveImage = () => {
    if (selectedImagePreview) URL.revokeObjectURL(selectedImagePreview);
    setSelectedImagePreview(null);
    setSelectedImageBase64(null);
  };

  /* ---------------- Save message to DB helper ---------------- */
  const saveMessageToDB = async (msg: Message) => {
    if (!userId) return;

    await fetch(`${API_BASE}/users/${userId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: msg.id,
        role: msg.role,
        text: msg.text,
        image: msg.image ?? null,
        timestamp: msg.timestamp,
        date: selectedDate,
      }),
    });
  };

  /* ---------------- Helper: get readable error message ---------------- */
  const buildErrorMessage = async (res: Response) => {
    // พยายามอ่าน detail จาก backend
    let detail = "";
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // ignore JSON parse errors
    }

    if (res.status === 409) {
      return "⏳ NutriFriend กำลังคิดคำตอบอยู่แล้วนะ ห้ามกดซ้ำ รอสักครู่แล้วค่อยส่งใหม่อีกทีครับ";
    }
    if (res.status === 429) {
      return "🚦 ส่งถี่เกินไป (429) กรุณารอสักครู่แล้วลองใหม่ครับ";
    }
    if (res.status === 503) {
      return "😵‍💫 AI มีคนใช้งานเยอะ (503) ลองใหม่อีกครั้งในอีกสักครู่ครับ";
    }
    if (res.status === 500) {
      return detail ? `❌ ${detail}` : "❌ Server มีปัญหา ลองใหม่อีกครั้งครับ";
    }

    // fallback
    return detail ? `❌ ${detail}` : "❌ ไม่สามารถตอบได้ในขณะนี้ กรุณาลองใหม่";
  };

  /* ---------------- Send message ---------------- */
  const handleSend = async () => {
    if ((!input.trim() && !selectedImageBase64) || isLoading || !userId) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: "user",
      text: input.trim(),
      image: selectedImageBase64 ?? undefined,
      timestamp: Date.now(),
      date: selectedDate,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    handleRemoveImage();
    setIsLoading(true);

    try {
      // ✅ 1) บันทึกข้อความ user ลง DB
      await saveMessageToDB(userMsg);

      // ✅ 2) คุยกับ AI
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg.text,
          image: userMsg.image,
          profile: userProfile,
          foodLogs,
        }),
      });

      if (!res.ok) {
        const msg = await buildErrorMessage(res);
        throw new Error(msg);
      }

      const data = await res.json();

      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: "model",
        text: data.response,
        timestamp: Date.now(),
        date: selectedDate,
      };

      setMessages((prev) => [...prev, aiMsg]);

      // ✅ 3) บันทึกข้อความ AI ลง DB
      await saveMessageToDB(aiMsg);
    } catch (err: any) {
      const errorMsg: Message = {
        id: Date.now().toString(),
        role: "model",
        text: err?.message || "❌ ไม่สามารถวิเคราะห์/ตอบได้ กรุณาลองใหม่",
        timestamp: Date.now(),
        date: selectedDate,
      };
      setMessages((prev) => [...prev, errorMsg]);

      // ถ้าอยากให้ error ถูกเก็บด้วย ให้เปิดบรรทัดนี้
      // await saveMessageToDB(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  /* ---------------- UI ---------------- */
  return (
    <div className="flex flex-col h-[calc(100vh-180px)] min-h-[400px] bg-white rounded-2xl border shadow-sm overflow-hidden">
      {/* Header */}
      <div className="bg-emerald-600 p-4 text-white flex justify-between items-center">
        <div className="flex items-center gap-2">
          <Bot size={20} />
          <h3 className="font-semibold">NutriFriend AI</h3>
        </div>
        <button onClick={handleClearHistory} title="ลบแชทของวันนั้น" className="opacity-90 hover:opacity-100">
          <Trash2 size={18} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] p-4 rounded-2xl text-sm shadow ${msg.role === "user" ? "bg-emerald-600 text-white" : "bg-white border"
                }`}
            >
              <div className="text-xs opacity-70 flex items-center gap-1 mb-1">
                {msg.role === "user" ? <UserIcon size={12} /> : <Bot size={12} />}
                {msg.role === "user" ? "คุณ" : "NutriFriend"}
              </div>

              {msg.image && <img src={msg.image} alt="uploaded" className="rounded-lg mb-2 max-h-60" />}

              <div className={`prose prose-sm max-w-none ${msg.role === "user" ? "prose-invert text-white" : "text-gray-800"}`}>
                <ReactMarkdown
                  components={{
                    // ปรับแต่ง style ของ element ต่างๆ ให้สวยงามขึ้น
                    p: ({ node, ...props }) => <p className="mb-2 last:mb-0" {...props} />,
                    ul: ({ node, ...props }) => <ul className="list-disc pl-4 mb-2 space-y-1" {...props} />,
                    ol: ({ node, ...props }) => <ol className="list-decimal pl-4 mb-2 space-y-1" {...props} />,
                    li: ({ node, ...props }) => <li className="" {...props} />,
                    strong: ({ node, ...props }) => <strong className="font-bold" {...props} />,
                  }}
                >
                  {msg.text}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-2 items-center text-gray-500 text-sm">
            <Loader2 className="animate-spin" size={16} />
            NutriFriend กำลังคิด...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t bg-white">
        {/* Preview */}
        {selectedImagePreview && (
          <div className="mb-3 flex items-center gap-2">
            <div className="relative">
              <img
                src={selectedImagePreview}
                alt="preview"
                className="h-16 w-16 object-cover rounded-lg border border-gray-200"
              />
              <button
                onClick={handleRemoveImage}
                className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 hover:bg-red-600 transition"
                title="ลบรูป"
              >
                <X size={12} />
              </button>
            </div>
            <span className="text-xs text-gray-500">พร้อมส่งรูปภาพ</span>
          </div>
        )}

        <div className="flex gap-2 items-center">
          <input type="file" hidden ref={fileInputRef} accept="image/*" onChange={handleImageSelect} />

          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 rounded-full hover:bg-emerald-50 text-gray-500 hover:text-emerald-600 transition"
            disabled={isLoading}
            title="แนบรูป"
          >
            <ImageIcon />
          </button>

          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            className="flex-1 border rounded-full px-4 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            placeholder={selectedImagePreview ? "ถามเพิ่มเติมเกี่ยวกับรูปนี้..." : "ถามเกี่ยวกับอาหาร..."}
            disabled={isLoading}
          />

          <button
            onClick={handleSend}
            disabled={isLoading || (!input.trim() && !selectedImageBase64)}
            className="bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 text-white p-2 rounded-full transition"
            title="ส่ง"
          >
            <Send />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatAssistant;
