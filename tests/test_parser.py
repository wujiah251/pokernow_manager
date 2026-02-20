#!/usr/bin/env python3
"""
德州扑克数据解析测试
"""

import unittest
import sys
import os

# 添加 scripts 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# 初始化数据库路径
from db import init_db_path
init_db_path()


class TestGameTypeDetection(unittest.TestCase):
    """游戏类型识别测试"""

    def test_detect_nlhe(self):
        """测试识别无限注德州"""
        from db import detect_game_type
        entry = '-- starting hand #266 (id: xrdzvysblawy)  No Limit Texas Hold\'em (dealer: "hyq") --'
        self.assertEqual(detect_game_type(entry), 'NLHE')

    def test_detect_27_game(self):
        """测试识别27游戏"""
        from db import detect_game_type
        entry = '-- starting hand #10 (id: abc123)  7-2 bounty (dealer: "wjh") --'
        self.assertEqual(detect_game_type(entry), '27')


class TestBombPotDetection(unittest.TestCase):
    """炸弹底池识别测试"""

    def test_bomb_pot_true(self):
        """测试炸弹底池为真"""
        from db import detect_bomb_pot
        logs = [
            {"entry": "Player stacks: ..."},
            {"entry": '"wjh @ yQzNmdWzgU" calls 4 (bomb pot bet)'}
        ]
        self.assertTrue(detect_bomb_pot(logs))

    def test_bomb_pot_false(self):
        """测试炸弹底池为假"""
        from db import detect_bomb_pot
        logs = [{"entry": '"wjh @ yQzNmdWzgU" bets 50'}]
        self.assertFalse(detect_bomb_pot(logs))


class TestActionParsing(unittest.TestCase):
    """行动解析测试"""

    def test_parse_fold(self):
        """测试解析弃牌"""
        from db import parse_action
        entry = '"wjh @ yQzNmdWzgU" folds'
        result = parse_action(entry)
        self.assertEqual(result["action"], "fold")
        self.assertEqual(result["player"], "wjh")

    def test_parse_check(self):
        """测试解析看牌"""
        from db import parse_action
        entry = '"cy @ A4iDUuyzZu" checks'
        result = parse_action(entry)
        self.assertEqual(result["action"], "check")
        self.assertEqual(result["player"], "cy")

    def test_parse_call(self):
        """测试解析跟注"""
        from db import parse_action
        entry = '"cy @ A4iDUuyzZu" calls 7'
        result = parse_action(entry)
        self.assertEqual(result["action"], "call")
        self.assertEqual(result["player"], "cy")
        self.assertEqual(result["amount"], 7)

    def test_parse_bet(self):
        """测试解析下注"""
        from db import parse_action
        entry = '"cy @ A4iDUuyzZu" bets 20'
        result = parse_action(entry)
        self.assertEqual(result["action"], "bet")
        self.assertEqual(result["player"], "cy")
        self.assertEqual(result["amount"], 20)

    def test_parse_raise(self):
        """测试解析加注"""
        from db import parse_action
        entry = '"hyq @ HZkdinonr0" raises to 7'
        result = parse_action(entry)
        self.assertEqual(result["action"], "raise")
        self.assertEqual(result["player"], "hyq")
        self.assertEqual(result["amount"], 7)

    def test_parse_small_blind(self):
        """测试解析小盲注"""
        from db import parse_action
        entry = '"mouyu1021 @ UAV9Myl4l0" posts a small blind of 1'
        result = parse_action(entry)
        self.assertEqual(result["action"], "blind")
        self.assertEqual(result["player"], "mouyu1021")
        self.assertEqual(result["amount"], 1)
        self.assertEqual(result["blind_type"], "small")

    def test_parse_big_blind(self):
        """测试解析大盲注"""
        from db import parse_action
        entry = '"cy @ A4iDUuyzZu" posts a big blind of 2'
        result = parse_action(entry)
        self.assertEqual(result["action"], "blind")
        self.assertEqual(result["player"], "cy")
        self.assertEqual(result["amount"], 2)
        self.assertEqual(result["blind_type"], "big")


