# backend/service/chat_service.py
# 作用：接收前端请求，调用 Agent 图，流式返回结果
# 封装成 class，统一管理 Agent 图的初始化和调用

import os
import sys
from typing import AsyncGenerator

# 把 agent 目录加入 Python 路径
# 这样才能 import agent 层的模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../agent'))

from langchain_core.messages import HumanMessage


class ChatService:
    """
    聊天服务类。
    负责接收前端请求，调用 Agent 图，流式返回结果。
    封装成 class 的好处：Agent 图只初始化一次，节省资源。
    """

    def __init__(self):
        # 延迟导入，确保 sys.path 已经设置好
        # Agent 图只初始化一次，后续所有请求复用
        from core.workflow.graph_manager import AgentGraphManager
        manager = AgentGraphManager()
        self.agent_graph = manager.build_graph()
        print("[ChatService] Agent 图初始化完成")

    async def stream_chat(
        self,
        query: str,
        user_id: str,
        session_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        调用 Agent 图处理用户问题，流式返回结果。

        流程：
        1. 把用户问题封装成 AgentState
        2. 调用 agent_graph.ainvoke() 执行整个 Agent 流程
        3. 取出最终回复，逐字流式返回给前端
        """

        # 封装成 AgentState，传给 Agent 图
        state = {
            "messages": [HumanMessage(content=query)],
            "user_id": user_id,
            "session_id": session_id,
            "next_agent": "",
            "response": "",
            "metadata": {},
        }

        try:
            # 调用 Agent 图，等待整个流程执行完毕
            result = await self.agent_graph.ainvoke(state)

            # 取出最后一条 AI 回复
            final_message = result["messages"][-1]
            answer = final_message.content

            print(f"[ChatService] 最终回复：{answer[:50]}...")

            # 逐字流式返回给前端
            for char in answer:
                safe_char = char.replace('\n', '<br>')
                yield f"data: {safe_char}\n\n"

            # 发送结束信号
            yield "data: [DONE]\n\n"

        except Exception as e:
            print(f"[ChatService] 错误：{e}")
            yield f"data: 系统出现错误，请稍后再试\n\n"
            yield "data: [DONE]\n\n"


# 全局实例，只初始化一次
chat_service = ChatService()


# 供 chat_router 调用的函数
async def stream_chat(
    query: str,
    user_id: str,
    session_id: str,
) -> AsyncGenerator[str, None]:
    async for chunk in chat_service.stream_chat(query, user_id, session_id):
        yield chunk