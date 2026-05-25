# agent/core/memory/preference_extractor.py
import logging
from typing import Any

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = """\
分析以下对话，提取用户的偏好、习惯和个人信息。
每条用单独一行，格式为"类别: 内容"。
只包含具体的、可操作的用户信息。
如果没有相关信息，就输出: 无
所有输出内容必须用中文。

提取示例：
  城市: 上海
  语言: 中文
  习惯: 每天早上查天气
  偏好: 回答简洁
  不喜欢: 长篇大论
  性格: 和善、平易近人

对话内容：
{conversation}

提取结果（或"无"）："""


class PreferenceExtractor:
    """
    用 LLM 从对话中提取用户偏好。
    输出格式：类别: 内容
    例如：开发语言: Java
    """

    def __init__(self, llm: Any, max_conversation_chars: int = 3000) -> None:
        self._llm = llm
        self._max_chars = max_conversation_chars

    async def extract(
        self,
        conversation_text: str,
        existing: list[str] | None = None,
    ) -> list[str]:
        """
        从对话文本中提取新的用户偏好。

        Args:
            conversation_text: 对话历史
            existing: 已有的偏好，用于去重

        Returns:
            新发现的偏好列表，格式为 "类别: 内容"
        """
        truncated = conversation_text[:self._max_chars]
        prompt = _PROMPT_TEMPLATE.format(conversation=truncated)

        try:
            response = await self._llm.ainvoke([{"role": "user", "content": prompt}])
            raw = response.content.strip()
            logger.debug("[EXTRACTOR] LLM 返回: %s", raw)
        except Exception as exc:
            logger.warning("PreferenceExtractor LLM 调用失败: %s", exc)
            return []

        # 没有偏好
        if not raw or raw.strip() in ("NONE", "无", "提取结果: 无", "无相关信息"):
            return []

        # 解析 "类别: 内容" 格式
        candidates = [line.strip() for line in raw.split("\n") if ":" in line]
        if not candidates:
            return []

        if not existing:
            return candidates

        # 去重
        existing_lower = [e.lower() for e in existing]
        new_items = []
        for item in candidates:
            item_lower = item.lower()
            if any(item_lower in ex or ex in item_lower for ex in existing_lower):
                continue
            new_items.append(item)

        logger.info("[EXTRACTOR] 提取到 %d 条新偏好: %s", len(new_items), new_items)
        return new_items