#!/usr/bin/env python3
"""
德州扑克数据管理系统 - 数据库操作模块
"""

import os
import sqlite3
import configparser
from datetime import datetime
from typing import Optional, List, Dict, Any

# 全局配置
DB_PATH = None


def init_db_path(config_path: str = None):
    """初始化数据库路径"""
    global DB_PATH
    if config_path and os.path.exists(config_path):
        config = configparser.ConfigParser()
        config.read(config_path)
        base_dir = os.path.dirname(os.path.abspath(config_path))
        DB_PATH = os.path.join(base_dir, config.get('database', 'db_path', fallback='data/poker.db'))
        DB_PATH = os.path.abspath(DB_PATH)
    else:
        DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "poker.db")
        DB_PATH = os.path.abspath(DB_PATH)

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
    添加玩家昵称映射，支持一个 nickname 多个 alias

    Args:
        nickname: 真实昵称
        alias: 别名

    Returns:
        tuple: (success, updated_count, error_msg)
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 直接插入新记录，支持同一个 nickname 多个不同的 alias
        cursor.execute("INSERT INTO players (nickname, alias) VALUES (?, ?)", (nickname, alias))

        # 2. 合并 daily_pnl 中的记录（如果 alias 已有记录）
        # 检查 alias 是否存在于 daily_pnl（即之前用 alias 上传过数据）
        cursor.execute("""
            SELECT date, total_buy_in, total_buy_out, total_stack, total_net, total_sessions
            FROM daily_pnl WHERE player_nickname = ?
        """, (alias,))
        alias_records = cursor.fetchall()

        updated_pnl = 0

        if alias_records:
            # 如果 alias 有记录，合并到 nickname
            for row in alias_records:
                # 检查 nickname 在同一天是否有记录
                cursor.execute("""
                    SELECT id FROM daily_pnl WHERE date = ? AND player_nickname = ?
                """, (row['date'], nickname))
                existing = cursor.fetchone()

                if existing:
                    # 累加到现有记录
                    cursor.execute("""
                        UPDATE daily_pnl SET
                            total_buy_in = total_buy_in + ?,
                            total_buy_out = total_buy_out + ?,
                            total_stack = total_stack + ?,
                            total_net = total_net + ?,
                            total_sessions = total_sessions + ?
                        WHERE date = ? AND player_nickname = ?
                    """, (row['total_buy_in'], row['total_buy_out'], row['total_stack'],
                          row['total_net'], row['total_sessions'], row['date'], nickname))
                else:
                    # 插入新记录
                    cursor.execute("""
                        INSERT INTO daily_pnl (date, player_nickname, total_buy_in, total_buy_out, total_stack, total_net, total_sessions)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (row['date'], nickname, row['total_buy_in'], row['total_buy_out'],
                          row['total_stack'], row['total_net'], row['total_sessions']))

            # 删除 alias 的记录
            cursor.execute("DELETE FROM daily_pnl WHERE player_nickname = ?", (alias,))
            updated_pnl = len(alias_records)

        # 3. 合并 ledger 中的记录
        cursor.execute("""
            UPDATE ledger SET player_nickname = ? WHERE player_nickname = ?
        """, (nickname, alias))

        cursor.execute("""
            SELECT changes() as cnt
        """)
        row = cursor.fetchone()
        updated_ledger = row['cnt'] if row else 0

        conn.commit()
        return (True, updated_pnl + updated_ledger, None)

    except Exception as e:
        conn.rollback()
        print(f"添加玩家映射失败: {e}")
        return (False, 0, str(e))
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


def ResolvePlayerNickname(alias: str) -> Optional[str]:
    """
    将 alias 解析为真实的 nickname（区分大小写）

    Args:
        alias: 必须是 players 表中存在的 alias

    Returns:
        Optional[str: 真实的 nickname，如果 alias 不存在则返回 None
    """
    if not alias:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 只通过 alias 查找（区分大小写）
        cursor.execute("SELECT nickname FROM players WHERE alias = ? COLLATE BINARY", (alias,))
        row = cursor.fetchone()
        if row:
            return row['nickname']

        # alias 不存在
        return None
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


def DeletePlayerMapping(nickname: str) -> tuple:
    """
    删除玩家映射

    Args:
        nickname: 要删除的昵称

    Returns:
        tuple: (success, deleted_count)
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 删除 players 表中的记录
        cursor.execute("DELETE FROM players WHERE nickname = ?", (nickname,))

        conn.commit()
        print(f"删除玩家映射: {nickname}")
        return (True, cursor.rowcount)

    except Exception as e:
        conn.rollback()
        print(f"删除玩家映射失败: {e}")
        return (False, 0)
    finally:
        conn.close()


def RenamePlayer(old_nickname: str, new_nickname: str) -> tuple:
    """
    重命名玩家昵称，并合并所有历史记录到目标昵称

    Args:
        old_nickname: 原昵称
        new_nickname: 目标昵称

    Returns:
        tuple: (success, updated_count)
    """
    if old_nickname == new_nickname:
        return (True, 0)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. 获取 old_nickname 对应的 alias
        cursor.execute("SELECT alias FROM players WHERE nickname = ?", (old_nickname,))
        old_row = cursor.fetchone()
        old_alias = old_row['alias'] if old_row else None

        # 2. 合并 daily_pnl 表：将 old_nickname 的数据加到 new_nickname 上
        # 先获取 old_nickname 的所有日期数据
        cursor.execute("""
            SELECT date, total_buy_in, total_buy_out, total_stack, total_net, total_sessions
            FROM daily_pnl WHERE player_nickname = ?
        """, (old_nickname,))
        old_pnl_records = cursor.fetchall()

        for row in old_pnl_records:
            # 检查目标昵称在该日期是否已有记录
            cursor.execute("""
                SELECT total_buy_in, total_buy_out, total_stack, total_net, total_sessions
                FROM daily_pnl WHERE date = ? AND player_nickname = ?
            """, (row['date'], new_nickname))
            existing = cursor.fetchone()

            if existing:
                # 累加到现有记录
                cursor.execute("""
                    UPDATE daily_pnl SET
                        total_buy_in = total_buy_in + ?,
                        total_buy_out = total_buy_out + ?,
                        total_stack = total_stack + ?,
                        total_net = total_net + ?,
                        total_sessions = total_sessions + ?
                    WHERE date = ? AND player_nickname = ?
                """, (row['total_buy_in'], row['total_buy_out'], row['total_stack'],
                      row['total_net'], row['total_sessions'], row['date'], new_nickname))
            else:
                # 插入新记录
                cursor.execute("""
                    INSERT INTO daily_pnl (date, player_nickname, total_buy_in, total_buy_out, total_stack, total_net, total_sessions)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (row['date'], new_nickname, row['total_buy_in'], row['total_buy_out'],
                      row['total_stack'], row['total_net'], row['total_sessions']))

        # 3. 删除 old_nickname 的 daily_pnl 记录
        cursor.execute("DELETE FROM daily_pnl WHERE player_nickname = ?", (old_nickname,))

        # 4. 更新 ledger 表
        cursor.execute("UPDATE ledger SET player_nickname = ? WHERE player_nickname = ?", (new_nickname, old_nickname))
        updated_ledger = cursor.rowcount

        # 5. 更新 players 表：删除 old_nickname 记录
        cursor.execute("DELETE FROM players WHERE nickname = ?", (old_nickname,))

        conn.commit()
        total_updated = len(old_pnl_records) + updated_ledger
        print(f"合并玩家: {old_nickname} -> {new_nickname}, 更新了 {total_updated} 条记录")
        return (True, total_updated)

    except Exception as e:
        conn.rollback()
        print(f"合并玩家失败: {e}")
        return (False, 0)
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


def EnsurePlayerExists(nickname: str) -> bool:
    """
    确保玩家存在于 players 表中，如果不存在则自动添加

    Args:
        nickname: 玩家昵称

    Returns:
        bool: 是否成功（存在或添加成功）
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 检查是否已存在
        cursor.execute("SELECT id FROM players WHERE nickname = ?", (nickname,))
        if cursor.fetchone():
            return True

        # 不存在则添加
        cursor.execute("INSERT INTO players (nickname) VALUES (?)", (nickname,))
        conn.commit()
        print(f"自动添加新玩家: {nickname}")
        return True
    except Exception as e:
        print(f"自动添加玩家失败: {e}")
        return False
    finally:
        conn.close()


def CheckPlayerMapping(aliases: List[str]) -> List[str]:
    """
    检查哪些 alias 没有在 players 表中映射（区分大小写）

    Args:
        aliases: 玩家别名列表

    Returns:
        List[str]: 没有映射的玩家别名列表
    """
    if not aliases:
        return []

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 只获取所有 alias（区分大小写）
        cursor.execute("SELECT alias FROM players WHERE alias IS NOT NULL AND alias != '' COLLATE BINARY")
        all_aliases = {row['alias'] for row in cursor.fetchall()}

        # 找出未映射的 alias
        unmapped = [a for a in aliases if a not in all_aliases]
        return unmapped

    finally:
        conn.close()


def EnsurePlayersExist(nicknames: List[str]) -> List[str]:
    """
    批量确保玩家存在，返回新添加的玩家列表

    Args:
        nicknames: 玩家昵称列表

    Returns:
        List[str]: 新添加的玩家昵称列表
    """
    new_players = []
    for nickname in nicknames:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT id FROM players WHERE nickname = ?", (nickname,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO players (nickname) VALUES (?)", (nickname,))
                conn.commit()
                new_players.append(nickname)
                print(f"自动添加新玩家: {nickname}")
        except Exception as e:
            print(f"自动添加玩家 {nickname} 失败: {e}")
        finally:
            conn.close()
    return new_players


# ========== 每日PNL数据接口 ==========

def SaveDailyPnl(date: str, player_nickname: str, total_buy_in: int, total_buy_out: int,
                 total_stack: int, total_net: int, total_sessions: int) -> bool:
    """保存每日PNL数据（替换已有记录）"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 使用 INSERT OR REPLACE 替换数据
        cursor.execute("""
            INSERT OR REPLACE INTO daily_pnl (date, player_nickname, total_buy_in, total_buy_out, total_stack, total_net, total_sessions)
            VALUES (?, ?, ?, ?, ?, ?, ?)
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
    """批量保存原始账本数据（累加模式，不删除已有记录）"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 直接插入新记录，累加到已有记录
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
    """根据ledger数据计算每日PNL并保存（先删除当天记录再重新计算）"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 先删除当天已有的pnl记录
        cursor.execute("DELETE FROM daily_pnl WHERE date = ?", (date,))
        conn.commit()

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
