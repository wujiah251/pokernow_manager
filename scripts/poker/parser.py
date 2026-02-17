import pandas as pd
import re
from typing import List, Dict
from .models import Hand, Action, ActionType, Street
from datetime import datetime

class PokerNowParser:
    def __init__(self):
        self.hands: List[Hand] = []

    def parse_csv(self, file_path: str) -> List[Hand]:
        df = pd.read_csv(file_path)
        # Sort by order ascending (chronological)
        if 'order' in df.columns:
            df = df.sort_values('order', ascending=True)
        else:
            # Fallback if order missing, assume reverse chronological and flip
            df = df.iloc[::-1]

        current_hand: Hand = None
        current_street = Street.PREFLOP
        hands = []

        player_pattern = re.compile(r'"(.*?)\s@\s(.*?)"')

        for index, row in df.iterrows():
            entry = row['entry']
            timestamp = pd.to_datetime(row['at'])

            # Start of Hand
            if "-- starting hand" in entry:
                if current_hand:
                    self._detect_bomb_pot(current_hand)
                    hands.append(current_hand)

                hand_id_match = re.search(r'hand #(\d+)', entry)
                hand_id = hand_id_match.group(1) if hand_id_match else "unknown"

                current_hand = Hand(hand_id=hand_id, date=timestamp)

                # Extract Dealer Name
                # "... (dealer: "Name") --"
                # Careful with quotes in name
                dealer_match = re.search(r'\(dealer: "(.*?)"\)', entry)
                if dealer_match:
                     # This name usually matches the alias part or full part?
                     # PokerNow logs: dealer: "hyq @ HZkdinonr0"
                     # So it captures the full string inside quotes usually
                     dealer_raw = dealer_match.group(1)
                     # Try to parse ID from it if possible
                     pm = player_pattern.search(f'"{dealer_raw}"') # Wrap in quotes to match pattern
                     if pm:
                         current_hand.dealer_name = pm.group(1)
                         current_hand.dealer_id = pm.group(2)
                     else:
                         # Fallback if format is just name
                         current_hand.dealer_name = dealer_raw

                current_street = Street.PREFLOP
                continue

            if not current_hand:
                continue

            # Player Stacks (Seat Order)
            if entry.startswith("Player stacks:"):
                # Format: Player stacks: #1 "Name @ ID" (100) | #2 ...
                # We need to extract IDs in order
                # Use regex to find all players in this line
                # The pattern matches "Name @ ID" inside quotes
                # But splits are by " | "
                parts = entry.split(" | ")
                for part in parts:
                    pm = player_pattern.search(part)
                    if pm:
                        p_id = pm.group(2)
                        p_name = pm.group(1)
                        current_hand.seated_players.append(p_id)
                        current_hand.players[p_id] = p_name # Ensure they are in players map
                continue

            # Street Changes
            if entry.startswith("Flop:"):
                current_street = Street.FLOP
                continue
            elif entry.startswith("Turn:"):
                current_street = Street.TURN
                continue
            elif entry.startswith("River:"):
                current_street = Street.RIVER
                continue
            elif "-- ending hand" in entry:
                continue

            # Player Actions
            # Extract player info first
            player_match = player_pattern.search(entry)
            if player_match:
                p_name = player_match.group(1)
                p_id = player_match.group(2)

                # Update player map
                current_hand.players[p_id] = p_name

                action_type = None
                amount = 0.0

                if "folds" in entry:
                    action_type = ActionType.FOLD
                elif "checks" in entry:
                    action_type = ActionType.CHECK
                elif "calls" in entry:
                    action_type = ActionType.CALL
                    amt_match = re.search(r'calls (\d+(\.\d+)?)', entry)
                    if amt_match:
                        amount = float(amt_match.group(1))
                elif "bets" in entry:
                    action_type = ActionType.BET
                    amt_match = re.search(r'bets (\d+(\.\d+)?)', entry)
                    if amt_match:
                        amount = float(amt_match.group(1))
                elif "raises to" in entry:
                    action_type = ActionType.RAISE
                    amt_match = re.search(r'raises to (\d+(\.\d+)?)', entry)
                    if amt_match:
                        amount = float(amt_match.group(1))
                elif "posts a small blind" in entry:
                    action_type = ActionType.POST_SB
                    amt_match = re.search(r'of (\d+(\.\d+)?)', entry)
                    if amt_match:
                        amount = float(amt_match.group(1))
                        current_hand.small_blind = amount
                elif "posts a big blind" in entry:
                    action_type = ActionType.POST_BB
                    amt_match = re.search(r'of (\d+(\.\d+)?)', entry)
                    if amt_match:
                        amount = float(amt_match.group(1))
                        current_hand.big_blind = amount
                elif "posts a straddle" in entry:
                    action_type = ActionType.POST_STRADDLE
                    amt_match = re.search(r'of (\d+(\.\d+)?)', entry)
                    if amt_match:
                        amount = float(amt_match.group(1))
                elif "posts" in entry:
                    action_type = ActionType.POST
                    # Try "posts X" or "posts ... of X"
                    amt_match = re.search(r'posts (\d+(\.\d+)?)', entry)
                    if not amt_match:
                         amt_match = re.search(r'of (\d+(\.\d+)?)', entry)

                    if amt_match:
                        amount = float(amt_match.group(1))
                elif "shows" in entry:
                    action_type = ActionType.SHOW
                    # Could parse cards here
                elif "collected" in entry:
                    action_type = ActionType.WIN
                    amt_match = re.search(r'collected (\d+(\.\d+)?)', entry)
                    if amt_match:
                        amount = float(amt_match.group(1))
                elif "Uncalled bet" in entry:
                    action_type = ActionType.UNCALLED
                elif "does not show" in entry or "mucks" in entry:
                    action_type = ActionType.SHOW
                    # Treat mucks as "Went to Showdown" (SHOW) but lost
                    # We use SHOW action to detect WTSD.
                    # Muck means they were at showdown.

                if action_type:
                    action = Action(
                        player_name=p_name,
                        player_id=p_id,
                        action_type=action_type,
                        amount=amount,
                        street=current_street,
                        raw_log=entry,
                        timestamp=timestamp
                    )
                    current_hand.actions.append(action)

        if current_hand:
            self._detect_bomb_pot(current_hand)
            hands.append(current_hand)

        return hands

    def _detect_bomb_pot(self, hand: Hand):
        # Bomb pot logic: Everyone seated posted something pre-flop.
        posters = set()
        posting_actions = [ActionType.POST_SB, ActionType.POST_BB, ActionType.POST_STRADDLE, ActionType.POST]

        for action in hand.actions:
            if action.street == Street.PREFLOP and action.action_type in posting_actions:
                posters.add(action.player_id)

        # If all seated players posted, it's likely a bomb pot
        if len(hand.seated_players) > 0 and len(posters) == len(hand.seated_players):
             hand.is_bomb_pot = True
