from __future__ import annotations
from typing import Optional, Union, List
from pydantic import BaseModel


class Trade(BaseModel):
    """
    交易记录模型 - 支持订单簿模式的shares和amount字段
    
    字段说明:
        id: 交易唯一标识符
        taker_order_id: 接受者订单ID
        market: 市场ID
        asset_id: 资产ID (Token ID)
        side: 交易方向 (BUY/SELL)
        amount: 总花费金额 (订单簿模式下的实际花费)
        shares: 交易份额数量 (订单簿模式下的实际获得份额)
        fee_rate_bps: 手续费率 (基点)
        price: 平均价格 (amount / shares)
        status: 交易状态 (PENDING/EXECUTED/FAILED)
        match_time: 匹配时间戳
        last_update: 最后更新时间戳
        outcome: 预测结果 (Yes/No)
        maker_address: 做市商地址
        owner: 交易所有者地址
        transaction_hash: 交易哈希
        bucket_index: 桶索引
        maker_orders: 做市商订单
        type: 订单类型 (LIMIT/MARKET)
        event_ids: 关联的事件ID列表
    """
    id: int
    taker_order_id: str
    market: str
    asset_id: str
    side: str
    amount: str  # 总花费金额
    shares: str  # 交易份额数量
    fee_rate_bps: str
    price: str  # 平均价格 (amount / shares)
    status: str
    match_time: str
    last_update: str
    outcome: str
    maker_address: str
    owner: str
    transaction_hash: str  # 单次交易的哈希
    bucket_index: str
    maker_orders: str  # 单次交易的maker订单
    type: str
    # 新增字段
    event_ids: list[int]  # 对应的event_id列表


class TradeCreateRequest(BaseModel):
    """
    交易创建请求模型 - 用于创建交易时的输入参数
    
    字段说明:
        market_id: 市场ID
        asset_id: 资产ID (Token ID)
        side: 交易方向 (BUY/SELL)
        shares: 交易份额数量 (对于BUY是想要买入的份额，对于SELL是想要卖出的份额)
        amount: 交易金额 (对于BUY是愿意支付的总金额，对于SELL是想要卖出的份额数量)
        outcome: 预测结果 (Yes/No)
        event_ids: 关联的事件ID列表
    """
    market_id: str
    asset_id: str
    side: str  # BUY/SELL
    shares: int  # 交易份额数量
    amount: float  # 交易金额 (BUY时是总花费，SELL时是shares数量)
    outcome: str  # Yes/No
    event_ids: List[int]


class SimpleMarket(BaseModel):
    id: int
    question: str
    # start: str
    end: str
    description: str
    active: bool
    # deployed: Optional[bool]
    funded: bool
    # orderMinSize: float
    # orderPriceMinTickSize: float
    rewardsMinSize: float
    rewardsMaxSpread: float
    # volume: Optional[float]
    spread: float
    outcomes: str
    outcome_prices: str
    clob_token_ids: Optional[str]
    tags: Optional[list[Tag]] = None
    volume: Optional[float] = None
    enableOrderBook: Optional[bool] = None


class ClobReward(BaseModel):
    id: str  # returned as string in api but really an int?
    conditionId: str
    assetAddress: str
    rewardsAmount: float  # only seen 0 but could be float?
    rewardsDailyRate: int  # only seen ints but could be float?
    startDate: str  # yyyy-mm-dd formatted date string
    endDate: str  # yyyy-mm-dd formatted date string


class Tag(BaseModel):
    id: str
    label: Optional[str] = None
    slug: Optional[str] = None
    forceShow: Optional[bool] = None  # missing from current events data
    createdAt: Optional[str] = None  # missing from events data
    updatedAt: Optional[str] = None  # missing from current events data
    _sync: Optional[bool] = None

class SimpleEvent(BaseModel):
    id: int
    ticker: str
    slug: str
    title: str
    description: str
    startDate: Optional[str] = None
    end: str
    endDate: Optional[str] = None
    active: bool
    closed: bool
    archived: bool
    restricted: bool
    new: bool
    featured: bool
    markets: str
    tags: Optional[list[Tag]] = None
    volume: Optional[float] = None
    volume24hr: Optional[float] = None
    liquidity: Optional[float] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    commentCount: Optional[int] = None
    enableOrderBook: Optional[bool] = None

class PolymarketEvent(BaseModel):
    id: str  # "11421"
    ticker: Optional[str] = None
    slug: Optional[str] = None
    title: Optional[str] = None
    startDate: Optional[str] = None
    creationDate: Optional[str] = (
        None  # fine in market event but missing from events response
    )
    endDate: Optional[str] = None
    image: Optional[str] = None
    icon: Optional[str] = None
    active: Optional[bool] = None
    closed: Optional[bool] = None
    archived: Optional[bool] = None
    new: Optional[bool] = None
    featured: Optional[bool] = None
    restricted: Optional[bool] = None
    liquidity: Optional[float] = None
    volume: Optional[float] = None
    reviewStatus: Optional[str] = None
    createdAt: Optional[str] = None  # 2024-07-08T01:06:23.982796Z,
    updatedAt: Optional[str] = None  # 2024-07-15T17:12:48.601056Z,
    competitive: Optional[float] = None
    volume24hr: Optional[float] = None
    enableOrderBook: Optional[bool] = None
    liquidityClob: Optional[float] = None
    _sync: Optional[bool] = None
    commentCount: Optional[int] = None
    # markets: list[str, 'Market'] # forward reference Market defined below - TODO: double check this works as intended
    markets: Optional[list[Market]] = None
    tags: Optional[list[Tag]] = None
    cyom: Optional[bool] = None
    showAllOutcomes: Optional[bool] = None
    showMarketImages: Optional[bool] = None
    
    def to_simple_event(self) -> 'SimpleEvent':
        """
        将PolymarketEvent转换为SimpleEvent
        
        Returns:
            SimpleEvent实例
        """
        return SimpleEvent(
            id=int(self.id),
            ticker=self.ticker or "",
            slug=self.slug or "",
            title=self.title or "",
            description="",  # PolymarketEvent没有description字段
            end=self.endDate or "",
            active=self.active or False,
            closed=self.closed or False,
            archived=self.archived or False,
            restricted=self.restricted or False,
            new=self.new or False,
            featured=self.featured or False,
            markets="",
            tags=self.tags or []
        )


