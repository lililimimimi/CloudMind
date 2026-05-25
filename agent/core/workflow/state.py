# agent/core/workflow/state.py
import operator
from typing import TypedDict, Annotated, Sequence, Any
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    # 消息记录，operator.add 确保新消息追加而不是覆盖
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # 用户 ID
    user_id: str

    # 会话 ID
    session_id: str

    # orchestrator 判断后下一个要执行的 Agent
    next_agent: str

    # 最终回复内容
    response: str

    # 附加元数据，比如 is_finops_workflow 标记
    metadata: dict
    
    memory_context: str 
    
    