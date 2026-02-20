# Tag 定义文档

本文档定义每个 tag 的完整匹配规则和真实日志示例。

---

## 重要说明

### 翻前动作的特殊性
在翻牌前阶段，以下动作**本身就是该玩家在翻前的最后一个动作**：
- `preflop_call`：玩家跟注后，等待翻牌圈（除非有人再加注）
- `preflop_raise`：玩家加注后，等待其他人行动
- `preflop_allin`：玩家全下后，等待翻牌圈
- `preflop_fold`：玩家弃牌后，本局游戏与其无关

因此，这些 tag 的匹配规则是：**该玩家在翻前阶段是否执行过该动作**。

---

## 阶段一：Preflop（翻牌前）

### 标签列表

| Tag | 匹配规则 | 说明 |
|-----|----------|------|
| `participated` | 所有参与玩家 | 每局必打 |
| `preflop_sb` | blind_type='small' | 小盲 |
| `preflop_bb` | blind_type='big' | 大盲 |
| `preflop_sb` | 只有1个 blind，默认算大盲 | 只有一个盲注时 |
| `preflop_call` | 该玩家在 preflop 有 call 动作 | 翻前跟注 |
| `preflop_raise` | 该玩家在 preflop 有 raise 动作 | 翻前加注 |
| `preflop_allin` | 该玩家在 preflop 有 allin 动作 | 翻前全下 |
| `preflop_fold` | 该玩家在 preflop 有 fold 动作 | 翻前弃牌 |
| `voluntarily_put_in` | 翻前有 call/bet/raise/allin（非 blind） | 主动入池 |
| `preflop_open_raise` | 翻前第一个 raise 的玩家 | 公开加注（open raise） |
| `preflop_last_raiser` | 翻前最后一个 raise 的玩家 | 翻前最后加注者 |
| `preflop_3bet` | 翻前第2个 raise 的玩家 | 3-bet（反加注） |
| `preflop_4bet` | 翻前第3个 raise 的玩家 | 4-bet |

### 真实日志示例

#### 示例1：wjh open raise 后 everyone fold
```json
{
  "preflop": [
    {"player": "hyq", "action": "blind", "blind_type": "small", "amount": 1},
    {"player": "ran", "action": "blind", "blind_type": "big", "amount": 2},
    {"player": "wjh", "action": "raise", "amount": 5},
    {"player": "wyf", "action": "fold"},
    {"player": "cy", "action": "fold"},
    {"player": "hyq", "action": "fold"},
    {"player": "ran", "action": "fold"}
  ]
}
```
**匹配结果：**
- `hyq`: participated, preflop_sb
- `ran`: participated, preflop_bb, preflop_fold（盲注后弃牌）
- `wjh`: participated, preflop_raise, preflop_open_raise, preflop_last_raiser, voluntarily_put_in
- `wyf`: participated, preflop_fold
- `cy`: participated, preflop_fold

#### 示例2：cy open raise，ran call
```json
{
  "preflop": [
    {"player": "hyq", "action": "blind", "blind_type": "small", "amount": 1},
    {"player": "ran", "action": "blind", "blind_type": "big", "amount": 2},
    {"player": "wjh", "action": "fold"},
    {"player": "cy", "action": "raise", "amount": 7},
    {"player": "hyq", "action": "fold"},
    {"player": "ran", "action": "call", "amount": 7}
  ]
}
```
**匹配结果：**
- `hyq`: participated, preflop_sb, preflop_fold
- `ran`: participated, preflop_bb, preflop_call, voluntarily_put_in
- `wjh`: participated, preflop_fold
- `cy`: participated, preflop_raise, preflop_open_raise, preflop_last_raiser, voluntarily_put_in

---

## 阶段二：Flop（翻牌圈）

### 标签列表

| Tag | 匹配规则 | 说明 |
|-----|----------|------|
| `saw_flop` | 该玩家进入了翻牌圈（非 fold 且非 allin 输） | 看到翻牌 |
| `flop_bet` | 该玩家在 flop 有 bet 动作 | 翻牌圈下注 |
| `flop_raise` | 该玩家在 flop 有 raise 动作 | 翻牌圈加注 |
| `flop_call` | 该玩家在 flop 有 call 动作 | 翻牌圈跟注 |
| `flop_fold` | 该玩家在 flop 有 fold 动作 | 翻牌圈弃牌 |
| `flop_check` | 该玩家在 flop 有 check 动作 | 翻牌圈看牌 |
| `flop_cbet` | preflop_last_raiser 且 flop 第一个 bet/raise 的玩家 | 持续下注 |
| `flop_donk` | 非 preflop_last_raiser 在 flop 主动 bet | 主动下注（donk bet） |

