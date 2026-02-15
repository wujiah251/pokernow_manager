# check-balance

检查指定日期的pnl数据是否平账。

德州扑克是零和游戏，所有玩家的净盈亏(net)总和应该为0。

## 目录结构

```
2026spring/
├── daily/
│   └── 20260213/
│       └── pnl_daily.csv    # 每日pnl汇总
├── 20260213/
│   └── ledger_*.csv        # 原始账本
└── .claude/skills/check-balance/
    └── script.py
```

## 使用方式

```bash
python3 .claude/skills/check-balance/script.py [日期]
```

- 日期可选，格式为 YYYYMMDD，默认当天日期

## 输出示例

```
检查日期: 20260213
汇总文件: daily/20260213/pnl_daily.csv
============================================================

【汇总统计】
  总买入:       86889
  总退出:       84196
  总剩余:        2693
  总净盈亏:         0

【平账检查】
  ✅ 平账成功！总净盈亏为 0
```
