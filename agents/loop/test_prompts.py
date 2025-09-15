import os
from typing import Any, Dict, List
from dotenv import load_dotenv

from agents.loop.prompts import Prompter
from agents.api.open_ai import OpenAIClient
from agents.connectors.search import Search
from agents.connectors.extract import Extract
from agents.connectors.news import News
from agents.connectors.binance_tool import BinanceTool
from agents.utils.objects import SimpleEvent, Market


def build_execute_trades_tool_description(config: Dict[str, Any]) -> Dict[str, Any]:
    """本地抄写自 main_loop._get_description()，避免直接依赖 main_loop。

    Returns:
        OpenAI tools schema for execute_trades
    """
    buy_config = config.get("trade", {}).get("Buy", {})
    sell_config = config.get("trade", {}).get("Sell", {})
    min_amount = buy_config.get("min_amount", 5)
    max_amount = buy_config.get("max_amount", 20)
    min_shares = sell_config.get("min_shares", 5)

    return {
        "type": "function",
        "function": {
            "name": "execute_trades",
            "description": "Execute trading decisions for a market with Yes/No outcomes",
            "parameters": {
                "type": "object",
                "properties": {
                    "Yes": {
                        "type": "object",
                        "description": "Trading decision for Yes outcome",
                        "properties": {
                            "should_trade": {
                                "type": "boolean",
                                "description": "Whether to execute trade for Yes outcome",
                            },
                            "side": {
                                "type": "string",
                                "description": "Trading side: Buy or Sell",
                                "enum": ["Buy", "Sell"],
                            },
                            "amount": {
                                "type": "integer",
                                "description": f"Trading amount. For Buy: must be between {min_amount} and {max_amount}. For Sell: must be between {min_shares} and current balance",
                            },
                        },
                        "required": ["should_trade", "side", "amount"],
                    },
                    "No": {
                        "type": "object",
                        "description": "Trading decision for No outcome",
                        "properties": {
                            "should_trade": {
                                "type": "boolean",
                                "description": "Whether to execute trade for No outcome",
                            },
                            "side": {
                                "type": "string",
                                "description": "Trading side: Buy or Sell",
                                "enum": ["Buy", "Sell"],
                            },
                            "amount": {
                                "type": "integer",
                                "description": f"Trading amount. For Buy: must be between {min_amount} and {max_amount}. For Sell: must be between {min_shares} and current balance",
                            },
                        },
                        "required": ["should_trade", "side", "amount"],
                    },
                    "next_process_time": {
                        "type": "string",
                        "description": "Next processing time in UTC ISO 8601 format without milliseconds: YYYY-MM-DDTHH:MM:SSZ (e.g., 2025-09-12T01:40:32Z)",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the trading decision.",
                    },
                },
                "required": ["Yes", "No", "next_process_time"],
            },
        },
    }


def build_demo_config() -> Dict[str, Any]:
    return {
        "model": {
            "openai": {
                "model_name": "gpt-5-mini",
                "temperature": 0.3,
                "max_token": 8192,
                "enable_thinking": False,
                "retry_count": 2,
                "timeout": 30,
            }
        },
        "search": {"length": 10, "type": "basic", "workers": 3, "max_search_queries": 3},
        "extract": {"depth": "basic", "max_extract_url_num": 3, "max_text_length": 2000},
        "news": {"page_size": 5, "categories": [
            "business",
            "entertainment",
            "general",
            "health",
            "science",
            "sports",
            "technology"
        ]},
        "crypto": {
            "symbol_white_list": ["BTCUSDT", "ETHUSDT"],
            "max_days": 20,
        },
        "next_process_time": {"min_ratio": 0.33},
        "trade": {"Buy": {"max_count": 3, "max_amount": 20, "min_amount": 5}, "Sell": {"min_shares": 5}},
        "agent": {"max_turn": 8},
    }


