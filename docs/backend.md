# 后端接口文档

## 基础信息

- 端口：8080
- 基础路径：`/api`

## 接口列表

### 1. 获取玩家映射列表

```
GET /api/players
```

返回所有 nickname ↔ alias 映射关系。

**响应示例：**
```json
[
  {"id": 1, "nickname": "wjh", "alias": "wjh123", "created_at": "2026-02-15 11:17:05"}
]
```

### 2. 添加玩家映射

```
POST /api/players
```

**请求体：**
```json
{
  "nickname": "新昵称",
  "alias": "别名"
}
```

**说明：**
- alias 不能被其他 nickname 使用
- 添加映射后会自动合并历史 PnL 数据

### 3. 获取所有玩家（用于下拉选择）

```
GET /api/players/all
```

返回所有在 daily_pnl 中出现过的玩家昵称（去重）。

### 4. 获取指定日期的 PnL

```
GET /api/pnl/<date>
```

**参数：**
- `date`：日期，格式 YYYY-MM-DD
- `player`（可选）：玩家昵称筛选

**响应示例：**
```json
[
  {"date": "2026-02-14", "player_nickname": "wjh", "total_net": 1328}
]
```

### 5. 获取累计 PnL（单个玩家）

```
GET /api/pnl/range/cumulative
```

**参数：**
- `start`：开始日期
- `end`：结束日期
- `player`（可选）：玩家昵称

**响应示例：**
```json
[
  {"date": "2026-02-13", "total_net": 489, "cumulative_net": 489},
  {"date": "2026-02-14", "total_net": 839, "cumulative_net": 1328}
]
```

### 6. 获取所有玩家的累计 PnL

```
GET /api/pnl/range/all
```

**参数：**
- `start`：开始日期
- `end`：结束日期

**响应示例：**
```json
{
  "dates": ["2026-02-13", "2026-02-14"],
  "players": {
    "wjh": [
      {"date": "2026-02-13", "player_nickname": "wjh", "total_net": 489, "cumulative_net": 489}
    ],
    "Nuo": [...]
  }
}
```

### 7. 获取所有有数据的日期

```
GET /api/dates
```

**响应示例：**
```json
["2026-02-13", "2026-02-14", "2026-02-15"]
```

### 8. 上传 Ledger CSV

```
POST /api/ledger/upload
```

**表单字段：**
- `file`：CSV 文件
- `date`：日期（YYYY-MM-DD）

**CSV 格式：**
| 字段 | 说明 |
|------|------|
| player_nickname | 玩家昵称 |
| session_start_at | 开始时间 |
| session_end_at | 结束时间 |
| buy_in | 买入金额 |
| buy_out | 退出金额 |
| stack | 剩余筹码 |
| net | 净盈亏 |

### 9. 删除记录

```
POST /api/delete
```

**请求体：**
```json
{
  "start_date": "2026-02-13",
  "end_date": "2026-02-14",
  "delete_pnl": true,
  "delete_ledger": true
}
```

**响应示例：**
```json
{
  "success": true,
  "deleted_pnl": 30,
  "deleted_ledger": 50
}
```
