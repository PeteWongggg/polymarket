from typing import List
from datetime import datetime
from agents.utils.objects import SimpleEvent, Market, MarketTrades


class Prompter:
    def __init__(self):
        pass
    
    def generate_common_system_message(self) -> str:
        return f"""
        You are a trader.

        Polymarket is a binary prediction market where each market resolves to two outcomes: "Yes" and "No".
        Contracts trade between $0.01 and $0.99 and map directly to implied probabilities
        (e.g., $0.63 ≈ 63%). At resolution, the winning outcome pays $1 and the losing outcome
        pays $0. Your objective is to estimate true event probabilities better than the current
        market price and to execute profitable, risk-aware trades.

        Trading mechanics to keep in mind:
        - Order book: place limit orders at a chosen price and size; partial fills are possible.
        - Fees/spread/slippage: account for transaction fees, bid–ask spreads, and impact.
        - Liquidity: thin books move on small size; prefer limit orders near your fair value.
        - Risk: cap exposure per market; avoid martingales and concentration risk.

        Your task in this session:
        - Consume the provided market and event context (question, resolution criteria, end time,
          current prices, order book, historical trades, and any supplied notes).
        - Use the provided tools to gather timely, verifiable information relevant to resolution
          (e.g., news, web search, data/exchange connectors). Prefer primary sources.
        - Produce a probabilistic forecast (your fair probability for "Yes" and "No").
        - Compare your fair to the market’s price and decide to Buy Yes, Buy No (i.e., sell Yes), or Skip.
        - Return decisions exclusively via the execute_trades tool. Regardless of trading or skipping,
          always provide a sensible next_process_time for when to reprocess this market.

        Constraints:
        - Only use information available in the provided context or fetched via the allowed tools; do not invent facts.
        - Cite which tools/sources informed your view; ignore irrelevant signals.
        - If evidence is insufficient or uncertainty is high, prefer Skip.
        """
    
    def generate_crypto_system_message(self, symbol_white_list: list) -> str:
        return f"""
        Now, You are analyzing a crypto-related Polymarket market. In addition to the tools for
        gathering real-time information (batch_query, extract, news), you are also provided a
        Binance-SDK-based tool: get_klines to fetch cryptocurrency K-lines (candlesticks) for supported symbols.

        IMPORTANT symbol policy:
        - You are ONLY allowed to process markets for the following cryptocurrencies:
          {', '.join(symbol_white_list)}
        - If the market symbol is not in this whitelist, you MUST refuse to trade and skip the market.

        Trading and decision guidance:
        - Follow the same binary prediction principles as Polymarket (Yes/No, price ≈ probability).
        - Use available tools to collect timely, verifiable evidence.
        - If symbol is not whitelisted, set should_trade=False and provide a sensible next_process_time.
        - Cryptocurrency trends are typically influenced by global political, economic, and financial factors including US government policies, Federal Reserve decisions, US stock market performance, employment indicators, inflation data, regulatory announcements, institutional adoption, and geopolitical events. It is recommended to use information gathering tools to collect the latest policy updates, news reports, and market analysis to inform trading decisions.

        Current time: {datetime.now().isoformat()}
        """
    
    def generate_politic_business_system_message(self) -> str:
        return f"""
        Now, You are analyzing a political/business-related Polymarket market. You have access to
        the following tools for gathering real-time information:
        - batch_query: for web search and information gathering
        - extract: for extracting content from specific URLs
        - news: for accessing current news articles and updates

        Trading and decision guidance:
        - Follow the same binary prediction principles as Polymarket (Yes/No, price ≈ probability).
        - Use available tools to collect timely, verifiable evidence from multiple sources.
        - Focus on authoritative sources, official statements, and credible news outlets.
        - Consider political developments, economic indicators, and market sentiment.
        - Always provide a sensible next_process_time for market reprocessing.

        Current time: {datetime.now().isoformat()}
        """
    
    def generate_event_message(self, event: SimpleEvent) -> str:
        # 由于本模块不直接依赖pydantic对象的导入，这里仅假设传入的是具有相同字段的对象
        title = getattr(event, 'title', '') or ''
        description = getattr(event, 'description', '') or ''
        tags = getattr(event, 'tags', []) or []
        created_at = getattr(event, 'createdAt', '') or ''
        end_date = getattr(event, 'endDate', '') or getattr(event, 'end', '') or ''
        volume = getattr(event, 'volume', None)
        volume24hr = getattr(event, 'volume24hr', None)
        tags_str = ', '.join([getattr(t, 'label', '') or getattr(t, 'slug', '') or str(t) for t in tags]) if tags else ''
        volume_str = f"{volume}" if volume is not None else "N/A"
        volume24_str = f"{volume24hr}" if volume24hr is not None else "N/A"

        return f"""
        <Information>

        Here is the market-related information: <Linked Event>

        - Title: {title}
        - Description: {description}
        - Tags: {tags_str}
        - Created At: {created_at}
        - End Date: {end_date}
        - Total Volume: {volume_str}
        - 24h Volume: {volume24_str}
        """
    
    def generate_market_message(self, market: Market) -> str:
        # 获取市场相关信息
        question = getattr(market, 'question', '') or ''
        description = getattr(market, 'description', '') or ''
        end_date = getattr(market, 'endDate', '') or ''
        liquidity = getattr(market, 'liquidity', None)
        volume = getattr(market, 'volume', None)
        volume24hr = getattr(market, 'volume24hr', None)
        
        # 格式化数值
        liquidity_str = f"{liquidity}" if liquidity is not None else "N/A"
        volume_str = f"{volume}" if volume is not None else "N/A"
        volume24_str = f"{volume24hr}" if volume24hr is not None else "N/A"

        return f"""
        Here is the market information: <Market Details>

        - Question: {question}
        - Description: {description}
        - End Date: {end_date}
        - Liquidity: {liquidity_str}
        - Total Volume: {volume_str}
        - 24h Volume: {volume24_str}
        """
    
    def generate_order_book_message(self, yes_order_book: dict, no_order_book: dict) -> str:
        # 期望结构：{"bids": [{"price": "0.10", "size": "100"}, ...], "asks": [...], "tick_size": "0.01", "min_order_size": "0.001"}
        
        def format_order_book(order_book: dict, outcome_name: str) -> str:
            if not isinstance(order_book, dict):
                return f"        - {outcome_name} Order Book: N/A"
            
            bids = order_book.get("bids", [])
            asks = order_book.get("asks", [])
            tick_size = order_book.get("tick_size")
            min_order_size = order_book.get("min_order_size")

            def format_levels(levels: list, top_n: int = 5) -> str:
                if not isinstance(levels, list) or len(levels) == 0:
                    return "            - N/A"
                lines = []
                for lvl in levels[:top_n]:
                    price = lvl.get("price", "") if isinstance(lvl, dict) else ""
                    size = lvl.get("size", "") if isinstance(lvl, dict) else ""
                    lines.append(f"            - price: {price}, size: {size}")
                return "\n".join(lines)

            bids_block = format_levels(bids, 10)
            asks_block = format_levels(asks, 10)
            tick_size_str = f"{tick_size}" if tick_size is not None else "N/A"
            min_order_size_str = f"{min_order_size}" if min_order_size is not None else "N/A"

            return f"""        - {outcome_name} Order Book:
          - Tick Size: {tick_size_str}
          - Min Order Size: {min_order_size_str}
          - Top Bids (price, size):
{bids_block}
          - Top Asks (price, size):
{asks_block}"""

        yes_book_str = format_order_book(yes_order_book, "Yes")
        no_book_str = format_order_book(no_order_book, "No")

        return f"""
        Here is the market order book snapshot: <Order Book>

{yes_book_str}

{no_book_str}

        </Information>
        """

    def generate_exsisting_trades_message(self, market_trades: MarketTrades) -> str:
        # 汇总函数
        def summarize_outcome(outcome_data) -> dict:
            trades = getattr(outcome_data, 'Trades', []) or []
            balance = getattr(outcome_data, 'balance', 0) or 0
            buy_count = 0
            sell_count = 0
            buy_shares = 0.0
            sell_shares = 0.0
            buy_amount = 0.0
            sell_amount = 0.0

            for tr in trades:
                side = (getattr(tr, 'side', '') or '').upper()
                shares_str = getattr(tr, 'shares', '0') or '0'
                amount_str = getattr(tr, 'amount', '0') or '0'
                try:
                    shares_val = float(shares_str)
                except Exception:
                    shares_val = 0.0
                try:
                    amount_val = float(amount_str)
                except Exception:
                    amount_val = 0.0

                if side == 'BUY':
                    buy_count += 1
                    buy_shares += shares_val
                    buy_amount += amount_val
                elif side == 'SELL':
                    sell_count += 1
                    sell_shares += shares_val
                    sell_amount += amount_val

            return {
                'balance': balance,
                'buy_count': buy_count,
                'sell_count': sell_count,
                'buy_shares': buy_shares,
                'sell_shares': sell_shares,
                'buy_amount': buy_amount,
                'sell_amount': sell_amount,
            }

        # 市场与事件信息
        mi = market_trades.market_info
        event_title = getattr(mi, 'event_title', '') or ''
        event_description = getattr(mi, 'event_description', '') or ''
        event_tags = getattr(mi, 'event_tags', []) or []
        event_tags_str = ', '.join([str(t) for t in event_tags]) if event_tags else ''
        market_question = getattr(mi, 'market_question', '') or ''
        market_description = getattr(mi, 'market_description', '') or ''
        market_end_date = getattr(mi, 'market_end_date', '') or ''

        # 汇总 Yes / No
        yes_summary = summarize_outcome(market_trades.Yes)
        no_summary = summarize_outcome(market_trades.No)

        return f"""
        Here are the existing trades and related context: <4. Existing Trades Snapshot>

        Here is the market-related information: <Linked Event>
        - Title: {event_title}
        - Description: {event_description}
        - Tags: {event_tags_str}

        Here is the market information: <Market Details>
        - Question: {market_question}
        - Description: {market_description}
        - End Date: {market_end_date}

        Here is the positions and trades: <Positions & Trades>
        - Yes:
          - Balance (shares): {yes_summary['balance']}
          - Buys: count={yes_summary['buy_count']}, shares={yes_summary['buy_shares']}, amount={yes_summary['buy_amount']}
          - Sells: count={yes_summary['sell_count']}, shares={yes_summary['sell_shares']}, amount={yes_summary['sell_amount']}
        - No:
          - Balance (shares): {no_summary['balance']}
          - Buys: count={no_summary['buy_count']}, shares={no_summary['buy_shares']}, amount={no_summary['buy_amount']}
          - Sells: count={no_summary['sell_count']}, shares={no_summary['sell_shares']}, amount={no_summary['sell_amount']}
        """
    
    def generate_notice_message(self, config: dict) -> str:
        loop_notice = self.generate_loop_notice_message(config)
        tool_notice = self.generate_tool_notice_message(config)
        
        return f"""
        <notice>
        {loop_notice}
        
        {tool_notice}
        </notice>
        """

    def generate_loop_notice_message(self, config: dict) -> str:
        max_turn = config.get("agent", {}).get("max_turn", 8)
        
        return f"""
        Loop Execution Guidelines:
        
        0. Tool Call Required Each Turn: In every turn, you MUST select and call at least one tool from the available tool list.
        
        1. Tool Usage Priority: Prioritize calling available tools to gather relevant information for decision-making. Use batch_query, extract, news, and get_klines (for crypto markets) to collect comprehensive data before making trading decisions.
        
        2. Maximum Turn Limit: When reaching the maximum turn limit ({max_turn}), you MUST call the execute_trades tool to output your final decision. Do not exceed this limit.
        
        3. Professional Trading Approach: Based on your prediction of event outcomes and expected returns, maintain a cautious and professional trading attitude. Consider risk management, market volatility, and your confidence level in predictions.
        """
    
    def generate_tool_notice_message(self, config: dict) -> str:
        min_ratio = config.get("next_process_time", {}).get("min_ratio", 0.33)
        max_count = config.get("trade", {}).get("Buy", {}).get("max_count", 3)
        
        return f"""
        Tool Usage and Decision Requirements:
        
        1. Mandatory Tool Call: Regardless of your final decision to trade or not, you MUST call the execute_trades tool to output your decision. To refuse trading, set should_trade to False.
        
        2. Simultaneous Trading: Based on your prediction of market future trends, order book depth, and historical trading volume, you can choose to buy or sell both 'Yes' and 'No' outcomes simultaneously.
        
        3. Next Process Time: When outputting your decision, consider the time interval between current time and market close time. Provide next processing time in UTC ISO 8601 without milliseconds, strictly as YYYY-MM-DDTHH:MM:SSZ (e.g., 2025-09-12T00:00:00Z). Prefer an interval greater than {min_ratio} of the remaining time until market close; if no further processing is needed, set a time after market close.
        
        4. Reason Length: Output your trading reason in less than 200 words.
        
        5. Buy Count Limit: The maximum buy count for the same outcome in one market cannot exceed {max_count} times. If the limit is reached, you must refuse to trade.
        
        6. Tool Compliance: All tool calls must strictly follow the relevant instructions and constraints specified in each tool's description.
        """
    
    def generate_last_turn_notice_message(self) -> str:
        return f"""
        <Final Turn Notice>

        You have reached the maximum turn. Regardless of whether you decide to trade or skip,
        you MUST call the execute_trades tool to output your decision.
        
        </Final Turn Notice>
        """
    
    def generate_binance_tool_response_message(self, klines: list) -> str:
        # 期望结构：[{"date": str, "open": float, "high": float, "low": float, "close": float, "volume": float}, ...]
        if not isinstance(klines, list) or len(klines) == 0:
            return f"""
        <tool_response>
        Binance K-lines summary:
        - Samples: 0
        - Window: N/A
        - Range: low=N/A, high=N/A
        - First open: N/A, Last close: N/A
        - Avg volume: N/A
        - Latest candle: N/A
        - Recent candles: N/A
        </tool_response>
        """

        n = len(klines)
        first = klines[0] if n > 0 else {}
        last = klines[-1] if n > 0 else {}

        def safe_get(item: dict, key: str, default=None):
            try:
                return item.get(key, default)
            except Exception:
                return default

        start_date = safe_get(first, "date", "") or ""
        end_date = safe_get(last, "date", "") or ""

        try:
            lows = [float(safe_get(x, "low", 0.0) or 0.0) for x in klines]
            highs = [float(safe_get(x, "high", 0.0) or 0.0) for x in klines]
            volumes = [float(safe_get(x, "volume", 0.0) or 0.0) for x in klines]
        except Exception:
            lows, highs, volumes = [], [], []

        low_min = min(lows) if lows else None
        high_max = max(highs) if highs else None
        avg_volume = (sum(volumes) / n) if volumes and n > 0 else None

        first_open = safe_get(first, "open", None)
        last_close = safe_get(last, "close", None)

        latest = {
            "date": safe_get(last, "date", "N/A"),
            "open": safe_get(last, "open", "N/A"),
            "high": safe_get(last, "high", "N/A"),
            "low": safe_get(last, "low", "N/A"),
            "close": safe_get(last, "close", "N/A"),
            "volume": safe_get(last, "volume", "N/A"),
        }

        low_str = f"{low_min}" if low_min is not None else "N/A"
        high_str = f"{high_max}" if high_max is not None else "N/A"
        first_open_str = f"{first_open}" if first_open is not None else "N/A"
        last_close_str = f"{last_close}" if last_close is not None else "N/A"
        avg_vol_str = f"{avg_volume}" if avg_volume is not None else "N/A"

        # 最近14根（或更少）K线明细
        recent = klines[-14:] if n >= 14 else klines
        def format_candle(c: dict) -> str:
            return (
                f"          - date={safe_get(c, 'date', 'N/A')}, open={safe_get(c, 'open', 'N/A')}, "
                f"high={safe_get(c, 'high', 'N/A')}, low={safe_get(c, 'low', 'N/A')}, "
                f"close={safe_get(c, 'close', 'N/A')}, volume={safe_get(c, 'volume', 'N/A')}"
            )
        recent_block = "\n".join([format_candle(c) for c in recent]) if recent else "          - N/A"

        return f"""
        <tool_response>
        Binance K-lines summary:
        - Samples: {n}
        - Window: {start_date} → {end_date}
        - Range: low={low_str}, high={high_str}
        - First open: {first_open_str}, Last close: {last_close_str}
        - Avg volume: {avg_vol_str}
        - Latest candle: date={latest['date']}, open={latest['open']}, high={latest['high']}, low={latest['low']}, close={latest['close']}, volume={latest['volume']}
        - Recent candles (up to 14):
{recent_block}
        </tool_response>
        """
    
    def generate_extract_tool_response_message(self, extract_results: list) -> str:
        # 期望结构：[{"url": str, "raw_content": str}, ...]
        if not isinstance(extract_results, list) or len(extract_results) == 0:
            return f"""
        <tool_response>
        Extract Results:
          - N/A
        </tool_response>
        """

        def item_block(idx: int, item: dict) -> str:
            if not isinstance(item, dict):
                return f"          - item#{idx+1}: value={item}"
            url = item.get("url", "") or ""
            content = item.get("raw_content", "") or ""
            return (
                f"          - item#{idx+1}:\n"
                f"            url: {url}\n"
                f"            raw_content: {content}"
            )

        items_block = "\n".join([item_block(i, it) for i, it in enumerate(extract_results)]) if extract_results else "          - N/A"

        return f"""
        <tool_response>
        Extract Results:
{items_block}
        </tool_response>
        """
    
    def generate_search_tool_response_message(self, search_results: dict) -> str:
        # 期望结构示例（见 agents/connectors/search_ret.txt）：
        # {
        #   'Query A': [ { 'url': '...', 'content': '...' }, ...],
        #   'Query B': [ ... ]
        # }
        if not isinstance(search_results, dict) or not search_results:
            return f"""
        <tool_response>
        Search Results:
          - N/A
        </tool_response>
        """

        blocks = []
        for query, items in search_results.items():
            if not isinstance(items, list) or len(items) == 0:
                blocks.append(
                    f"        Query: {query}\n          - N/A"
                )
                continue

            lines = [f"        Query: {query}"]
            for idx, it in enumerate(items):
                if not isinstance(it, dict):
                    lines.append(f"          - item#{idx+1}: value={it}")
                    continue
                url = it.get('url', '') or ''
                content = it.get('content', '') or ''
                lines.append(
                    f"          - item#{idx+1}:\n"
                    f"            url: {url}\n"
                    f"            content: {content}"
                )
            blocks.append("\n".join(lines))

        body = "\n".join(blocks) if blocks else "          - N/A"

        return f"""
        <tool_response>
        Search Results:
{body}
        </tool_response>
        """
    
    def generate_news_tool_response_message(self, news_result: dict) -> str:
        # 期望结构（NewsAPI）：{"status": "ok", "totalResults": int, "articles": [ {"source": {"id":..., "name":...}, "author":..., "title":..., "description":..., "url":..., "urlToImage":..., "publishedAt":..., "content":...}, ... ]}
        if not isinstance(news_result, dict):
            return f"""
        <tool_response>
        Articles:
          - N/A
        </tool_response>
        """

        articles = news_result.get("articles", []) or []

        def article_block(idx: int, a: dict) -> str:
            source_name = ""
            try:
                source_name = (a.get("source", {}) or {}).get("name", "")
            except Exception:
                source_name = ""
            author = a.get("author", "") or ""
            title = a.get("title", "") or ""
            description = a.get("description", "") or ""
            url = a.get("url", "") or ""
            url_to_image = a.get("urlToImage", "") or ""
            published = a.get("publishedAt", "") or ""
            content = a.get("content", "") or ""
            return (
                f"          - article#{idx+1}:\n"
                f"            source: {source_name}\n"
                f"            author: {author}\n"
                f"            title: {title}\n"
                f"            description: {description}\n"
                f"            url: {url}\n"
                f"            urlToImage: {url_to_image}\n"
                f"            publishedAt: {published}\n"
                f"            content: {content}"
            )

        items_block = "\n".join([article_block(i, a) for i, a in enumerate(articles)]) if articles else "          - N/A"

        return f"""
        <tool_response>
        Articles:
{items_block}
        </tool_response>
        """

    
    


    
