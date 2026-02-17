"""扑克统计数据计算模块"""
from typing import List, Dict
from .models import PlayerStat, BaseStats


def calculate_percentages(s: BaseStats) -> Dict:
    """
    计算统计百分比

    Args:
        s: BaseStats 对象

    Returns:
        包含所有统计百分比的字典
    """
    def pct(num, den):
        return round((num / den * 100), 1) if den > 0 else 0

    return {
        "hands": s.hands_played,
        "vpip": pct(s.vpip_count, s.hands_played),
        "pfr": pct(s.pfr_count, s.hands_played),
        "three_bet": pct(s.three_bet_count, s.three_bet_opp),
        "fold_to_3bet": pct(s.fold_to_3bet_count, s.faced_3bet_count),
        "four_bet": pct(s.four_bet_count, s.four_bet_opp),
        "fold_to_4bet": pct(s.fold_to_4bet_count, s.faced_4bet_count),
        "five_bet": pct(s.five_bet_count, s.five_bet_opp),
        "fold_to_5bet": pct(s.fold_to_5bet_count, s.faced_5bet_count),
        "c_bet": pct(s.c_bet_count, s.c_bet_opp),
        "fold_to_cbet": pct(s.fold_to_cbet_count, s.faced_cbet_count),
        "af": round((s.aggression_actions / s.call_actions), 2) if s.call_actions > 0 else s.aggression_actions,

        # WTSD: Went to Showdown / Seen Flop
        "wtsd": pct(s.wtsd_count, s.seen_flop_count),

        # WTSD Turn: Went to Showdown / Seen Turn
        "wtsd_turn": pct(s.wtsd_count, s.seen_turn_count),

        # WTSD River: Went to Showdown / Seen River
        "wtsd_river": pct(s.wtsd_count, s.seen_river_count),

        # W$SD: Won Money at Showdown / Went to Showdown
        "wtsd_won": pct(s.won_at_showdown_count, s.wtsd_count),

        "wwsf": pct(s.won_when_seen_flop_count, s.seen_flop_count),
        "wwst": pct(s.won_when_seen_turn_count, s.seen_turn_count),
        "wwsr": pct(s.won_when_seen_river_count, s.seen_river_count),

        # Raw counts for frontend tooltips
        "vpip_count": s.vpip_count,
        "pfr_count": s.pfr_count,
        "three_bet_count": s.three_bet_count, "three_bet_opp": s.three_bet_opp,
        "fold_to_3bet_count": s.fold_to_3bet_count, "faced_3bet_count": s.faced_3bet_count,
        "four_bet_count": s.four_bet_count, "four_bet_opp": s.four_bet_opp,
        "fold_to_4bet_count": s.fold_to_4bet_count, "faced_4bet_count": s.faced_4bet_count,
        "c_bet_count": s.c_bet_count, "c_bet_opp": s.c_bet_opp,
        "fold_to_cbet_count": s.fold_to_cbet_count, "faced_cbet_count": s.faced_cbet_count,
        "aggression_actions": s.aggression_actions, "call_actions": s.call_actions,
        "wtsd_count": s.wtsd_count, "won_at_showdown_count": s.won_at_showdown_count,

        "seen_flop_count": s.seen_flop_count, "won_when_seen_flop_count": s.won_when_seen_flop_count,
        "seen_turn_count": s.seen_turn_count, "won_when_seen_turn_count": s.won_when_seen_turn_count,
        "seen_river_count": s.seen_river_count, "won_when_seen_river_count": s.won_when_seen_river_count
    }


def get_summary(analyzer) -> List[Dict]:
    """
    获取玩家统计摘要

    Args:
        analyzer: Analyzer 实例，包含处理后的统计数据

    Returns:
        玩家统计数据列表
    """
    aggregated_stats: Dict[str, PlayerStat] = {}

    for pid, stat in analyzer.stats.items():
        display_name = analyzer.player_aliases.get(pid, stat.name)
        key = display_name

        if key not in aggregated_stats:
            aggregated_stats[key] = PlayerStat(player_id=key, name=display_name)

        agg = aggregated_stats[key]

        # Helper to merge BaseStats
        def merge_base(target: BaseStats, source: BaseStats):
            target.hands_played += source.hands_played
            target.vpip_count += source.vpip_count
            target.pfr_count += source.pfr_count
            target.three_bet_count += source.three_bet_count
            target.three_bet_opp += source.three_bet_opp
            target.fold_to_3bet_count += source.fold_to_3bet_count
            target.faced_3bet_count += source.faced_3bet_count

            target.four_bet_count += source.four_bet_count
            target.four_bet_opp += source.four_bet_opp
            target.fold_to_4bet_count += source.fold_to_4bet_count
            target.faced_4bet_count += source.faced_4bet_count

            target.five_bet_count += source.five_bet_count
            target.five_bet_opp += source.five_bet_opp
            target.fold_to_5bet_count += source.fold_to_5bet_count
            target.faced_5bet_count += source.faced_5bet_count

            target.c_bet_count += source.c_bet_count
            target.c_bet_opp += source.c_bet_opp
            target.fold_to_cbet_count += source.fold_to_cbet_count
            target.faced_cbet_count += source.faced_cbet_count

            target.aggression_actions += source.aggression_actions
            target.call_actions += source.call_actions
            target.wtsd_count += source.wtsd_count
            target.won_at_showdown_count += source.won_at_showdown_count
            target.won_hand_count += source.won_hand_count

            target.seen_flop_count += source.seen_flop_count
            target.won_when_seen_flop_count += source.won_when_seen_flop_count
            target.seen_turn_count += source.seen_turn_count
            target.won_when_seen_turn_count += source.won_when_seen_turn_count
            target.seen_river_count += source.seen_river_count
            target.won_when_seen_river_count += source.won_when_seen_river_count

        # Merge Global
        merge_base(agg, stat)

        # Merge Positions
        for pos, p_stat in stat.position_stats.items():
            if pos not in agg.position_stats:
                agg.position_stats[pos] = BaseStats()
            merge_base(agg.position_stats[pos], p_stat)

    results = []

    for name, stat in aggregated_stats.items():
        global_stats = calculate_percentages(stat)

        # Process Positional Stats
        pos_breakdown = {}
        for pos, p_stat in stat.position_stats.items():
            pos_breakdown[pos] = calculate_percentages(p_stat)

        results.append({
            "id": name,
            "name": name,
            **global_stats,
            "position_stats": pos_breakdown
        })

    return results