def build_demo_crypto_event_and_market() -> Dict[str, Any]:
    event = SimpleEvent(
        id=10001,
        ticker="BTC",
        slug="btc-price",
        title="Will BTC close above $120k on Dec 31, 2025?",
        description="A crypto event tracking BTC price by year-end.",
        end="2025-12-31T23:59:59Z",
        endDate="2025-12-31T23:59:59Z",
        active=True,
        closed=False,
        archived=False,
        restricted=False,
        new=True,
        featured=False,
        markets="20002",
    )

    market = Market(
        id=20002,
        question="Will BTC close above $120k on Dec 31, 2025?",
        description="YES if BTC/USD closing price is strictly above $120,000 at 2025-12-31 UTC.",
        endDate="2025-12-31T23:59:59Z",
        liquidity=12345.67,
        volume=987654.32,
        volume24hr=12345.0,
        active=True,
        closed=False,
    )

    order_book = {
        "bids": [
            {"price": "0.45", "size": "200"},
            {"price": "0.46", "size": "150"},
            {"price": "0.47", "size": "120"},
            {"price": "0.48", "size": "110"},
            {"price": "0.49", "size": "90"},
        ],
        "asks": [
            {"price": "0.55", "size": "210"},
            {"price": "0.54", "size": "160"},
            {"price": "0.53", "size": "130"},
            {"price": "0.52", "size": "100"},
            {"price": "0.51", "size": "95"},
        ],
        "tick_size": "0.01",
        "min_order_size": "0.001",
    }

    return {"event": event, "market": market, "order_book": order_book}


