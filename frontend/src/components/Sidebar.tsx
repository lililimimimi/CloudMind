import {
  CloudOutlined,
  HistoryOutlined,
  MenuFoldOutlined,
  MessageOutlined,
  PlusOutlined,
  UserOutlined,
} from "@ant-design/icons";
import type { ReactNode } from "react";

const menuItems: { icon: ReactNode; label: string }[] = [];

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">
          <img alt="cloudmind logo" src="/logo-options/cloudmind-logo-option-1.svg" />
        </div>
        <span>CloudMind</span>
        <MenuFoldOutlined className="sidebar-collapse" />
      </div>

      <button className="new-chat-button" type="button">
        <span>
          <MessageOutlined />
          新对话
        </span>
        <PlusOutlined />
      </button>

      <nav className="sidebar-nav">
        <div className="nav-heading">
          <HistoryOutlined />
          对话历史
        </div>
        {menuItems.map((item) => (
          <button className="nav-item" key={item.label} type="button">
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
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
