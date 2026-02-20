# 数据库文档

## 数据库文件

```
data/poker.db
```

## 表结构

### 1. players 表

玩家昵称 ↔ 别名映射表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| nickname | TEXT | 玩家昵称（唯一） |
| alias | TEXT | 别名 |
| created_at | TEXT | 创建时间 |

**说明：**
- nickname 唯一
- alias 可用于合并历史数据

### 2. daily_pnl 表

每日玩家盈亏汇总

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| date | TEXT | 日期 (YYYY-MM-DD) |
| player_nickname | TEXT | 玩家昵称 |
| total_buy_in | INTEGER | 当日总买入 |
| total_buy_out | INTEGER | 当日总退出 |
| total_stack | INTEGER | 当日剩余筹码总和 |
| total_net | INTEGER | 当日净盈亏 |
| total_sessions | INTEGER | 当日对局场次 |
| created_at | TEXT | 创建时间 |

**说明：**
- 按 (date, player_nickname) 唯一
- 上传 ledger 后自动计算生成

### 3. ledger 表

原始对局记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| date | TEXT | 日期 (YYYY-MM-DD) |
| player_nickname | TEXT | 玩家昵称 |
| player_id | TEXT | 玩家ID（原始数据） |
| session_start_at | TEXT | 开始时间 |
| session_end_at | TEXT | 结束时间 |
| buy_in | INTEGER | 买入金额 |
| buy_out | INTEGER | 退出金额 |
| stack | INTEGER | 剩余筹码 |
| net | INTEGER | 净盈亏 |
| source_file | TEXT | 来源文件名 |
| created_at | TEXT | 创建时间 |

## 常用查询

### 查看所有玩家映射
```sql
SELECT * FROM players;
```

### 查看指定日期的 PnL
```sql
SELECT * FROM daily_pnl WHERE date = '2026-02-14';
```

### 按日期汇总
```sql
SELECT date, SUM(total_net) as total_net
FROM daily_pnl
GROUP BY date
ORDER BY date;
```

### 查看玩家累计盈亏
```sql
SELECT player_nickname, SUM(total_net) as cumulative
FROM daily_pnl
GROUP BY player_nickname
ORDER BY cumulative DESC;
```

### 4. hands 表

手牌基本信息的核心表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| date | TEXT | 日期 (YYYY-MM-DD) |
| hand_number | INTEGER | 手牌编号 |
| hand_id | TEXT | 手牌唯一ID |
| game_type | TEXT | 游戏类型 (NLHE/27) |
| is_bomb_pot | BOOLEAN | 是否为炸弹底池 |
| dealer | TEXT | 庄家昵称 |
| player_num | INTEGER | 玩家数量 |
| total_pot | INTEGER | 最终底池大小 |
| winner | TEXT | 赢家昵称 |
| winner_profit | INTEGER | 赢家盈利 |
| loser | TEXT | 输家昵称 |
| loser_profit | INTEGER | 输家亏损 |
| action_line | TEXT | 玩家行动线 (JSON格式) |
| source_file | TEXT | 来源文件 |
| created_at | TEXT | 创建时间 |

**说明：**
- 按 (date, hand_number) 唯一
- game_type: NLHE=无限注德州, 27=27游戏（7-2 bounty）

### 5. hand_players 表

每手牌中玩家的详细信息

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| hand_id | INTEGER | 关联 hands 表 |
| player_nickname | TEXT | 玩家昵称 |
| player_alias | TEXT | 玩家别名 |
| starting_stack | INTEGER | 初始筹码 |
| ending_stack | INTEGER | 结束筹码 |
| profit | INTEGER | 净盈亏 |
| position | TEXT | 位置 |
| hole_cards | TEXT | 底牌 |
| is_winner | BOOLEAN | 是否为赢家 |

**说明：**
- 按 (hand_id, player_nickname) 唯一

## 行动线格式 (action_line)

hands 表中的 action_line 字段为 JSON 格式，记录每条街的玩家动作：

```json
{
  "preflop": [
    {"player": "mouyu1021", "action": "blind", "blind_type": "small", "amount": 1},
    {"player": "cy", "action": "blind", "blind_type": "big", "amount": 2},
    {"player": "wjh", "action": "fold"},
    {"player": "hyq", "action": "raise", "amount": 7},
    {"player": "cy", "action": "call", "amount": 7}
  ],
  "flop": [
    {"player": "cy", "action": "check"},
    {"player": "hyq", "action": "bet", "amount": 15},
    {"player": "cy", "action": "call", "amount": 15}
  ],
  "turn": [
    {"player": "cy", "action": "bet", "amount": 20},
    {"player": "hyq", "action": "fold"}
  ],
  "river": []
}
```

### 支持的动作类型

| action | 说明 | 额外字段 |
|--------|------|----------|
| blind | 盲注 | blind_type: small/big, amount |
| fold | 弃牌 | - |
| check | 看牌 | - |
| call | 跟注 | amount |
| bet | 下注 | amount |
| raise | 加注 | amount |
| allin | 全下 | amount |

## 导入手牌数据

从 PokerNow 导出的 poker.csv 导入：

```python
from db import init_db_path, init_db, import_poker_log

init_db_path()
init_db()

# 导入指定日期的 poker.csv
import_poker_log('2026-02-13', 'origindata/20260213/poker.csv')
```

## 常用查询

### 查询某天的所有手牌
```sql
SELECT hand_number, game_type, is_bomb_pot, player_num, total_pot, winner
FROM hands
WHERE date = '2026-02-13'
ORDER BY hand_number;
```

### 查询炸弹底池
```sql
SELECT date, hand_number, winner, total_pot
FROM hands
WHERE is_bomb_pot = 1;
```

### 查询某手牌的行动线
```sql
SELECT hand_number, action_line
FROM hands
WHERE hand_number = 266;
```

### 查询某玩家的所有手牌
```sql
SELECT h.date, h.hand_number, h.winner, h.total_pot
FROM hands h
JOIN hand_players hp ON h.id = hp.hand_id
WHERE hp.player_nickname = 'cy'
ORDER BY h.date, h.hand_number;
```

### 统计每天手牌数
```sql
SELECT date, COUNT(*) as hand_count
FROM hands
GROUP BY date;
```
