# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

德州扑克2026春节数据记录项目，用于维护过年期间所有用户的德州扑克盈亏统计。

## Documentation

- [前端功能文档](./docs/frontend.md)
- [后端接口文档](./docs/backend.md)
- [数据库文档](./docs/db.md)

## Start

```
python script/api.py -c config.ini
```

## Directory Structure

```
2026spring/
├── docs/                       # 文档目录
│   ├── frontend.md            # 前端功能文档
│   ├── backend.md             # 后端接口文档
│   └── db.md                 # 数据库文档
├── origindata/                # 原始数据目录（只读）
│   └── 20260213/             # 原始账本和日志
│   └── 20260214/
├── frontend/                  # 前端文件
│   ├── index.html            # 主页面
│   ├── app.js                # Vue 应用
│   ├── styles.css            # 样式
│   └── vue.js                # Vue 本地化
├── data/
│   └── poker.db              # SQLite数据库
├── scripts/
│   ├── api.py                # Flask API 服务
│   └── db.py                 # 数据库操作模块
├── logs/                     # 日志目录
│   └── api.log               # API 日志
└── CLAUDE.md                 # 本文件
```

> ⚠️ origindata 目录为只读，保存原始数据文件，不应修改。

## Data Format

### ledger_XXX.csv (原始账本)
| 字段 | 说明 |
|------|------|
| player_nickname | 玩家昵称 |
| player_id | 玩家唯一ID |
| session_start_at | 开始时间 (ISO 8601格式) |
| session_end_at | 结束时间 |
| buy_in | 买入金额 |
| buy_out | 退出金额 |
| stack | 剩余筹码 |
| net | 净盈亏 (buy_out + stack - buy_in) |

### pnl_daily.csv (每日汇总)

> 按 player_nickname 合并，每人每天一条记录

| 字段 | 说明 |
|------|------|
| date | 日期 (YYYY-MM-DD) |
| player_nickname | 玩家昵称 |
| total_net | 当日总净盈亏 |
| total_buy_in | 当日总买入 |
| total_buy_out | 当日总退出 |
| total_stack | 当日剩余筹码总和 |
| total_sessions | 当日总游戏场次 |

## Adding New Data

1. 每日创建新的日期目录 `YYYYMMDD/`
2. 将原始账本文件放入对应日期目录
3. 更新 `pnl_daily.csv`，按日期和玩家汇总所有session的net值

## Key Conventions

- 日期目录使用 `YYYYMMDD` 格式
- 文件名包含唯一标识符（如日期戳或ID）
- 新增日期数据时，需同步更新pnl_daily.csv的汇总
