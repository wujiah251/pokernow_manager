from typing import List, Dict, Set
from .models import Hand, ActionType, Street, PlayerStat, BaseStats

class Analyzer:
    def __init__(self):
        self.stats: Dict[str, PlayerStat] = {} # player_id -> Stat
        self.player_aliases: Dict[str, str] = {} # player_id -> display_name
        self.processed_hand_ids: Set[str] = set() # Track processed hands to prevent duplicates

    def add_alias(self, player_id: str, alias: str):
        self.player_aliases[player_id] = alias

    def process_hands(self, hands: List[Hand]):
        # Clear stats to avoid double counting if re-processing?
        # For now assume additive or handled by caller resetting.
        for hand in hands:
            # Use hand_id + timestamp to identify unique hands across different sessions
            # PokerNow hand IDs reset to 1 for each new session log
            unique_key = f"{hand.hand_id}_{hand.date}"
            if unique_key in self.processed_hand_ids:
                continue
            self._process_single_hand(hand)
            self.processed_hand_ids.add(unique_key)

    def _determine_position(self, hand: Hand, player_id: str) -> str:
        # Based on seated_players and dealer_id
        if not hand.seated_players or not hand.dealer_id:
            return "Unknown"

        if player_id not in hand.seated_players:
            return "Unknown" # Observer or error

        num_players = len(hand.seated_players)
        try:
            dealer_idx = hand.seated_players.index(hand.dealer_id)
            player_idx = hand.seated_players.index(player_id)
        except ValueError:
            return "Unknown"

        # Calculate offset from Dealer (BTN)
        # 0 = BTN
        # 1 = SB
        # 2 = BB
        # 3 = UTG (in 6-max)

        # Calculate distance from button (moving clockwise)
        # distance = (player_idx - dealer_idx) % num_players
        # Wait, seat order usually moves clockwise?
        # #1, #2, #3. If #1 is dealer, #2 is SB, #3 is BB.
        # Yes.

        dist = (player_idx - dealer_idx) % num_players

        if num_players == 2:
            # Heads Up
            if dist == 0: return "BTN" # Dealer is BTN/SB in HU usually, but acts first preflop.
            # In HU: Dealer posts SB. Other posts BB.
            # So Dealer is SB. Other is BB.
            # BUT standard naming: BTN is Dealer.
            if dist == 0: return "BTN"
            if dist == 1: return "BB"

        elif num_players == 3:
            if dist == 0: return "BTN"
            if dist == 1: return "SB"
            if dist == 2: return "BB"

        elif num_players == 4:
            if dist == 0: return "BTN"
            if dist == 1: return "SB"
            if dist == 2: return "BB"
            if dist == 3: return "CO" # or UTG

        elif num_players == 5:
            if dist == 0: return "BTN"
            if dist == 1: return "SB"
            if dist == 2: return "BB"
            if dist == 3: return "UTG"
            if dist == 4: return "CO"

        elif num_players == 6:
            if dist == 0: return "BTN"
            if dist == 1: return "SB"
            if dist == 2: return "BB"
            if dist == 3: return "UTG"
            if dist == 4: return "HJ" # Middle Position often called HJ in 6-max
            if dist == 5: return "CO"

        elif num_players >= 7:
            # Generalize
            if dist == 0: return "BTN"
            if dist == 1: return "SB"
            if dist == 2: return "BB"
            if dist == num_players - 1: return "CO"
            if dist == num_players - 2: return "HJ"
            if dist == num_players - 3: return "LJ" # or MP
            # Remaining are UTG, UTG+1...
            # distance 3 is UTG
            utg_pos = dist - 3
            if utg_pos >= 0:
                if utg_pos == 0: return "UTG"
                return f"UTG+{utg_pos}"

        return "Unknown"

    def _update_stats(self, stat: BaseStats, update_fn):
        update_fn(stat)

    def _process_single_hand(self, hand: Hand):
        if hand.is_bomb_pot:
            return

        # 检测 bomb pot 和 7-2 bounty 对局
        for action in hand.actions:
            raw_lower = action.raw_log.lower()
            if 'bomb pot' in raw_lower or '7-2 bounty' in raw_lower:
                return

        players_in_hand = set(hand.players.keys())

        # Determine winners (actions with WIN)
        winners = set()
        for action in hand.actions:
            if action.action_type == ActionType.WIN:
                winners.add(action.player_id)
        hand.winners = list(winners)

        # Map Player -> Position
        player_positions = {}
        for pid in players_in_hand:
            pos = self._determine_position(hand, pid)
            player_positions[pid] = pos

            # Init stats
            if pid not in self.stats:
                self.stats[pid] = PlayerStat(player_id=pid, name=hand.players[pid])

            # Init position stats
            if pos not in self.stats[pid].position_stats:
                self.stats[pid].position_stats[pos] = BaseStats()

            self.stats[pid].hands_played += 1
            self.stats[pid].position_stats[pos].hands_played += 1

        # --- Trackers for this hand ---
        # We need to track stats for Global AND Position specific
        # Helper to update both
        def update_stat(pid, field, increment=1):
            if pid not in self.stats: return
            # Update Global
            setattr(self.stats[pid], field, getattr(self.stats[pid], field) + increment)
            # Update Position
            pos = player_positions.get(pid, "Unknown")
            if pos in self.stats[pid].position_stats:
                p_stat = self.stats[pid].position_stats[pos]
                setattr(p_stat, field, getattr(p_stat, field) + increment)

        did_vpip = set()
        did_pfr = set()
        did_3bet = set()
        did_4bet = set()
        did_5bet = set()

        # Facing stats
        faced_3bet = set()
        folded_to_3bet = set()
        faced_4bet = set()
        folded_to_4bet = set()
        faced_5bet = set()
        folded_to_5bet = set()

        # C-Bet
        preflop_aggressor = None

        actions_by_street = {
            Street.PREFLOP: [],
            Street.FLOP: [],
            Street.TURN: [],
            Street.RIVER: []
        }
        for action in hand.actions:
            if action.street in actions_by_street:
                actions_by_street[action.street].append(action)

        # --- Preflop ---
        pf_actions = actions_by_street[Street.PREFLOP]

        # State tracking for bets
        current_raise_count = 0

        # Logic for N-Bet:
        # 1 raise = PFR (Open)
        # 2 raises = 3-Bet
        # 3 raises = 4-Bet
        # 4 raises = 5-Bet

        # Track who made which bet to determine who is facing next
        last_bettor = None

        for action in pf_actions:
            pid = action.player_id

            # VPIP
            if action.action_type in [ActionType.CALL, ActionType.RAISE, ActionType.BET]:
                did_vpip.add(pid)

            # Bet/Raise Logic
            if action.action_type == ActionType.RAISE:
                current_raise_count += 1
                last_bettor = pid

                if current_raise_count == 1:
                    did_pfr.add(pid)
                    preflop_aggressor = pid
                elif current_raise_count == 2:
                    did_3bet.add(pid)
                    did_pfr.add(pid) # 3-bet is also a PFR
                    preflop_aggressor = pid
                elif current_raise_count == 3:
                    did_4bet.add(pid)
                    did_pfr.add(pid) # 4-bet is also a PFR
                    preflop_aggressor = pid
                elif current_raise_count >= 4: # 5-bet+
                    did_5bet.add(pid)
                    did_pfr.add(pid) # 5-bet is also a PFR
                    preflop_aggressor = pid

            # Fold Logic (Check what they faced)
            if action.action_type == ActionType.FOLD:
                # If current raise count is X, they folded to X-bet?
                # No, if raise count is 2 (3-bet happened), and I fold, I folded to 3-bet.
                if current_raise_count == 2:
                    folded_to_3bet.add(pid)
                elif current_raise_count == 3:
                    folded_to_4bet.add(pid)
                elif current_raise_count >= 4:
                    folded_to_5bet.add(pid)

            # Check "Faced" logic (Any action implies facing)

            # --- Pre-calculate Max Raise Count for this street ---
            # To know what the final state was.

            # Re-run for precise "Faced" and "Opp" logic

            # We need to know who made which raise to avoid "facing own raise"

            # Mapping: raise_level -> player_id
            raisers = {}
            # Re-scan to find raisers
            temp_rc = 0
            for action in pf_actions:
                if action.action_type == ActionType.RAISE:
                    temp_rc += 1
                    raisers[temp_rc] = action.player_id

            curr_raises = 0

            # Use sets to avoid double counting per player per hand
            had_3bet_opp = set()
            had_4bet_opp = set()
            had_5bet_opp = set()

            # Logic:
            # If current raise count = 1 (Open Raise happened):
            #   - Next players are facing PFR.
            #   - If they Act (Call/Fold/Raise), they had a chance to 3-Bet.
            #   - EXCEPTION: The Open Raiser himself is not facing PFR.

            for action in pf_actions:
                pid = action.player_id

                # Determine status BEFORE this action

                if curr_raises == 1:
                    # Facing Open Raise (Opportunity to 3-Bet)
                    # Exclude the Open Raiser (PFR)
                    if pid != raisers.get(1):
                        had_3bet_opp.add(pid)

                if curr_raises == 2:
                    # Facing 3-Bet (Opportunity to 4-Bet)
                    # Exclude the 3-Bettor
                    if pid != raisers.get(2):
                        had_4bet_opp.add(pid)
                        faced_3bet.add(pid)

                if curr_raises == 3:
                    # Facing 4-Bet (Opportunity to 5-Bet)
                    if pid != raisers.get(3):
                        had_5bet_opp.add(pid)
                        faced_4bet.add(pid)

                if curr_raises >= 4:
                    # Facing 5-bet+
                    if pid != raisers.get(curr_raises):
                        faced_5bet.add(pid)

                # Update State AFTER processing action
                if action.action_type == ActionType.RAISE:
                    curr_raises += 1

        # --- Post-flop (C-Bet & AF) ---
        c_bet_opp_player = preflop_aggressor
        made_c_bet = False
        faced_cbet_players = set()
        folded_to_cbet_players = set()

        flop_actions = actions_by_street[Street.FLOP]
        if c_bet_opp_player and len(flop_actions) > 0:
            aggressor_acted = False
            for action in flop_actions:
                if action.player_id == c_bet_opp_player:
                    aggressor_acted = True
                    if action.action_type == ActionType.BET:
                        made_c_bet = True
                    break

            if aggressor_acted:
                update_stat(c_bet_opp_player, 'c_bet_opp')
                if made_c_bet:
                    update_stat(c_bet_opp_player, 'c_bet_count')

        if made_c_bet:
            c_bet_index = -1
            for i, action in enumerate(flop_actions):
                if action.player_id == c_bet_opp_player and action.action_type == ActionType.BET:
                    c_bet_index = i
                    break

            if c_bet_index != -1:
                for i in range(c_bet_index + 1, len(flop_actions)):
                    act = flop_actions[i]
                    if act.player_id != c_bet_opp_player:
                        faced_cbet_players.add(act.player_id)
                        if act.action_type == ActionType.FOLD:
                            folded_to_cbet_players.add(act.player_id)

        # --- WWSF / WWSR / WWST ---
        # WWSF: Won When Saw Flop
        # Denom: Players who saw flop (not folded preflop)
        # Num: Won hand (and saw flop)

        # Check if flop occurred
        if len(actions_by_street[Street.FLOP]) > 0 or len(actions_by_street[Street.TURN]) > 0 or len(actions_by_street[Street.RIVER]) > 0 or len(hand.community_cards) >= 3:
             saw_flop_players = set()
             for pid in players_in_hand:
                 # Check if they folded preflop
                 folded_pre = False
                 for action in pf_actions:
                     if action.player_id == pid and action.action_type == ActionType.FOLD:
                         folded_pre = True
                         break
                 if not folded_pre:
                     saw_flop_players.add(pid)

             for pid in saw_flop_players:
                 update_stat(pid, 'seen_flop_count')
                 if pid in winners:
                     update_stat(pid, 'won_when_seen_flop_count')

        # Check Turn
        if len(actions_by_street[Street.TURN]) > 0 or len(actions_by_street[Street.RIVER]) > 0 or len(hand.community_cards) >= 4:
            saw_turn_players = set()
            # Must have seen flop AND not folded on flop
            for pid in players_in_hand:
                folded_pre_or_flop = False
                # Check preflop fold
                for action in pf_actions:
                    if action.player_id == pid and action.action_type == ActionType.FOLD:
                        folded_pre_or_flop = True
                        break
                if folded_pre_or_flop: continue

                # Check flop fold
                for action in actions_by_street[Street.FLOP]:
                    if action.player_id == pid and action.action_type == ActionType.FOLD:
                        folded_pre_or_flop = True
                        break

                if not folded_pre_or_flop:
                    saw_turn_players.add(pid)

            for pid in saw_turn_players:
                update_stat(pid, 'seen_turn_count')
                if pid in winners:
                    update_stat(pid, 'won_when_seen_turn_count')

        # Check River
        if len(actions_by_street[Street.RIVER]) > 0 or len(hand.community_cards) >= 5:
            saw_river_players = set()
            for pid in players_in_hand:
                folded_early = False
                # Check folds on Pre, Flop, Turn
                for street in [Street.PREFLOP, Street.FLOP, Street.TURN]:
                    for action in actions_by_street[street]:
                         if action.player_id == pid and action.action_type == ActionType.FOLD:
                             folded_early = True
                             break
                    if folded_early: break

                if not folded_early:
                    saw_river_players.add(pid)

            for pid in saw_river_players:
                update_stat(pid, 'seen_river_count')
                if pid in winners:
                    update_stat(pid, 'won_when_seen_river_count')

        # --- Showdown ---
        # Re-calculate WTSD logic based on Definition:
        # WTSD = (Hands went to showdown / Hands saw flop)
        # Note: Some definitions say "Hands went to showdown / Hands played" but "Hands saw flop" is more accurate for post-flop tendency.
        # However, standard HUDs (HM2/PT4) usually use: WTSD% = (Times went to SD / Times saw flop)
        # BUT your current code uses: WTSD = (Times went to SD / Total Hands Played) which is WRONG if looking for standard definition.
        # Let's align with standard: WTSD = (Times went to SD / Times seen flop)
        # If user folds preflop, it shouldn't count against their WTSD.

        # Update: User requested "WTSD: Player saw flop and went to showdown %"
        # My previous code: "wtsd": pct(s.wtsd_count, s.hands_played) -> This is definitely wrong (denominator is too big).
        # Correct denominator should be s.seen_flop_count.

        # Logic for WTSD numerator (wtsd_count) is already correct (players at showdown).
        # Logic for WTSD denominator: I will use seen_flop_count in get_summary.

        showdown_occurred = any(a.action_type == ActionType.SHOW for a in hand.actions)
        players_at_showdown = set()
        if showdown_occurred:
            for action in hand.actions:
                if action.action_type == ActionType.SHOW:
                    players_at_showdown.add(action.player_id)

            winners_at_showdown = players_at_showdown.intersection(winners)
            for pid in players_at_showdown:
                update_stat(pid, 'wtsd_count')
                if pid in winners_at_showdown:
                    update_stat(pid, 'won_at_showdown_count')

        # --- Apply Bulk Stats ---
        for pid in players_in_hand:
            if pid in did_vpip: update_stat(pid, 'vpip_count')
            if pid in did_pfr: update_stat(pid, 'pfr_count')
            if pid in did_3bet: update_stat(pid, 'three_bet_count')
            if pid in did_4bet: update_stat(pid, 'four_bet_count')
            if pid in did_5bet: update_stat(pid, 'five_bet_count')

            if pid in had_3bet_opp: update_stat(pid, 'three_bet_opp')
            if pid in had_4bet_opp: update_stat(pid, 'four_bet_opp')
            if pid in had_5bet_opp: update_stat(pid, 'five_bet_opp')

            if pid in faced_3bet: update_stat(pid, 'faced_3bet_count')
            if pid in folded_to_3bet: update_stat(pid, 'fold_to_3bet_count')

            if pid in faced_4bet: update_stat(pid, 'faced_4bet_count')
            if pid in folded_to_4bet: update_stat(pid, 'fold_to_4bet_count')

            if pid in faced_5bet: update_stat(pid, 'faced_5bet_count')
            if pid in folded_to_5bet: update_stat(pid, 'fold_to_5bet_count')

            if pid in faced_cbet_players: update_stat(pid, 'faced_cbet_count')
            if pid in folded_to_cbet_players: update_stat(pid, 'fold_to_cbet_count')

            if pid in winners: update_stat(pid, 'won_hand_count')

            # AF
            for street in [Street.FLOP, Street.TURN, Street.RIVER]:
                for action in actions_by_street[street]:
                    if action.player_id == pid:
                        if action.action_type in [ActionType.BET, ActionType.RAISE]:
                            update_stat(pid, 'aggression_actions')
                        elif action.action_type == ActionType.CALL:
                            update_stat(pid, 'call_actions')
