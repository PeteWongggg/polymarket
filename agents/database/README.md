# 数据库模块

这个模块提供了本地SQLite数据库的增删改查功能，用于存储Polymarket的events和markets数据。

## 功能特性

- **Events表**: 存储所有Polymarket事件信息
- **Markets表**: 存储所有市场信息
- **自动同步**: 支持增量更新，自动删除已关闭/已归档的数据
- **按ID查询**: 支持根据ID快速查询events和markets
- **数据统计**: 提供详细的数据库统计信息

## 使用方法

### 1. 基本使用

```python
from agents.database import Database

# 初始化数据库
db = Database("./data")

# 获取数据库统计信息
stats = db.get_database_stats()
print(f"Events: {stats['events']['total']} 个")
print(f"Markets: {stats['markets']['total']} 个")
```

### 2. 查询数据

```python
# 根据ID查询event
event = db.get_event_by_id("11421")
if event:
    print(f"Event: {event.title}")

# 根据ID查询market
market = db.get_market_by_id(12345)
if market:
    print(f"Market: {market.question}")

# 获取所有events
all_events = db.get_all_events()
print(f"总共有 {len(all_events)} 个events")

# 获取所有markets
all_markets = db.get_all_markets()
print(f"总共有 {len(all_markets)} 个markets")
```

### 3. 同步数据

```python
# 同步events数据
events_sync_stats = db.sync_events(new_events)
print(f"删除: {events_sync_stats['deleted']} 个")
print(f"更新/新增: {events_sync_stats['upserted']} 个")

# 同步markets数据（只保存对应event在数据库中的markets）
existing_event_ids = {event.id for event in db.get_all_events()}
markets_sync_stats = db.sync_markets(new_markets, existing_event_ids)
print(f"删除: {markets_sync_stats['deleted']} 个")
print(f"更新/新增: {markets_sync_stats['upserted']} 个")
```

## 数据库结构

### Events表字段

- `id`: 事件ID（主键）
- `title`: 事件标题
- `ticker`: 事件代码
- `slug`: 事件URL标识
- `active`: 是否活跃
- `closed`: 是否已关闭
- `archived`: 是否已归档
- `liquidity`: 流动性
- `volume`: 交易量
- `tags`: 标签（JSON格式）
- `markets`: 关联的市场（JSON格式）
- `last_updated`: 最后更新时间

### Markets表字段

- `id`: 市场ID（主键）
- `question`: 市场问题
- `conditionId`: 条件ID
- `active`: 是否活跃
- `closed`: 是否已关闭
- `archived`: 是否已归档
- `liquidity`: 流动性
- `volume`: 交易量
- `outcome`: 结果选项（JSON格式）
- `outcomePrices`: 结果价格（JSON格式）
- `events`: 关联的事件（JSON格式）
- `last_updated`: 最后更新时间

## 配置

数据库路径在 `config.yaml` 中配置：

```yaml
db:
  path: "./data"
```

## 注意事项

1. 数据库文件会自动创建在指定路径下
2. 支持增量更新，已关闭或已归档的数据会被自动删除
3. Markets只会保存对应event在数据库中的markets
4. 所有复杂对象（如tags、markets等）都以JSON格式存储
5. 布尔值字段在数据库中存储为整数（0/1）
