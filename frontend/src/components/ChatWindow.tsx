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

function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [sessionId, setSessionId] = useState("session_001");

  // 新对话
  const handleNewChat = () => {
    if (messages.length > 0) {
      const title = messages[0].content.slice(0, 18) + "...";
      setConversations((prev) => [
        {
          id: sessionId,
          title,
          messages,
        },
        ...prev,
      ]);
    }
    setSessionId(`session_${Date.now()}`);
    setMessages([]);
  };

  // 切换历史对话
  const handleSelectConversation = (conv: Conversation) => {
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
      const res = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          user_id: "user_1001",
          session_id: sessionId,
        }),
      });

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const text = line.replace("data: ", "");
          if (text === "[DONE]") break;

          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              role: "assistant",
              content: updated[updated.length - 1].content + text,
            };
            return updated;
          });
        }
      }
    } catch (err) {
      console.error(err);
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
