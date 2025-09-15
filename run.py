#!/usr/bin/env python3
"""
主运行文件 - 启动交易策略
"""

from agents.application.trade import Trader
from agents.polymarket.polymarket import Polymarket
from agents.database import Database
from agents.logger.logger import Logger
from agents.loop.main_loop import Loop
from collections import Counter
import yaml
import os
import argparse


def analyze_event_tags(events, logger):
    """分析所有事件的标签并返回聚合结果"""
    logger.info("开始分析事件标签")
    
    # 统计所有标签
    all_tags = []
    tag_details = {}  # 存储标签的详细信息
    
    for event in events:
        if event.tags:
            for tag in event.tags:
                all_tags.append(tag.label if tag.label else tag.slug)
                # 保存标签详细信息
                tag_key = tag.label if tag.label else tag.slug
                if tag_key not in tag_details:
                    tag_details[tag_key] = {
                        'id': tag.id,
                        'slug': tag.slug,
                        'label': tag.label,
                        'count': 0
                    }
                tag_details[tag_key]['count'] += 1
    
    # 统计标签出现次数
    tag_counter = Counter(all_tags)
    
    logger.info(f"分析了 {len(events)} 个事件，发现 {len(tag_counter)} 个不同标签")
    logger.debug(f"标签总出现次数: {sum(tag_counter.values())}")
    
    # 记录前10个最频繁的标签
    for i, (tag, count) in enumerate(tag_counter.most_common(10), 1):
        percentage = (count / len(events)) * 100
        logger.debug(f"标签 {i}: {tag} - {count} 次 ({percentage:.1f}%)")
    
    return tag_counter, tag_details


