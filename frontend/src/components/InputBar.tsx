// src/components/InputBar.tsx
import { useState } from "react";
import { Button, Input } from "antd";
import { SendOutlined } from "@ant-design/icons";

const { TextArea } = Input;

interface Props {
  onSend: (query: string) => void;
  loading: boolean;
}

function InputBar({ onSend, loading }: Props) {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim() || loading) return;
    onSend(input);
    setInput("");
  };

  return (
    <footer className="composer-wrap">
      <div className="composer">
        <TextArea
          autoSize={{ minRows: 1, maxRows: 5 }}
          className="composer-input"
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="请输入您的问题，Shift + Enter 换行，Enter 发送"
          value={input}
        />

        <div className="composer-tools">
          <Button
            className="send-button"
            disabled={!input.trim() || loading}
            icon={<SendOutlined />}
            loading={loading}
            onClick={handleSend}
            type="primary"
          >
            发送
          </Button>
        </div>
      </div>
    </footer>
  );
}

export default InputBar;
