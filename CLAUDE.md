# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

德州扑克2026春节数据记录项目，用于维护过年期间所有用户的德州扑克盈亏统计。

## Directory Structure

```
2026spring/
├── origindata/                  # 原始数据目录（只读）
│   └── 20260213/              # 原始账本和日志
│   └── 20260214/
├── daily/                      # 每日pnl汇总目录
│   └── 20260213/
│       └── pnl_daily.csv     # 每日用户pnl汇总表
├── data/
│   └── poker.db               # SQLite数据库
├── scripts/
│   └── db.py                  # 数据库操作模块
├── .claude/skills/            # 自定义技能
│   └── check-balance/         # 平账检查脚本
└── CLAUDE.md                   # 本文件
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
