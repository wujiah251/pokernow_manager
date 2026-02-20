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

    # 初始化 hands 和 hand_players 表
    _init_hands_tables(conn, cursor)

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


# ========== 手牌数据接口 ==========

import json
import re


def _init_hands_tables(conn, cursor):
    """初始化 hands 和 hand_players 表"""
    # hands 表 - 存储每手牌的基本信息
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            hand_number INTEGER NOT NULL,
            hand_id TEXT,
            game_type TEXT DEFAULT 'NLHE',
            is_bomb_pot BOOLEAN DEFAULT FALSE,
            dealer TEXT,
            player_num INTEGER NOT NULL,
            total_pot INTEGER DEFAULT 0,
            winner TEXT,
            winner_profit INTEGER DEFAULT 0,
            loser TEXT,
            loser_profit INTEGER DEFAULT 0,
            action_line TEXT,
            source_file TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, hand_number)
        )
    """)

    # hand_players 表 - 存储每手牌中各玩家的详细信息
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hand_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hand_id INTEGER NOT NULL,
            player_nickname TEXT NOT NULL,
            player_alias TEXT,
            starting_stack INTEGER,
            ending_stack INTEGER,
            profit INTEGER DEFAULT 0,
            position TEXT,
            hole_cards TEXT,
            is_winner BOOLEAN DEFAULT FALSE,
            FOREIGN KEY(hand_id) REFERENCES hands(id),
            UNIQUE(hand_id, player_nickname)
        )
    """)

    # 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hands_date ON hands(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hands_number ON hands(hand_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hand_players_hand_id ON hand_players(hand_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hand_players_nickname ON hand_players(player_nickname)")


def detect_game_type(starting_hand_entry: str) -> str:
    """识别游戏类型"""
    if "7-2 bounty" in starting_hand_entry:
        return "27"
    return "NLHE"


def detect_bomb_pot(hand_logs: List[Dict]) -> bool:
    """识别是否为炸弹底池"""
    for log in hand_logs:
        entry = log.get("entry", "")
        if entry and "bomb pot bet" in entry.lower():
            return True
    return False


def extract_player_from_entry(entry: str) -> tuple:
    """
    从日志条目中提取玩家昵称和别名

    Args:
        entry: 日志条目，如 '"wjh @ yQzNmdWzgU" folds'

    Returns:
        tuple: (nickname, alias) 或 (None, None)
    """
    # 匹配 "nickname @ alias" 格式
    pattern = r'"(.+?)\s*@\s*(.+?)"'
    match = re.search(pattern, entry)
    if match:
        nickname = match.group(1).strip()
        alias = match.group(2).strip()
        # 尝试解析为真实昵称
        resolved = ResolvePlayerNickname(alias)
        if resolved:
            return (resolved, alias)
        return (nickname, alias)
    return (None, None)


def parse_action(entry: str) -> Dict:
    """解析单条动作日志，返回空字典如果无法解析"""
    result = {}

    # 先提取玩家信息
    nickname, alias = extract_player_from_entry(entry)
    if nickname:
        result["player"] = nickname

    # 检测动作类型
    if '" folds' in entry:
        result["action"] = "fold"
    elif '" checks' in entry:
        result["action"] = "check"
    elif '" calls' in entry:
        result["action"] = "call"
        # 提取金额
        match = re.search(r'calls\s+(\d+)', entry)
        if match:
            result["amount"] = int(match.group(1))
    elif '" bets ' in entry:
        result["action"] = "bet"
        match = re.search(r'bets\s+(\d+)', entry)
        if match:
            result["amount"] = int(match.group(1))
    elif '" raises to ' in entry:
        result["action"] = "raise"
        match = re.search(r'raises to\s+(\d+)', entry)
        if match:
            result["amount"] = int(match.group(1))
    elif 'posts a small blind' in entry:
        result["action"] = "blind"
        result["blind_type"] = "small"
        match = re.search(r'of\s+(\d+)', entry)
        if match:
            result["amount"] = int(match.group(1))
    elif 'posts a big blind' in entry:
        result["action"] = "blind"
        result["blind_type"] = "big"
        match = re.search(r'of\s+(\d+)', entry)
        if match:
            result["amount"] = int(match.group(1))
    elif '" all-in' in entry or '" is all in' in entry:
        result["action"] = "allin"
        match = re.search(r'(?:bets|calls|raises to)\s+(\d+)', entry)
        if match:
            result["amount"] = int(match.group(1))

    return result


def extract_hand_info(starting_hand_entry: str) -> Dict:
    """提取手牌基本信息"""
    info = {
        "hand_number": None,
        "hand_id": None,
        "game_type": "NLHE",
        "dealer": None
    }

    # 提取手牌编号: -- starting hand #266 --
    match = re.search(r'#(\d+)', starting_hand_entry)
    if match:
        info["hand_number"] = int(match.group(1))

    # 提取 hand_id: (id: xrdzvysblawy)
    match = re.search(r'\(id:\s*(\w+)\)', starting_hand_entry)
    if match:
        info["hand_id"] = match.group(1)

    # 识别游戏类型
    info["game_type"] = detect_game_type(starting_hand_entry)

    # 提取庄家: (dealer: "hyq")
    match = re.search(r'dealer:\s*"(.+?)"', starting_hand_entry)
    if match:
        dealer_str = match.group(1)
        nickname, _ = extract_player_from_entry(f'"{dealer_str}"')
        if nickname:
            info["dealer"] = nickname

    return info


