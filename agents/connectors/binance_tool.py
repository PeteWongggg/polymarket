import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

# 宏定义
GET_KLINES_FUNCTION_NAME = "get_klines"

try:
    # 优先使用新 SDK 名称
    from binance import Client
except Exception:
    # 兼容旧包名
    from binance.client import Client


class BinanceTool:
    def __init__(self, logger=None, config: Optional[dict] = None):
        self.logger = logger
        self.config = config or {}

        # 从配置读取白名单并标准化为小写列表
        white_list = (
            self.config.get("crypto", {}).get("symbol_white_list", ['BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','BNBUSDT'])
            if isinstance(self.config, dict)
            else []
        )
        self.symbol_list: List[str] = [s for s in white_list if isinstance(s, str)]
        self._symbol_list_lower: List[str] = [s.lower() for s in self.symbol_list]
        self.max_days = self.config.get("crypto", {}).get("max_days", 100) # 支持获取的最大长度限制
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        if not api_key or not api_secret:
            raise ValueError("BINANCE_API_KEY / BINANCE_API_SECRET 未设置")

        # 现货客户端
        self.client = Client(api_key=api_key, api_secret=api_secret)

    def get_klines(self, symbol: str, timeframe: str, days: int) -> Optional[List[Dict]]:
        # 参数校验
        if not symbol or not isinstance(symbol, str):
            if self.logger:
                self.logger.error(f"无效 symbol: {symbol}")
            return None
        if not timeframe or not isinstance(timeframe, str):
            if self.logger:
                self.logger.error(f"无效 timeframe: {timeframe}")
            return None
        if not isinstance(days, int) or days <= 0:
            if self.logger:
                self.logger.error(f"无效天数: {days}")
            return None
        
        days = min(days, self.max_days) # 限制获取数据长度

        # 处理白名单匹配（大小写不敏感）
        symbol_lower = symbol.lower()
        mapped_symbol: Optional[str] = None
        if self._symbol_list_lower:
            try:
                idx = self._symbol_list_lower.index(symbol_lower)
                mapped_symbol = self.symbol_list[idx]
            except ValueError:
                if self.logger:
                    self.logger.warning(
                        f"symbol 不在白名单中: {symbol}. 白名单: {self.symbol_list}"
                    )
                return None
        else:
            # 无白名单配置则直接使用传入的 symbol
            mapped_symbol = symbol

        # 计算开始时间（UTC）
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        # binance SDK 支持 start_str 参数，如 "1 day ago UTC"，也可传毫秒
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        try:
            raw = self.client.get_klines(
                symbol=mapped_symbol.upper(),
                interval=timeframe,
                startTime=start_ms,
                endTime=end_ms,
            )
        except Exception as e:
            if self.logger:
                self.logger.error(f"获取K线失败: {e} | symbol={symbol}, timeframe={timeframe}, days={days}")
            return None

        # Binance K线返回结构：[open_time, open, high, low, close, volume, close_time, ...]
        result: List[Dict] = []
        for row in raw or []:
            try:
                open_time_ms = row[0]
                item = {
                    "date": datetime.utcfromtimestamp(open_time_ms / 1000).strftime("%Y-%m-%d %H:%M:%S"),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                }
                result.append(item)
            except Exception:
                continue

        return result

    def _get_name(self) -> str:
        """
        Returns the function name for OpenAI tool definition
        
        Returns:
            Function name string
        """
        return GET_KLINES_FUNCTION_NAME

    def _get_description(self) -> dict:
        """
        Returns OpenAI tool definition for get_klines function
        
        Returns:
            OpenAI format tool definition dictionary
        """
        return {
            "type": "function",
            "function": {
                "name": self._get_name(),
                "description": "Get Binance exchange K-line data with support for multiple timeframes and trading pairs",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": f"Trading pair symbol. Only supports the following symbols: {', '.join(self.symbol_list)}",
                            "enum": self.symbol_list
                        },
                        "timeframe": {
                            "type": "string",
                            "description": "K-line timeframe interval",
                            "enum": ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
                        },
                        "days": {
                            "type": "integer",
                            "description": f"Number of days to retrieve data, maximum {self.max_days} days",
                            "minimum": 1,
                            "maximum": self.max_days
                        }
                    },
                    "required": ["symbol", "timeframe", "days"]
                }
            }
        }


if __name__ == "__main__":
    b = BinanceTool()
    data = b.get_klines("BTCUSDT", "1h", 2)
    if data:
        for i, r in enumerate(data[:5]):
            print(i, r)

