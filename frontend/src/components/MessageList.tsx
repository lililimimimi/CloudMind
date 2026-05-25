// src/components/MessageList.tsx
import { useEffect, useRef } from "react";
import { Avatar } from "antd";
import { RobotOutlined, UserOutlined } from "@ant-design/icons";
import type { Message } from "./ChatWindow";

interface Props {
  messages: Message[];
  loading: boolean;
}

function MessageList({ messages, loading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="message-list">
      {messages.map((msg, i) => (
        <div className={`message-row ${msg.role}`} key={`${msg.role}-${i}`}>
          {msg.role === "assistant" && (
            <Avatar
              className="message-avatar assistant"
              icon={<RobotOutlined />}
            />
          )}

          <div className={`message-bubble ${msg.role}`}>
            <div
              dangerouslySetInnerHTML={{
                __html: msg.content.replace(/<br>/g, "\n"),
              }}
              style={{ whiteSpace: "pre-wrap" }}
            />
            {msg.role === "assistant" &&
              loading &&
              i === messages.length - 1 && (
                <span
                  style={{
                    display: "inline-block",
                    width: "2px",
                    height: "14px",
                    background: "#3b82f6",
                    marginLeft: "4px",
                    verticalAlign: "middle",
                    animation: "blink 1s infinite",
                  }}
                />
              )}
          </div>

          {msg.role === "user" && (
            <Avatar className="message-avatar user" icon={<UserOutlined />} />
          )}
        </div>
      ))}

      <div ref={bottomRef} />
    </div>
  );
}

export default MessageList;
