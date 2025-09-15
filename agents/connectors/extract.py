import os
import json
import requests
import re

from typing import List, Optional, Union
from dotenv import load_dotenv

load_dotenv()

# 宏定义
EXTRACT_FUNCTION_NAME = "extract"

class Extract:
    def __init__(self, logger=None, config: Optional[dict] = None):
        self.logger = logger
        self.config = {
            "depth": config.get("extract", {}).get("depth", "basic"),
            "max_extract_url_num": config.get("extract", {}).get("max_extract_url_num", 5),
            "max_text_length": config.get("extract", {}).get("max_text_length", 5000)
        }

        self.base_url = "https://api.tavily.com/extract"
        self.api_key = os.getenv("TAVILY_API_KEY")

        if not self.api_key:
            raise ValueError("TAVILY_API_KEY 环境变量未设置。")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def extract(self, urls: List[str]):
        # 参数校验
        if not isinstance(urls, list) or not all(isinstance(u, str) and u.strip() for u in urls):
            if self.logger:
                self.logger.error(f"urls 必须为非空字符串列表: {urls}")
            return None

        # 限制URL数量
        max_urls = self.config.get("max_extract_url_num", 5)
        if len(urls) > max_urls:
            if self.logger:
                self.logger.warning(f"URL数量超过限制，从{len(urls)}个减少到{max_urls}个")
            urls = urls[:max_urls]

        depth = self.config.get("depth", "basic")
       
        payload = {
            "urls": urls,
            "extract_depth": depth,
        }

        try:
            resp = self.session.post(self.base_url, data=json.dumps(payload), timeout=50)
            resp.raise_for_status()

            data = resp.json()

            # 标准化返回：确保为 list[dict]
            results = None
            if isinstance(data, dict) and "results" in data and isinstance(data["results"], list):
                results = data["results"]
            elif isinstance(data, list):
                results = data
            else:
                results = [data]
            
            # 截断内容长度
            return self._truncate_content(results)
        except requests.HTTPError as http_err:
            if self.logger:
                self.logger.error(f"Tavily extract HTTP 错误: {http_err} | payload={payload}")
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Tavily extract 失败: {e} | payload={payload}")
            return None

    def _count_words(self, text: str) -> int:
        """
        快速计算文本的单词数量
        
        Args:
            text: 输入文本
            
        Returns:
            单词数量
        """
        if not text or not isinstance(text, str):
            return 0
        
        # 使用正则表达式分割单词，支持多种语言
        # \b\w+\b 匹配单词边界，\w+ 匹配一个或多个字母、数字、下划线
        words = re.findall(r'\b\w+\b', text)
        return len(words)

    def _truncate_content(self, results: List[dict]) -> List[dict]:
        """
        截断raw_content的长度，确保不超过配置的最大单词数量
        
        Args:
            results: 包含url和raw_content字段的结果列表
            
        Returns:
            截断后的结果列表
        """
        if not results or not isinstance(results, list):
            return results
        
        max_words = self.config.get("max_text_length", 5000)
        truncated_results = []
        
        for item in results:
            if not isinstance(item, dict):
                truncated_results.append(item)
                continue
                
            # 复制原始项目
            truncated_item = item.copy()
            
            # 检查并截断raw_content
            if "raw_content" in truncated_item and isinstance(truncated_item["raw_content"], str):
                content = truncated_item["raw_content"]
                word_count = self._count_words(content)
                
                if word_count > max_words:
                    # 按单词截断
                    words = re.findall(r'\b\w+\b', content)
                    truncated_words = words[:max_words]
                    
                    # 重新构建文本，保持原始格式
                    truncated_text = content
                    for i, word in enumerate(truncated_words):
                        if i == 0:
                            # 找到第一个单词的位置
                            truncated_text = content[content.find(word):]
                        else:
                            # 找到当前单词的位置
                            start_pos = truncated_text.find(word)
                            if start_pos != -1:
                                truncated_text = truncated_text[:start_pos + len(word)]
                    
                    truncated_item["raw_content"] = truncated_text
                    
                    if self.logger:
                        self.logger.debug(f"截断URL {item.get('url', 'unknown')} 的单词数量: {word_count} -> {max_words}")
            
            truncated_results.append(truncated_item)
        
        return truncated_results

    def _get_name(self) -> str:
        """
        Returns the function name for OpenAI tool definition
        
        Returns:
            Function name string
        """
        return EXTRACT_FUNCTION_NAME

    def _get_description(self) -> dict:
        """
        Returns OpenAI tool definition for extract function
        
        Returns:
            OpenAI format tool definition dictionary
        """
        max_urls = self.config.get("max_extract_url_num", 5)
        return {
            "type": "function",
            "function": {
                "name": self._get_name(),
                "description": f"Extract content from web URLs. Maximum {max_urls} URLs allowed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "urls": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": f"List of URLs to extract content from. Maximum {max_urls} URLs allowed.",
                            "maxItems": max_urls
                        }
                    },
                    "required": ["urls"]
                }
            }
        }


if __name__ == "__main__":
    sample_urls = [
        "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "https://en.wikipedia.org/wiki/Machine_learning",
    ]
    config = {"extract": {"depth": "basic"}}
    client = Extract(config=config)
    results = client.extract(sample_urls)
    #print(type(results), len(results) if results else 0)
    if results:
        for item in results:
            print(item.keys())
            '''
            {
                'url': '',
                'raw_content': '',
            }
            '''
            
        #for i, r in enumerate(results[:2]):
            # 仅打印关键字段，避免控制台太长
            #print(i, {k: r.get(k) for k in list(r.keys())[:4]})

