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

    # 玩家表 - 存储真实名称和别名映射
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT UNIQUE NOT NULL,
            nickname TEXT NOT NULL,
            alias TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # player_id合并映射表 - 用于将多个player_id映射到同一个nickname
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_id_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_player_id TEXT NOT NULL,
            target_nickname TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(original_player_id)
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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_player_id ON ledger(player_id)")

    conn.commit()
    conn.close()
    print(f"数据库初始化完成: {DB_PATH}")

# ========== 玩家别名管理接口 ==========

def AddPlayer(player_id: str, nickname: str, alias: str = None) -> bool:
    """
    添加或更新玩家信息

    Args:
        player_id: 玩家唯一ID
        nickname: 真实昵称
        alias: 别名（可选）

    Returns:
        bool: 是否成功
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO players (player_id, nickname, alias)
            VALUES (?, ?, ?)
            ON CONFLICT(player_id) DO UPDATE SET
                nickname = excluded.nickname,
                alias = COALESCE(excluded.alias, players.alias)
        """, (player_id, nickname, alias))
        conn.commit()
        return True
    except Exception as e:
        print(f"添加玩家失败: {e}")
        return False
    finally:
        conn.close()

def AddAlias(player_id: str, alias: str) -> bool:
    """
    为玩家添加别名

    Args:
        player_id: 玩家唯一ID
        alias: 别名

    Returns:
        bool: 是否成功
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 获取现有别名
        cursor.execute("SELECT alias FROM players WHERE player_id = ?", (player_id,))
        row = cursor.fetchone()

        if row:
            existing_alias = row['alias'] or ""
            aliases = [a.strip() for a in existing_alias.split(",") if a.strip()]
            if alias not in aliases:
                aliases.append(alias)
                new_alias = ",".join(aliases)
                cursor.execute("UPDATE players SET alias = ? WHERE player_id = ?", (new_alias, player_id))
        else:
            # 玩家不存在，先创建一个
            cursor.execute("INSERT INTO players (player_id, nickname, alias) VALUES (?, ?, ?)",
                          (player_id, player_id, alias))

        conn.commit()
        return True
    except Exception as e:
        print(f"添加别名失败: {e}")
        return False
    finally:
        conn.close()

def MergePlayerIds(target_nickname: str, player_ids: List[str]) -> bool:
    """
    将多个player_id合并到同一个昵称

    Args:
        target_nickname: 目标昵称（最终统一的名称）
        player_ids: 需要合并的player_id列表

    Returns:
        bool: 是否成功
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        for pid in player_ids:
            cursor.execute("""
                INSERT OR REPLACE INTO player_id_map (original_player_id, target_nickname)
                VALUES (?, ?)
            """, (pid, target_nickname))

            # 同时更新players表
            cursor.execute("""
                INSERT INTO players (player_id, nickname)
                VALUES (?, ?)
                ON CONFLICT(player_id) DO UPDATE SET nickname = excluded.nickname
            """, (pid, target_nickname))

        conn.commit()
        return True
    except Exception as e:
        print(f"合并player_id失败: {e}")
        return False
    finally:
        conn.close()

def GetPlayerIdMapping(player_id: str) -> Optional[str]:
    """
    查询player_id对应的目标昵称

    Args:
        player_id: 原始player_id

    Returns:
        目标昵称，如果未映射返回None
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT target_nickname FROM player_id_map
            WHERE original_player_id = ?
        """, (player_id,))
        row = cursor.fetchone()
        return row['target_nickname'] if row else None
    finally:
        conn.close()

def QueryRealName(nickname_or_id: str) -> Optional[str]:
    """
    根据昵称或ID查询真实名称

    Args:
        nickname_or_id: 昵称或玩家ID

    Returns:
        真实昵称，如果未找到返回None
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 先尝试精确匹配player_id
        cursor.execute("SELECT nickname FROM players WHERE player_id = ?", (nickname_or_id,))
        row = cursor.fetchone()
        if row:
            return row['nickname']

        # 再尝试匹配昵称
        cursor.execute("SELECT nickname FROM players WHERE nickname = ?", (nickname_or_id,))
        row = cursor.fetchone()
        if row:
            return row['nickname']

        # 尝试匹配别名
        cursor.execute("SELECT nickname, alias FROM players WHERE alias LIKE ?", (f"%{nickname_or_id}%",))
        row = cursor.fetchone()
        if row:
            return row['nickname']

        return None
    finally:
        conn.close()

def GetPlayerById(player_id: str) -> Optional[Dict[str, Any]]:
    """
    根据player_id获取玩家信息

    Args:
        player_id: 玩家唯一ID

    Returns:
        玩家信息字典
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM players WHERE player_id = ?", (player_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def GetAllPlayers() -> List[Dict[str, Any]]:
    """
    获取所有玩家信息

    Returns:
        玩家列表
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM players ORDER BY nickname")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

# ========== 每日PNL数据接口 ==========

def SaveDailyPnl(date: str, player_nickname: str, total_buy_in: int, total_buy_out: int,
                 total_stack: int, total_net: int, total_sessions: int) -> bool:
    """
    保存或更新每日PNL数据

    Args:
        date: 日期 (YYYY-MM-DD)
        player_nickname: 玩家昵称
        total_buy_in: 总买入
        total_buy_out: 总退出
        total_stack: 总剩余筹码
        total_net: 净盈亏
        total_sessions: 总场次

    Returns:
        bool: 是否成功
    """
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
    """
    查询每日PNL记录

    Args:
        date: 日期 (YYYY-MM-DD)
        player_nickname: 玩家昵称（可选）

    Returns:
        PNL记录列表
    """
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

def QueryPnlSummary(date: str) -> Dict[str, Any]:
    """
    查询每日PNL汇总（平账检查用）

    Args:
        date: 日期 (YYYY-MM-DD)

    Returns:
        汇总字典
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                SUM(total_buy_in) as total_buy_in,
                SUM(total_buy_out) as total_buy_out,
                SUM(total_stack) as total_stack,
                SUM(total_net) as total_net,
                SUM(total_sessions) as total_sessions,
                COUNT(*) as player_count
            FROM daily_pnl
            WHERE date = ?
        """, (date,))

        row = cursor.fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()

def GetAllDates() -> List[str]:
    """
    获取所有有数据的日期

    Returns:
        日期列表
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT DISTINCT date FROM daily_pnl ORDER BY date DESC")
        return [row['date'] for row in cursor.fetchall()]
    finally:
        conn.close()

