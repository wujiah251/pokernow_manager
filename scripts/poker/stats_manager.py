"""
扑克统计数据管理模块

负责从数据库读取预处理后的手牌数据，计算统计数据
"""
from typing import List, Dict, Optional
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
from poker.models import Hand, Action, ActionType, Street, PlayerStat, BaseStats
from poker.analyzer import Analyzer
from poker.stats import get_summary as calc_summary, calculate_percentages


def rebuild_hands_from_db(start_date: str = None, end_date: str = None, player_nickname: str = None) -> List[Hand]:
    """
    从数据库重建 Hand 对象列表

    Args:
        start_date: 开始日期
        end_date: 结束日期
        player_nickname: 玩家昵称筛选

    Returns:
        List[Hand]: Hand 对象列表
    """
    # 获取原始数据
    raw_data = db.GetProcessedHands(start_date, end_date, player_nickname)

    if not raw_data:
        return []

    # 按 hand_id 和 date 分组
    hands_dict: Dict[str, Dict] = {}

    for row in raw_data:
        key = f"{row['date']}_{row['hand_id']}"
        if key not in hands_dict:
            hands_dict[key] = {
                'hand_id': row['hand_id'],
                'date': datetime.fromisoformat(row['date']) if isinstance(row['date'], str) else row['date'],
                'players': {},
                'actions': [],
                'seated_players': [],
                'dealer_id': None,
                'community_cards': [],
                'is_bomb_pot': False
            }

        hand = hands_dict[key]

        # 更新玩家信息
        player_id = row['player_id']
        player_nickname = row['player_nickname']
        if player_id not in hand['players']:
            hand['players'][player_id] = player_nickname
            hand['seated_players'].append(player_id)

        # 添加动作
        action = Action(
            player_name=player_nickname,
            player_id=player_id,
            action_type=row['action_type'],
            amount=row['amount'] or 0,
            street=row['street'] or Street.PREFLOP,
            raw_log=row.get('raw_log', ''),
            timestamp=hand['date']
        )
        hand['actions'].append(action)

    # 转换为 Hand 对象
    hands = []
    for hand_data in hands_dict.values():
        hand = Hand(
            hand_id=hand_data['hand_id'],
            date=hand_data['date'],
            players=hand_data['players'],
            actions=hand_data['actions'],
            seated_players=hand_data['seated_players'],
            dealer_id=hand_data['dealer_id'],
            community_cards=hand_data['community_cards'],
            is_bomb_pot=hand_data['is_bomb_pot']
        )
        hands.append(hand)

    return hands


def calculate_stats(start_date: str = None, end_date: str = None, player_nickname: str = None) -> List[Dict]:
    """
    计算扑克统计数据

    Args:
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        player_nickname: 玩家昵称筛选

    Returns:
        List[Dict]: 统计结果列表
    """
    # 从数据库重建手牌数据
    hands = rebuild_hands_from_db(start_date, end_date, player_nickname)

    if not hands:
        return []

    # 使用 Analyzer 计算统计
    analyzer = Analyzer()
    analyzer.process_hands(hands)

    # 获取统计摘要
    summary = calc_summary(analyzer)

    return summary


def get_players_with_data() -> List[str]:
    """获取有统计数据的玩家列表"""
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT player_nickname FROM processed_hands ORDER BY player_nickname")
        return [row['player_nickname'] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_hand_count(start_date: str = None, end_date: str = None, player_nickname: str = None) -> int:
    """获取手牌数量"""
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        query = "SELECT COUNT(DISTINCT hand_id || date) as cnt FROM processed_hands WHERE 1=1"
        params = []

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
        if player_nickname:
            query += " AND player_nickname = ?"
            params.append(player_nickname)

        cursor.execute(query, params)
        row = cursor.fetchone()
        return row['cnt'] if row else 0
    finally:
        conn.close()
