#!/usr/bin/env python3
"""
合并同一玩家的多行数据，将数值字段汇总到 session_start 最早的那一行

用法: python merge_ledger.py <输入文件> [输出文件]
     python merge_ledger.py ledger_2.csv  # 输出 ledger_2_merged.csv
     python merge_ledger.py ledger_2.csv output.csv  # 输出 output.csv
"""

import csv
import os
import sys
from datetime import datetime
from collections import defaultdict


def parse_datetime(dt_str):
    """解析 ISO 8601 格式的时间字符串"""
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    except:
        return None


def main():
    if len(sys.argv) < 2:
        print("用法: python merge_ledger.py <输入文件> [输出文件]")
        sys.exit(1)

    input_file = sys.argv[1]

    if len(sys.argv) >= 3:
        output_file = sys.argv[2]
    else:
        # 默认输出到同目录，原文件名 + _merged.csv
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_merged.csv"
    # 读取所有数据
    rows = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # 按玩家分组
    player_groups = defaultdict(list)
    for row in rows:
        player_groups[row['player_nickname']].append(row)

    # 合并每个玩家的数据
    merged_rows = []
    for nickname, group in player_groups.items():
        if len(group) == 1:
            # 只有一个session，直接保留
            merged_rows.append(group[0])
        else:
            # 找到 session_start 最小的行
            min_start_row = min(group, key=lambda r: parse_datetime(r['session_start_at']) or datetime.max)

            # 计算汇总值（保持浮点数格式）
            total_buy_in = sum(float(r['buy_in']) for r in group if r['buy_in'])
            total_buy_out = sum(float(r['buy_out']) for r in group if r['buy_out'])
            total_stack = sum(float(r['stack']) for r in group if r['stack'])
            total_net = sum(float(r['net']) for r in group if r['net'])

            # 更新主行
            merged_row = min_start_row.copy()

            def fmt(x):
                if x == int(x):
                    return str(int(x))
                # 四舍五入到2位小数，去掉多余的0
                return f"{round(x, 2):g}"

            merged_row['buy_in'] = fmt(total_buy_in)
            merged_row['buy_out'] = fmt(total_buy_out)
            merged_row['stack'] = fmt(total_stack)
            merged_row['net'] = fmt(total_net)

            # session_end_at 取最大的
            max_end = None
            max_end_dt = None
            for r in group:
                end_dt = parse_datetime(r['session_end_at'])
                if end_dt and (max_end_dt is None or end_dt > max_end_dt):
                    max_end_dt = end_dt
                    max_end = r['session_end_at']
            if max_end:
                merged_row['session_end_at'] = max_end

            merged_rows.append(merged_row)

            print(f"合并玩家 {nickname}: {len(group)} 条记录")
            print(f"  buy_in: {total_buy_in}, buy_out: {total_buy_out}, stack: {total_stack}, net: {total_net}")

    # 按 session_start_at 排序
    merged_rows.sort(key=lambda r: parse_datetime(r['session_start_at']) or datetime.max)

    # 写入输出文件
    fieldnames = ['player_nickname', 'player_id', 'session_start_at', 'session_end_at',
                  'buy_in', 'buy_out', 'stack', 'net']
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged_rows)

    print(f"\n合并完成: {len(rows)} 条 -> {len(merged_rows)} 条")
    print(f"输出文件: {output_file}")


if __name__ == "__main__":
    main()
