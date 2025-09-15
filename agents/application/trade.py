
import random
import time
from typing import List, Optional, Dict, Any
from agents.database import Database
from agents.utils.objects import Trade, Market, SimpleEvent
from agents.utils.utils import should_skip_trading_due_to_time_buffer
from agents.loop.main_loop import Loop


class Trader:
    def __init__(self, db: Database, logger=None):
        """
        初始化交易者
        
        Args:
            db: 已初始化的数据库实例
            logger: 日志记录器
        """
        self.logger = logger
        self.db = db
        self.trades: List[Trade] = []
    
    
    def calculate_shares_balance(self, market_id: str) -> Dict[str, int]:
        """
        计算指定market的'Yes'和'No'的shares余额
        
        Args:
            market_id: 市场ID
            
        Returns:
            包含'Yes'和'No'余额的字典
        """
        # 获取market的交易数据
        market_data = self.db.get_trades_by_market(market_id)
        if not market_data:
            return {'Yes': 0, 'No': 0}
        
        balances = {'Yes': 0, 'No': 0}
        
        for outcome_type in ['Yes', 'No']:
            if outcome_type in market_data:
                outcome_data = market_data[outcome_type]
                trades = outcome_data.get('Trades', [])
                
                balance = 0
                for trade in trades:
                    if trade.status == 'EXECUTED':  # 只计算已执行的交易
                        shares = int(float(trade.shares))
                        if trade.side == 'BUY':
                            balance += shares  # 买入增加余额
                        elif trade.side == 'SELL':
                            balance -= shares  # 卖出减少余额
                
                balances[outcome_type] = balance
                if self.logger:
                    self.logger.debug(f"{outcome_type} 余额计算: {balance} shares")
        
        return balances
    
    def update_market_balances(self, market_id: str) -> Dict[str, int]:
        """
        更新指定market的shares余额（直接访问数据库）
        
        Args:
            market_id: 市场ID
            
        Returns:
            更新后的余额字典 {'Yes': balance, 'No': balance}
        """
        if self.logger:
            self.logger.debug(f"直接更新 Market {market_id} 的余额")
        balances = self.db.update_market_balances_direct(market_id)
        if self.logger:
            self.logger.info(f"Market {market_id} 余额更新完成: Yes={balances['Yes']} shares, No={balances['No']} shares")
        return balances
    
    def filter_closed_archived_markets(self, markets: List[Market]) -> List[Market]:
        """
        过滤已关闭或归档的markets，并将相关数据迁移到value_history
        
        Args:
            markets: 所有markets列表
            
        Returns:
            过滤后的有效markets列表
        """
        if self.logger:
            self.logger.info("开始过滤已关闭或归档的markets")
        
        filtered_markets = []
        closed_markets = []
        
        for market in markets:
            # 检查market是否关闭或归档
            is_closed = getattr(market, 'closed', False) or False
            is_archived = getattr(market, 'archived', False) or False
            
            if is_closed or is_archived:
                closed_markets.append(market)
                if self.logger:
                    self.logger.info(f"发现已关闭/归档的Market {market.id}: closed={is_closed}, archived={is_archived}")
            else:
                filtered_markets.append(market)
        
        if self.logger:
            self.logger.info(f"过滤结果: 有效markets {len(filtered_markets)}, 已关闭/归档markets {len(closed_markets)}")
        
        # 处理已关闭/归档的markets
        for market in closed_markets:
            market_id = str(market.id)
            
            try:
                # 1. 从markets.db中删除
                success = self.db.delete_market(market_id)
                if success:
                    if self.logger:
                        self.logger.info(f"已从markets.db中删除Market {market_id}")
                else:
                    if self.logger:
                        self.logger.warning(f"从markets.db中删除Market {market_id}失败")
                
                # 2. 检查trades.db中是否存在该market的数据
                market_trades_data = self.db.get_trades_by_market(market_id)
                if market_trades_data:
                    if self.logger:
                        self.logger.info(f"发现Market {market_id}在trades.db中有交易数据，开始迁移到value_history")
                    
                    # 3. 将trades数据迁移到value_history
                    migration_success = self.db.migrate_trades_to_value_history(market_id, market_trades_data)
                    if migration_success:
                        if self.logger:
                            self.logger.info(f"Market {market_id}的交易数据已成功迁移到value_history")
                        
                        # 4. 从trades.db中删除该market的数据
                        delete_success = self.db.delete_trades_by_market(market_id)
                        if delete_success:
                            if self.logger:
                                self.logger.info(f"已从trades.db中删除Market {market_id}的交易数据")
                        else:
                            if self.logger:
                                self.logger.warning(f"从trades.db中删除Market {market_id}的交易数据失败")
                    else:
                        if self.logger:
                            self.logger.error(f"Market {market_id}的交易数据迁移到value_history失败")
                else:
                    if self.logger:
                        self.logger.debug(f"Market {market_id}在trades.db中没有交易数据，无需迁移")
                        
            except Exception as e:
                if self.logger:
                    self.logger.error(f"处理Market {market_id}时发生错误: {e}")
        
        return filtered_markets

    def process_trading_decision(self, buffer_minutes: float = 1440.0, enable_time_buffer: bool = True, polymarket=None, loop: Loop = None) -> Dict[str, int]:
        """
        交易决策并立即执行交易
        
        Args:
            buffer_minutes: 市场关闭前的缓冲时间（分钟）
            enable_time_buffer: 是否启用时间缓冲检查
            polymarket: Polymarket实例用于执行交易
            loop: Loop实例用于处理新市场决策
        
        Returns:
            交易执行统计信息
        """
        if self.logger:
            self.logger.info("开始处理新交易决策并立即执行")
            self.logger.debug(f"时间缓冲配置: {buffer_minutes} 分钟 ({buffer_minutes/60:.1f} 小时)")
            self.logger.debug(f"启用时间缓冲检查: {enable_time_buffer}")
        
        # 获取盘口数据库中所有markets
        all_markets = self.db.get_all_markets()
        if self.logger:
            self.logger.info(f"数据库中有 {len(all_markets)} 个markets")
        
        # 过滤已关闭或归档的markets
        filtered_markets = self.filter_closed_archived_markets(all_markets)
        if self.logger:
            self.logger.info(f"过滤后剩余 {len(filtered_markets)} 个有效markets")
        
        # 不再分新旧，统一遍历并从trades.db判断是否已有交易
        stats = {
            'total_markets_processed': 0,
            'markets_with_trades': 0,
            'total_trades_created': 0,
            'total_trades_executed': 0,
            'total_trades_saved': 0,
            'new_markets_evaluated': 0,
            'existing_markets_evaluated': 0,
            'new_markets_with_trades': 0,
            'existing_markets_with_trades': 0,
            'existing_markets_buys': 0,
            'existing_markets_sells': 0,
            'total_yes_buys': 0,
            'total_yes_sells': 0,
            'total_no_buys': 0,
            'total_no_sells': 0,
        }
        
        
        current_time = int(time.time())

        # 此处开始判断是否进行交易
        for market in filtered_markets:
            # 获取market对应的events
            event_ids = []
            if hasattr(market, 'events') and market.events:
                for event in market.events:
                    try:
                        event_int = int(event.id)
                        event_ids.append(event_int)
                    except (ValueError, TypeError):
                        continue
            market_id = str(market.id)
            stats['total_markets_processed'] += 1
            
            # 检查market的next_process_time（已包含于get_all_markets的返回中）
            next_pt = getattr(market, 'next_process_time', None)
            if next_pt and next_pt > 0:
                if current_time < next_pt:
                    if self.logger:
                        self.logger.debug(f"Market {market_id} 未到处理时间，跳过 (当前: {current_time}, 下次处理: {next_pt})")
                    continue
                else:
                    if self.logger:
                        self.logger.debug(f"Market {market_id} 到达处理时间，开始处理 (当前: {current_time}, 下次处理: {next_pt})")
            else:
                if self.logger:
                    self.logger.debug(f"Market {market_id} next_process_time为0或None，可以立即处理")
            
            # 检查时间缓冲（如果启用）
            if enable_time_buffer and market.endDate:
                if self.logger:
                    self.logger.debug(f"检查 Market {market_id} 的时间缓冲")
                    self.logger.debug(f"市场结束时间: {market.endDate}")
                    self.logger.debug(f"配置缓冲阈值: {buffer_minutes} 分钟")
                if should_skip_trading_due_to_time_buffer(market.endDate, buffer_minutes):
                    print(f"  ❌ Market {market_id} 在缓冲时间内关闭，跳过新交易")
                    continue
                else:
                    if self.logger:
                        self.logger.debug(f"Market {market_id} 不在缓冲时间内，继续处理")
            elif not enable_time_buffer:
                if self.logger:
                    self.logger.debug(f"Market {market_id}: 时间缓冲检查已禁用，继续处理")
            elif not market.endDate:
                if self.logger:
                    self.logger.debug(f"Market {market_id}: 无结束时间信息，继续处理")
            
            # 使用loop进行决策（根据是否已有交易分流）
            decision_result = None
            simple_event = None
            if not loop:
                if self.logger:
                    self.logger.debug(f"没有提供loop实例，跳过 Market {market_id}")
                continue
            
            # 统一处理：一开始就读取trades.db，如果存在就用现有数据，不存在就创建空结构
            market_trades_struct = self.db.get_trades_by_market_struct(market_id)
            has_existing_trades = False
            
            if not market_trades_struct:
                # 如果没有现有交易数据，创建空的MarketTrades结构
                from agents.utils.objects import MarketTrades, OutcomeTradesData, MarketInfo
                
                # 获取market的clobTokenIds
                if not market.clobTokenIds or len(market.clobTokenIds) < 2:
                    if self.logger:
                        self.logger.warning(f"Market {market_id} 没有足够的clobTokenIds，跳过")
                    continue
                
                yes_token_id = market.clobTokenIds[0]
                no_token_id = market.clobTokenIds[1]
                
                # 获取event信息（基于第一个event ID）
                event_title = ""
                event_description = ""
                event_tags = []
                
                if event_ids and len(event_ids) > 0:
                    first_event_id = event_ids[0]
                    simple_event = self.db.get_event_by_id(str(first_event_id))
                    if simple_event:
                        event_title = simple_event.title or ""
                        event_description = simple_event.description or ""
                        event_tags = [tag.dict() for tag in simple_event.tags] if simple_event.tags else []
                
                # 创建空的MarketTrades结构
                market_trades_struct = MarketTrades(
                    Yes=OutcomeTradesData(TokenID=yes_token_id, Trades=[], balance=0),
                    No=OutcomeTradesData(TokenID=no_token_id, Trades=[], balance=0),
                    market_info=MarketInfo(
                        market_question=market.question or "",
                        market_description=market.description or "",
                        event_title=event_title,
                        event_description=event_description,
                        event_tags=event_tags,
                        market_created_at=market.createdAt or "",
                        market_end_date=market.endDate or "",
                        next_process_time=0
                    )
                )
            else:
                # 有现有交易数据
                yes_trades = market_trades_struct.Yes.Trades
                no_trades = market_trades_struct.No.Trades
                has_existing_trades = (len(yes_trades) + len(no_trades)) > 0
            
            # 根据是否有现有交易选择处理方式
            if has_existing_trades:
                stats['existing_markets_evaluated'] += 1
                try:
                    decision_result = loop.process_existing_market(market_trades_struct)
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"调用process_existing_market失败: {e}")
                    continue
            else:
                stats['new_markets_evaluated'] += 1
                # 新潜在交易，调用process_new_market
                if market.events and len(market.events) > 0:
                    event = market.events[0]
                    simple_event = event.to_simple_event()
                if not simple_event:
                    if self.logger:
                        self.logger.warning(f"Market {market_id} 没有有效的event信息，跳过")
                    continue
                decision_result = loop.process_new_market(market, simple_event)
            
            # 决策结果统计日志
            should_trade_yes = decision_result.Yes.should_trade
            should_trade_no = decision_result.No.should_trade
            if should_trade_yes or should_trade_no:
                if self.logger:
                    self.logger.info(f"Loop决定交易 Market {market_id} - Yes: {should_trade_yes}, No: {should_trade_no}")
                stats['markets_with_trades'] += 1
                if has_existing_trades:
                    stats['existing_markets_with_trades'] += 1
                else:
                    stats['new_markets_with_trades'] += 1
            else:
                if self.logger:
                    self.logger.debug(f"Loop决定不交易 Market {market_id}")
                
            # 获取market的clobTokenIds
            if not market.clobTokenIds or len(market.clobTokenIds) < 2:
                if self.logger:
                    self.logger.warning(f"Market {market_id} 没有足够的clobTokenIds，跳过")
                continue
            
            yes_token_id = market.clobTokenIds[0]
            no_token_id = market.clobTokenIds[1]
            
            # 直接执行交易
            if polymarket:
                if self.logger:
                    self.logger.info(f"立即执行 Market {market_id} 的交易")
                executed_trades = []
                
                # 根据loop的决策结果执行交易（不再依赖simple_event）
                should_trade_yes = decision_result.Yes.should_trade
                should_trade_no = decision_result.No.should_trade
                yes_amount = decision_result.Yes.amount
                no_amount = decision_result.No.amount
                yes_side = decision_result.Yes.side.upper() if decision_result.Yes.side else "BUY"
                no_side = decision_result.No.side.upper() if decision_result.No.side else "BUY"
                
                # 执行Yes交易
                if should_trade_yes:
                    try:
                        if self.logger:
                            self.logger.debug(f"执行Yes交易: {yes_side} {yes_amount} (TokenID: {yes_token_id})")
                        yes_result = polymarket.execute_market_order_by_token_id(
                            token_id=yes_token_id,
                            amount=yes_amount,
                            side=yes_side
                        )
                        
                        if yes_result and yes_result.get('success', False):
                            if self.logger:
                                self.logger.info(f"Yes交易成功: {yes_result.get('orderID', 'N/A')}")
                            stats['total_trades_executed'] += 1
                            if has_existing_trades:
                                if yes_side == 'BUY':
                                    stats['existing_markets_buys'] += 1
                                    stats['total_yes_buys'] += 1
                                else:
                                    stats['existing_markets_sells'] += 1
                                    stats['total_yes_sells'] += 1
                            
                            # 创建交易记录
                            yes_trade = Trade(
                                id=len(self.trades) + 1,
                                taker_order_id=f"order_{current_time}_{market_id}",
                                market=market_id,
                                asset_id=yes_token_id,
                                side=yes_side,
                                amount=str(yes_result.get('amount', yes_amount)),
                                shares=str(yes_result.get('shares', yes_amount)),
                                fee_rate_bps="1",
                                price=str(float(yes_result.get('amount', yes_amount)) / float(yes_result.get('shares', yes_amount)) if float(yes_result.get('shares', yes_amount)) > 0 else 0),
                                status="EXECUTED",
                                match_time=str(current_time),
                                last_update=str(current_time),
                                outcome="Yes",
                                maker_address="0x0000000000000000000000000000000000000000",
                                owner="0x0000000000000000000000000000000000000000",
                                transaction_hash=yes_result.get('transactionsHashes', [''])[0] if yes_result.get('transactionsHashes') else '',
                                bucket_index=str(random.randint(1, 100)),
                                maker_orders=f"maker_order_{current_time}_{market_id}",
                                type="LIMIT",
                                event_ids=event_ids
                            )
                            executed_trades.append(('Yes', yes_trade))
                            stats['total_trades_created'] += 1
                        else:
                            if self.logger:
                                self.logger.error(f"Yes交易失败: {yes_result}")
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"Yes交易执行异常: {e}")
                    
                # 执行No交易
                if should_trade_no:
                    try:
                        if self.logger:
                            self.logger.debug(f"执行No交易: {no_side} {no_amount} (TokenID: {no_token_id})")
                        no_result = polymarket.execute_market_order_by_token_id(
                            token_id=no_token_id,
                            amount=no_amount,
                            side=no_side
                        )
                        
                        if no_result and no_result.get('success', False):
                            if self.logger:
                                self.logger.info(f"No交易成功: {no_result.get('orderID', 'N/A')}")
                            stats['total_trades_executed'] += 1
                            if has_existing_trades:
                                if no_side == 'BUY':
                                    stats['existing_markets_buys'] += 1
                                    stats['total_no_buys'] += 1
                                else:
                                    stats['existing_markets_sells'] += 1
                                    stats['total_no_sells'] += 1
                            
                            # 创建交易记录
                            no_trade = Trade(
                                id=len(self.trades) + 2,
                                taker_order_id=f"order_{current_time}_{market_id}",
                                market=market_id,
                                asset_id=no_token_id,
                                side=no_side,
                                amount=str(no_result.get('amount', no_amount)),
                                shares=str(no_result.get('shares', no_amount)),
                                fee_rate_bps="1",
                                price=str(float(no_result.get('amount', no_amount)) / float(no_result.get('shares', no_amount)) if float(no_result.get('shares', no_amount)) > 0 else 0),
                                status="EXECUTED",
                                match_time=str(current_time),
                                last_update=str(current_time),
                                outcome="No",
                                maker_address="0x0000000000000000000000000000000000000000",
                                owner="0x0000000000000000000000000000000000000000",
                                transaction_hash=no_result.get('transactionsHashes', [''])[0] if no_result.get('transactionsHashes') else '',
                                bucket_index=str(random.randint(1, 100)),
                                maker_orders=f"maker_order_{current_time}_{market_id}",
                                type="LIMIT",
                                event_ids=event_ids
                            )
                            executed_trades.append(('No', no_trade))
                            stats['total_trades_created'] += 1
                        else:
                            if self.logger:
                                self.logger.error(f"No交易失败: {no_result}")
                    except Exception as e:
                        if self.logger:
                            self.logger.error(f"No交易执行异常: {e}")
                
                # 使用loop决策结果中的next_process_time
                next_process_time = decision_result.next_process_time
                
                # 处理交易保存和next_process_time更新
                if executed_trades:
                    if self.logger:
                        self.logger.info(f"保存 Market {market_id} 的 {len(executed_trades)} 个交易")
                    
                    # 直接将新交易append到现有的market_trades_struct中
                    for outcome_type, trade in executed_trades:
                        if outcome_type == 'Yes':
                            market_trades_struct.Yes.Trades.append(trade)
                        elif outcome_type == 'No':
                            market_trades_struct.No.Trades.append(trade)
                    
                    # 转换为保存格式并保存到trades.db（只保存交易数据）
                    market_data = {
                        'Yes': {
                            'TokenID': market_trades_struct.Yes.TokenID,
                            'Trades': market_trades_struct.Yes.Trades
                        },
                        'No': {
                            'TokenID': market_trades_struct.No.TokenID,
                            'Trades': market_trades_struct.No.Trades
                        }
                    }
                    
                    saved_count = self.db.save_trades_by_market(market_id, market_data)
                    stats['total_trades_saved'] += saved_count
                    
                    if self.logger:
                        self.logger.info(f"Market {market_id} 交易保存完成: {len(executed_trades)} 个交易保存到数据库")
                    
                    # 计算并更新market的shares余额
                    if self.logger:
                        self.logger.debug(f"计算 Market {market_id} 的余额")
                    balances = self.update_market_balances(market_id)
                    if self.logger:
                        self.logger.info(f"Market {market_id} 余额更新完成: Yes={balances['Yes']} shares, No={balances['No']} shares")
                else:
                    if self.logger:
                        self.logger.debug(f"Market {market_id} 没有交易成功执行")
                
                # 无论是否有交易，都更新markets.db中的next_process_time
                success = self.db.update_market_next_process_time(market_id, next_process_time)
                if success:
                    if self.logger:
                        self.logger.debug(f"Market {market_id} markets.db中的next_process_time已更新: {next_process_time}")
                else:
                    if self.logger:
                        self.logger.warning(f"Market {market_id} markets.db中的next_process_time更新失败")
            else:
                if self.logger:
                    self.logger.warning(f"没有提供polymarket实例，跳过交易执行")
        
        if self.logger:
            self.logger.info(f"交易决策处理完成 - 处理markets: {stats['total_markets_processed']}, 有交易markets: {stats['markets_with_trades']}, 执行交易: {stats['total_trades_executed']}")
            self.logger.debug(f"交易详情: 创建 {stats['total_trades_created']}, 保存 {stats['total_trades_saved']}")
        
        return stats
    
    
    def get_trades_by_market(self, market_id: int) -> Dict[str, Dict[str, Any]]:
        """
        获取指定market的所有交易记录 - 支持新的嵌套结构
        
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
        return self.db.get_trades_by_market(str(market_id))
    
    def get_trades_by_event(self, event_id: int) -> List[Trade]:
        """
        获取指定event的所有交易记录
        
        Args:
            event_id: 事件ID
            
        Returns:
            该event的交易列表
        """
        return [trade for trade in self.trades if event_id in trade.event_ids]
    
    def get_pending_trades(self) -> List[Trade]:
        """
        获取需要处理的交易（基于next_process_time）
        
        Returns:
            需要处理的交易列表
        """
        current_time = int(time.time())
        return [trade for trade in self.trades if trade.next_process_time <= current_time]
    
    def get_market_trade_summary(self, market_id: int) -> Dict[str, any]:
        """
        获取指定market的交易汇总信息 - 支持订单簿模式的shares和amount字段
        
        Args:
            market_id: 市场ID
            
        Returns:
            该market的交易汇总信息，包含:
                - total_volume: 总份额数量 (基于shares字段)
                - total_value: 总金额 (基于amount字段)
                - average_price: 平均价格 (total_value / total_volume)
                - 其他统计信息
        """
        market_data = self.get_trades_by_market(market_id)
        
        if not market_data:
            return {
                'market_id': market_id,
                'total_trades': 0,
                'total_volume': 0.0,
                'average_price': 0.0,
                'total_value': 0.0,
                'yes_trades': 0,
                'no_trades': 0
            }
        
        total_trades = 0
        total_volume = 0.0
        total_value = 0.0
        yes_trades = 0
        no_trades = 0
        
        for outcome_type, outcome_data in market_data.items():
            trades = outcome_data.get('Trades', [])
            outcome_count = len(trades)
            
            if outcome_type == 'Yes':
                yes_trades = outcome_count
            elif outcome_type == 'No':
                no_trades = outcome_count
            
            total_trades += outcome_count
            
            for trade in trades:
                shares = float(trade.shares)
                amount = float(trade.amount)
                total_volume += shares
                total_value += amount
        
        average_price = total_value / total_volume if total_volume > 0 else 0.0
        
        return {
            'market_id': market_id,
            'total_trades': total_trades,
            'total_volume': total_volume,
            'average_price': average_price,
            'total_value': total_value,
            'yes_trades': yes_trades,
            'no_trades': no_trades,
            'market_data': market_data
        }


if __name__ == "__main__":
    t = Trader()
    trades = t.process_trading_decision()
    print(f"生成了 {len(trades)} 个交易")