def load_config(logger):
    """加载配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            if logger:
                logger.info(f"成功加载配置文件: {config_path}")
            return config
    except FileNotFoundError:
        if logger:
            logger.error(f"配置文件未找到: {config_path}")
        else:
            print(f"配置文件未找到: {config_path}")
        return {"tags": {"whitelist": [], "blacklist": []}}
    except Exception as e:
        if logger:
            logger.error(f"加载配置文件时出错: {e}")
        else:
            print(f"加载配置文件时出错: {e}")
        return {"tags": {"whitelist": [], "blacklist": []}}

def display_config_info(config, logger):
    """显示配置信息"""
    whitelist = config.get("tags", {}).get("whitelist", [])
    blacklist = config.get("tags", {}).get("blacklist", [])
    db_path = config.get("db", {}).get("path", "./data")
    log_path = config.get("logging", {}).get("path", "./logs")
    
    logger.info(f"配置信息 - 白名单: {len(whitelist)} 个, 黑名单: {len(blacklist)} 个, 数据库路径: {db_path}, 日志路径: {log_path}")
    
    if whitelist:
        logger.debug(f"标签白名单: {', '.join(whitelist)}")
    if blacklist:
        logger.debug(f"标签黑名单: {', '.join(blacklist)}")

def sync_live_events_and_markets(polymarket, db, logger):
    """
    同步实时事件和市场数据
    
    Args:
        polymarket: Polymarket实例
        db: 数据库实例
        logger: 日志记录器
        
    Returns:
        tuple: (events_sync_stats, markets_sync_stats)
    """
    logger.info("开始同步实时事件和市场数据")
    
    # 获取所有可交易事件
    logger.info("开始获取所有可交易事件")
    events = polymarket.get_all_tradeable_events()
    logger.info(f"成功获取 {len(events)} 个可交易事件")

    # 同步events到数据库
    logger.info("开始同步events到数据库")
    events_sync_stats = db.sync_events(events)
    logger.info(f"Events同步完成 - 删除: {events_sync_stats['deleted']}, 更新/新增: {events_sync_stats['upserted']}")
    logger.debug(f"Events同步详情: 现有 {events_sync_stats['total_existing']}, 新获取 {events_sync_stats['total_new']}")

    # 获取所有可交易的markets
    logger.info("开始获取所有可交易markets")
    markets = polymarket.get_all_tradeable_markets()
    logger.info(f"成功获取 {len(markets)} 个可交易markets")
    
    # 获取数据库中存在的event IDs
    existing_events = db.get_all_events()
    existing_event_ids = {event.id for event in existing_events}
    logger.debug(f"数据库中存在 {len(existing_event_ids)} 个events")
    
    # 同步markets到数据库（只保存对应event在数据库中的markets）
    logger.info("开始同步markets到数据库")
    markets_sync_stats = db.sync_markets(markets, existing_event_ids)
    logger.info(f"Markets同步完成 - 删除: {markets_sync_stats['deleted']}, 更新/新增: {markets_sync_stats['upserted']}")
    logger.debug(f"Markets同步详情: 现有 {markets_sync_stats['total_existing']}, 过滤后 {markets_sync_stats['total_new']}, 原始 {markets_sync_stats['filtered_from']}")
    
    # 显示最终数据库状态
    final_stats = db.get_database_stats()
    logger.info(f"最终数据库状态 - Events: {final_stats['events']['total']} 个, Markets: {final_stats['markets']['total']} 个")
    
    return events_sync_stats, markets_sync_stats

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Polymarket 交易机器人')
    parser.add_argument('--skip-sync', action='store_true', 
                       help='跳过同步实时事件和市场数据步骤')
    parser.add_argument('--sync-only', action='store_true',
                       help='仅执行同步步骤，不执行交易')
    return parser.parse_args()

def main():
    """主函数 - 创建交易者实例并执行最佳交易策略"""
    # 解析命令行参数
    args = parse_arguments()
    
    # 先加载配置以获取日志路径
    config = load_config(None)  # 临时传入None，因为logger还没创建
    
    # 从配置中获取日志路径
    log_path = config.get("logging", {}).get("path", "./logs")
    
    # 初始化日志记录器
    logger = Logger(log_path)
    logger.info("启动 Polymarket 交易机器人")
    
    # 记录命令行参数
    if args.skip_sync:
        logger.info("命令行参数: 跳过同步步骤")
    if args.sync_only:
        logger.info("命令行参数: 仅执行同步步骤")
    
    # 创建Polymarket实例
    polymarket = Polymarket(logger=logger)
    
    # 实例化Loop类
    loop = Loop(logger=logger, polymarket=polymarket, config=config)
    
    try:
        # 显示配置信息
        display_config_info(config, logger)
        
        # 初始化数据库
        db_path = config.get("db", {}).get("path", "./data")
        logger.info(f"初始化数据库: {db_path}")
        db = Database(db_path, logger=logger)
        
        # 创建交易者实例
        trader = Trader(db=db, logger=logger)
        
        # 显示数据库当前状态
        stats = db.get_database_stats()
        logger.info(f"数据库当前状态 - Events: {stats['events']['total']} 个, Markets: {stats['markets']['total']} 个")
        logger.debug(f"Events详情: 活跃 {stats['events']['active']}, 已关闭 {stats['events']['closed']}, 已归档 {stats['events']['archived']}")
        logger.debug(f"Markets详情: 活跃 {stats['markets']['active']}, 已关闭 {stats['markets']['closed']}, 已归档 {stats['markets']['archived']}")

        # 根据命令行参数决定是否执行同步
        if not args.skip_sync:
            # 执行同步实时事件和市场数据
            events_sync_stats, markets_sync_stats = sync_live_events_and_markets(polymarket, db, logger)
        else:
            logger.info("跳过同步步骤，使用现有数据库数据")
            events_sync_stats = {"deleted": 0, "upserted": 0, "total_existing": stats['events']['total'], "total_new": 0}
            markets_sync_stats = {"deleted": 0, "upserted": 0, "total_existing": stats['markets']['total'], "total_new": 0, "filtered_from": 0}
        
        # 如果设置了仅同步模式，则退出
        if args.sync_only:
            logger.info("仅同步模式，跳过交易执行")
            return 0
        
        # 获取时间缓冲配置
        buffer_minutes = config.get("trading", {}).get("market_close_buffer_minutes", 1440.0)
        enable_time_buffer = config.get("trading", {}).get("enable_time_buffer", True)
        
        logger.info(f"时间缓冲配置: {buffer_minutes} 分钟 ({buffer_minutes/60:.1f} 小时), 启用: {enable_time_buffer}")
        
        # 执行新交易决策并立即执行交易
        logger.info("开始执行交易决策并立即执行")
        trading_stats = trader.process_trading_decision(buffer_minutes, enable_time_buffer, polymarket, loop)
        
        logger.info(f"新交易决策执行完成 - 处理markets: {trading_stats['total_markets_processed']}, 有交易markets: {trading_stats['markets_with_trades']}, 执行交易: {trading_stats['total_trades_executed']}")
        logger.debug(f"新交易详情: 创建 {trading_stats['total_trades_created']}, 保存 {trading_stats['total_trades_saved']}")
        
        # 显示成功执行的交易统计（从数据库查询）
        if trading_stats['total_trades_saved'] > 0:
            logger.info("开始显示成功执行的交易统计")
            # 获取所有交易数据用于显示
            all_trades = trader.db.get_all_trades_by_market()
            markets_with_trades = 0
            total_trades_count = 0
            
            for market_id, market_data in all_trades.items():
                # 只显示最近处理的markets
                if 'market_info' in market_data:
                    total_trades = sum(len(outcome_data.get('Trades', [])) for outcome_type, outcome_data in market_data.items() if outcome_type != 'market_info')
                    if total_trades > 0:
                        markets_with_trades += 1
                        total_trades_count += total_trades
                        
                        # 显示市场信息
                        market_info = market_data.get('market_info', {})
                        if market_info:
                            logger.debug(f"Market {market_id}: {market_info.get('market_question', 'N/A')} - {total_trades} 个交易")
                            
                            # 显示事件标签
                            event_tags = market_info.get('event_tags', [])
                            if event_tags:
                                tag_labels = [tag.get('label', tag.get('slug', '')) for tag in event_tags if tag]
                                logger.debug(f"Market {market_id} 事件标签: {', '.join(tag_labels) if tag_labels else 'N/A'}")
                        
                        for outcome_type, outcome_data in market_data.items():
                            if outcome_type == 'market_info':
                                continue
                                
                            trades = outcome_data.get('Trades', [])
                            token_id = outcome_data.get('TokenID', '')
                            logger.debug(f"Market {market_id} {outcome_type} 交易: {len(trades)} 个, TokenID: {token_id}")
                            
                            for i, trade in enumerate(trades, 1):
                                logger.debug(f"Market {market_id} {outcome_type} 交易 {i}: ID={trade.id}, 方向={trade.side}, 价格={trade.price}, 份额={trade.shares}, 金额={trade.amount}, 状态={trade.status}")
                        
                        # 显示该market的汇总信息
                        summary = trader.get_market_trade_summary(int(market_id))
                        logger.debug(f"Market {market_id} 汇总: 总份额={summary['total_volume']:.2f}, 平均价格={summary['average_price']:.4f}, 总金额={summary['total_value']:.2f}")
            
            logger.info(f"交易统计完成 - 有交易的markets: {markets_with_trades}, 总交易数: {total_trades_count}")
        else:
            logger.info("没有成功执行的交易")
        
        
    except Exception as e:
        logger.error(f"运行过程中发生错误: {e}")
        import traceback
        logger.error(f"错误详情: {traceback.format_exc()}")
        return 1
    
    logger.info("Polymarket 交易机器人运行完成")
    return 0


if __name__ == "__main__":
    exit(main())
