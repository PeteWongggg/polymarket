from datetime import datetime
import os
from dotenv import load_dotenv

from newsapi import NewsApiClient
from typing import Optional

# 加载环境变量
load_dotenv()

# 宏定义
GET_REGION_TOP_ARTICLES_FUNCTION_NAME = "get_region_top_articles_from_category"

class Source():
    id: Optional[str]
    name: Optional[str]

class Article():
    source: Optional[Source]
    author: Optional[str]
    title: Optional[str]
    description: Optional[str]
    url: Optional[str]
    urlToImage: Optional[str]
    publishedAt: Optional[str]
    content: Optional[str]

class News:
    def __init__(self, logger=None, config: dict = None) -> None:
        cfg = config or {}
        news_cfg = cfg.get("news", {}) if isinstance(cfg, dict) else {}
        categories_cfg = news_cfg.get("categories") or [
            "business",
            "entertainment",
            "general",
            "health",
            "science",
            "sports",
            "technology",
        ]

        self.configs = {
            "language": "en",
            "country": "us", # just for default
            "top_headlines": "https://newsapi.org/v2/top-headlines?country=us&apiKey=",
            "base_url": "https://newsapi.org/v2/",
            "page_size": int(news_cfg.get("page_size", 10)),
        }

        # 统一为小写集合
        self.categories = {str(c).lower() for c in categories_cfg if isinstance(c, str)}

        # 支持的 ISO 3166-1 国家代码（根据 NewsAPI 文档）
        self.supported_countries = {
            "ae", "ar", "at", "au", "be", "bg", "br", "ca", "ch", "cn", "co", "cu", "cz", "de", "eg", "fr", 
            "gb", "gr", "hk", "hu", "id", "ie", "il", "in", "it", "jp", "kr", "lt", "lv", "ma", "mx", "my", 
            "ng", "nl", "no", "nz", "ph", "pl", "pt", "ro", "rs", "ru", "sa", "se", "sg", "si", "sk", "th", 
            "tr", "tw", "ua", "us", "ve", "za"
        }
        self.logger = logger
        
        api_key = os.getenv("NEWSAPI_API_KEY")
        if not api_key:
            raise ValueError("NEWSAPI_API_KEY 环境变量未设置。请设置您的 NewsAPI 密钥。")
        self.API = NewsApiClient(api_key)

    def get_articles_for_cli_keywords(self, keywords) -> "list[Article]":
        query_words = keywords.split(",")
        all_articles = self.get_articles_for_options(query_words)
        article_objects: list[Article] = []
        for _, articles in all_articles.items():
            for article in articles:
                article_objects.append(Article(**article))
        return article_objects

    def get_region_top_articles_from_category(self, country: str, category: str) -> "list[Article]":
        # 参数校验
        if not country or not isinstance(country, str):
            if self.logger:
                self.logger.warning(f"无效的 country 参数: {country}")
            return None
            
        if not category or not isinstance(category, str):
            if self.logger:
                self.logger.warning(f"无效的 category 参数: {category}")
            return None
        
        # 检查 country 是否为有效的 ISO 3166-1 代码
        country_lower = country.lower()
        if country_lower not in self.supported_countries:
            if self.logger:
                self.logger.warning(f"不支持的国家代码: {country}。支持的国家代码: {sorted(self.supported_countries)}")
            return None
        
        # 检查 category 是否为有效类别
        category_lower = category.lower()
        if category_lower not in self.categories:
            if self.logger:
                self.logger.warning(f"不支持的类别: {category}。支持的类别: {sorted(self.categories)}")
            return None
        
        return self.API.get_top_headlines(
            language="en", country=country_lower, category=category_lower, page_size=self.configs["page_size"]
        )

    def get_articles_for_options(
        self,
        market_options: "list[str]",
        date_start: datetime = None,
        date_end: datetime = None,
    ) -> "list[Article]":

        all_articles = {}
        # Default to top articles if no start and end dates are given for search
        if not date_start and not date_end:
            for option in market_options:
                response_dict = self.API.get_top_headlines(
                    q=option.strip(),
                    language=self.configs["language"],
                    country=self.configs["country"],
                )
                articles = response_dict["articles"]
                all_articles[option] = articles
        else:
            for option in market_options:
                response_dict = self.API.get_everything(
                    q=option.strip(),
                    language=self.configs["language"],
                    country=self.configs["country"],
                    from_param=date_start,
                    to=date_end,
                )
                articles = response_dict["articles"]
                all_articles[option] = articles

        return all_articles

    def get_category(self, market_object: dict) -> str:
        news_category = "general"
        market_category = market_object["category"]
        if market_category in self.categories:
            news_category = market_category
        return news_category

    def _get_name(self) -> str:
        """
        Returns the function name for OpenAI tool definition
        
        Returns:
            Function name string
        """
        return GET_REGION_TOP_ARTICLES_FUNCTION_NAME

    def _get_description(self) -> dict:
        """
        Returns OpenAI tool definition for get_region_top_articles_from_category function
        
        Returns:
            OpenAI format tool definition dictionary
        """
        return {
            "type": "function",
            "function": {
                "name": self._get_name(),
                "description": "Get top news articles from a specific country and category using NewsAPI",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "country": {
                            "type": "string",
                            "description": f"Country code (ISO 3166-1). Supported countries: {', '.join(sorted(self.supported_countries))}",
                            "enum": sorted(self.supported_countries)
                        },
                        "category": {
                            "type": "string",
                            "description": f"News category. Supported categories: {', '.join(sorted(self.categories))}",
                            "enum": sorted(self.categories)
                        }
                    },
                    "required": ["country", "category"]
                }
            }
        }

if __name__ == "__main__":
    # 构造本地配置
    config = {
        "news": {
            "page_size": 10,
            "categories": [
                "business",
                "entertainment",
                "general",
                "health",
                "science",
                "sports",
                "technology",
            ],
        }
    }

    news = News(logger=None, config=config)
    articles = news.get_region_top_articles_from_category("us", "business")
    print(len(articles.get("articles", [])))
    for item in articles.get("articles", [])[:5]:
        print(f"source: {item.get('source', {}).get('name', '')}")
        print(f"author: {item.get('author', '')}")
        print(f"title: {item.get('title', '')}")
        print(f"url: {item.get('url', '')}")
        print(f"publishedAt: {item.get('publishedAt', '')}")
        print("---")