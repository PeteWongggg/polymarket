#!/usr/bin/env python3
"""
数据库查询脚本 - 展示events.db、markets.db、trades.db中第一条数据的完整信息
"""

import sqlite3
import json
from pathlib import Path
from agents.database import Database
from agents.utils.objects import SimpleEvent, Market, Trade

def query_events_db(db_path: str = "./data"):
    """查询events.db中第一条数据"""
    print("=" * 80)
    print("EVENTS.DB 第一条数据")
    print("=" * 80)
    
    events_db_path = Path(db_path) / "events.db"
    if not events_db_path.exists():
        print("❌ events.db 文件不存在")
        return
    
    conn = sqlite3.connect(events_db_path)
    cursor = conn.cursor()
    
    # 获取表结构
    cursor.execute("PRAGMA table_info(events)")
    columns = [column[1] for column in cursor.fetchall()]
    print(f"表结构 ({len(columns)} 个字段):")
    for i, col in enumerate(columns, 1):
        print(f"  {i:2d}. {col}")
    print()
    
    # 获取第一条数据
    cursor.execute("SELECT * FROM events LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        print("第一条数据:")
        for i, (col, value) in enumerate(zip(columns, row), 1):
            if col in ['tags', 'markets'] and value:
                try:
                    parsed_value = json.loads(value)
                    print(f"  {i:2d}. {col}: {parsed_value}")
                except:
                    print(f"  {i:2d}. {col}: {value}")
            else:
                print(f"  {i:2d}. {col}: {value}")
    else:
        print("❌ 没有找到数据")
    
    conn.close()

def query_markets_db(db_path: str = "./data"):
    """查询markets.db中第一条数据"""
    print("\n" + "=" * 80)
    print("MARKETS.DB 第一条数据")
    print("=" * 80)
    
    markets_db_path = Path(db_path) / "markets.db"
    if not markets_db_path.exists():
        print("❌ markets.db 文件不存在")
        return
    
    conn = sqlite3.connect(markets_db_path)
    cursor = conn.cursor()
    
    # 获取表结构
    cursor.execute("PRAGMA table_info(markets)")
    columns = [column[1] for column in cursor.fetchall()]
    print(f"表结构 ({len(columns)} 个字段):")
    for i, col in enumerate(columns, 1):
        print(f"  {i:2d}. {col}")
    print()
    
    # 获取第一条数据
    cursor.execute("SELECT * FROM markets LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        print("第一条数据:")
        for i, (col, value) in enumerate(zip(columns, row), 1):
            if col in ['outcome', 'outcomePrices', 'clobTokenIds', 'clobRewards', 'events'] and value:
                try:
                    parsed_value = json.loads(value)
                    print(f"  {i:2d}. {col}: {parsed_value}")
                except:
                    print(f"  {i:2d}. {col}: {value}")
            else:
                print(f"  {i:2d}. {col}: {value}")
    else:
        print("❌ 没有找到数据")
    
    conn.close()

def query_trades_db(db_path: str = "./data"):
    """查询trades.db中第一条数据"""
    print("\n" + "=" * 80)
    print("TRADES.DB 第一条数据")
    print("=" * 80)
    
    trades_db_path = Path(db_path) / "trades.db"
    if not trades_db_path.exists():
        print("❌ trades.db 文件不存在")
        return
    
    conn = sqlite3.connect(trades_db_path)
    cursor = conn.cursor()
    
    # 获取表结构
    cursor.execute("PRAGMA table_info(trades)")
    columns = [column[1] for column in cursor.fetchall()]
    print(f"表结构 ({len(columns)} 个字段):")
    for i, col in enumerate(columns, 1):
        print(f"  {i:2d}. {col}")
    print()
    
    # 获取第一条数据
    cursor.execute("SELECT * FROM trades LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        print("第一条数据:")
        for i, (col, value) in enumerate(zip(columns, row), 1):
            if col in ['trades_data', 'event_tags'] and value:
                try:
                    parsed_value = json.loads(value)
                    print(f"  {i:2d}. {col}: {parsed_value}")
                except:
                    print(f"  {i:2d}. {col}: {value}")
            else:
                print(f"  {i:2d}. {col}: {value}")
    else:
        print("❌ 没有找到数据")
    
    conn.close()

def query_market_with_multiple_trades(db_path: str = "./data"):
    """查询trades.db中存在多条Trades的Market完整信息"""
    print("\n" + "=" * 80)
    print("TRADES.DB 存在多条Trades的Market信息")
    print("=" * 80)
    
    trades_db_path = Path(db_path) / "trades.db"
    if not trades_db_path.exists():
        print("❌ trades.db 文件不存在")
        return
    
    conn = sqlite3.connect(trades_db_path)
    cursor = conn.cursor()
    
    # 查找存在多条Trades的market
    cursor.execute('''
        SELECT market_id, outcome_type, 
               json_array_length(trades_data) as trade_count
        FROM trades 
        WHERE trades_data IS NOT NULL 
        AND json_array_length(trades_data) > 1
        ORDER BY trade_count DESC
        LIMIT 5
    ''')
    
    results = cursor.fetchall()
    
    if not results:
        print("❌ 没有找到存在多条Trades的Market")
        conn.close()
        return
    
    print(f"找到 {len(results)} 个存在多条Trades的Market:")
    for i, (market_id, outcome_type, trade_count) in enumerate(results, 1):
        print(f"  {i}. Market {market_id} - {outcome_type}: {trade_count} 个交易")
    
    # 选择第一个结果进行详细展示
    market_id, outcome_type, trade_count = results[0]
    print(f"\n详细展示 Market {market_id} - {outcome_type} ({trade_count} 个交易):")
    print("-" * 60)
    
    # 获取该market的所有outcome数据
    cursor.execute('''
        SELECT * FROM trades 
        WHERE market_id = ? 
        ORDER BY outcome_type
    ''', (market_id,))
    
    market_rows = cursor.fetchall()
    columns = [column[0] for column in cursor.description]
    
    # 按outcome分组显示
    market_data = {}
    for row in market_rows:
        row_dict = dict(zip(columns, row))
        outcome = row_dict['outcome_type']
        market_data[outcome] = row_dict
    
    # 显示市场基本信息
    if market_data:
        first_row = list(market_data.values())[0]
        print(f"市场ID: {first_row['market_id']}")
        print(f"市场问题: {first_row['market_question']}")
        print(f"市场描述: {first_row['market_description']}")
        print(f"事件标题: {first_row['event_title']}")
        print(f"事件描述: {first_row['event_description']}")
        print(f"市场创建时间: {first_row['market_created_at']}")
        print(f"市场结束时间: {first_row['market_end_date']}")
        
        # 解析并显示事件标签
        if first_row['event_tags']:
            try:
                event_tags = json.loads(first_row['event_tags'])
                if event_tags:
                    tag_labels = [tag.get('label', tag.get('slug', '')) for tag in event_tags if tag]
                    print(f"事件标签: {', '.join(tag_labels) if tag_labels else 'N/A'}")
            except:
                print(f"事件标签: {first_row['event_tags']}")
        else:
            print("事件标签: N/A")
        
        print()
    
    # 显示每个outcome的详细信息
    for outcome_type in ['Yes', 'No']:
        if outcome_type in market_data:
            row = market_data[outcome_type]
            print(f"{outcome_type} 交易信息:")
            print(f"  TokenID: {row['token_id']}")
            print(f"  余额: {row['balance']} shares")
            
            # 解析并显示交易详情
            if row['trades_data']:
                try:
                    trades_data = json.loads(row['trades_data'])
                    print(f"  详细交易列表 ({len(trades_data)} 个):")
                    for i, trade in enumerate(trades_data, 1):
                        print(f"    {i}. 交易ID: {trade.get('id', 'N/A')}")
                        print(f"       方向: {trade.get('side', 'N/A')}")
                        print(f"       份额: {trade.get('shares', 'N/A')}")
                        print(f"       金额: {trade.get('amount', 'N/A')}")
                        print(f"       价格: {trade.get('price', 'N/A')}")
                        print(f"       状态: {trade.get('status', 'N/A')}")
                        print(f"       匹配时间: {trade.get('match_time', 'N/A')}")
                        print(f"       交易哈希: {trade.get('transaction_hash', 'N/A')}")
                        print(f"       关联事件: {trade.get('event_ids', [])}")
                        print()
                except Exception as e:
                    print(f"  ❌ 解析交易数据失败: {e}")
            else:
                print("  无交易数据")
        else:
            print(f"{outcome_type} 交易信息: 无数据")
        
        print()
    
    conn.close()

def query_markets_next_process_time(db_path: str = "./data"):
    """查询markets.db中next_process_time的分布情况"""
    print("\n" + "=" * 80)
    print("MARKETS.DB next_process_time 分布情况")
    print("=" * 80)
    
    markets_db_path = Path(db_path) / "markets.db"
    if not markets_db_path.exists():
        print("❌ markets.db 文件不存在")
        return
    
    conn = sqlite3.connect(markets_db_path)
    cursor = conn.cursor()
    
    # 查询next_process_time的分布
    cursor.execute('''
        SELECT next_process_time, COUNT(*) as count
        FROM markets 
        GROUP BY next_process_time 
        ORDER BY next_process_time
    ''')
    
    results = cursor.fetchall()
    
    if results:
        print("next_process_time 分布:")
        for next_time, count in results:
            if next_time == 0:
                print(f"  next_process_time = 0: {count} 条记录 (初始状态)")
            else:
                import datetime
                dt = datetime.datetime.fromtimestamp(next_time)
                print(f"  next_process_time = {next_time}: {count} 条记录 (时间: {dt})")
        
        print()
        
        # 显示前5条记录的详细信息
        cursor.execute('''
            SELECT id, question, next_process_time 
            FROM markets 
            ORDER BY next_process_time DESC 
            LIMIT 5
        ''')
        
        top_records = cursor.fetchall()
        print("前5条记录详情:")
        for i, (market_id, question, next_time) in enumerate(top_records, 1):
            if next_time == 0:
                status = "初始状态"
            else:
                import datetime
                dt = datetime.datetime.fromtimestamp(next_time)
                status = f"下次处理: {dt}"
            print(f"  {i}. Market {market_id}: {question[:50]}... -> {status}")
    else:
        print("❌ 没有找到数据")
    
    conn.close()

def query_value_history_db(db_path: str = "./data"):
    """查询ValueHistory.db中第一条数据"""
    print("\n" + "=" * 80)
    print("VALUEHISTORY.DB 第一条数据")
    print("=" * 80)
    
    value_history_db_path = Path(db_path) / "ValueHistory.db"
    if not value_history_db_path.exists():
        print("❌ ValueHistory.db 文件不存在")
        return
    
    conn = sqlite3.connect(value_history_db_path)
    cursor = conn.cursor()
    
    # 获取表结构
    cursor.execute("PRAGMA table_info(value_history)")
    columns = [column[1] for column in cursor.fetchall()]
    print(f"表结构 ({len(columns)} 个字段):")
    for i, col in enumerate(columns, 1):
        print(f"  {i:2d}. {col}")
    print()
    
    # 获取第一条数据
    cursor.execute("SELECT * FROM value_history LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        print("第一条数据:")
        for i, (col, value) in enumerate(zip(columns, row), 1):
            if col in ['trades_data', 'event_tags'] and value:
                try:
                    parsed_value = json.loads(value)
                    print(f"  {i:2d}. {col}: {parsed_value}")
                except:
                    print(f"  {i:2d}. {col}: {value}")
            else:
                print(f"  {i:2d}. {col}: {value}")
    else:
        print("❌ 没有找到数据")
    
    conn.close()

def query_using_database_class(db_path: str = "./data"):
    """使用Database类查询数据"""
    print("\n" + "=" * 80)
    print("使用Database类查询数据")
    print("=" * 80)
    
    try:
        db = Database(db_path)
        
        # 查询events
        print("EVENTS (使用Database类):")
        events = db.get_all_events()
        if events:
            event = events[0]
            print(f"  事件ID: {event.id}")
            print(f"  标题: {event.title}")
            print(f"  描述: {event.description}")
            print(f"  开始日期: {event.startDate}")
            print(f"  结束日期: {event.endDate}")
            print(f"  活跃状态: {event.active}")
            print(f"  标签数量: {len(event.tags) if event.tags else 0}")
            if event.tags:
                print(f"  标签: {[tag.label for tag in event.tags[:3]]}...")
        else:
            print("  ❌ 没有找到events")
        
        # 查询markets
        print("\nMARKETS (使用Database类):")
        markets = db.get_all_markets()
        if markets:
            market = markets[0]
            print(f"  市场ID: {market.id}")
            print(f"  问题: {market.question}")
            print(f"  描述: {market.description}")
            print(f"  创建日期: {market.createdAt}")
            print(f"  结束日期: {market.endDate}")
            print(f"  活跃状态: {market.active}")
            print(f"  关闭状态: {market.closed}")
            print(f"  归档状态: {market.archived}")
            print(f"  clobTokenIds数量: {len(market.clobTokenIds) if market.clobTokenIds else 0}")
            if market.clobTokenIds:
                print(f"  Yes TokenID: {market.clobTokenIds[0]}")
                print(f"  No TokenID: {market.clobTokenIds[1]}")
        else:
            print("  ❌ 没有找到markets")
        
        # 查询trades
        print("\nTRADES (使用Database类):")
        trades_by_market = db.get_all_trades_by_market()
        if trades_by_market:
            market_id = list(trades_by_market.keys())[0]
            market_data = trades_by_market[market_id]
            print(f"  市场ID: {market_id}")
            
            # 显示市场信息
            market_info = market_data.get('market_info', {})
            if market_info:
                print(f"  市场问题: {market_info.get('market_question', 'N/A')}")
                print(f"  市场描述: {market_info.get('market_description', 'N/A')}")
                print(f"  事件标题: {market_info.get('event_title', 'N/A')}")
                print(f"  事件描述: {market_info.get('event_description', 'N/A')}")
                print(f"  创建日期: {market_info.get('market_created_at', 'N/A')}")
                print(f"  结束日期: {market_info.get('market_end_date', 'N/A')}")
                print(f"  下次处理时间: {market_info.get('next_process_time', 'N/A')}")
            
            # 显示Yes交易
            if 'Yes' in market_data:
                yes_data = market_data['Yes']
                yes_trades = yes_data.get('Trades', [])
                print(f"  Yes交易数量: {len(yes_trades)}")
                if yes_trades:
                    trade = yes_trades[0]
                    print(f"    交易ID: {trade.id}")
                    print(f"    价格: {trade.price}")
                    print(f"    份额: {trade.shares}")
                    print(f"    金额: {trade.amount}")
                    print(f"    状态: {trade.status}")
                    print(f"    关联事件: {trade.event_ids}")
            
            # 显示No交易
            if 'No' in market_data:
                no_data = market_data['No']
                no_trades = no_data.get('Trades', [])
                print(f"  No交易数量: {len(no_trades)}")
                if no_trades:
                    trade = no_trades[0]
                    print(f"    交易ID: {trade.id}")
                    print(f"    价格: {trade.price}")
                    print(f"    份额: {trade.shares}")
                    print(f"    金额: {trade.amount}")
                    print(f"    状态: {trade.status}")
                    print(f"    关联事件: {trade.event_ids}")
        else:
            print("  ❌ 没有找到trades")
            
    except Exception as e:
        print(f"❌ 查询Database类时出错: {e}")

def main():
    """主函数"""
    print("数据库查询脚本")
    print("=" * 80)
    
    db_path = "./data"
    
    # 查询各个数据库
    query_events_db(db_path)
    query_markets_db(db_path)
    query_trades_db(db_path)
    query_market_with_multiple_trades(db_path)
    query_markets_next_process_time(db_path)
    query_value_history_db(db_path)
    
    # 使用Database类查询
    query_using_database_class(db_path)
    
    print("\n" + "=" * 80)
    print("查询完成")
    print("=" * 80)

if __name__ == "__main__":
    main()
