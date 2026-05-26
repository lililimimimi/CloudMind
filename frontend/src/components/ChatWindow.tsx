// src/components/ChatWindow.tsx
import { useState } from "react";
import Sidebar from "./Sidebar";
import WelcomeScreen from "./WelcomeScreen";
import MessageList from "./MessageList";
import InputBar from "./InputBar";

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
}

const tabItems = ["Multi-Agent", "Billing", "Promotion", "FinOps"];
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const DEMO_USER_ID = import.meta.env.VITE_DEMO_USER_ID ?? "user_1001";

function createSessionId() {
  return `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function getConversationTitle(messages: Message[]) {
  const firstUserMessage = messages.find((message) => message.role === "user");
  if (!firstUserMessage) return "新对话";
  return firstUserMessage.content.length > 18
    ? `${firstUserMessage.content.slice(0, 18)}...`
    : firstUserMessage.content;
}

function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [sessionId, setSessionId] = useState(createSessionId);

  const saveCurrentConversation = () => {
    if (messages.length === 0) return;

    const snapshot: Conversation = {
      id: sessionId,
      title: getConversationTitle(messages),
      messages,
    };

    setConversations((prev) => {
      const existingIndex = prev.findIndex((conv) => conv.id === sessionId);
      if (existingIndex === -1) return [snapshot, ...prev];

      const updated = [...prev];
      updated[existingIndex] = snapshot;
      return updated;
    });
  };

  // 新对话
  const handleNewChat = () => {
    saveCurrentConversation();
    setSessionId(createSessionId());
    setMessages([]);
  };

  // 切换历史对话
  const handleSelectConversation = (conv: Conversation) => {
    saveCurrentConversation();
    setMessages(conv.messages);
    setSessionId(conv.id);
  };

  const handleSend = async (query: string) => {
    if (!query.trim()) return;

    const userMsg: Message = { role: "user", content: query };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const res = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          user_id: DEMO_USER_ID,
          session_id: sessionId,
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`Chat request failed: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamDone = false;

      while (!streamDone) {
        const { done, value } = await reader.read();
        buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
        if (done) streamDone = true;

        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const event of events) {
          const dataLines = event
            .split("\n")
            .filter((line) => line.startsWith("data: "))
            .map((line) => line.slice(6));

          if (dataLines.length === 0) continue;

          try {
            const parsed = JSON.parse(dataLines.join("\n"));

            // 收到结束信号
            if (parsed.done) {
              streamDone = true;
              break;
            }

            // 追加内容
            if (parsed.content) {
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  role: "assistant",
                  content: updated[updated.length - 1].content + parsed.content,
                };
                return updated;
              });
            }
          } catch {
            // 单个 SSE 事件异常时跳过，不影响后续事件
            continue;
          }
        }
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          content: "请求失败，请确认后端服务已启动后重试。",
        };
        return updated;
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <Sidebar
        conversations={conversations}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
      />

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <h1>企业云智能客服</h1>
            <div className="tab-strip" aria-label="业务场景">
              {tabItems.map((item) => (
                <span className="tab-item" key={item}>
                  {item}
                </span>
              ))}
            </div>
          </div>
        </header>

        <section className="content-area">
          {messages.length === 0 ? (
            <WelcomeScreen onSend={handleSend} />
          ) : (
            <MessageList messages={messages} loading={loading} />
          )}
        </section>

        <InputBar onSend={handleSend} loading={loading} />
      </main>
    </div>
  );
}

export default ChatWindow;