# ========== 原始账本数据接口 ==========

def SaveLedger(date: str, records: List[Dict[str, Any]], source_file: str = None) -> bool:
    """
    批量保存原始账本数据（清洗后）

    Args:
        date: 日期
        records: 账本记录列表
        source_file: 源文件

    Returns:
        bool: 是否成功
    """
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

def QueryLedger(date: str, player_id: str = None) -> List[Dict[str, Any]]:
    """
    查询原始账本记录

    Args:
        date: 日期
        player_id: 玩家ID（可选）

    Returns:
        账本记录列表
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if player_id:
            cursor.execute("""
                SELECT * FROM ledger
                WHERE date = ? AND player_id = ?
                ORDER BY session_start_at
            """, (date, player_id))
        else:
            cursor.execute("SELECT * FROM ledger WHERE date = ? ORDER BY session_start_at", (date,))

        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

# ========== 工具函数 ==========

def NormalizeNickname(nickname: str, alias_map: Dict[str, str] = None) -> str:
    """
    标准化昵称（将别名映射到真实名称）

    Args:
        nickname: 原始昵称
        alias_map: 别名映射字典（可选）

    Returns:
        标准化后的昵称
    """
    if alias_map and nickname in alias_map:
        return alias_map[nickname]

    # 查询数据库
    real_name = QueryRealName(nickname)
    return real_name if real_name else nickname

def ImportLedgerFiles(date: str, ledger_dir: str, alias_map: Dict[str, str] = None) -> bool:
    """
    导入指定日期的所有ledger文件并清洗数据

    Args:
        date: 日期 (YYYYMMDD)
        ledger_dir: ledger文件目录
        alias_map: 别名映射字典

    Returns:
        bool: 是否成功
    """
    import glob
    import csv

    date_formatted = f"20{date[2:4]}-{date[4:6]}-{date[6:8]}"  # YYYY-MM-DD

    # 查找所有ledger文件
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

                # 1. 先检查player_id是否有映射（如 wn/nw 合并）
                mapped_nickname = GetPlayerIdMapping(original_player_id)
                if mapped_nickname:
                    clean_nickname = mapped_nickname
                else:
                    # 2. 再检查别名映射（如 latent(1) -> latent）
                    normalized_nickname = NormalizeNickname(original_nickname, alias_map)

                    # 3. 查询players表
                    player_info = GetPlayerById(original_player_id)
                    if player_info:
                        clean_nickname = player_info['nickname']
                    else:
                        clean_nickname = normalized_nickname

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

    # 保存到数据库
    if SaveLedger(date_formatted, all_records):
        print(f"成功导入 {len(all_records)} 条账本记录")
        return True

    return False

def CalculateDailyPnl(date: str) -> bool:
    """
    根据ledger数据计算每日PNL并保存（按昵称合并）

    Args:
        date: 日期 (YYYY-MM-DD)

    Returns:
        bool: 是否成功
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 按玩家昵称汇总
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
            nickname = row['player_nickname']

            # 查找该昵称对应的player_id
            cursor2 = conn.cursor()
            cursor2.execute("""
                SELECT player_id FROM ledger
                WHERE date = ? AND player_nickname = ? LIMIT 1
            """, (date, nickname))
            pid_row = cursor2.fetchone()
            player_id = pid_row['player_id'] if pid_row else nickname

            SaveDailyPnl(
                date=date,
                player_nickname=nickname,
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

def ExportDailyPnlCsv(date: str, output_dir: str = None) -> str:
    """
    导出每日PNL为CSV文件

    Args:
        date: 日期 (YYYY-MM-DD)
        output_dir: 输出目录，默认 daily/{date}

    Returns:
        输出文件路径
    """
    import csv

    if output_dir is None:
        project_root = os.path.dirname(os.path.dirname(__file__))
        output_dir = os.path.join(project_root, "daily", date.replace("-", ""))

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "pnl_daily.csv")

    # 直接从数据库按昵称汇总查询
    conn = get_connection()
    cursor = conn.cursor()

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
        ORDER BY total_net DESC
    """, (date,))

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'player_nickname', 'total_net',
                        'total_buy_in', 'total_buy_out', 'total_stack', 'total_sessions'])

        for row in cursor.fetchall():
            writer.writerow([
                date,
                row[0],  # player_nickname
                row[4],  # total_net
                row[1],  # total_buy_in
                row[2],  # total_buy_out
                row[3],  # total_stack
                row[5]   # total_sessions
            ])

    conn.close()
    return output_file

if __name__ == "__main__":
    # 初始化数据库
    init_db()
