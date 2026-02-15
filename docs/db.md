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
