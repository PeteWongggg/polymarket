import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from openai import OpenAI



load_dotenv()


class OpenAIClient:
    def __init__(self, logger=None, config: Optional[dict] = None) -> None:
        self.logger = logger
        self.config = config or {}

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY 环境变量未设置。")

        self.client = OpenAI(api_key=api_key)

        model_cfg = self.config.get("model", {}) if isinstance(self.config, dict) else {}
        openai_cfg = model_cfg.get("openai", {}) if isinstance(model_cfg, dict) else {}
        self.model_name: str = openai_cfg.get("model_name", "gpt-4o-mini")
        self.temperature: float = float(openai_cfg.get("temperature", 0.3))
        self.max_tokens: Optional[int] = openai_cfg.get("max_token")
        try:
            if self.max_tokens is not None:
                self.max_tokens = int(self.max_tokens)
        except Exception:
            self.max_tokens = None
        self.enable_thinking: bool = bool(openai_cfg.get("enable_thinking", False))
        self.retry_count: int = int(openai_cfg.get("retry_count", 3))
        self.timeout: int = int(openai_cfg.get("timeout", 30))

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """统一的对话接口。

        参数：
          - messages: 消息列表，每个元素包含 role 和 content
          - tools: OpenAI 工具定义（函数调用）

        返回：
          - { status, content, tool_calls, finish_reason, usage }
        """

        kwargs: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if tools:
            kwargs["tools"] = tools

        # 重试机制
        last_error = None
        for attempt in range(self.retry_count):
            try:
                resp = self.client.chat.completions.create(**kwargs)
                break  # 成功则跳出重试循环
            except Exception as e:
                last_error = e
                if self.logger:
                    self.logger.warning(f"OpenAI ChatCompletion 失败 (尝试 {attempt + 1}/{self.retry_count}): {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    # 最后一次重试失败
                    if self.logger:
                        self.logger.error(f"OpenAI ChatCompletion 最终失败: {e}")
                    return {
                        "status": "failed",
                        "content": None,
                        "tool_calls": None,
                        "finish_reason": None,
                        "usage": None,
                    }

        choice = resp.choices[0] if resp.choices else None
        content = None
        tool_calls = None
        finish_reason = None

        if choice:
            msg = choice.message
            content = getattr(msg, "content", None)
            tool_calls = getattr(msg, "tool_calls", None)
            finish_reason = getattr(choice, "finish_reason", None)

        usage = getattr(resp, "usage", None)

        return {
            "status": "success",
            "content": content,
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
            "usage": usage.model_dump() if hasattr(usage, "model_dump") else usage,
        }


if __name__ == "__main__":
    demo_config = {
        "model": {
            "openai": {
                "model_name": "gpt-5",
                "temperature": 0.3,
                "max_token": 128,
                "enable_thinking": False,
                "retry_count": 3,
                "timeout": 30,
            }
        }
    }
    client = OpenAIClient(config=demo_config)
    
    # 定义工具
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "联网搜索功能，用于获取最新信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "querys": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "搜索查询列表"
                        }
                    },
                    "required": ["querys"]
                }
            }
        },
        {
            "type": "function", 
            "function": {
                "name": "answer",
                "description": "提供最终回答",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "answer": {
                            "type": "string",
                            "description": "最终回答内容"
                        }
                    },
                    "required": ["answer"]
                }
            }
        }
    ]
    
    # 测试需要搜索的prompt
    messages = [
        {"role": "system", "content": "你是一个智能助手，可以搜索最新信息并提供准确回答。"},
        {"role": "user", "content": "请搜索一下2024年美国总统大选的最新进展，包括主要候选人和当前民调情况，然后给我一个总结。"},
    ]
    
    result = client.chat(messages=messages, tools=tools)
    print(result)
    print("status:", result.get("status"))
    print("content:", result.get("content"))
    print("finish_reason:", result.get("finish_reason"))
    
    # 如果有工具调用，打印工具调用信息
    if result.get("tool_calls"):
        print("tool_calls:")
        for tool_call in result.get("tool_calls"):
            print(f"  - function: {tool_call.function.name}")
            print(f"    arguments: {tool_call.function.arguments}")