### 匹配规则详解

#### saw_flop
- 条件：该玩家在 flop 有任何非 fold 的动作
- 或者：该玩家没有在翻前 fold
- 排除：该玩家在翻前 fold，则不可能看到 flop

#### flop_cbet（持续下注）
- 条件1：该玩家是 preflop_last_raiser
- 条件2：该玩家是 flop 第一个 bet 或 raise 的玩家
- 两个条件必须同时满足

### 真实日志示例

```json
{
  "preflop": [...],
  "flop": [
    {"player": "hyq", "action": "check"},
    {"player": "ran", "action": "bet", "amount": 8},
    {"player": "hyq", "action": "raise", "amount": 24},
    {"player": "ran", "action": "call", "amount": 24}
  ]
}
```
**匹配结果：**
- `hyq`: saw_flop, flop_check, flop_raise（flop 第一个 action）
- `ran`: saw_flop, flop_bet, flop_call

---

## 阶段三：Turn（转牌圈）

### 标签列表

| Tag | 匹配规则 | 说明 |
|-----|----------|------|
| `saw_turn` | 该玩家进入了转牌圈 | 看到转牌 |
| `turn_bet` | 该玩家在 turn 有 bet 动作 | 转牌圈下注 |
| `turn_raise` | 该玩家在 turn 有 raise 动作 | 转牌圈加注 |
| `turn_call` | 该玩家在 turn 有 call 动作 | 转牌圈跟注 |
| `turn_fold` | 该玩家在 turn 有 fold 动作 | 转牌圈弃牌 |
| `turn_check` | 该玩家在 turn 有 check 动作 | 转牌圈看牌 |

### saw_turn 匹配规则
- 条件：该玩家在 turn 有任何非 fold 的动作
- 或者：该玩家有 saw_flop 且没有在 flop fold

---

## 阶段四：River（河牌圈）

### 标签列表

| Tag | 匹配规则 | 说明 |
|-----|----------|------|
| `saw_river` | 该玩家进入了河牌圈 | 看到河牌 |
| `river_bet` | 该玩家在 river 有 bet 动作 | 河牌圈下注 |
| `river_raise` | 该玩家在 river 有 raise 动作 | 河牌圈加注 |
| `river_call` | 该玩家在 river 有 call 动作 | 河牌圈跟注 |
| `river_fold` | 该玩家在 river 有 fold 动作 | 河牌圈弃牌 |
| `saw_showdown` | 该玩家进入了河牌圈且没有 fold | 看到摊牌 |

### saw_showdown 匹配规则
- 条件：该玩家在 river 有任何非 fold 的动作
- 或者：该玩家有 saw_river 且没有在 river fold

---

## 全局标签（需结合 hand_players 表）

| Tag | 匹配规则 | 说明 |
|-----|----------|------|
| `won_at_showdown` | hand_players.is_winner = TRUE | 摊牌获胜 |
| `lost_at_showdown` | saw_showdown = TRUE 且 is_winner = FALSE | 摊牌输掉 |

---

## 统计指标与 Tag 对应

| 指标 | 分子 Tag | 分母 Tag |
|------|----------|----------|
| VPIP | voluntarily_put_in | participated |
| PFR | preflop_raise | participated |
| 3-Bet | preflop_3bet | preflop_open_raise（遇到 open raise 的玩家） |
| C-Bet | flop_cbet | preflop_last_raiser 且 saw_flop |
| WTSD | saw_showdown | voluntarily_put_in |
| W$SD | won_at_showdown | saw_showdown |

---

## Match 函数签名

```python
def match_tag(action_line: Dict, hand_players: List[Dict], tag: str) -> Dict[str, bool]:
    """
    参数:
        action_line: hands 表中的 action_line JSON
        hand_players: hand_players 表中该手牌的所有玩家列表
        tag: 标签名称

    返回: {nickname: True/False}，表示该玩家是否满足该 tag
    """
```

### 实现提示

1. **翻前 tag（preflop_call, preflop_raise 等）**：遍历 preflop 数组，检查是否有该动作
2. **各阶段 tag（flop_bet, turn_raise 等）**：遍历对应阶段数组
3. **复合 tag（saw_flop, saw_turn 等）**：需要根据前置阶段判断
4. **计数 tag（preflop_open_raise, preflop_last_raiser 等）**：需要遍历计数