def extract_players_from_stacks(stacks_entry: str) -> List[Dict]:
    """从 Player stacks 条目提取玩家信息"""
    players = []

    # 格式: Player stacks: #1 "wjh @ yQzNmdWzgU" (889) | #2 "hyq @ HZkdinonr0" (1826) | ...
    # 匹配每个玩家: #1 "nickname @ alias" (stack)
    pattern = r'#\d+\s+"(.+?)\s*@\s*(.+?)"\s+\((\d+)\)'
    matches = re.findall(pattern, stacks_entry)

    for match in matches:
        nickname = match[0].strip()
        alias = match[1].strip()
        stack = int(match[2])

        # 尝试解析为真实昵称
        resolved = ResolvePlayerNickname(alias)
        if resolved:
            nickname = resolved

        players.append({
            "nickname": nickname,
            "alias": alias,
            "starting_stack": stack,
            "ending_stack": None,
            "profit": 0
        })

    return players


def parse_street_actions(logs: List[Dict], start_idx: int, street_name: str) -> tuple:
    """解析某个街区的动作"""
    actions = []
    i = start_idx

    while i < len(logs):
        entry = logs[i].get("entry", "")

        # 跳过非动作行
        if not entry or entry.startswith("Player stacks:") or \
           entry.startswith("-- starting hand") or \
           entry.startswith("-- ending hand") or \
           entry.startswith("Flop:") or entry.startswith("Turn:") or entry.startswith("River:") or \
           entry.startswith("Undealt cards") or \
           entry.startswith("Your hand is"):
            break

        # 跳过 collected 和 Uncalled bet
        if "collected" in entry or "Uncalled bet" in entry:
            i += 1
            continue

        # 解析动作
        action = parse_action(entry)
        if action.get("action"):
            actions.append(action)

        i += 1

    return actions, i


def detect_street(entry: str) -> str:
    """检测当前街区"""
    if entry.startswith("Flop:"):
        return "flop"
    elif entry.startswith("Turn:"):
        return "turn"
    elif entry.startswith("River:"):
        return "river"
    elif "-- starting hand" in entry:
        return "preflop"
    return None


def parse_poker_hand(hand_logs: List[Dict]) -> Dict:
    """解析一手牌的所有信息"""
    if not hand_logs:
        return {}

    result = {
        "hand_number": None,
        "hand_id": None,
        "game_type": "NLHE",
        "is_bomb_pot": False,
        "dealer": None,
        "player_num": 0,
        "players": [],
        "action_line": {},
        "total_pot": 0,
        "winner": None,
        "winner_profit": 0,
        "loser": None,
        "loser_profit": 0,
        "collected": [],
        "uncalled_bets": 0
    }

    # 第一条日志应该是 starting hand
    first_entry = hand_logs[0].get("entry", "")
    if "-- starting hand" in first_entry:
        hand_info = extract_hand_info(first_entry)
        result.update(hand_info)

    # 检查炸弹底池
    result["is_bomb_pot"] = detect_bomb_pot(hand_logs)

    # 解析所有日志
    current_street = "preflop"
    players_initialized = False

    for i, log in enumerate(hand_logs):
        entry = log.get("entry", "")

        # 跳过无关日志
        if not entry:
            continue

        # 检测玩家和筹码
        if entry.startswith("Player stacks:") and not players_initialized:
            result["players"] = extract_players_from_stacks(entry)
            result["player_num"] = len(result["players"])
            players_initialized = True
            continue

        # 检测公共牌
        if entry.startswith("Flop:"):
            current_street = "flop"
            result["action_line"]["flop"] = []
        elif entry.startswith("Turn:"):
            current_street = "turn"
            result["action_line"]["turn"] = []
        elif entry.startswith("River:"):
            current_street = "river"
            result["action_line"]["river"] = []
            continue

        # 跳过收集和未收回的下注
        if "collected" in entry:
            # 提取赢得的玩家和金额
            match = re.search(r'"(.+?)\s*@\s*(.+?)"\s+collected\s+(\d+)', entry)
            if match:
                nickname = match.group(1).strip()
                alias = match.group(2).strip()
                amount = int(match.group(3))

                resolved = ResolvePlayerNickname(alias)
                if resolved:
                    nickname = resolved

                result["collected"].append({
                    "player": nickname,
                    "amount": amount
                })
            continue

        if "Uncalled bet" in entry:
            match = re.search(r'(\d+)', entry)
            if match:
                result["uncalled_bets"] += int(match.group(1))
            continue

        # 解析动作
        if "-- starting hand" not in entry and "-- ending hand" not in entry and \
           "Undealt cards" not in entry and "Your hand is" not in entry and \
           "collected" not in entry and "Uncalled bet" not in entry and \
           "shows" not in entry and "shows" not in entry:

            action = parse_action(entry)
            if action.get("action"):
                if current_street not in result["action_line"]:
                    result["action_line"][current_street] = []
                result["action_line"][current_street].append(action)

    # 计算底池
    total_collected = sum(c["amount"] for c in result["collected"])
    result["total_pot"] = total_collected - result["uncalled_bets"]

    # 计算 winner/loser
    if result["collected"]:
        # 赢得最多的为 winner
        winner_data = max(result["collected"], key=lambda x: x["amount"])
        result["winner"] = winner_data["player"]
        result["winner_profit"] = winner_data["amount"]

        # 输家计算：需要根据初始和结束筹码计算
        # 这里先简化：使用collected为0且有动作的玩家作为可能的输家
        # 实际计算需要对比 ending_stack

    return result


