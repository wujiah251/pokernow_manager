from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime

class ActionType:
    POST_SB = "POST_SB"
    POST_BB = "POST_BB"
    POST_STRADDLE = "POST_STRADDLE"
    POST = "POST"
    FOLD = "FOLD"
    CHECK = "CHECK"
    CALL = "CALL"
    BET = "BET"
    RAISE = "RAISE"
    SHOW = "SHOW"
    WIN = "WIN"
    UNCALLED = "UNCALLED"

class Street:
    PREFLOP = "PREFLOP"
    FLOP = "FLOP"
    TURN = "TURN"
    RIVER = "RIVER"
    SHOWDOWN = "SHOWDOWN"

class Action(BaseModel):
    player_name: str
    player_id: str
    action_type: str
    amount: float = 0.0
    street: str
    raw_log: str
    timestamp: datetime

class Hand(BaseModel):
    hand_id: str
    date: datetime
    actions: List[Action] = []
    players: Dict[str, str] = {}  # id -> name (Players who acted)
    seated_players: List[str] = [] # list of player_ids in seat order
    dealer_name: Optional[str] = None # Name of dealer
    dealer_id: Optional[str] = None # ID of dealer (if parsable)
    small_blind: float = 0.0
    big_blind: float = 0.0
    is_bomb_pot: bool = False
    community_cards: List[str] = []
    winners: List[str] = [] # list of player_ids who won

class BaseStats(BaseModel):
    hands_played: int = 0

    # Preflop
    vpip_count: int = 0
    pfr_count: int = 0
    three_bet_count: int = 0
    three_bet_opp: int = 0
    fold_to_3bet_count: int = 0
    faced_3bet_count: int = 0

    four_bet_count: int = 0
    four_bet_opp: int = 0
    fold_to_4bet_count: int = 0
    faced_4bet_count: int = 0

    five_bet_count: int = 0
    five_bet_opp: int = 0
    fold_to_5bet_count: int = 0
    faced_5bet_count: int = 0

    # Postflop
    c_bet_count: int = 0
    c_bet_opp: int = 0
    fold_to_cbet_count: int = 0
    faced_cbet_count: int = 0

    # Aggression
    aggression_actions: int = 0 # Bet + Raise (Post-flop)
    call_actions: int = 0 # Call (Post-flop)

    # Showdown
    wtsd_count: int = 0  # Went to Showdown
    won_at_showdown_count: int = 0 # Won money at showdown

    # WWSF / WWSR / WWST
    seen_flop_count: int = 0
    won_when_seen_flop_count: int = 0

    seen_river_count: int = 0
    won_when_seen_river_count: int = 0

    seen_turn_count: int = 0
    won_when_seen_turn_count: int = 0

    # General
    won_hand_count: int = 0
    total_winnings: float = 0.0

class PlayerStat(BaseStats):
    player_id: str
    name: str

    # Positional Stats: Key is position name (UTG, BTN, etc.) -> Stats object
    # To avoid circular dependency or recursion issues, we store a dictionary of BaseStats-like dicts
    position_stats: Dict[str, BaseStats] = {}