def main():
    # 提示：在运行脚本前，请先激活虚拟环境：
    # source ./venv/bin/activate

    # 加载项目根目录下的 .env
    load_dotenv()

    config = build_demo_config()

    # 初始化工具（仅用于获取工具描述，不实际联网调用），缺失密钥时跳过对应工具
    tools: List[Dict[str, Any]] = []
    try:
        search_tool = Search(logger=None, config=config)
        tools.append(search_tool._get_description())
    except Exception as e:
        print(f"[Warn] Init Search failed: {e}")
    try:
        extract_tool = Extract(logger=None, config=config)
        tools.append(extract_tool._get_description())
    except Exception as e:
        print(f"[Warn] Init Extract failed: {e}")
    try:
        news_tool = News(logger=None, config=config)
        tools.append(news_tool._get_description())
    except Exception as e:
        print(f"[Warn] Init News failed: {e}")
    try:
        binance_tool = BinanceTool(logger=None, config=config)
        tools.append(binance_tool._get_description())
    except Exception as e:
        print(f"[Warn] Init BinanceTool failed: {e}")

    # 添加 execute_trades（抄写）
    tools.append(build_execute_trades_tool_description(config))

    # 构建 System & User Prompts
    prompter = Prompter()
    demo = build_demo_crypto_event_and_market()
    symbol_white_list = config.get("crypto", {}).get("symbol_white_list", [])

    system_common = prompter.generate_common_system_message()
    system_crypto = prompter.generate_crypto_system_message(symbol_white_list)
    system_message = f"{system_common}\n\n{system_crypto}"

    user_event = prompter.generate_event_message(demo["event"])
    user_market = prompter.generate_market_message(demo["market"])
    user_order_book = prompter.generate_order_book_message(demo["order_book"])
    user_notice = prompter.generate_notice_message(config)
    user_prompt = f"{user_event}\n\n{user_market}\n\n{user_order_book}\n\n{user_notice}"

    # 调用 OpenAI（第一轮）
    client = OpenAIClient(logger=None, config=config)
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_prompt},
    ]

    print("==== System Message ====")
    print(system_message)
    print("\n==== User Prompt ====")
    print(user_prompt)

    print("\n==== Calling OpenAI... ====")
    result = client.chat(messages=messages, tools=tools)
    print("status:", result.get("status"))
    print("finish_reason:", result.get("finish_reason"))
    print("tool_calls:", result.get("tool_calls"))
    print("\n==== Model Content ====")
    print(result.get("content"))
    try:
        import json
        print("\n==== Full OpenAI Response ====")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception:
        print("\n[Warn] Cannot pretty print full response.")

    # 简单的工具执行回路：最多 6 步
    prompter_local = prompter
    step_guard = 0
    while result.get("tool_calls") and step_guard < 6:
        step_guard += 1
        tool_calls = result["tool_calls"]
        # 先附加包含 tool_calls 的 assistant 消息
        try:
            assistant_tool_calls = []
            for call in tool_calls:
                assistant_tool_calls.append({
                    "id": getattr(call, "id", ""),
                    "type": "function",
                    "function": {
                        "name": getattr(call.function, "name", ""),
                        "arguments": getattr(call.function, "arguments", "{}"),
                    },
                })
            messages.append({
                "role": "assistant",
                "content": result.get("content") or "",
                "tool_calls": assistant_tool_calls,
            })
        except Exception as _e:
            print(f"[Warn] build assistant tool_calls failed: {_e}")
        for call in tool_calls:
            name = getattr(call.function, "name", "")
            raw_args = getattr(call.function, "arguments", "{}")
            try:
                import json as _json
                args = _json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                args = {}

            tool_output_text = None
            # 执行各工具
            if name == "get_klines":
                try:
                    kl = binance_tool.get_klines(args.get("symbol"), args.get("timeframe"), int(args.get("days", 7)))
                    tool_output_text = prompter_local.generate_binance_tool_response_message(kl or [])
                except Exception as e:
                    tool_output_text = f"<tool_response>get_klines failed: {e}</tool_response>"
            elif name == "batch_query":
                try:
                    sq = search_tool.batch_query(args.get("queries", []))
                    tool_output_text = prompter_local.generate_search_tool_response_message(sq or {})
                except Exception as e:
                    tool_output_text = f"<tool_response>batch_query failed: {e}</tool_response>"
            elif name == "extract":
                try:
                    ex = extract_tool.extract(args.get("urls", []))
                    tool_output_text = prompter_local.generate_extract_tool_response_message(ex or [])
                except Exception as e:
                    tool_output_text = f"<tool_response>extract failed: {e}</tool_response>"
            elif name == "get_region_top_articles_from_category":
                try:
                    nw = news_tool.get_region_top_articles_from_category(args.get("country"), args.get("category"))
                    tool_output_text = prompter_local.generate_news_tool_response_message(nw or {})
                except Exception as e:
                    tool_output_text = f"<tool_response>news failed: {e}</tool_response>"
            elif name == "execute_trades":
                print("\n==== execute_trades (final) ====")
                try:
                    import json as _json
                    # 转换 next_process_time 为时间戳以便校验（规范为 UTC ISO8601 无毫秒）
                    iso_time = args.get("next_process_time")
                    ts = None
                    if isinstance(iso_time, str) and iso_time:
                        from datetime import datetime
                        try:
                            t = iso_time.strip()
                            # 去除毫秒
                            if "." in t:
                                t = t.split(".", 1)[0]
                            # 补全时区 Z
                            if t.endswith("Z"):
                                fmt = "%Y-%m-%dT%H:%M:%SZ"
                                ts = int(datetime.strptime(t, fmt).timestamp())
                            else:
                                # 若无Z且无偏移，则按UTC补Z
                                if "+" not in t and "-" in t[10:]:
                                    # 已含偏移，转为 fromisoformat
                                    ts = int(datetime.fromisoformat(t).timestamp())
                                else:
                                    t = f"{t}Z"
                                    fmt = "%Y-%m-%dT%H:%M:%SZ"
                                    ts = int(datetime.strptime(t, fmt).timestamp())
                        except Exception:
                            ts = None
                    args_with_ts = dict(args)
                    args_with_ts["_next_process_time_ts"] = ts
                    print(_json.dumps(args_with_ts, indent=2, ensure_ascii=False))
                except Exception:
                    print(args)
                # 结束流程
                return
            else:
                tool_output_text = f"<tool_response>Unknown tool: {name}</tool_response>"

            # 将工具输出作为 tool 消息追加
            messages.append({
                "role": "tool",
                "content": tool_output_text or "<tool_response/>",
                "tool_call_id": getattr(call, "id", "")
            })

        # 再次请求模型
        result = client.chat(messages=messages, tools=tools)
        print("\n==== Next Round ====")
        print("status:", result.get("status"))
        print("finish_reason:", result.get("finish_reason"))
        print("tool_calls:", result.get("tool_calls"))
        print("content:", result.get("content"))
        
        # 如果模型没有调用工具，继续下一轮
        if not result.get("tool_calls"):
            print("\n==== No tool calls, continuing to next round ====")
            # 将模型的回复添加到消息历史中
            if result.get("content"):
                messages.append({"role": "assistant", "content": result.get("content")})
            continue


if __name__ == "__main__":
    # 环境变量检查（提示用户）
    if not os.getenv("OPENAI_API_KEY"):
        print("[Warn] OPENAI_API_KEY 未设置，模型调用将失败。请先在环境变量中配置。")
    # 运行主流程
    main()


