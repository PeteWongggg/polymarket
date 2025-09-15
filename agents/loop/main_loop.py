from agents.api.open_ai import OpenAIClient
from agents.connectors.extract import Extract
from agents.connectors.news import News
from agents.connectors.search import Search
from agents.connectors.binance_tool import BinanceTool
from agents.polymarket.polymarket import Polymarket
from agents.utils.objects import Market, SimpleEvent, ProcessMarketResult, MarketDecision, MarketTrades
from agents.loop.prompts import Prompter
from typing import Dict, Any
import time
import random
import json

# 宏定义
EXECUTE_TRADES_FUNCTION_NAME = "execute_trades"


class Loop:
    def __init__(self, logger, polymarket, config=None):
        """
        初始化Loop类
        
        Args:
            logger: 日志记录器
            polymarket: Polymarket实例
            config: 配置字典，包含各个组件的配置
        """
        self.logger = logger
        self.polymarket = polymarket
        
        # 设置默认配置
        default_config = {
            "next_process_time": {
                "min_ratio": 0.33
            },
            "trade": {
                "Buy": {
                    "max_count": 3,
                    "max_amount": 20,
                    "min_amount": 5
                },
                "Sell": {
                    "min_shares": 5
                }
            },
            "crypto": {
                "symbol_white_list": [
                    "BTCUSDT",
                    "ETHUSDT", 
                    "SOLUSDT",
                    "XRPUSDT",
                    "DOGEUSDT",
                    "BNBUSDT"
                ],
                "max_days": 100
            },
            "agent": {
                "max_turn": 8
            }
        }
        
        # 合并用户配置和默认配置
        if config:
            # 深度合并配置
            self.config = self._merge_config(default_config, config)
        else:
            self.config = default_config
        
        # 初始化各个组件
        self.openai_client = OpenAIClient(logger=logger, config=self.config)
        self.extract = Extract(logger=logger, config=self.config)
        self.news = News(logger=logger, config=self.config)
        self.search = Search(logger=logger, config=self.config)
        self.binance_tool = BinanceTool(logger=logger, config=self.config)
        self.prompter = Prompter()
        
        self.logger.debug("Loop类初始化完成")
    
    def _merge_config(self, default_config, user_config):
        """
        深度合并配置字典
        
        Args:
            default_config: 默认配置
            user_config: 用户配置
            
        Returns:
            合并后的配置
        """
        merged = default_config.copy()
        
        for key, value in user_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # 如果两个值都是字典，递归合并
                merged[key] = self._merge_config(merged[key], value)
            else:
                # 如果key不存在或值不是字典，直接覆盖
                merged[key] = value
        
        return merged
    
    def _calibrate_next_process_time(self, result: ProcessMarketResult, end_date: str, market_id: int = 0) -> ProcessMarketResult:
        """
        校准next_process_time，确保符合配置限制
        
        Args:
            result: ProcessMarketResult实例
            end_date: 市场结束时间字符串
            market_id: 市场ID，用于日志记录
            
        Returns:
            校准后的ProcessMarketResult
        """
        current_time = int(time.time())
        
        # 获取配置中的最小比例
        min_ratio = self.config.get("next_process_time", {}).get("min_ratio", 0.33)
        
        # 如果没有结束时间，使用默认的一周后
        if not end_date:
            result.next_process_time = current_time + (7*24*3600)
            return result
        
        try:
            from datetime import datetime
            
            # 解析结束时间
            end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            end_timestamp = int(end_datetime.timestamp())
            
            # 计算剩余时间
            remaining_time = end_timestamp - current_time
            
            # 如果已经过期，设置为默认的一周后
            if remaining_time <= 0:
                result.next_process_time = current_time + (7*24*3600)
                return result
            
            # 计算最小等待时间
            min_wait_time = int(remaining_time * min_ratio)
            min_next_process_time = current_time + min_wait_time
            
            # 如果决策的next_process_time太频繁，则使用最小等待时间
            if result.next_process_time < min_next_process_time:
                result.next_process_time = min_next_process_time
                self.logger.debug(f"Market {market_id} next_process_time校准: 原值太频繁，调整为 {min_next_process_time}")
            
        except Exception as e:
            self.logger.warning(f"校准Market {market_id} next_process_time失败: {e}, 使用默认值")
            result.next_process_time = current_time + (7*24*3600)
        
        return result
    
    def _calibrate_buy_operations(self, result: ProcessMarketResult, market_trades: MarketTrades = None) -> ProcessMarketResult:
        """
        校准Buy操作，检查金额限制和次数限制
        
        Args:
            result: ProcessMarketResult实例
            market_trades: MarketTrades实例，可选
            
        Returns:
            校准后的ProcessMarketResult
        """
        # 获取买入配置
        buy_config = self.config.get("trade", {}).get("Buy", {})
        max_amount = buy_config.get("max_amount", 20)
        min_amount = buy_config.get("min_amount", 5)
        max_count = buy_config.get("max_count", 3)
        
        # 校准Yes的Buy操作
        if result.Yes.should_trade and result.Yes.side == "Buy":
            # 检查金额限制
            if result.Yes.amount < min_amount:
                result.Yes.amount = min_amount
                self.logger.debug(f"Yes Buy金额过小，调整为最小值 {min_amount}")
            elif result.Yes.amount > max_amount:
                result.Yes.amount = max_amount
                self.logger.debug(f"Yes Buy金额过大，调整为最大值 {max_amount}")
            
            # 检查次数限制
            if market_trades:
                buy_count = sum(1 for trade in market_trades.Yes.Trades if trade.side == "BUY")
                if buy_count >= max_count:
                    result.Yes.should_trade = False
                    result.Yes.amount = 0
                    self.logger.debug(f"Yes Buy次数已达上限 {max_count}，取消本次Buy操作")
        
        # 校准No的Buy操作
        if result.No.should_trade and result.No.side == "Buy":
            # 检查金额限制
            if result.No.amount < min_amount:
                result.No.amount = min_amount
                self.logger.debug(f"No Buy金额过小，调整为最小值 {min_amount}")
            elif result.No.amount > max_amount:
                result.No.amount = max_amount
                self.logger.debug(f"No Buy金额过大，调整为最大值 {max_amount}")
            
            # 检查次数限制
            if market_trades:
                buy_count = sum(1 for trade in market_trades.No.Trades if trade.side == "BUY")
                if buy_count >= max_count:
                    result.No.should_trade = False
                    result.No.amount = 0
                    self.logger.debug(f"No Buy次数已达上限 {max_count}，取消本次Buy操作")
        
        return result
    
    def _calibrate_sell_operations(self, result: ProcessMarketResult, market_trades: MarketTrades = None) -> ProcessMarketResult:
        """
        校准Sell操作，检查余额限制和数量限制
        
        Args:
            result: ProcessMarketResult实例
            market_trades: MarketTrades实例，可选
            
        Returns:
            校准后的ProcessMarketResult
        """
        # 获取卖出配置
        sell_config = self.config.get("trade", {}).get("Sell", {})
        min_shares = sell_config.get("min_shares", 5)
        
        # 校准Yes的Sell操作
        if result.Yes.should_trade and result.Yes.side == "Sell":
            if not market_trades or market_trades.Yes.balance < min_shares:
                # 没有交易数据或余额不足，取消Sell操作
                result.Yes.should_trade = False
                result.Yes.amount = 0
                self.logger.debug(f"Yes Sell余额不足最小限制 {min_shares}，取消Sell操作")
            else:
                # 检查卖出数量是否超过余额
                if result.Yes.amount > market_trades.Yes.balance:
                    result.Yes.amount = market_trades.Yes.balance
                    self.logger.debug(f"Yes Sell数量超过余额，调整为余额数量 {market_trades.Yes.balance}")
        
        # 校准No的Sell操作
        if result.No.should_trade and result.No.side == "Sell":
            if not market_trades or market_trades.No.balance < min_shares:
                # 没有交易数据或余额不足，取消Sell操作
                result.No.should_trade = False
                result.No.amount = 0
                self.logger.debug(f"No Sell余额不足最小限制 {min_shares}，取消Sell操作")
            else:
                # 检查卖出数量是否超过余额
                if result.No.amount > market_trades.No.balance:
                    result.No.amount = market_trades.No.balance
                    self.logger.debug(f"No Sell数量超过余额，调整为余额数量 {market_trades.No.balance}")
        
        return result
    
    def calibrate_decision(self, market: Market = None, result: ProcessMarketResult = None, market_trades: MarketTrades = None) -> ProcessMarketResult:
        """
        校准ProcessMarketResult决策结果
        
        Args:
            market: Market实例，可选
            result: ProcessMarketResult实例
            market_trades: MarketTrades实例，可选
            
        Returns:
            校准后的ProcessMarketResult
        """
        # 确定market_id和end_date
        if market:
            market_id = market.id
            end_date = market.endDate
        elif market_trades:
            market_id = 0  # 使用默认ID
            end_date = market_trades.market_info.market_end_date
        else:
            market_id = 0
            end_date = None
        
        self.logger.debug(f"开始校准Market {market_id}的决策结果")
        
        # 1. 校准next_process_time
        result = self._calibrate_next_process_time(result, end_date, market_id)
        
        # 2. 校准Buy操作
        result = self._calibrate_buy_operations(result, market_trades)
        
        # 3. 校准Sell操作
        result = self._calibrate_sell_operations(result, market_trades)
        
        self.logger.debug(f"Market {market_id}决策结果校准完成")
        return result
    
    def _convert_iso_to_timestamp(self, iso_time: str, fallback_timestamp: int) -> int:
        """
        将ISO 8601格式时间转换为时间戳
        
        Args:
            iso_time: ISO 8601格式时间字符串 (YYYY-MM-DDTHH:MM:SSZ)
            fallback_timestamp: 转换失败时的备用时间戳
            
        Returns:
            int: 时间戳
        """
        if not iso_time or not isinstance(iso_time, str):
            return fallback_timestamp
            
        try:
            from datetime import datetime
            # 去除毫秒
            t = iso_time.strip()
            if "." in t:
                t = t.split(".", 1)[0]
            # 补全时区 Z
            if t.endswith("Z"):
                fmt = "%Y-%m-%dT%H:%M:%SZ"
                return int(datetime.strptime(t, fmt).timestamp())
            else:
                # 若无Z且无偏移，则按UTC补Z
                if "+" not in t and "-" in t[10:]:
                    # 已含偏移，转为 fromisoformat
                    return int(datetime.fromisoformat(t).timestamp())
                else:
                    t = f"{t}Z"
                    fmt = "%Y-%m-%dT%H:%M:%SZ"
                    return int(datetime.strptime(t, fmt).timestamp())
        except Exception as e:
            self.logger.warning(f"时间转换失败: {iso_time}, 使用备用时间戳: {e}")
            return fallback_timestamp

    def _execute_tool(self, function_name: str, function_args: dict) -> str:
        """
        执行工具调用
        
        Args:
            function_name: 工具函数名
            function_args: 工具参数
            
        Returns:
            str: 工具执行结果
        """
        try:
            if function_name == "batch_query":
                queries = function_args.get("queries", [])
                result = self.search.batch_query(queries)
                return self.prompter.generate_search_tool_response_message(result or {})
            elif function_name == "extract":
                urls = function_args.get("urls", [])
                result = self.extract.extract(urls)
                return self.prompter.generate_extract_tool_response_message(result or [])
            elif function_name == "get_region_top_articles_from_category":
                country = function_args.get("country", "us")
                category = function_args.get("category", "business")
                result = self.news.get_region_top_articles_from_category(country, category)
                return self.prompter.generate_news_tool_response_message(result or {})
            elif function_name == "get_klines":
                symbol = function_args.get("symbol", "BTCUSDT")
                timeframe = function_args.get("timeframe", "1d")
                days = function_args.get("days", 7)
                result = self.binance_tool.get_klines(symbol, timeframe, days)
                return self.prompter.generate_binance_tool_response_message(result or [])
            else:
                return f"<tool_response>Unknown tool: {function_name}</tool_response>"
        except Exception as e:
            self.logger.error(f"工具执行失败 {function_name}: {e}")
            return f"<tool_response>Tool execution failed: {e}</tool_response>"

    def process_new_market(self, market: Market, event: SimpleEvent) -> ProcessMarketResult:
        """
        处理新市场的交易决策
        
        Args:
            market: Market类实例
            event: SimpleEvent类实例
            
        Returns:
            ProcessMarketResult: 包含Yes/No交易决策和下次处理时间的结构体
        """
        self.logger.info(f"开始处理新市场: {market.id} - {market.question}")
        self.logger.debug(f"市场详情: ID={market.id}, 问题='{market.question}', 结束时间={market.endDate}")
        self.logger.debug(f"事件详情: ID={event.id}, 标题='{event.title}', 标签={[tag.label for tag in event.tags] if event.tags else 'None'}")
        
        # 获取当前时间戳
        current_time = int(time.time())
        
        # 默认下次处理时间（10秒后）
        next_process_time = current_time + 10
        
        # 判断是否为加密货币相关事件
        is_crypto = False
        if hasattr(event, 'tags') and event.tags:
            self.logger.debug(f"检查事件标签: {len(event.tags)} 个标签")
            for i, tag in enumerate(event.tags):
                tag_label = getattr(tag, 'label', '') or ''
                tag_slug = getattr(tag, 'slug', '') or ''
                self.logger.debug(f"标签 {i+1}: label='{tag_label}', slug='{tag_slug}'")
                if tag_label and 'crypto' in tag_label.lower():
                    is_crypto = True
                    self.logger.info(f"检测到crypto标签: '{tag_label}'")
                    break
                elif tag_slug and 'crypto' in tag_slug.lower():
                    is_crypto = True
                    self.logger.info(f"检测到crypto标签: '{tag_slug}'")
                    break
        else:
            self.logger.debug("事件无标签或标签为空")
        
        self.logger.info(f"市场类型判断: {'Crypto' if is_crypto else 'Non-Crypto'}")
        
        # 获取订单簿数据
        self.logger.info("开始获取订单簿数据")
        clob_token_ids = getattr(market, 'clobTokenIds', None)
        if not clob_token_ids or not isinstance(clob_token_ids, list) or len(clob_token_ids) < 2:
            self.logger.warning(f"市场 {market.id} 缺少有效的clobTokenIds，跳过交易")
            # 返回默认不交易决策，保持market的next_process_time
            default_next_time = getattr(market, 'next_process_time', current_time + 3600)
            yes_decision = MarketDecision(should_trade=False, side="Buy", amount=0)
            no_decision = MarketDecision(should_trade=False, side="Buy", amount=0)
            return ProcessMarketResult(
                Yes=yes_decision,
                No=no_decision,
                next_process_time=default_next_time,
                reason="缺少有效的clobTokenIds"
            )
        
        yes_token_id = clob_token_ids[0]
        no_token_id = clob_token_ids[1]
        self.logger.debug(f"订单簿Token IDs: Yes={yes_token_id}, No={no_token_id}")
        
        # 获取Yes订单簿
        yes_order_book = self.polymarket.get_order_book_compact(yes_token_id)
        if not yes_order_book:
            self.logger.warning(f"无法获取Yes订单簿数据，token_id={yes_token_id}，跳过交易")
            default_next_time = getattr(market, 'next_process_time', current_time + 3600)
            yes_decision = MarketDecision(should_trade=False, side="Buy", amount=0)
            no_decision = MarketDecision(should_trade=False, side="Buy", amount=0)
            return ProcessMarketResult(
                Yes=yes_decision,
                No=no_decision,
                next_process_time=default_next_time,
                reason="无法获取Yes订单簿数据"
            )
        
        # 获取No订单簿
        no_order_book = self.polymarket.get_order_book_compact(no_token_id)
        if not no_order_book:
            self.logger.warning(f"无法获取No订单簿数据，token_id={no_token_id}，跳过交易")
            default_next_time = getattr(market, 'next_process_time', current_time + 3600)
            yes_decision = MarketDecision(should_trade=False, side="Buy", amount=0)
            no_decision = MarketDecision(should_trade=False, side="Buy", amount=0)
            return ProcessMarketResult(
                Yes=yes_decision,
                No=no_decision,
                next_process_time=default_next_time,
                reason="无法获取No订单簿数据"
            )
        
        self.logger.info(f"成功获取订单簿数据: Yes bids={len(yes_order_book.get('bids', []))}, No bids={len(no_order_book.get('bids', []))}")
        
        # 构建系统消息
        self.logger.debug("开始构建系统消息")
        system_message = self.prompter.generate_common_system_message()
        if is_crypto:
            symbol_white_list = self.config.get("crypto", {}).get("symbol_white_list", [])
            self.logger.debug(f"使用Crypto系统消息，白名单: {symbol_white_list}")
            system_message += self.prompter.generate_crypto_system_message(symbol_white_list)
        else:
            self.logger.debug("使用政治/商业系统消息")
            system_message += self.prompter.generate_politic_business_system_message()
        
        self.logger.debug(f"系统消息长度: {len(system_message)} 字符")
        
        # 构建用户消息
        self.logger.debug("开始构建用户消息")
        user_message = ""
        user_message += self.prompter.generate_event_message(event)
        user_message += self.prompter.generate_market_message(market)
        
        # 添加订单簿消息
        user_message += self.prompter.generate_order_book_message(yes_order_book, no_order_book)
        user_message += self.prompter.generate_notice_message(self.config)
        
        self.logger.debug(f"用户消息长度: {len(user_message)} 字符")
        
        # 构建工具列表
        self.logger.debug("开始构建工具列表")
        tools = []
        tools.append(self.search._get_description())
        tools.append(self.extract._get_description())
        tools.append(self.news._get_description())
        if is_crypto:
            tools.append(self.binance_tool._get_description())
            self.logger.debug("添加了binance_tool到工具列表")
        tools.append(self._get_description())  # execute_trades
        
        self.logger.info(f"工具列表构建完成: {len(tools)} 个工具")
        tool_names = [tool.get('function', {}).get('name', 'unknown') for tool in tools]
        self.logger.debug(f"工具名称: {tool_names}")
        
        # 调用OpenAI
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        # 打印发送给模型的prompts
        print(f"\n==== Sending to Model (Turn 1) ====")
        print(f"System Message Length: {len(system_message)} chars")
        print(f"User Message Length: {len(user_message)} chars")
        print(f"Tools Count: {len(tools)}")
        print(f"System Message Preview: {system_message[:200]}...")
        print(f"User Message Preview: {user_message[:200]}...")
        
        max_turns = self.config.get("agent", {}).get("max_turn", 8)
        final_result = None
        
        for turn in range(max_turns):
            self.logger.info(f"第 {turn + 1} 轮对话")
            
            response = self.openai_client.chat(messages=messages, tools=tools)
            
            # 打印模型返回结果
            print(f"\n==== Model Response (Turn {turn + 1}) ====")
            print(f"Status: {response.get('status')}")
            print(f"Finish Reason: {response.get('finish_reason')}")
            tool_calls = response.get('tool_calls') or []
            print(f"Tool Calls Count: {len(tool_calls)}")
            print(f"Content Length: {len(response.get('content', '')) if response.get('content') else 0}")
            if response.get('content'):
                print(f"Content Preview: {response.get('content')[:200]}...")
            if tool_calls:
                for i, tool_call in enumerate(tool_calls):
                    print(f"Tool Call {i+1}: {tool_call.function.name}")
                    print(f"  Arguments: {tool_call.function.arguments[:100]}...")
            
            if response["status"] != "success":
                self.logger.error(f"OpenAI调用失败: {response}")
                break
                
            if response["tool_calls"]:
                # 先添加assistant消息
                messages.append({
                    "role": "assistant",
                    "content": response.get("content", ""),
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        } for tool_call in response["tool_calls"]
                    ]
                })
                
                # 处理工具调用
                for tool_call in response["tool_calls"]:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    if function_name == "execute_trades":
                        # 处理交易决策
                        try:
                            yes_data = function_args.get("Yes", {})
                            no_data = function_args.get("No", {})
                            next_process_time_iso = function_args.get("next_process_time", "")
                            reason = function_args.get("reason", "")
                            
                            # 转换时间戳
                            next_process_time = self._convert_iso_to_timestamp(next_process_time_iso, next_process_time)
                            
                            # 构建决策结果
                            yes_decision = MarketDecision(
                                should_trade=yes_data.get("should_trade", False),
                                side=yes_data.get("side", "Buy"),
                                amount=yes_data.get("amount", 0)
                            )
                            
                            no_decision = MarketDecision(
                                should_trade=no_data.get("should_trade", False),
                                side=no_data.get("side", "Buy"),
                                amount=no_data.get("amount", 0)
                            )
                            
                            final_result = ProcessMarketResult(
                                Yes=yes_decision,
                                No=no_decision,
                                next_process_time=next_process_time,
                                reason=reason
                            )
                            
                            self.logger.info(f"收到交易决策: Yes={yes_decision.should_trade}, No={no_decision.should_trade}")
                            break
                            
                        except Exception as e:
                            self.logger.error(f"解析交易决策失败: {e}")
                            break
                    else:
                        # 处理其他工具调用
                        tool_output = self._execute_tool(function_name, function_args)
                        messages.append({
                            "role": "tool",
                            "content": tool_output,
                            "tool_call_id": tool_call.id
                        })
                
                if final_result:
                    break
            else:
                # 没有工具调用，继续对话
                if response.get("content"):
                    messages.append({"role": "assistant", "content": response["content"]})
        
        # 如果没有得到最终结果，使用默认决策
        if not final_result:
            self.logger.warning("未收到交易决策，使用默认决策")
            # 使用market的next_process_time，如果没有则使用默认值
            default_next_time = getattr(market, 'next_process_time', current_time + 3600)
            yes_decision = MarketDecision(should_trade=False, side="Buy", amount=0)
            no_decision = MarketDecision(should_trade=False, side="Buy", amount=0)
            final_result = ProcessMarketResult(
                Yes=yes_decision,
                No=no_decision,
                next_process_time=default_next_time,
                reason="未收到有效决策"
            )
        
        # 校准决策结果
        final_result = self.calibrate_decision(market, final_result)
        
        self.logger.info(f"市场 {market.id} 处理完成，下次处理时间: {final_result.next_process_time}")
        return final_result


    def process_existing_market(self, market_trades: MarketTrades) -> ProcessMarketResult:
        """
        处理已有交易的市场决策
        
        Args:
            market_trades: 来自trades.db的该market的完整结构体快照
        
        Returns:
            ProcessMarketResult: 包含Yes/No交易决策和下次处理时间
        """
        # 基础策略占位：与新市场相同的随机逻辑，可在此处接入更复杂策略（基于余额/历史交易等）
        current_time = int(time.time())
        next_process_time = current_time + 10

        # 读取余额（单位：shares）
        yes_balance = int(market_trades.Yes.balance or 0)
        no_balance = int(market_trades.No.balance or 0)

        # Yes 决策
        yes_should_trade = random.random() < 0.5
        yes_side = "Buy"
        yes_amount = 0
        if yes_should_trade:
            if yes_balance > 0 and random.random() < 0.5:
                # 有余额时可能卖出，金额为 1..余额 的随机整数
                yes_side = "Sell"
                yes_amount = random.randint(1, yes_balance)
            else:
                yes_side = "Buy"
                yes_amount = random.randint(1, 10)

        # No 决策
        no_should_trade = random.random() < 0.5
        no_side = "Buy"
        no_amount = 0
        if no_should_trade:
            if no_balance > 0 and random.random() < 0.5:
                no_side = "Sell"
                no_amount = random.randint(1, no_balance)
            else:
                no_side = "Buy"
                no_amount = random.randint(1, 10)

        yes_decision = MarketDecision(
            should_trade=yes_should_trade,
            side=yes_side,
            amount=yes_amount
        )
        no_decision = MarketDecision(
            should_trade=no_should_trade,
            side=no_side,
            amount=no_amount
        )

        result = ProcessMarketResult(Yes=yes_decision, No=no_decision, next_process_time=next_process_time)
        
        # 校准决策结果（传入market_trades用于检查历史交易）
        result = self.calibrate_decision(market=None, result=result, market_trades=market_trades)
        
        return result

    def _get_name(self) -> str:
        """
        Returns the function name for OpenAI tool definition
        
        Returns:
            Function name string
        """
        return EXECUTE_TRADES_FUNCTION_NAME

    def _get_description(self) -> dict:
        """
        Returns OpenAI tool definition for execute_trade function
        
        Returns:
            OpenAI format tool definition dictionary
        """
        # 获取配置中的交易限制
        buy_config = self.config.get("trade", {}).get("Buy", {})
        sell_config = self.config.get("trade", {}).get("Sell", {})
        min_amount = buy_config.get("min_amount", 5)
        max_amount = buy_config.get("max_amount", 20)
        min_shares = sell_config.get("min_shares", 5)
        
        return {
            "type": "function",
            "function": {
                "name": self._get_name(),
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
                                    "description": "Whether to execute trade for Yes outcome"
                                },
                                "side": {
                                    "type": "string",
                                    "description": "Trading side: Buy or Sell",
                                    "enum": ["Buy", "Sell"]
                                },
                                "amount": {
                                    "type": "integer",
                                    "description": f"Trading amount. For Buy: must be between {min_amount} and {max_amount}. For Sell: must be between {min_shares} and current balance"
                                }
                            },
                            "required": ["should_trade", "side", "amount"]
                        },
                        "No": {
                            "type": "object",
                            "description": "Trading decision for No outcome",
                            "properties": {
                                "should_trade": {
                                    "type": "boolean",
                                    "description": "Whether to execute trade for No outcome"
                                },
                                "side": {
                                    "type": "string",
                                    "description": "Trading side: Buy or Sell",
                                    "enum": ["Buy", "Sell"]
                                },
                                "amount": {
                                    "type": "integer",
                                    "description": f"Trading amount. For Buy: must be between {min_amount} and {max_amount}. For Sell: must be between {min_shares} and current balance"
                                }
                            },
                            "required": ["should_trade", "side", "amount"]
                        },
                        "next_process_time": {
                            "type": "string",
                            "description": "Next processing time in UTC ISO 8601 format without milliseconds: YYYY-MM-DDTHH:MM:SSZ (e.g., 2025-09-12T01:40:32Z)."
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for the trading decision."
                        }
                    },
                    "required": ["Yes", "No", "next_process_time"]
                }
            }
        }