def save_hand(hand_data: Dict, date: str, source_file: str = None) -> int:
    """保存一手牌到数据库，返回 hand_id"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 插入 hands 表
        action_line_json = json.dumps(hand_data.get("action_line", {}), ensure_ascii=False)

        cursor.execute("""
            INSERT OR REPLACE INTO hands (
                date, hand_number, hand_id, game_type, is_bomb_pot, dealer,
                player_num, total_pot, winner, winner_profit, loser, loser_profit,
                action_line, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date,
            hand_data.get("hand_number"),
            hand_data.get("hand_id"),
            hand_data.get("game_type", "NLHE"),
            hand_data.get("is_bomb_pot", False),
            hand_data.get("dealer"),
            hand_data.get("player_num", 0),
            hand_data.get("total_pot", 0),
            hand_data.get("winner"),
            hand_data.get("winner_profit", 0),
            hand_data.get("loser"),
            hand_data.get("loser_profit", 0),
            action_line_json,
            source_file
        ))

        hand_id = cursor.lastrowid

        # 插入 hand_players 表
        players = hand_data.get("players", [])
        for player in players:
            cursor.execute("""
                INSERT OR REPLACE INTO hand_players (
                    hand_id, player_nickname, player_alias, starting_stack,
                    ending_stack, profit, is_winner
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                hand_id,
                player.get("nickname"),
                player.get("alias"),
                player.get("starting_stack"),
                player.get("ending_stack"),
                player.get("profit", 0),
                player.get("nickname") == hand_data.get("winner")
            ))

        # 批量确保玩家存在于 players 表
        player_nicknames = [p.get("nickname") for p in players if p.get("nickname")]
        if player_nicknames:
            for nickname in set(player_nicknames):
                cursor.execute("INSERT OR IGNORE INTO players (nickname) VALUES (?)", (nickname,))

        conn.commit()
        return hand_id

    except Exception as e:
        conn.rollback()
        print(f"保存手牌失败: {e}")
        return -1
    finally:
        conn.close()


def import_poker_log(date: str, poker_file: str) -> bool:
    """导入 poker.csv 文件"""
    import csv

    if not os.path.exists(poker_file):
        print(f"文件不存在: {poker_file}")
        return False

    with open(poker_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_logs = list(reader)

    if not all_logs:
        print(f"文件为空: {poker_file}")
        return False

    # 按 order 列排序（时间顺序）
    all_logs.sort(key=lambda x: int(x.get('order', 0)))

    # 按手牌分割日志
    hands_logs = []
    current_hand = []

    for log in all_logs:
        entry = log.get("entry", "")
        if "-- starting hand" in entry:
            # 开始新手牌
            if current_hand:
                hands_logs.append(current_hand)
            current_hand = [log]
        elif "-- ending hand" in entry:
            # 结束当前手牌
            current_hand.append(log)
            hands_logs.append(current_hand)
            current_hand = []
        else:
            current_hand.append(log)

    # 处理最后一个手牌（如果没有以 ending hand 结束）
    if current_hand:
        hands_logs.append(current_hand)

    print(f"发现 {len(hands_logs)} 手牌")

    # 解析并保存每手牌
    saved_count = 0
    for hand_logs in hands_logs:
        hand_data = parse_poker_hand(hand_logs)
        if hand_data.get("hand_number"):
            hand_id = save_hand(hand_data, date, poker_file)
            if hand_id > 0:
                saved_count += 1

    print(f"成功保存 {saved_count} 手牌")
    return saved_count > 0


def get_hand_by_number(date: str, hand_number: int) -> Optional[Dict]:
    """根据日期和手牌编号获取手牌信息"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT * FROM hands WHERE date = ? AND hand_number = ?
        """, (date, hand_number))

        row = cursor.fetchone()
        if not row:
            return None

        hand = dict(row)

        # 获取玩家信息
        cursor.execute("""
            SELECT * FROM hand_players WHERE hand_id = ?
        """, (hand["id"],))

        hand["players"] = [dict(p) for p in cursor.fetchall()]

        return hand
    finally:
        conn.close()


def get_hands_by_date(date: str) -> List[Dict]:
    """获取指定日期的所有手牌"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT * FROM hands WHERE date = ? ORDER BY hand_number
        """, (date,))

        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
