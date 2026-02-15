#!/usr/bin/env python3
"""
检查当日pnl数据是否平账
德州扑克是零和游戏，所有玩家的净盈亏(net)总和应该为0
"""

import os
import sys
from datetime import datetime
import csv

def get_project_root():
    """获取项目根目录"""
    current = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(os.path.dirname(current)))

def find_pnl_file(date_str):
    """查找指定日期的pnl_daily.csv文件"""
    project_root = get_project_root()
    pnl_file = os.path.join(project_root, "daily", date_str, "pnl_daily.csv")

    if os.path.exists(pnl_file):
        return pnl_file
    return None

def parse_pnl_daily(file_path):
    """解析pnl_daily.csv文件，返回玩家统计"""
    players = []

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            players.append({
                'nickname': row['player_nickname'],
                'net': int(row['total_net']),
                'player_id': row['player_id'],
                'buy_in': int(row['total_buy_in']),
                'buy_out': int(row['total_buy_out']),
                'stack': int(row['total_stack']),
                'sessions': int(row['total_sessions'])
            })

    return players

def check_balance(date_str):
    """检查指定日期的pnl是否平账"""
    pnl_file = find_pnl_file(date_str)

    if not pnl_file:
        print(f"错误：未找到日期 {date_str} 的pnl_daily.csv文件")
        print(f"请确认目录 daily/{date_str}/ 存在且包含 pnl_daily.csv 文件")
        sys.exit(1)

    print(f"检查日期: {date_str}")
    print(f"汇总文件: daily/{date_str}/pnl_daily.csv")
    print("=" * 60)

    players = parse_pnl_daily(pnl_file)

    # 计算总计
    total_buy_in = sum(p['buy_in'] for p in players)
    total_buy_out = sum(p['buy_out'] for p in players)
    total_stack = sum(p['stack'] for p in players)
    total_net = sum(p['net'] for p in players)

    print(f"\n【汇总统计】")
    print(f"  总买入:   {total_buy_in:>10}")
    print(f"  总退出:   {total_buy_out:>10}")
    print(f"  总剩余:   {total_stack:>10}")
    print(f"  总净盈亏: {total_net:>10}")

    # 检查是否平账
    print("\n【平账检查】")
    if total_net == 0:
        print("  ✅ 平账成功！总净盈亏为 0")
    else:
        print(f"  ❌ 未平账！总净盈亏为 {total_net}")

    # 显示每人明细
    print("\n【玩家明细】")
    print(f"{'昵称':<12} {'ID':<15} {'买入':>8} {'退出':>8} {'剩余':>8} {'净盈亏':>8} {'场次':>4}")
    print("-" * 80)

    sorted_players = sorted(players, key=lambda x: x['net'], reverse=True)
    for p in sorted_players:
        print(f"{p['nickname']:<12} {p['player_id']:<15} {p['buy_in']:>8} {p['buy_out']:>8} {p['stack']:>8} {p['net']:>8} {p['sessions']:>4}")

    print("-" * 80)
    print(f"{'合计':<12} {'':<15} {total_buy_in:>8} {total_buy_out:>8} {total_stack:>8} {total_net:>8} {len(players):>4}")

    return total_net == 0

def main():
    # 默认使用当天日期
    date_str = datetime.now().strftime("%Y%m%d")

    # 如果传入了日期参数
    if len(sys.argv) > 1:
        date_str = sys.argv[1]

    check_balance(date_str)

if __name__ == "__main__":
    main()