if __name__ == "__main__":
    # 测试process_new_market函数
    import sys
    from agents.logger.logger import Logger
    from agents.utils.objects import Tag
    
    # 重定向输出到文件
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    try:
        with open("./agents/loop/ret.txt", "w", encoding="utf-8") as f:
            sys.stdout = f
            sys.stderr = f
            
            print("==== Process New Market Test ====")
            print(f"Test started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 创建测试用的logger
            test_logger = Logger("./logs")
            
            # 创建测试配置
            test_config = {
                "model": {
                    "openai": {
                        "model_name": "gpt-4o-mini",
                        "temperature": 0.3,
                        "max_token": 8192,
                        "enable_thinking": False,
                        "retry_count": 3,
                        "timeout": 30,
                    }
                },
                "search": {
                    "length": 10,
                    "type": "basic",
                    "workers": 3,
                    "max_search_queries": 3
                },
                "extract": {
                    "depth": "basic",
                    "max_extract_url_num": 3,
                    "max_text_length": 2000
                },
                "news": {
                    "page_size": 5,
                    "categories": ["business", "technology", "general"]
                },
                "crypto": {
                    "symbol_white_list": ['BTCUSDT', 'ETHUSDT'],
                    "max_days": 7
                },
                "next_process_time": {"min_ratio": 0.33},
                "trade": {"Buy": {"max_count": 3, "max_amount": 20, "min_amount": 5}, "Sell": {"min_shares": 5}},
                "agent": {"max_turn": 8}
            }
            
            print("\n==== Configuration ====")
            print(f"Model: {test_config['model']['openai']['model_name']}")
            print(f"Max tokens: {test_config['model']['openai']['max_token']}")
            print(f"Max turns: {test_config['agent']['max_turn']}")
            print(f"Crypto symbols: {test_config['crypto']['symbol_white_list']}")
            
            # 创建Polymarket实例
            print("\n==== Initializing Polymarket ====")
            test_polymarket = Polymarket(logger=test_logger)
            print("Polymarket initialized successfully")
            
            # 实例化Loop类
            print("\n==== Initializing Loop ====")
            loop = Loop(logger=test_logger, polymarket=test_polymarket, config=test_config)
            print("Loop initialized successfully")
            
            # 测试1: 加密货币相关事件
            print("\n==== Test 1: Crypto Event ====")
            crypto_tag = Tag(id="1", label="crypto", slug="crypto")
            test_crypto_event = SimpleEvent(
                id=10001,
                ticker="BTC",
                slug="btc-price-test",
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
                tags=[crypto_tag]
            )
            
            test_crypto_market = Market(
                id=20002,
                question="Will BTC close above $120k on Dec 31, 2025?",
                description="YES if BTC/USD closing price is strictly above $120,000 at 2025-12-31 UTC.",
                endDate="2025-12-31T23:59:59Z",
                liquidity=12345.67,
                volume=987654.32,
                volume24hr=12345.0,
                active=True,
                closed=False
            )
            
            print(f"Event: {test_crypto_event.title}")
            print(f"Market: {test_crypto_market.question}")
            print(f"Tags: {[tag.label for tag in test_crypto_event.tags] if test_crypto_event.tags else 'None'}")
            print("Expected: Crypto system message + binance_tool")
            
            try:
                print("\n--- Calling process_new_market for crypto event ---")
                crypto_result = loop.process_new_market(test_crypto_market, test_crypto_event)
                
                print(f"\n--- Crypto Result ---")
                print(f"Status: Success")
                print(f"Yes Decision: should_trade={crypto_result.Yes.should_trade}, side={crypto_result.Yes.side}, amount={crypto_result.Yes.amount}")
                print(f"No Decision: should_trade={crypto_result.No.should_trade}, side={crypto_result.No.side}, amount={crypto_result.No.amount}")
                print(f"Next Process Time: {crypto_result.next_process_time}")
                print(f"Reason: {crypto_result.reason}")
                
            except Exception as e:
                print(f"Crypto test failed: {e}")
                import traceback
                traceback.print_exc()
            
            # 测试2: 非加密货币事件
            print("\n\n==== Test 2: Non-Crypto Event ====")
            politics_tag = Tag(id="2", label="politics", slug="politics")
            test_politics_event = SimpleEvent(
                id=10002,
                ticker="POL",
                slug="election-2024",
                title="Will the Democratic candidate win the 2024 US Presidential election?",
                description="A political event tracking the 2024 US Presidential election outcome.",
                end="2024-11-05T23:59:59Z",
                endDate="2024-11-05T23:59:59Z",
                active=True,
                closed=False,
                archived=False,
                restricted=False,
                new=True,
                featured=False,
                markets="20003",
                tags=[politics_tag]
            )
            
            test_politics_market = Market(
                id=20003,
                question="Will the Democratic candidate win the 2024 US Presidential election?",
                description="YES if the Democratic candidate receives more electoral votes than the Republican candidate.",
                endDate="2024-11-05T23:59:59Z",
                liquidity=50000.0,
                volume=2000000.0,
                volume24hr=50000.0,
                active=True,
                closed=False
            )
            
            print(f"Event: {test_politics_event.title}")
            print(f"Market: {test_politics_market.question}")
            print(f"Tags: {[tag.label for tag in test_politics_event.tags] if test_politics_event.tags else 'None'}")
            print("Expected: Political/Business system message, no binance_tool")
            
            try:
                print("\n--- Calling process_new_market for politics event ---")
                politics_result = loop.process_new_market(test_politics_market, test_politics_event)
                
                print(f"\n--- Politics Result ---")
                print(f"Status: Success")
                print(f"Yes Decision: should_trade={politics_result.Yes.should_trade}, side={politics_result.Yes.side}, amount={politics_result.Yes.amount}")
                print(f"No Decision: should_trade={politics_result.No.should_trade}, side={politics_result.No.side}, amount={politics_result.No.amount}")
                print(f"Next Process Time: {politics_result.next_process_time}")
                print(f"Reason: {politics_result.reason}")
                
            except Exception as e:
                print(f"Politics test failed: {e}")
                import traceback
                traceback.print_exc()
            
            print(f"\n==== Test completed at: {time.strftime('%Y-%m-%d %H:%M:%S')} ====")
            
    except Exception as e:
        print(f"Test execution failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 恢复标准输出
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        print("Test completed. Results saved to ./agents/loop/ret.txt")
