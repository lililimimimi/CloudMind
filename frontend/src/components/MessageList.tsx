// src/components/MessageList.tsx
import { useEffect, useRef } from "react";
import { Avatar } from "antd";
import { RobotOutlined, UserOutlined } from "@ant-design/icons";
import type { Message } from "./ChatWindow";

interface Props {
  messages: Message[];
  loading: boolean;
}

function renderContent(content: string) {
  const lines = content.split("\n");
  return lines.map((line: string, idx: number) => {
    // 检测 markdown 图片 ![alt](url)
    const imgMatch = line.match(/!\[(.+?)\]\((.+?)\)/);
    if (imgMatch) {
      return (
        <div
          key={idx}
          style={{
            margin: "8px 0",
            position: "relative",
            display: "inline-block",
            width: "100%",
          }}
        >
          <img
            src={imgMatch[2]}
            alt={imgMatch[1]}
            style={{
              maxWidth: "100%",
              borderRadius: "8px",
              cursor: "pointer",
              display: "block",
            }}
            onClick={() => window.open(imgMatch[2], "_blank")}
          />
          {/* 底部渐变遮罩 + 文字 */}
          <div
            style={{
              position: "absolute",
              bottom: 0,
              left: 0,
              right: 0,
              background: "linear-gradient(transparent, rgba(0,0,0,0.75))",
              color: "#fff",
              padding: "24px 14px 12px",
              borderRadius: "0 0 8px 8px",
              fontSize: "13px",
              fontWeight: 600,
            }}
          >
            {imgMatch[1]}
          </div>
        </div>
      );
    }

    // 检测 markdown 链接 [text](url)
    const linkMatch = line.match(/\[(.+?)\]\((.+?)\)/);
    if (linkMatch) {
      const before = line.slice(0, line.indexOf(linkMatch[0]));
      const after = line.slice(
        line.indexOf(linkMatch[0]) + linkMatch[0].length,
      );
      return (
        <div key={idx}>
          <span>{before}</span>
          <a
            href={linkMatch[2]}
            target="_blank"
            rel="noreferrer"
            style={{ color: "#4f8ef7", textDecoration: "underline" }}
          >
            {linkMatch[1]}
          </a>
          <span>{after}</span>
        </div>
      );
    }

    // 普通文字
    return <div key={idx}>{line.replace(/<br>/g, "") || "\u00A0"}</div>;
  });
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
            {/* 内容为空时显示思考动画 */}
            {msg.role === "assistant" &&
            loading &&
            i === messages.length - 1 &&
            msg.content === "" ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  color: "#888",
                  fontSize: "13px",
                }}
              >
                <span style={{ display: "flex", gap: "4px" }}>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        background: "#4f8ef7",
                        display: "inline-block",
                        animation: "blink 1s infinite",
                        animationDelay: `${i * 0.2}s`,
                      }}
                    />
                  ))}
                </span>
                正在思考...
              </div>
            ) : (
              <>
                {renderContent(msg.content)}
                {msg.role === "assistant" &&
                  loading &&
                  i === messages.length - 1 &&
                  msg.content !== "" && (
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
              </>
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
