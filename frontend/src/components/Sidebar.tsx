import {
  CloudOutlined,
  HistoryOutlined,
  MenuFoldOutlined,
  MessageOutlined,
  PlusOutlined,
  UserOutlined,
} from "@ant-design/icons";
import type { Conversation } from "./ChatWindow";

interface Props {
  conversations: Conversation[];
  onNewChat: () => void;
  onSelectConversation: (conv: Conversation) => void;
}

function Sidebar({ conversations, onNewChat, onSelectConversation }: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">
          <img
            alt="cloudmind logo"
            src="/logo-options/cloudmind-logo-option-1.svg"
          />
        </div>
        <span>CloudMind</span>
        <MenuFoldOutlined className="sidebar-collapse" />
      </div>

      {/* 新对话按钮 */}
      <button className="new-chat-button" type="button" onClick={onNewChat}>
        <span>
          <MessageOutlined />
          新对话
        </span>
        <PlusOutlined />
      </button>

      {/* 对话历史 */}
      <nav className="sidebar-nav">
        <div className="nav-heading">
          <HistoryOutlined />
          对话历史
        </div>
        {conversations.length === 0 ? (
          <div style={{ padding: "8px 12px", fontSize: "12px", color: "#aaa" }}>
            暂无历史记录
          </div>
        ) : (
          conversations.map((conv) => (
            <button
              className="nav-item"
              key={conv.id}
              type="button"
              onClick={() => onSelectConversation(conv)}
            >
              <MessageOutlined />
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {conv.title}
              </span>
            </button>
          ))
        )}
      </nav>

      <div className="sidebar-user">
        <div className="user-avatar">
          <UserOutlined />
        </div>
        <div className="user-meta">
          <strong>user_1001</strong>
          <span>企业成员</span>
        </div>
        <CloudOutlined className="user-menu" />
      </div>
    </aside>
  );
}

export default Sidebar;
