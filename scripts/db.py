#!/usr/bin/env python3
"""
德州扑克数据管理系统 - 数据库操作模块
"""

import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "poker.db")

def get_connection():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表结构"""
    conn = get_connection()
    cursor = conn.cursor()

    # 玩家表 - 存储昵称和别名映射（nickname 唯一）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT UNIQUE NOT NULL,
            alias TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 每日汇总表 - 用player_nickname唯一标识
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_pnl (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            player_nickname TEXT NOT NULL,
            total_buy_in INTEGER DEFAULT 0,
            total_buy_out INTEGER DEFAULT 0,
            total_stack INTEGER DEFAULT 0,
            total_net INTEGER DEFAULT 0,
            total_sessions INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, player_nickname)
        )
    """)

    # 原始账本表 - 存储清洗后的原始数据
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            player_nickname TEXT NOT NULL,
            player_id TEXT NOT NULL,
            session_start_at TEXT,
            session_end_at TEXT,
            buy_in INTEGER DEFAULT 0,
            buy_out INTEGER DEFAULT 0,
            stack INTEGER DEFAULT 0,
            net INTEGER DEFAULT 0,
            source_file TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_pnl_date ON daily_pnl(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_pnl_player ON daily_pnl(player_nickname)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_date ON ledger(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_player ON ledger(player_nickname)")

    conn.commit()
    conn.close()
    print(f"数据库初始化完成: {DB_PATH}")

# ========== 玩家别名管理接口 ==========

def AddPlayerMapping(nickname: str, alias: str) -> tuple:
    """
    添加玩家昵称映射，并更新历史数据中使用该别名的记录

    Args:
        nickname: 真实昵称
        alias: 别名

    Returns:
        tuple: (success, updated_count)
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. 插入或更新 players 表
        cursor.execute("""
            INSERT INTO players (nickname, alias)
            VALUES (?, ?)
            ON CONFLICT(nickname) DO UPDATE SET
                alias = excluded.alias
        """, (nickname, alias))

        # 2. 合并 daily_pnl 中的记录（如果目标昵称已存在）
        # 先检查目标昵称是否存在
        cursor.execute("""
            SELECT date, SUM(total_buy_in) as total_buy_in, SUM(total_buy_out) as total_buy_out,
                   SUM(total_stack) as total_stack, SUM(total_net) as total_net,
                   SUM(total_sessions) as total_sessions
            FROM daily_pnl
            WHERE player_nickname IN (?, ?)
            GROUP BY date
        """, (nickname, alias))
        merged_records = cursor.fetchall()

        # 删除原有的两条记录
        cursor.execute("DELETE FROM daily_pnl WHERE player_nickname IN (?, ?)", (nickname, alias))

        # 插入合并后的记录
        for row in merged_records:
            cursor.execute("""
                INSERT INTO daily_pnl (date, player_nickname, total_buy_in, total_buy_out, total_stack, total_net, total_sessions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (row['date'], nickname, row['total_buy_in'], row['total_buy_out'],
                  row['total_stack'], row['total_net'], row['total_sessions']))

        updated_pnl = len(merged_records)

        # 3. 合并 ledger 中的记录
        cursor.execute("""
            UPDATE ledger
            SET player_nickname = ?
            WHERE player_nickname = ?
        """, (nickname, alias))

        cursor.execute("""
            SELECT COUNT(*) as cnt FROM ledger WHERE player_nickname = ?
        """, (alias,))
        row = cursor.fetchone()
        updated_ledger = row['cnt'] if row else 0

        conn.commit()
        return (True, updated_pnl + updated_ledger)

    except Exception as e:
        conn.rollback()
        print(f"添加玩家映射失败: {e}")
        return (False, 0)
    finally:
        conn.close()


def GetPlayerByNickname(nickname: str) -> Optional[Dict[str, Any]]:
    """根据昵称获取玩家信息"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM players WHERE nickname = ?", (nickname,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def GetAllPlayers() -> List[Dict[str, Any]]:
    """获取所有玩家信息"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM players ORDER BY nickname")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def GetPlayerAliases() -> List[Dict[str, Any]]:
    """获取所有玩家和别名映射（用于下拉选择）"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nickname, alias FROM players ORDER BY nickname")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ========== 每日PNL数据接口 ==========

def SaveDailyPnl(date: str, player_nickname: str, total_buy_in: int, total_buy_out: int,
                 total_stack: int, total_net: int, total_sessions: int) -> bool:
    """保存或更新每日PNL数据"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO daily_pnl (date, player_nickname, total_buy_in, total_buy_out, total_stack, total_net, total_sessions)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, player_nickname) DO UPDATE SET
                total_buy_in = excluded.total_buy_in,
                total_buy_out = excluded.total_buy_out,
                total_stack = excluded.total_stack,
                total_net = excluded.total_net,
                total_sessions = excluded.total_sessions
        """, (date, player_nickname, total_buy_in, total_buy_out, total_stack, total_net, total_sessions))
        conn.commit()
        return True
    except Exception as e:
        print(f"保存每日PNL失败: {e}")
        return False
    finally:
        conn.close()


def QueryPnlRecord(date: str, player_nickname: str = None) -> List[Dict[str, Any]]:
    """查询每日PNL记录"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if player_nickname:
            cursor.execute("""
                SELECT * FROM daily_pnl
                WHERE date = ? AND player_nickname = ?
                ORDER BY total_net DESC
            """, (date, player_nickname))
        else:
            cursor.execute("""
                SELECT * FROM daily_pnl
                WHERE date = ?
                ORDER BY total_net DESC
            """, (date,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def GetAllDates() -> List[str]:
    """获取所有有数据的日期"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT date FROM daily_pnl ORDER BY date DESC")
        return [row['date'] for row in cursor.fetchall()]
    finally:
        conn.close()


# ========== 原始账本数据接口 ==========

def SaveLedger(date: str, records: List[Dict[str, Any]], source_file: str = None) -> bool:
    """批量保存原始账本数据"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 先删除当日数据
        cursor.execute("DELETE FROM ledger WHERE date = ?", (date,))
        # 批量插入
        for r in records:
            cursor.execute("""
                INSERT INTO ledger (date, player_nickname, player_id, session_start_at, session_end_at,
                                   buy_in, buy_out, stack, net, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (date, r.get('player_nickname'), r.get('player_id'),
                  r.get('session_start_at'), r.get('session_end_at'),
                  r.get('buy_in', 0), r.get('buy_out', 0), r.get('stack', 0),
                  r.get('net', 0), source_file))
        conn.commit()
        return True
    except Exception as e:
        print(f"保存账本失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def QueryLedger(date: str, player_nickname: str = None) -> List[Dict[str, Any]]:
    """查询原始账本记录"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if player_nickname:
            cursor.execute("""
                SELECT * FROM ledger
                WHERE date = ? AND player_nickname = ?
                ORDER BY session_start_at
            """, (date, player_nickname))
        else:
            cursor.execute("SELECT * FROM ledger WHERE date = ? ORDER BY session_start_at", (date,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def ImportLedgerFiles(date: str, ledger_dir: str, alias_map: Dict[str, str] = None) -> bool:
    """导入指定日期的所有ledger文件并清洗数据"""
    import glob
    import csv

    date_formatted = f"20{date[2:4]}-{date[4:6]}-{date[6:8]}"  # YYYY-MM-DD

    pattern = os.path.join(ledger_dir, "ledger_*.csv")
    files = glob.glob(pattern)

    if not files:
        print(f"未找到ledger文件: {pattern}")
        return False

    all_records = []

    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                original_nickname = row['player_nickname']
                original_player_id = row['player_id']

                # 查询 players 表获取映射
                player_info = GetPlayerByNickname(original_nickname)
                if player_info and player_info.get('alias'):
                    # 如果有别名映射，使用别名作为标准名
                    clean_nickname = player_info['nickname']
                else:
                    clean_nickname = original_nickname

                record = {
                    'player_nickname': clean_nickname,
                    'player_id': original_player_id,
                    'session_start_at': row.get('session_start_at'),
                    'session_end_at': row.get('session_end_at'),
                    'buy_in': int(row['buy_in']) if row.get('buy_in') else 0,
                    'buy_out': int(row['buy_out']) if row.get('buy_out') else 0,
                    'stack': int(row['stack']) if row.get('stack') else 0,
                    'net': int(row['net']) if row.get('net') else 0,
                }
                all_records.append(record)

    if SaveLedger(date_formatted, all_records):
        print(f"成功导入 {len(all_records)} 条账本记录")
        return True
    return False


def CalculateDailyPnl(date: str) -> bool:
    """根据ledger数据计算每日PNL并保存（按昵称合并）"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT player_nickname,
                   SUM(buy_in) as total_buy_in,
                   SUM(buy_out) as total_buy_out,
                   SUM(stack) as total_stack,
                   SUM(net) as total_net,
                   COUNT(*) as total_sessions
            FROM ledger
            WHERE date = ?
            GROUP BY player_nickname
        """, (date,))

        for row in cursor.fetchall():
            SaveDailyPnl(
                date=date,
                player_nickname=row['player_nickname'],
                total_buy_in=row['total_buy_in'],
                total_buy_out=row['total_buy_out'],
                total_stack=row['total_stack'],
                total_net=row['total_net'],
                total_sessions=row['total_sessions']
            )

        print(f"成功计算 {date} 的每日PNL")
        return True
    except Exception as e:
        print(f"计算每日PNL失败: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