class TestPlayerExtraction(unittest.TestCase):
    """玩家信息提取测试"""

    def test_extract_player_from_entry(self):
        """测试从日志中提取玩家"""
        from db import extract_player_from_entry
        entry = '"wjh @ yQzNmdWzgU" folds'
        nickname, alias = extract_player_from_entry(entry)
        self.assertEqual(nickname, "wjh")
        self.assertEqual(alias, "yQzNmdWzgU")


class TestHandInfoExtraction(unittest.TestCase):
    """手牌信息提取测试"""

    def test_extract_hand_info(self):
        """测试提取手牌基本信息"""
        from db import extract_hand_info
        entry = '-- starting hand #266 (id: xrdzvysblawy)  No Limit Texas Hold\'em (dealer: "hyq @ HZkdinonr0") --'
        info = extract_hand_info(entry)
        self.assertEqual(info["hand_number"], 266)
        self.assertEqual(info["hand_id"], "xrdzvysblawy")
        self.assertEqual(info["game_type"], "NLHE")
        self.assertEqual(info["dealer"], "hyq")


class TestPlayerStacksExtraction(unittest.TestCase):
    """玩家筹码提取测试"""

    def test_extract_players_from_stacks(self):
        """测试从 Player stacks 条目提取玩家"""
        from db import extract_players_from_stacks
        entry = 'Player stacks: #1 "wjh @ yQzNmdWzgU" (889) | #2 "hyq @ HZkdinonr0" (1826) | #3 "mouyu1021 @ UAV9Myl4l0" (510)'
        players = extract_players_from_stacks(entry)
        self.assertEqual(len(players), 3)
        self.assertEqual(players[0]["nickname"], "wjh")
        self.assertEqual(players[0]["alias"], "yQzNmdWzgU")
        self.assertEqual(players[0]["starting_stack"], 889)


class TestFullHandParsing(unittest.TestCase):
    """完整手牌解析测试"""

    def test_parse_full_hand(self):
        """测试解析完整手牌"""
        from db import parse_poker_hand

        hand_logs = [
            {"entry": '-- starting hand #266 (id: xrdzvysblawy)  No Limit Texas Hold\'em (dealer: "hyq @ HZkdinonr0") --'},
            {"entry": 'Player stacks: #1 "wjh @ yQzNmdWzgU" (889) | #2 "hyq @ HZkdinonr0" (1826) | #3 "mouyu1021 @ UAV9Myl4l0" (510) | #4 "cy @ A4iDUuyzZu" (734) | #10 "lmm @ 0_1uK8q5GK" (187)'},
            {"entry": '"wjh @ yQzNmdWzgU" folds'},
            {"entry": '"lmm @ 0_1uK8q5GK" folds'},
            {"entry": '"mouyu1021 @ UAV9Myl4l0" folds'},
            {"entry": '"cy @ A4iDUuyzZu" collected 45 from pot'},
            {"entry": '-- ending hand #266 --'}
        ]

        result = parse_poker_hand(hand_logs)

        self.assertEqual(result["hand_number"], 266)
        self.assertEqual(result["game_type"], "NLHE")
        self.assertEqual(result["player_num"], 5)
        self.assertEqual(len(result["players"]), 5)


class TestWinnerLoserCalculation(unittest.TestCase):
    """Winner/Loser 计算测试"""

    def test_calculate_winner_from_collected(self):
        """测试从 collected 记录计算 winner"""
        from db import parse_poker_hand

        hand_logs = [
            {"entry": '-- starting hand #1 (id: test123)  No Limit Texas Hold\'em (dealer: "wjh") --'},
            {"entry": 'Player stacks: #1 "wjh @ A" (100) | #2 "cy @ B" (100)'},
            {"entry": '"wjh @ A" folds'},
            {"entry": '"cy @ B" collected 45 from pot'},
            {"entry": '-- ending hand #1 --'}
        ]

        result = parse_poker_hand(hand_logs)
        self.assertEqual(result["winner"], "cy")
        self.assertEqual(result["winner_profit"], 45)
        self.assertEqual(result["total_pot"], 45)


if __name__ == "__main__":
    unittest.main()
