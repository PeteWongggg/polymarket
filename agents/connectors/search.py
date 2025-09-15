import os, json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

# 宏定义
BATCH_QUERY_FUNCTION_NAME = "batch_query"

class Search:
    def __init__(self, logger=None, config=None):
        self.logger = logger
        self.config = {
            "search_length": config.get("search", {}).get("length", 10),
            "search_type": config.get("search", {}).get("type", "basic"),
            "workers": config.get("search", {}).get("workers", 5),
            "max_search_queries": config.get("search", {}).get("max_search_queries", 5),
        }
        self.tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

    def search(self, query: str):
        try:
            raw = self.tavily_client.get_search_context(
                query=query,
                max_results=self.config.get("search_length", 10),
                search_depth=self.config.get("search_type", "basic"),
            )
            # 可能返回多层字符串形式的 JSON：逐层解析直到不是字符串
            data = raw
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="ignore")
            decode_guard = 0
            while isinstance(data, str) and decode_guard < 3:
                try:
                    data = json.loads(data)
                except Exception:
                    break
                finally:
                    decode_guard += 1

            # 统一标准化为 list[dict]
            if isinstance(data, list):
                # 有些实现会返回列表里的字符串，需要逐个 json 解析
                normalized = []
                for item in data:
                    if isinstance(item, str):
                        try:
                            normalized.append(json.loads(item))
                        except Exception:
                            # 非 JSON 字符串则包装为字典
                            normalized.append({"value": item})
                    elif isinstance(item, dict):
                        normalized.append(item)
                    else:
                        normalized.append({"value": item})
                return normalized

            if isinstance(data, dict):
                # 单个对象，包装成列表
                return [data]

            # 其他类型，包装为字典列表
            return [{"value": data}]
        except Exception as e:
            self.logger.error(f"搜索失败: {e}, query: {query}.")
            return None
    
    def batch_query(self, queries: List[str]) -> Dict[str, Any]:
        """
        并发执行多个搜索查询
        
        Args:
            queries: 查询字符串列表
            
        Returns:
            Dict[str, Any]: 键为查询字符串，值为对应的搜索结果
        """
        results = {}
        max_queries = self.config.get("max_search_queries", 5)
        workers = self.config.get("workers", 5)
        
        # 限制查询数量
        if len(queries) > max_queries:
            if self.logger:
                self.logger.warning(f"查询数量超过限制，从{len(queries)}个减少到{max_queries}个")
            queries = queries[:max_queries]
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 提交所有任务
            future_to_query = {
                executor.submit(self.search, query): query 
                for query in queries
            }
            
            # 收集结果
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    result = future.result()
                    results[query] = result
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"批量搜索失败: {e}, query: {query}")
                    results[query] = None
        
        return results

    def _get_name(self) -> str:
        """
        Returns the function name for OpenAI tool definition
        
        Returns:
            Function name string
        """
        return BATCH_QUERY_FUNCTION_NAME

    def _get_description(self) -> dict:
        """
        Returns OpenAI tool definition for batch_query function
        
        Returns:
            OpenAI format tool definition dictionary
        """
        max_queries = self.config.get("max_search_queries", 5)
        return {
            "type": "function",
            "function": {
                "name": self._get_name(),
                "description": f"Execute multiple search queries concurrently. Maximum {max_queries} queries allowed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": f"List of search query strings. Maximum {max_queries} queries allowed.",
                            "maxItems": max_queries
                        }
                    },
                    "required": ["queries"]
                }
            }
        }


if __name__ == "__main__":
    config = {
        "search": {
            "length": 10,
            "type": "basic",
            "workers": 3
        },
        "extract": {
            "type": "basic"
        }
    }
    search = Search(config=config)
    
    # 测试批量查询
    queries = [
        "Will Biden drop out of the race?",
        "Bitcoin price prediction 2024",
        "AI technology trends"
    ]
    
    results = search.batch_query(queries)
    print(results)
    '''
    for query, result in results.items():
        print(f"查询: {query}")
        if result:
            print(f"结果数量: {len(result)}")
            for item in result[:2]:  # 只显示前2个结果
                print(f"  {item}")
        else:
            print("  搜索失败")
        print("-" * 50)
    '''