"""
本地数据库模块 - 使用SQLite实现events和markets的增删改查功能
"""

import os
import sqlite3
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from agents.utils.objects import PolymarketEvent, Market, SimpleEvent, Trade, MarketTrades, OutcomeTradesData, MarketInfo


class Database:
    """本地SQLite数据库管理类"""
    
    def __init__(self, db_path: str, logger=None):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径
            logger: 日志记录器
        """
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.logger = logger
        
        self.events_db_path = self.db_path / "events.db"
        self.markets_db_path = self.db_path / "markets.db"
        self.trades_db_path = self.db_path / "trades.db"
        self.value_history_db_path = self.db_path / "ValueHistory.db"
        
        # 初始化数据库表
        self._init_events_table()
        self._init_markets_table()
        self._init_trades_table()
        self._init_value_history_table()
        

    
    def _init_events_table(self):
        """初始化events表"""
        conn = sqlite3.connect(self.events_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                ticker TEXT,
                slug TEXT,
                title TEXT,
                description TEXT,
                startDate TEXT,
                end TEXT,
                endDate TEXT,
                image TEXT,
                icon TEXT,
                active INTEGER,
                closed INTEGER,
                archived INTEGER,
                new INTEGER,
                featured INTEGER,
                restricted INTEGER,
                liquidity REAL,
                volume REAL,
                volume24hr REAL,
                reviewStatus TEXT,
                createdAt TEXT,
                updatedAt TEXT,
                competitive REAL,
                enableOrderBook INTEGER,
                liquidityClob REAL,
                commentCount INTEGER,
                cyom INTEGER,
                showAllOutcomes INTEGER,
                showMarketImages INTEGER,
                tags TEXT,  -- JSON字符串存储tags
                markets TEXT,  -- JSON字符串存储markets
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _init_markets_table(self):
        """初始化markets表"""
        conn = sqlite3.connect(self.markets_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS markets (
                id INTEGER PRIMARY KEY,
                question TEXT,
                conditionId TEXT,
                slug TEXT,
                resolutionSource TEXT,
                endDate TEXT,
                liquidity REAL,
                startDate TEXT,
                image TEXT,
                icon TEXT,
                description TEXT,
                outcome TEXT,  -- JSON字符串存储outcome
                outcomePrices TEXT,  -- JSON字符串存储outcomePrices
                volume REAL,
                active INTEGER,
                closed INTEGER,
                marketMakerAddress TEXT,
                createdAt TEXT,
                updatedAt TEXT,
                new INTEGER,
                featured INTEGER,
                submitted_by TEXT,
                archived INTEGER,
                resolvedBy TEXT,
                restricted INTEGER,
                groupItemTitle TEXT,
                groupItemThreshold INTEGER,
                questionID TEXT,
                enableOrderBook INTEGER,
                orderPriceMinTickSize REAL,
                orderMinSize INTEGER,
                volumeNum REAL,
                liquidityNum REAL,
                endDateIso TEXT,
                startDateIso TEXT,
                hasReviewedDates INTEGER,
                volume24hr REAL,
                clobTokenIds TEXT,  -- JSON字符串存储clobTokenIds
                umaBond INTEGER,
                umaReward INTEGER,
                volume24hrClob REAL,
                volumeClob REAL,
                liquidityClob REAL,
                acceptingOrders INTEGER,
                negRisk INTEGER,
                commentCount INTEGER,
                ready INTEGER,
                deployed INTEGER,
                funded INTEGER,
                deployedTimestamp TEXT,
                acceptingOrdersTimestamp TEXT,
                cyom INTEGER,
                competitive REAL,
                pagerDutyNotificationEnabled INTEGER,
                reviewStatus TEXT,
                approved INTEGER,
                clobRewards TEXT,  -- JSON字符串存储clobRewards
                rewardsMinSize INTEGER,
                rewardsMaxSpread REAL,
                spread REAL,
                events TEXT,  -- JSON字符串存储events
                next_process_time INTEGER,  -- 下次处理时间戳
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _init_trades_table(self):
        """初始化trades表 - 支持MarketID->Yes/No->TokenID->Trades的嵌套结构，包含市场信息"""
        conn = sqlite3.connect(self.trades_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                market_id TEXT,
                outcome_type TEXT,  -- 'Yes' 或 'No'
                token_id TEXT,      -- 对应的TokenID
                trades_data TEXT,   -- JSON字符串存储该outcome的所有交易
                balance INTEGER DEFAULT 0,  -- 当前shares余额
                market_question TEXT,  -- 市场问题
                market_description TEXT,  -- 市场描述
                event_title TEXT,       -- 事件标题
                event_description TEXT, -- 事件描述
                event_tags TEXT,        -- 事件标签(JSON格式)
                market_created_at TEXT,   -- 市场创建日期
                market_end_date TEXT,     -- 市场结束日期
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (market_id, outcome_type)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _init_value_history_table(self):
        """初始化value_history表 - 与trades表结构完全一致"""
        conn = sqlite3.connect(self.value_history_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS value_history (
                market_id TEXT,
                outcome_type TEXT,  -- 'Yes' 或 'No'
                token_id TEXT,      -- 对应的TokenID
                trades_data TEXT,   -- JSON字符串存储该outcome的所有交易
                balance INTEGER DEFAULT 0,  -- 当前shares余额
                market_question TEXT,  -- 市场问题
                market_description TEXT,  -- 市场描述
                event_title TEXT,       -- 事件标题
                event_description TEXT, -- 事件描述
                event_tags TEXT,        -- 事件标签(JSON格式)
                market_created_at TEXT,   -- 市场创建日期
                market_end_date TEXT,     -- 市场结束日期
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (market_id, outcome_type)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _event_to_dict(self, event) -> Dict[str, Any]:
        """将Event对象转换为字典，支持PolymarketEvent和SimpleEvent"""
        # 检查是否是SimpleEvent类型
        if hasattr(event, 'description') and hasattr(event, 'end'):
            # SimpleEvent类型
            return {
                'id': str(event.id),
                'ticker': event.ticker,
                'slug': event.slug,
                'title': event.title,
                'description': event.description,
                'startDate': event.startDate,
                'end': event.end,
                'endDate': event.endDate,
                'image': None,
                'icon': None,
                'active': 1 if event.active else 0,
                'closed': 1 if event.closed else 0,
                'archived': 1 if event.archived else 0,
                'new': 1 if event.new else 0,
                'featured': 1 if event.featured else 0,
                'restricted': 1 if event.restricted else 0,
                'liquidity': event.liquidity,
                'volume': event.volume,
                'volume24hr': event.volume24hr,
                'reviewStatus': None,
                'createdAt': event.createdAt,
                'updatedAt': event.updatedAt,
                'competitive': None,
                'enableOrderBook': 1 if event.enableOrderBook else 0,
                'liquidityClob': None,
                'commentCount': event.commentCount,
                'cyom': None,
                'showAllOutcomes': None,
                'showMarketImages': None,
                'tags': json.dumps([tag.dict() for tag in event.tags]) if event.tags else None,
                'markets': event.markets if isinstance(event.markets, str) else json.dumps(event.markets) if event.markets else None,
            }
        else:
            # PolymarketEvent类型
            return {
                'id': event.id,
                'ticker': event.ticker,
                'slug': event.slug,
                'title': event.title,
                'description': None,
                'startDate': event.startDate,
                'end': event.endDate,
                'endDate': event.endDate,
                'image': event.image,
                'icon': event.icon,
                'active': 1 if event.active else 0,
                'closed': 1 if event.closed else 0,
                'archived': 1 if event.archived else 0,
                'new': 1 if event.new else 0,
                'featured': 1 if event.featured else 0,
                'restricted': 1 if event.restricted else 0,
                'liquidity': event.liquidity,
                'volume': event.volume,
                'volume24hr': event.volume24hr,
                'reviewStatus': event.reviewStatus,
                'createdAt': event.createdAt,
                'updatedAt': event.updatedAt,
                'competitive': event.competitive,
                'enableOrderBook': 1 if event.enableOrderBook else 0,
                'liquidityClob': event.liquidityClob,
                'commentCount': event.commentCount,
                'cyom': 1 if event.cyom else 0,
                'showAllOutcomes': 1 if event.showAllOutcomes else 0,
                'showMarketImages': 1 if event.showMarketImages else 0,
                'tags': json.dumps([tag.dict() for tag in event.tags]) if event.tags else None,
                'markets': json.dumps([market.dict() for market in event.markets]) if event.markets else None,
            }
    
    def _market_to_dict(self, market: Market) -> Dict[str, Any]:
        """将Market对象转换为字典 - 新markets的next_process_time设为0"""
        return {
            'id': market.id,
            'question': market.question,
            'conditionId': market.conditionId,
            'slug': market.slug,
            'resolutionSource': market.resolutionSource,
            'endDate': market.endDate,
            'liquidity': market.liquidity,
            'startDate': market.startDate,
            'image': market.image,
            'icon': market.icon,
            'description': market.description,
            'outcome': json.dumps(market.outcome) if market.outcome else None,
            'outcomePrices': json.dumps(market.outcomePrices) if market.outcomePrices else None,
            'volume': market.volume,
            'active': 1 if market.active else 0,
            'closed': 1 if market.closed else 0,
            'marketMakerAddress': market.marketMakerAddress,
            'createdAt': market.createdAt,
            'updatedAt': market.updatedAt,
            'new': 1 if market.new else 0,
            'featured': 1 if market.featured else 0,
            'submitted_by': market.submitted_by,
            'archived': 1 if market.archived else 0,
            'resolvedBy': market.resolvedBy,
            'restricted': 1 if market.restricted else 0,
            'groupItemTitle': market.groupItemTitle,
            'groupItemThreshold': market.groupItemThreshold,
            'questionID': market.questionID,
            'enableOrderBook': 1 if market.enableOrderBook else 0,
            'orderPriceMinTickSize': market.orderPriceMinTickSize,
            'orderMinSize': market.orderMinSize,
            'volumeNum': market.volumeNum,
            'liquidityNum': market.liquidityNum,
            'endDateIso': market.endDateIso,
            'startDateIso': market.startDateIso,
            'hasReviewedDates': 1 if market.hasReviewedDates else 0,
            'volume24hr': market.volume24hr,
            'clobTokenIds': json.dumps(market.clobTokenIds) if market.clobTokenIds else None,
            'umaBond': market.umaBond,
            'umaReward': market.umaReward,
            'volume24hrClob': market.volume24hrClob,
            'volumeClob': market.volumeClob,
            'liquidityClob': market.liquidityClob,
            'acceptingOrders': 1 if market.acceptingOrders else 0,
            'negRisk': 1 if market.negRisk else 0,
            'commentCount': market.commentCount,
            'ready': 1 if market.ready else 0,
            'deployed': 1 if market.deployed else 0,
            'funded': 1 if market.funded else 0,
            'deployedTimestamp': market.deployedTimestamp,
            'acceptingOrdersTimestamp': market.acceptingOrdersTimestamp,
            'cyom': 1 if market.cyom else 0,
            'competitive': market.competitive,
            'pagerDutyNotificationEnabled': 1 if market.pagerDutyNotificationEnabled else 0,
            'reviewStatus': market.reviewStatus,
            'approved': 1 if market.approved else 0,
            'clobRewards': json.dumps([reward.dict() for reward in market.clobRewards]) if market.clobRewards else None,
            'rewardsMinSize': market.rewardsMinSize,
            'rewardsMaxSpread': market.rewardsMaxSpread,
            'spread': market.spread,
            'events': json.dumps([event.dict() for event in market.events]) if market.events else None,
            'next_process_time': 0,  # 新markets的next_process_time设为0，表示可以立即处理
        }
    
    def upsert_events(self, events: List[SimpleEvent]) -> int:
        """
        插入或更新events数据
        
        Args:
            events: SimpleEvent对象列表
            
        Returns:
            插入/更新的记录数
        """
        conn = sqlite3.connect(self.events_db_path)
        cursor = conn.cursor()
        
        updated_count = 0
        for event in events:
            event_dict = self._event_to_dict(event)
            
            # 使用INSERT OR REPLACE来更新现有记录或插入新记录
            placeholders = ', '.join(['?' for _ in event_dict])
            columns = ', '.join(event_dict.keys())
            
            cursor.execute(f'''
                INSERT OR REPLACE INTO events ({columns})
                VALUES ({placeholders})
            ''', list(event_dict.values()))
            
            updated_count += 1
        
        conn.commit()
        conn.close()
        
        return updated_count
    
    def upsert_markets(self, markets: List[Market]) -> int:
        """
        插入或更新markets数据 - 保留现有的next_process_time
        
        Args:
            markets: Market对象列表
            
        Returns:
            插入/更新的记录数
        """
        conn = sqlite3.connect(self.markets_db_path)
        cursor = conn.cursor()
        
        updated_count = 0
        for market in markets:
            market_dict = self._market_to_dict(market)
            
            # 检查market是否已存在
            cursor.execute('SELECT next_process_time FROM markets WHERE id = ?', (market.id,))
            existing_row = cursor.fetchone()
            
            if existing_row and existing_row[0] is not None and existing_row[0] > 0:
                # 如果market已存在且有next_process_time > 0，保留它
                existing_next_process_time = existing_row[0]
                market_dict['next_process_time'] = existing_next_process_time
                
                # 使用UPDATE而不是INSERT OR REPLACE
                set_clauses = ', '.join([f'{key} = ?' for key in market_dict.keys()])
                values = list(market_dict.values()) + [market.id]
                
                cursor.execute(f'''
                    UPDATE markets SET {set_clauses} WHERE id = ?
                ''', values)
            else:
                # 如果market不存在或next_process_time为0/None，使用新数据（next_process_time=0）
                placeholders = ', '.join(['?' for _ in market_dict])
                columns = ', '.join(market_dict.keys())
                
                cursor.execute(f'''
                    INSERT OR REPLACE INTO markets ({columns})
                    VALUES ({placeholders})
                ''', list(market_dict.values()))
            
            updated_count += 1
        
        conn.commit()
        conn.close()
        
        return updated_count
    
    def get_event_by_id(self, event_id: str) -> Optional[SimpleEvent]:
        """
        根据ID查询event
        
        Args:
            event_id: 事件ID
            
        Returns:
            SimpleEvent对象或None
        """
        conn = sqlite3.connect(self.events_db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM events WHERE id = ?', (event_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return self._row_to_event(row)
        return None
    
    def get_market_by_id(self, market_id: int) -> Optional[Market]:
        """
        根据ID查询market
        
        Args:
            market_id: 市场ID
            
        Returns:
            Market对象或None
        """
        conn = sqlite3.connect(self.markets_db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM markets WHERE id = ?', (market_id,))
        row = cursor.fetchone()
        
        conn.close()
        
        if row:
            return self._row_to_market(row)
        return None
    
    def get_all_events(self) -> List[SimpleEvent]:
        """
        获取所有events
        
        Returns:
            SimpleEvent对象列表
        """
        conn = sqlite3.connect(self.events_db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM events')
        rows = cursor.fetchall()
        
        conn.close()
        
        return [self._row_to_event(row) for row in rows]
    
    def get_all_markets(self) -> List[Market]:
        """
        获取所有markets
        
        Returns:
            Market对象列表
        """
        conn = sqlite3.connect(self.markets_db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM markets')
        rows = cursor.fetchall()
        
        conn.close()
        
        return [self._row_to_market(row) for row in rows]
    
    def delete_closed_events(self) -> int:
        """
        删除已关闭或已归档的events
        
        Returns:
            删除的记录数
        """
        conn = sqlite3.connect(self.events_db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM events WHERE closed = 1 OR archived = 1')
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted_count
    
    def delete_closed_markets(self) -> int:
        """
        删除已关闭或已归档的markets
        
        Returns:
            删除的记录数
        """
        conn = sqlite3.connect(self.markets_db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM markets WHERE closed = 1 OR archived = 1')
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted_count
    
    def _row_to_event(self, row) -> SimpleEvent:
        """将数据库行转换为SimpleEvent对象"""
        # 获取列名
        conn = sqlite3.connect(self.events_db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(events)')
        columns = [column[1] for column in cursor.fetchall()]
        conn.close()
        
        # 创建字典
        event_dict = dict(zip(columns, row))
        
        # 处理JSON字段
        if event_dict.get('tags'):
            event_dict['tags'] = json.loads(event_dict['tags'])
        if event_dict.get('markets'):
            # markets字段可能是JSON字符串或已经是字符串，需要特殊处理
            markets_value = event_dict['markets']
            if isinstance(markets_value, str):
                try:
                    # 尝试解析为JSON
                    parsed_markets = json.loads(markets_value)
                    # 如果是列表，转换为逗号分隔的字符串
                    if isinstance(parsed_markets, list):
                        event_dict['markets'] = ','.join(map(str, parsed_markets))
                    else:
                        event_dict['markets'] = str(parsed_markets)
                except (json.JSONDecodeError, TypeError):
                    # 如果解析失败，保持原字符串
                    event_dict['markets'] = str(markets_value)
            else:
                # 如果不是字符串，转换为字符串
                event_dict['markets'] = str(markets_value)
        
        # 处理布尔值
        bool_fields = ['active', 'closed', 'archived', 'new', 'featured', 'restricted', 
                      'enableOrderBook', 'cyom', 'showAllOutcomes', 'showMarketImages']
        for field in bool_fields:
            if event_dict.get(field) is not None:
                event_dict[field] = bool(event_dict[field])
        
        # 转换ID为整数
        if event_dict.get('id'):
            event_dict['id'] = int(event_dict['id'])
        
        return SimpleEvent(**event_dict)
    
    def _row_to_market(self, row) -> Market:
        """将数据库行转换为Market对象"""
        # 获取列名
        conn = sqlite3.connect(self.markets_db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(markets)')
        columns = [column[1] for column in cursor.fetchall()]
        conn.close()
        
        # 创建字典
        market_dict = dict(zip(columns, row))
        
        # 处理JSON字段
        json_fields = ['outcome', 'outcomePrices', 'clobTokenIds', 'clobRewards', 'events']
        for field in json_fields:
            if market_dict.get(field):
                market_dict[field] = json.loads(market_dict[field])
        
        # 处理布尔值
        bool_fields = ['active', 'closed', 'new', 'featured', 'archived', 'restricted',
                      'enableOrderBook', 'hasReviewedDates', 'acceptingOrders', 'negRisk',
                      'ready', 'deployed', 'funded', 'cyom', 'pagerDutyNotificationEnabled', 'approved']
        for field in bool_fields:
            if market_dict.get(field) is not None:
                market_dict[field] = bool(market_dict[field])
        
        return Market(**market_dict)
    
    def sync_events(self, new_events: List[SimpleEvent]) -> Dict[str, int]:
        """
        同步events数据 - 更新、删除、新增
        
        Args:
            new_events: 新的SimpleEvent列表
            
        Returns:
            同步统计信息
        """
        # 获取现有events
        existing_events = self.get_all_events()
        existing_ids = {event.id for event in existing_events}
        
        # 获取新events的ID
        new_ids = {event.id for event in new_events}
        
        # 计算需要删除的events（已关闭或已归档的）
        to_delete = [event for event in existing_events 
                    if event.id not in new_ids and (event.closed or event.archived)]
        
        # 计算需要新增/更新的events
        to_upsert = [event for event in new_events 
                    if event.id not in existing_ids or 
                    (event.id in existing_ids and not event.closed and not event.archived)]
        
        # 执行操作
        deleted_count = 0
        for event in to_delete:
            conn = sqlite3.connect(self.events_db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM events WHERE id = ?', (event.id,))
            deleted_count += cursor.rowcount
            conn.commit()
            conn.close()
        
        upserted_count = self.upsert_events(to_upsert)
        
        return {
            'deleted': deleted_count,
            'upserted': upserted_count,
            'total_existing': len(existing_events),
            'total_new': len(new_events)
        }
    
    def sync_markets(self, new_markets: List[Market], event_ids: set) -> Dict[str, int]:
        """
        同步markets数据 - 只保存对应event在数据库中的markets
        
        Args:
            new_markets: 新的markets列表
            event_ids: 数据库中存在的event ID集合
            
        Returns:
            同步统计信息
        """
        # 过滤出对应event在数据库中的markets
        filtered_markets = []
        for market in new_markets:
            # 检查market是否关联到数据库中的events
            if hasattr(market, 'events') and market.events:
                for event in market.events:
                    try:
                        event_int = int(event.id)
                    except:
                        continue
                    if event_int in event_ids:
                        filtered_markets.append(market)
                        break
            # 或者通过其他方式判断market是否应该保存
            # 这里可以根据实际需求调整过滤逻辑
        if self.logger:
            self.logger.debug(f"Filtered markets: {len(filtered_markets)}")

        # 获取现有markets
        existing_markets = self.get_all_markets()
        existing_ids = {market.id for market in existing_markets}
        
        # 获取新markets的ID
        new_ids = {market.id for market in filtered_markets}
        
        # 计算需要删除的markets（已关闭或已归档的）
        to_delete = [market for market in existing_markets 
                    if market.id not in new_ids and (market.closed or market.archived)]
        
        # 计算需要新增/更新的markets
        to_upsert = [market for market in filtered_markets 
                    if market.id not in existing_ids or 
                    (market.id in existing_ids and not market.closed and not market.archived)]
        
        # 执行操作
        deleted_count = 0
        for market in to_delete:
            conn = sqlite3.connect(self.markets_db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM markets WHERE id = ?', (market.id,))
            deleted_count += cursor.rowcount
            conn.commit()
            conn.close()
        
        upserted_count = self.upsert_markets(to_upsert)
        
        return {
            'deleted': deleted_count,
            'upserted': upserted_count,
            'total_existing': len(existing_markets),
            'total_new': len(filtered_markets),
            'filtered_from': len(new_markets)
        }
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息
        
        Returns:
            数据库统计信息
        """
        # Events统计
        conn = sqlite3.connect(self.events_db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM events')
        events_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM events WHERE active = 1')
        active_events_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM events WHERE closed = 1')
        closed_events_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM events WHERE archived = 1')
        archived_events_count = cursor.fetchone()[0]
        conn.close()
        
        # Markets统计
        conn = sqlite3.connect(self.markets_db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM markets')
        markets_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM markets WHERE active = 1')
        active_markets_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM markets WHERE closed = 1')
        closed_markets_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM markets WHERE archived = 1')
        archived_markets_count = cursor.fetchone()[0]
        conn.close()
        
        return {
            'events': {
                'total': events_count,
                'active': active_events_count,
                'closed': closed_events_count,
                'archived': archived_events_count
            },
            'markets': {
                'total': markets_count,
                'active': active_markets_count,
                'closed': closed_markets_count,
                'archived': archived_markets_count
            },
            'database_path': str(self.db_path)
        }
    
    def save_trades_by_market(self, market_id: str, market_data: Dict[str, Any]) -> int:
        """
        保存指定market的交易数据至trades.db
        
        Args:
            market_id: 市场ID
            market_data: 市场交易数据，结构为:
                {
                    'Yes': {'TokenID': token_id, 'Trades': [Trade1, Trade2, ...]},
                    'No': {'TokenID': token_id, 'Trades': [Trade1, Trade2, ...]}
                }
            
        Returns:
            保存的交易数量
        """
        conn = sqlite3.connect(self.trades_db_path)
        cursor = conn.cursor()
        
        total_saved = 0
        
        # 获取market信息以获取clobTokenIds和其他信息
        market = self.get_market_by_id(int(market_id))
        if not market or not market.clobTokenIds:
            if self.logger:
                self.logger.warning(f"Market {market_id} 没有clobTokenIds信息，跳过保存")
            conn.close()
            return 0
        
        clob_token_ids = market.clobTokenIds
        yes_token_id = clob_token_ids[0] if len(clob_token_ids) > 0 else None
        no_token_id = clob_token_ids[1] if len(clob_token_ids) > 1 else None
        
        # 获取市场相关信息
        market_question = market.question or ""
        market_description = market.description or ""
        market_created_at = market.createdAt or ""
        market_end_date = market.endDate or ""
        
        # 获取事件详细信息
        event_title = ""
        event_description = ""
        event_tags = ""
        
        if hasattr(market, 'events') and market.events:
            for event in market.events:
                try:
                    # 将event ID从字符串转换为整数
                    event_id = int(event.id)
                    # 从events表中查询对应的SimpleEvent
                    simple_event = self.get_event_by_id(str(event_id))
                    if simple_event:
                        event_title = simple_event.title or ""
                        event_description = simple_event.description or ""
                        # 将tags转换为JSON字符串
                        if simple_event.tags:
                            event_tags = json.dumps([tag.dict() for tag in simple_event.tags])
                        break
                except (ValueError, TypeError):
                    # 如果转换失败，跳过这个event
                    continue
        
        # 保存Yes和No的交易（无论是否有交易都保存结构）
        for outcome_type in ['Yes', 'No']:
            if outcome_type in market_data:
                outcome_data = market_data[outcome_type]
                trades = outcome_data.get('Trades', [])
                token_id = outcome_data.get('TokenID') or (yes_token_id if outcome_type == 'Yes' else no_token_id)
            else:
                # 如果没有outcome数据，创建空结构
                trades = []
                token_id = yes_token_id if outcome_type == 'Yes' else no_token_id
            
            # 将Trade对象转换为字典
            trades_dict = []
            for trade in trades:
                trade_dict = {
                    'id': trade.id,
                    'taker_order_id': trade.taker_order_id,
                    'market': trade.market,
                    'asset_id': trade.asset_id,
                    'side': trade.side,
                    'amount': trade.amount,
                    'shares': trade.shares,
                    'fee_rate_bps': trade.fee_rate_bps,
                    'price': trade.price,
                    'status': trade.status,
                    'match_time': trade.match_time,
                    'last_update': trade.last_update,
                    'outcome': trade.outcome,
                    'maker_address': trade.maker_address,
                    'owner': trade.owner,
                    'transaction_hash': trade.transaction_hash,
                    'bucket_index': trade.bucket_index,
                    'maker_orders': trade.maker_orders,
                    'type': trade.type,
                    'event_ids': trade.event_ids
                }
                trades_dict.append(trade_dict)
            
            # 计算当前outcome的balance
            balance = 0
            for trade_dict in trades_dict:
                if trade_dict.get('status') == 'EXECUTED':
                    shares = int(float(trade_dict.get('shares', 0)))
                    if trade_dict.get('side') == 'BUY':
                        balance += shares
                    elif trade_dict.get('side') == 'SELL':
                        balance -= shares
            
            # 保存到数据库，包含市场信息和事件信息（只保存交易数据）
            cursor.execute('''
                INSERT OR REPLACE INTO trades 
                (market_id, outcome_type, token_id, trades_data, balance, market_question, 
                 market_description, event_title, event_description, event_tags,
                 market_created_at, market_end_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (market_id, outcome_type, token_id, json.dumps(trades_dict), balance,
                  market_question, market_description, event_title, event_description, event_tags,
                  market_created_at, market_end_date))
            
            total_saved += len(trades_dict)
        
        conn.commit()
        conn.close()
        
        return total_saved
    
    def update_market_balances_direct(self, market_id: str) -> Dict[str, int]:
        """
        直接更新指定market的shares余额（不调用save_trades_by_market）
        
        Args:
            market_id: 市场ID
            
        Returns:
            更新后的余额字典 {'Yes': balance, 'No': balance}
        """
        conn = sqlite3.connect(self.trades_db_path)
        cursor = conn.cursor()
        
        balances = {'Yes': 0, 'No': 0}
        
        # 计算每个outcome的余额
        for outcome_type in ['Yes', 'No']:
            cursor.execute('SELECT trades_data FROM trades WHERE market_id = ? AND outcome_type = ?', 
                         (market_id, outcome_type))
            row = cursor.fetchone()
            
            if row and row[0]:
                trades_data = json.loads(row[0])
                balance = 0
                
                for trade_dict in trades_data:
                    if trade_dict.get('status') == 'EXECUTED':
                        shares = int(float(trade_dict.get('shares', 0)))
                        if trade_dict.get('side') == 'BUY':
                            balance += shares
                        elif trade_dict.get('side') == 'SELL':
                            balance -= shares
                
                balances[outcome_type] = balance
                
                # 直接更新数据库中的balance
                cursor.execute('''
                    UPDATE trades 
                    SET balance = ? 
                    WHERE market_id = ? AND outcome_type = ?
                ''', (balance, market_id, outcome_type))
        
        conn.commit()
        conn.close()
        
        return balances
    
    def update_market_next_process_time(self, market_id: str, next_process_time: int) -> bool:
        """
        更新markets表中指定market的next_process_time
        
        Args:
            market_id: 市场ID
            next_process_time: 下次处理时间戳
            
        Returns:
            bool: 更新是否成功
        """
        try:
            conn = sqlite3.connect(self.markets_db_path)
            cursor = conn.cursor()
            
            # 检查market是否存在
            cursor.execute('SELECT id FROM markets WHERE id = ?', (market_id,))
            if not cursor.fetchone():
                if self.logger:
                    self.logger.warning(f"Market {market_id} 不存在于markets表中")
                conn.close()
                return False
            
            # 更新next_process_time
            cursor.execute(
                'UPDATE markets SET next_process_time = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?',
                (next_process_time, market_id)
            )
            
            conn.commit()
            conn.close()
            
            if self.logger:
                self.logger.debug(f"成功更新 Market {market_id} 的next_process_time: {next_process_time}")
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"更新 Market {market_id} 的next_process_time时出错: {e}")
            return False
    
    def get_trades_by_market(self, market_id: str) -> Dict[str, Dict[str, Any]]:
        """
        获取指定market的所有交易 - 支持新的嵌套结构
        
        Args:
            market_id: 市场ID
            
        Returns:
            该market的交易数据，结构为:
                {
                    'Yes': {'TokenID': token_id, 'Trades': [Trade1, Trade2, ...]},
                    'No': {'TokenID': token_id, 'Trades': [Trade1, Trade2, ...]},
                    'market_info': {
                        'market_question': str,           # 市场问题
                        'market_description': str,        # 市场描述
                        'event_title': str,              # 事件标题
                        'event_description': str,        # 事件描述
                        'event_tags': List[Dict],        # 事件标签列表
                        'market_created_at': str,        # 市场创建时间
                        'market_end_date': str           # 市场结束时间
                    }
                }
        
        数据来源: trades表，包含12个字段的完整市场信息
        交易数据: 每个Trade对象包含amount(总花费)和shares(份额)字段，支持订单簿模式
        """
        conn = sqlite3.connect(self.trades_db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trades WHERE market_id = ?', (market_id,))
        rows = cursor.fetchall()
        
        conn.close()
        
        result = {}
        market_info = {}  # 存储市场信息
        
        for row in rows:
            # 获取列名
            columns = [str(column[0]) for column in cursor.description]
            row_dict = dict(zip(columns, row))
            
            outcome_type = row_dict['outcome_type']
            token_id = row_dict['token_id']
            trades_data = json.loads(row_dict['trades_data']) if row_dict['trades_data'] else []
            
            # 存储市场信息（只需要存储一次）
            if not market_info:
                # 解析event_tags
                event_tags = row_dict.get('event_tags', '')
                if event_tags:
                    try:
                        event_tags = json.loads(event_tags)
                    except (json.JSONDecodeError, TypeError):
                        event_tags = []
                else:
                    event_tags = []
                
                market_info = {
                    'market_question': row_dict.get('market_question', ''),
                    'market_description': row_dict.get('market_description', ''),
                    'event_title': row_dict.get('event_title', ''),
                    'event_description': row_dict.get('event_description', ''),
                    'event_tags': event_tags,
                    'market_created_at': row_dict.get('market_created_at', ''),
                    'market_end_date': row_dict.get('market_end_date', ''),
                    'next_process_time': 0  # trades表中不再存储next_process_time，设为0
                }
            
            # 将字典转换为Trade对象
            trades = []
            for trade_dict in trades_data:
                # 安全处理event_ids字段
                if 'event_ids' in trade_dict and trade_dict['event_ids']:
                    if isinstance(trade_dict['event_ids'], str):
                        try:
                            trade_dict['event_ids'] = json.loads(trade_dict['event_ids'])
                        except (json.JSONDecodeError, TypeError):
                            trade_dict['event_ids'] = []
                    # 如果已经是列表，保持不变
                else:
                    trade_dict['event_ids'] = []
                
                trades.append(Trade(**trade_dict))
            
            # 获取balance字段
            balance = row_dict.get('balance', 0)
            
            result[outcome_type] = {
                'TokenID': token_id,
                'Trades': trades,
                'balance': balance
            }
        
        # 将市场信息添加到结果中
        result['market_info'] = market_info
        
        return result

    def get_trades_by_market_struct(self, market_id: str) -> Optional[MarketTrades]:
        """
        获取指定market的所有交易，返回对齐objects.py的结构体MarketTrades
        """
        conn = sqlite3.connect(self.trades_db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM trades WHERE market_id = ?', (market_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return None

        # 临时容器
        yes_token = ""
        no_token = ""
        yes_trades: list[Trade] = []
        no_trades: list[Trade] = []
        yes_balance = 0
        no_balance = 0
        market_info: Dict[str, Any] = {}

        # 获取列名
        columns = [desc[0] for desc in cursor.description] if rows else []

        for row in rows:
            row_dict = dict(zip(columns, row))
            outcome_type = row_dict['outcome_type']
            token_id = row_dict['token_id']
            trades_data = json.loads(row_dict['trades_data']) if row_dict['trades_data'] else []

            # 市场信息（只设置一次）
            if not market_info:
                event_tags = row_dict.get('event_tags', '')
                if event_tags:
                    try:
                        event_tags = json.loads(event_tags)
                    except (json.JSONDecodeError, TypeError):
                        event_tags = []
                else:
                    event_tags = []

                market_info = {
                    'market_question': row_dict.get('market_question', ''),
                    'market_description': row_dict.get('market_description', ''),
                    'event_title': row_dict.get('event_title', ''),
                    'event_description': row_dict.get('event_description', ''),
                    'event_tags': event_tags,
                    'market_created_at': row_dict.get('market_created_at', ''),
                    'market_end_date': row_dict.get('market_end_date', ''),
                    'next_process_time': 0  # trades表中不再存储next_process_time
                }

            # trades转换
            converted_trades: list[Trade] = []
            for trade_dict in trades_data:
                # 归一化event_ids
                if 'event_ids' in trade_dict and trade_dict['event_ids']:
                    if isinstance(trade_dict['event_ids'], str):
                        try:
                            trade_dict['event_ids'] = json.loads(trade_dict['event_ids'])
                        except (json.JSONDecodeError, TypeError):
                            trade_dict['event_ids'] = []
                else:
                    trade_dict['event_ids'] = []
                converted_trades.append(Trade(**trade_dict))

            balance = row_dict.get('balance', 0)

            if outcome_type == 'Yes':
                yes_token = token_id
                yes_trades = converted_trades
                yes_balance = balance
            elif outcome_type == 'No':
                no_token = token_id
                no_trades = converted_trades
                no_balance = balance

            # next_process_time 最大化（trades表中不再存储next_process_time，跳过此逻辑）

        return MarketTrades(
            Yes=OutcomeTradesData(TokenID=yes_token, Trades=yes_trades, balance=yes_balance),
            No=OutcomeTradesData(TokenID=no_token, Trades=no_trades, balance=no_balance),
            market_info=MarketInfo(**market_info)
        )
    
    def get_all_trades_by_market(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """获取所有按market分组的交易（旧结构，向后兼容）。"""
        conn = sqlite3.connect(self.trades_db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM trades ORDER BY market_id, outcome_type')
        rows = cursor.fetchall()
        
        conn.close()
        
        trades_by_market = {}
        for row in rows:
            columns = [str(column[0]) for column in cursor.description]
            row_dict = dict(zip(columns, row))
            
            market_id = row_dict['market_id']
            outcome_type = row_dict['outcome_type']
            token_id = row_dict['token_id']
            trades_data = json.loads(row_dict['trades_data']) if row_dict['trades_data'] else []
            
            trades = []
            for trade_dict in trades_data:
                if 'event_ids' in trade_dict and trade_dict['event_ids']:
                    if isinstance(trade_dict['event_ids'], str):
                        try:
                            trade_dict['event_ids'] = json.loads(trade_dict['event_ids'])
                        except (json.JSONDecodeError, TypeError):
                            trade_dict['event_ids'] = []
                else:
                    trade_dict['event_ids'] = []
                
                trades.append(Trade(**trade_dict))
            
            if market_id not in trades_by_market:
                trades_by_market[market_id] = {}
            
            balance = row_dict.get('balance', 0)
            
            trades_by_market[market_id][outcome_type] = {
                'TokenID': token_id,
                'Trades': trades,
                'balance': balance
            }
            
            if 'market_info' not in trades_by_market[market_id]:
                event_tags = row_dict.get('event_tags', '')
                if event_tags:
                    try:
                        event_tags = json.loads(event_tags)
                    except (json.JSONDecodeError, TypeError):
                        event_tags = []
                else:
                    event_tags = []
                
                next_process_time = 0  # trades表中不再存储next_process_time
                
                trades_by_market[market_id]['market_info'] = {
                    'market_question': row_dict.get('market_question', ''),
                    'market_description': row_dict.get('market_description', ''),
                    'event_title': row_dict.get('event_title', ''),
                    'event_description': row_dict.get('event_description', ''),
                    'event_tags': event_tags,
                    'market_created_at': row_dict.get('market_created_at', ''),
                    'market_end_date': row_dict.get('market_end_date', ''),
                    'next_process_time': next_process_time
                }
            
            # next_process_time 最大化（trades表中不再存储next_process_time，跳过此逻辑）
        
        return trades_by_market

    def get_all_trades_by_market_structs(self) -> Dict[str, MarketTrades]:
        """获取所有按market分组的交易（对齐objects结构，返回MarketTrades映射）。"""
        conn = sqlite3.connect(self.trades_db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM trades ORDER BY market_id, outcome_type')
        rows = cursor.fetchall()
        conn.close()

        result: Dict[str, MarketTrades] = {}
        # 暂存器
        temp: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            columns = [str(column[0]) for column in cursor.description]
            row_dict = dict(zip(columns, row))

            market_id = row_dict['market_id']
            outcome_type = row_dict['outcome_type']  # 'Yes' / 'No'
            token_id = row_dict['token_id']
            trades_data = json.loads(row_dict['trades_data']) if row_dict['trades_data'] else []
            balance = row_dict.get('balance', 0)

            # 事件标签
            event_tags = row_dict.get('event_tags', '')
            if event_tags:
                try:
                    event_tags = json.loads(event_tags)
                except (json.JSONDecodeError, TypeError):
                    event_tags = []
            else:
                event_tags = []

            # 转Trade对象数组
            converted_trades: list[Trade] = []
            for trade_dict in trades_data:
                if 'event_ids' in trade_dict and trade_dict['event_ids']:
                    if isinstance(trade_dict['event_ids'], str):
                        try:
                            trade_dict['event_ids'] = json.loads(trade_dict['event_ids'])
                        except (json.JSONDecodeError, TypeError):
                            trade_dict['event_ids'] = []
                else:
                    trade_dict['event_ids'] = []
                converted_trades.append(Trade(**trade_dict))

            # 初始化临时容器
            if market_id not in temp:
                temp[market_id] = {
                    'Yes': {'TokenID': '', 'Trades': [], 'balance': 0},
                    'No': {'TokenID': '', 'Trades': [], 'balance': 0},
                    'market_info': {
                        'market_question': row_dict.get('market_question', ''),
                        'market_description': row_dict.get('market_description', ''),
                        'event_title': row_dict.get('event_title', ''),
                        'event_description': row_dict.get('event_description', ''),
                        'event_tags': event_tags,
                        'market_created_at': row_dict.get('market_created_at', ''),
                        'market_end_date': row_dict.get('market_end_date', ''),
                        'next_process_time': 0  # trades表中不再存储next_process_time,
                    }
                }

            temp[market_id][outcome_type]['TokenID'] = token_id
            temp[market_id][outcome_type]['Trades'] = converted_trades
            temp[market_id][outcome_type]['balance'] = balance

            npt = 0  # trades表中不再存储next_process_time
            if npt > temp[market_id]['market_info'].get('next_process_time', 0):
                temp[market_id]['market_info']['next_process_time'] = npt

        # 收敛为MarketTrades
        for mid, data in temp.items():
            result[mid] = MarketTrades(
                Yes=OutcomeTradesData(
                    TokenID=data['Yes']['TokenID'],
                    Trades=data['Yes']['Trades'],
                    balance=data['Yes']['balance']
                ),
                No=OutcomeTradesData(
                    TokenID=data['No']['TokenID'],
                    Trades=data['No']['Trades'],
                    balance=data['No']['balance']
                ),
                market_info=MarketInfo(**data['market_info'])
            )

        return result
    
    def delete_trades_by_market(self, market_id: str) -> int:
        """
        删除指定market的所有交易
        
        Args:
            market_id: 市场ID
            
        Returns:
            删除的交易数量
        """
        conn = sqlite3.connect(self.trades_db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM trades WHERE market_id = ?', (market_id,))
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted_count
    
    def save_to_value_history(self, market_id: str, trades_data: Dict[str, Dict[str, Any]], closed_at: str = None, archived_at: str = None) -> int:
        """
        保存已关闭/归档的market交易到历史记录 - 结构与trades表对齐
        
        Args:
            market_id: 市场ID
            trades_data: 交易数据，结构为:
                {
                    'Yes': {'TokenID': token_id, 'Trades': [Trade1, Trade2, ...]},
                    'No': {'TokenID': token_id, 'Trades': [Trade1, Trade2, ...]},
                    'market_info': {
                        'market_question': str,
                        'market_description': str,
                        'event_title': str,
                        'event_description': str,
                        'event_tags': List[Dict],
                        'market_created_at': str,
                        'market_end_date': str
                    }
                }
            closed_at: 关闭时间
            archived_at: 归档时间
            
        Returns:
            保存的记录数
        """
        conn = sqlite3.connect(self.value_history_db_path)
        cursor = conn.cursor()
        
        current_time = datetime.now().isoformat()
        total_saved = 0
        
        # 获取市场信息
        market_info = trades_data.get('market_info', {})
        npt = market_info.get('next_process_time', 0)
        
        for outcome_type, outcome_data in trades_data.items():
            if outcome_type == 'market_info':
                continue
                
            trades = outcome_data.get('Trades', [])
            token_id = outcome_data.get('TokenID', '')
            
            # 将Trade对象转换为字典并计算余额（与保存到trades时一致）
            trades_dict = []
            balance_calc = 0
            for trade in trades:
                trades_dict.append(trade.dict())
                if getattr(trade, 'status', '') == 'EXECUTED':
                    shares_val = int(float(getattr(trade, 'shares', 0)))
                    side_val = getattr(trade, 'side', '').upper()
                    if side_val == 'BUY':
                        balance_calc += shares_val
                    elif side_val == 'SELL':
                        balance_calc -= shares_val
            
            # 准备插入数据，与trades表结构完全一致
            insert_data = {
                'market_id': market_id,
                'outcome_type': outcome_type,
                'token_id': token_id,
                'trades_data': json.dumps(trades_dict),
                'balance': balance_calc,
                'market_question': market_info.get('market_question', ''),
                'market_description': market_info.get('market_description', ''),
                'event_title': market_info.get('event_title', ''),
                'event_description': market_info.get('event_description', ''),
                'event_tags': json.dumps(market_info.get('event_tags', [])),
                'market_created_at': market_info.get('market_created_at', ''),
                'market_end_date': market_info.get('market_end_date', '')
            }
            
            placeholders = ', '.join(['?' for _ in insert_data])
            columns = ', '.join(insert_data.keys())
            
            cursor.execute(f'''
                INSERT OR REPLACE INTO value_history ({columns})
                VALUES ({placeholders})
            ''', list(insert_data.values()))
            
            total_saved += 1
        
        conn.commit()
        conn.close()
        
        return total_saved
    
    def delete_market(self, market_id: str) -> bool:
        """
        从markets.db中删除指定的market
        
        Args:
            market_id: 市场ID
            
        Returns:
            删除是否成功
        """
        try:
            conn = sqlite3.connect(self.markets_db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM markets WHERE id = ?", (market_id,))
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if self.logger:
                self.logger.info(f"从markets.db中删除Market {market_id}: 删除了 {deleted_count} 条记录")
            
            return deleted_count > 0
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"删除Market {market_id}失败: {e}")
            return False

    def delete_trades_by_market(self, market_id: str) -> bool:
        """
        从trades.db中删除指定market的所有交易数据
        
        Args:
            market_id: 市场ID
            
        Returns:
            删除是否成功
        """
        try:
            conn = sqlite3.connect(self.trades_db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM trades WHERE market_id = ?", (market_id,))
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if self.logger:
                self.logger.info(f"从trades.db中删除Market {market_id}的交易数据: 删除了 {deleted_count} 条记录")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"删除Market {market_id}的交易数据失败: {e}")
            return False

    def migrate_trades_to_value_history(self, market_id: str, market_trades_data: Dict[str, Any]) -> bool:
        """
        将trades.db中的数据迁移到value_history.db
        
        Args:
            market_id: 市场ID
            market_trades_data: 从trades.db获取的市场交易数据
            
        Returns:
            迁移是否成功
        """
        try:
            if not market_trades_data:
                if self.logger:
                    self.logger.warning(f"Market {market_id}没有交易数据需要迁移")
                return True
            
            # 处理Yes和No两个outcome
            for outcome_type in ['Yes', 'No']:
                if outcome_type in market_trades_data:
                    outcome_data = market_trades_data[outcome_type]
                    trades = outcome_data.get('Trades', [])
                    token_id = outcome_data.get('TokenID', '')
                    
                    if trades:  # 只有当有交易时才迁移
                        # 计算余额
                        balance = 0
                        for trade in trades:
                            if trade.status == 'EXECUTED':
                                shares = int(float(trade.shares))
                                if trade.side == 'BUY':
                                    balance += shares
                                elif trade.side == 'SELL':
                                    balance -= shares
                        
                        # 获取市场信息
                        market_info = market_trades_data.get('market_info', {})
                        
                        # 保存到value_history
                        success = self.save_to_value_history(
                            market_id=market_id,
                            trades_data={outcome_type: outcome_data, 'market_info': market_info}
                        )
                        
                        if not success:
                            if self.logger:
                                self.logger.error(f"迁移Market {market_id}的{outcome_type}数据到value_history失败")
                            return False
            
            if self.logger:
                self.logger.info(f"Market {market_id}的所有交易数据已成功迁移到value_history")
            
            return True
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"迁移Market {market_id}的交易数据到value_history失败: {e}")
            return False

    def get_market_status(self, market_id: int) -> Dict[str, Any]:
        """
        获取market的状态信息
        
        Args:
            market_id: 市场ID
            
        Returns:
            market状态信息
        """
        market = self.get_market_by_id(market_id)
        if not market:
            return {'exists': False}
        
        return {
            'exists': True,
            'active': market.active,
            'closed': market.closed,
            'archived': market.archived,
            'market': market
        }