class Market(BaseModel):
    id: int
    question: Optional[str] = None
    conditionId: Optional[str] = None
    slug: Optional[str] = None
    resolutionSource: Optional[str] = None
    endDate: Optional[str] = None
    liquidity: Optional[float] = None
    startDate: Optional[str] = None
    image: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    outcome: Optional[list] = None
    outcomePrices: Optional[list] = None
    volume: Optional[float] = None
    active: Optional[bool] = None
    closed: Optional[bool] = None
    marketMakerAddress: Optional[str] = None
    createdAt: Optional[str] = None  # date type worth enforcing for dates?
    updatedAt: Optional[str] = None
    new: Optional[bool] = None
    featured: Optional[bool] = None
    submitted_by: Optional[str] = None
    archived: Optional[bool] = None
    resolvedBy: Optional[str] = None
    restricted: Optional[bool] = None
    groupItemTitle: Optional[str] = None
    groupItemThreshold: Optional[int] = None
    questionID: Optional[str] = None
    enableOrderBook: Optional[bool] = None
    orderPriceMinTickSize: Optional[float] = None
    orderMinSize: Optional[int] = None
    volumeNum: Optional[float] = None
    liquidityNum: Optional[float] = None
    endDateIso: Optional[str] = None  # iso format date = None
    startDateIso: Optional[str] = None
    hasReviewedDates: Optional[bool] = None
    volume24hr: Optional[float] = None
    clobTokenIds: Optional[list] = None
    umaBond: Optional[int] = None  # returned as string from api?
    umaReward: Optional[int] = None  # returned as string from api?
    volume24hrClob: Optional[float] = None
    volumeClob: Optional[float] = None
    liquidityClob: Optional[float] = None
    acceptingOrders: Optional[bool] = None
    negRisk: Optional[bool] = None
    commentCount: Optional[int] = None
    _sync: Optional[bool] = None
    events: Optional[list[PolymarketEvent]] = None
    ready: Optional[bool] = None
    deployed: Optional[bool] = None
    funded: Optional[bool] = None
    deployedTimestamp: Optional[str] = None  # utc z datetime string
    acceptingOrdersTimestamp: Optional[str] = None  # utc z datetime string,
    cyom: Optional[bool] = None
    competitive: Optional[float] = None
    pagerDutyNotificationEnabled: Optional[bool] = None
    reviewStatus: Optional[str] = None  # deployed, draft, etc.
    approved: Optional[bool] = None
    clobRewards: Optional[list[ClobReward]] = None
    rewardsMinSize: Optional[int] = (
        None  # would make sense to allow float but we'll see
    )
    rewardsMaxSpread: Optional[float] = None
    spread: Optional[float] = None
    next_process_time: Optional[int] = None  # 下次处理时间戳


class ComplexMarket(BaseModel):
    id: int
    condition_id: str
    question_id: str
    tokens: Union[str, str]
    rewards: str
    minimum_order_size: str
    minimum_tick_size: str
    description: str
    category: str
    end_date_iso: str
    game_start_time: str
    question: str
    market_slug: str
    min_incentive_size: str
    max_incentive_spread: str
    active: bool
    closed: bool
    seconds_delay: int
    icon: str
    fpmm: str
    name: str
    description: Union[str, None] = None
    price: float
    tax: Union[float, None] = None


class Source(BaseModel):
    id: Optional[str]
    name: Optional[str]


class Article(BaseModel):
    source: Optional[Source]
    author: Optional[str]
    title: Optional[str]
    description: Optional[str]
    url: Optional[str]
    urlToImage: Optional[str]
    publishedAt: Optional[str]
    content: Optional[str]


class MarketDecision(BaseModel):
    """
    市场决策结果模型 - 用于process_new_market函数的返回结果
    
    字段说明:
        should_trade: 是否应该交易
        side: 交易方向 (Buy/Sell)
        amount: 交易金额
    """
    should_trade: bool
    side: str  # Buy/Sell
    amount: int


class ProcessMarketResult(BaseModel):
    """
    处理市场的结果模型 - 用于存储处理新增交易和已有交易的返回结构
    
    字段说明:
        Yes: Yes结果的交易决策
        No: No结果的交易决策  
        next_process_time: 下次处理的时间戳
        reason: 决策原因（模型返回的简要说明）
    """
    Yes: MarketDecision
    No: MarketDecision
    next_process_time: int  # 时间戳
    reason: str = ""


# 存储在trades.db中的数据结构, key为marketID,value为MarketTrades。
class MarketTrades(BaseModel):
    Yes: OutcomeTradesData
    No: OutcomeTradesData
    market_info: MarketInfo

class OutcomeTradesData(BaseModel):
    TokenID: str = ""
    Trades: list[Trade] = []
    balance: int = 0

class MarketInfo(BaseModel):
    market_question: str = ""
    market_description: str = ""
    event_title: str = ""
    event_description: str = ""
    event_tags: list = []
    market_created_at: str = ""
    market_end_date: str = ""
    next_process_time: int = 0