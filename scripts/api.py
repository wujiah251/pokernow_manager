#!/usr/bin/env python3
"""
德州扑克数据管理系统 - Flask API 服务
"""

import os
import sys
import csv
import io
import logging
import argparse
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import db

# 解析命令行参数
parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', type=str, help='配置文件路径')
args = parser.parse_args()

# 初始化数据库路径
db.init_db_path(args.config)

# 配置日志
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "api.log"), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# 确保数据库已初始化
db.init_db()
logger.info("=" * 50)
logger.info("德州扑克数据管理系统启动")
logger.info(f"日志目录: {LOG_DIR}")
logger.info("=" * 50)


# ========== 玩家接口 ==========

@app.route('/api/players', methods=['GET'])
def get_players():
    """获取所有玩家和别名映射"""
    players = db.GetAllPlayers()
    return jsonify(players)


@app.route('/api/players', methods=['POST'])
def add_player():
    """添加或更新玩家映射"""
    data = request.get_json()
    nickname = data.get('nickname')
    alias = data.get('alias')

    if not nickname:
        logger.warning(f"添加玩家映射失败: nickname 为空")
        return jsonify({'error': 'nickname is required'}), 400

    if not alias:
        logger.warning(f"添加玩家映射失败: alias 为空")
        return jsonify({'error': 'alias is required'}), 400

    try:
        # 检查 alias 是否已被其他 nickname 使用（区分大小写）
        conn = db.get_connection()
        cursor = conn.cursor()
        # 直接用字符串拼接 alias，避免参数化查询的默认大小写问题
        cursor.execute(f"SELECT nickname, alias FROM players WHERE alias = '{alias}' COLLATE BINARY AND nickname != ?", (nickname,))
        existing = cursor.fetchone()
        conn.close()

        if existing:
            logger.warning(f"添加玩家映射失败: alias {alias} 已被 {existing['nickname']} 使用")
            return jsonify({'error': f"alias '{alias}' 已被 '{existing['nickname']}' 使用"}), 400

        # 使用新的映射函数，会自动更新历史数据
        logger.info(f"添加玩家映射: {alias} -> {nickname}")
        success, updated, error_msg = db.AddPlayerMapping(nickname, alias)
        if success:
            logger.info(f"添加成功: {alias} -> {nickname}, 更新了 {updated} 条记录")
            return jsonify({'success': True, 'updated': updated})
        else:
            logger.error(f"添加失败: {alias} -> {nickname}, {error_msg}")
            return jsonify({'error': error_msg or '添加失败'}), 500
    except Exception as e:
        logger.exception(f"添加玩家映射异常: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/players/rename', methods=['POST'])
def rename_player():
    """重命名玩家昵称"""
    data = request.get_json()
    old_nickname = data.get('old_nickname')
    new_nickname = data.get('new_nickname')

    if not old_nickname or not new_nickname:
        logger.warning(f"重命名玩家失败: 参数为空")
        return jsonify({'error': 'old_nickname and new_nickname are required'}), 400

    if old_nickname == new_nickname:
        return jsonify({'success': True, 'updated': 0})

    try:
        logger.info(f"重命名玩家: {old_nickname} -> {new_nickname}")
        success, updated = db.RenamePlayer(old_nickname, new_nickname)
        if success:
            logger.info(f"重命名成功: {old_nickname} -> {new_nickname}, 更新了 {updated} 条记录")
            return jsonify({'success': True, 'updated': updated})
        else:
            logger.error(f"重命名失败: {old_nickname} -> {new_nickname}")
            return jsonify({'error': '重命名失败'}), 500
    except Exception as e:
        logger.exception(f"重命名玩家异常: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/players/<nickname>', methods=['DELETE'])
def delete_player(nickname):
    """删除玩家映射"""
    if not nickname:
        return jsonify({'error': 'nickname is required'}), 400

    try:
        logger.info(f"删除玩家映射: {nickname}")
        success, deleted = db.DeletePlayerMapping(nickname)
        if success:
            logger.info(f"删除成功: {nickname}")
            return jsonify({'success': True, 'deleted': deleted})
        else:
            logger.error(f"删除失败: {nickname}")
            return jsonify({'error': '删除失败'}), 500
    except Exception as e:
        logger.exception(f"删除玩家异常: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/players/all', methods=['GET'])
def get_all_player_names():
    """获取所有参与过游戏的玩家昵称（用于下拉选择）"""
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT DISTINCT player_nickname
            FROM daily_pnl
            ORDER BY player_nickname
        """)
        players = [row['player_nickname'] for row in cursor.fetchall()]
        return jsonify(players)
    finally:
        conn.close()


# ========== PnL 接口 ==========

@app.route('/api/pnl/<date>', methods=['GET'])
def get_pnl(date):
    """获取指定日期的 PnL 记录（只返回 date, nickname 和 net）"""
    player_nickname = request.args.get('player')
    records = db.QueryPnlRecord(date, player_nickname)
    # 只返回 date, player_nickname 和 total_net
    simplified = [{'date': r['date'], 'player_nickname': r['player_nickname'], 'total_net': r['total_net']} for r in records]
    return jsonify(simplified)


@app.route('/api/pnl/range', methods=['GET'])
def get_pnl_range():
    """获取日期范围内的 PnL（用于曲线图）"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    player = request.args.get('player')

    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        if player:
            cursor.execute("""
                SELECT date, player_nickname, total_net
                FROM daily_pnl
                WHERE date >= ? AND date <= ? AND player_nickname = ?
                ORDER BY date
            """, (start_date, end_date, player))
        else:
            # 获取所有玩家的累计 PnL
            cursor.execute("""
                SELECT date, SUM(total_net) as total_net
                FROM daily_pnl
                WHERE date >= ? AND date <= ?
                GROUP BY date
                ORDER BY date
            """, (start_date, end_date))

        results = [dict(row) for row in cursor.fetchall()]
        return jsonify(results)
    finally:
        conn.close()


@app.route('/api/pnl/cumulative', methods=['GET'])
def get_cumulative_pnl():
    """获取累计 PnL（用于曲线图）"""
    player = request.args.get('player')

    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        if player:
            cursor.execute("""
                SELECT date, player_nickname, total_net
                FROM daily_pnl
                WHERE player_nickname = ?
                ORDER BY date
            """, (player,))

            # 计算累计
            records = [dict(row) for row in cursor.fetchall()]
            cumulative = 0
            for r in records:
                cumulative += r['total_net']
                r['cumulative_net'] = cumulative
            return jsonify(records)
        else:
            # 获取所有玩家的累计
            cursor.execute("""
                SELECT date, SUM(total_net) as total_net
                FROM daily_pnl
                GROUP BY date
                ORDER BY date
            """)

            records = [dict(row) for row in cursor.fetchall()]
            cumulative = 0
            for r in records:
                cumulative += r['total_net']
                r['cumulative_net'] = cumulative
            return jsonify(records)
    finally:
        conn.close()


@app.route('/api/pnl/range/cumulative', methods=['GET'])
def get_range_cumulative_pnl():
    """获取指定日期范围内的累计 PnL（用于曲线图）"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    player = request.args.get('player')

    if not start_date or not end_date:
        return jsonify({'error': 'start and end dates are required'}), 400

    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        if player:
            cursor.execute("""
                SELECT date, player_nickname, total_net
                FROM daily_pnl
                WHERE date >= ? AND date <= ? AND player_nickname = ?
                ORDER BY date
            """, (start_date, end_date, player))
        else:
            # 获取所有玩家的每日总计，然后计算累计
            cursor.execute("""
                SELECT date, SUM(total_net) as total_net
                FROM daily_pnl
                WHERE date >= ? AND date <= ?
                GROUP BY date
                ORDER BY date
            """, (start_date, end_date))

        records = [dict(row) for row in cursor.fetchall()]

        # 计算累计
        cumulative = 0
        for r in records:
            cumulative += r['total_net']
            r['cumulative_net'] = cumulative

        return jsonify(records)
    finally:
        conn.close()


@app.route('/api/pnl/range/all', methods=['GET'])
def get_range_all_players_pnl():
    """获取所有玩家在指定日期范围内的每日 PnL（用于多线曲线图）"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')

    if not start_date or not end_date:
        return jsonify({'error': 'start and end dates are required'}), 400

    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        # 获取所有玩家在日期范围内的每日数据
        cursor.execute("""
            SELECT date, player_nickname, total_net
            FROM daily_pnl
            WHERE date >= ? AND date <= ?
            ORDER BY date, player_nickname
        """, (start_date, end_date))

        raw_records = [dict(row) for row in cursor.fetchall()]

        # 按玩家分组，计算每个玩家的累计
        player_data = {}
        for r in raw_records:
            player = r['player_nickname']
            if player not in player_data:
                player_data[player] = []
            player_data[player].append(r)

        # 构建返回数据
        result = {}
        dates = sorted(set(r['date'] for r in raw_records))

        for player, records in player_data.items():
            # 按日期排序
            records.sort(key=lambda x: x['date'])
            # 计算累计
            cumulative = 0
            for r in records:
                cumulative += r['total_net']
                r['cumulative_net'] = cumulative
            result[player] = records

        return jsonify({
            'dates': dates,
            'players': result
        })
    finally:
        conn.close()


@app.route('/api/pnl/cumulative/to/<end_date>', methods=['GET'])
def get_cumulative_pnl_to_date(end_date):
    """获取从最早日期到指定日期的累计PnL（用于表格累计列）"""
    player = request.args.get('player')

    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        # 获取最早日期
        cursor.execute("SELECT MIN(date) as min_date FROM daily_pnl")
        min_date_row = cursor.fetchone()
        min_date = min_date_row['min_date'] if min_date_row else None

        if not min_date:
            return jsonify([])

        if player:
            cursor.execute("""
                SELECT date, player_nickname, total_net
                FROM daily_pnl
                WHERE player_nickname = ? AND date <= ?
                ORDER BY date
            """, (player, end_date))
        else:
            cursor.execute("""
                SELECT date, player_nickname, total_net
                FROM daily_pnl
                WHERE date <= ?
                ORDER BY date
            """, (end_date,))

        records = [dict(row) for row in cursor.fetchall()]

        # 计算累计
        cumulative = 0
        player_cumulative = {}
        for r in records:
            if player:
                cumulative += r['total_net']
                r['cumulative_net'] = cumulative
            else:
                # 汇总所有玩家
                p = r['player_nickname']
                if p not in player_cumulative:
                    player_cumulative[p] = 0
                player_cumulative[p] += r['total_net']
                r['cumulative_net'] = player_cumulative[p]

        if player:
            return jsonify(records)
        else:
            # 返回每个玩家的最终累计值
            result = [{'player_nickname': p, 'cumulative_net': c} for p, c in player_cumulative.items()]
            return jsonify(result)
    finally:
        conn.close()


@app.route('/api/pnl/range/selected', methods=['GET'])
def get_range_selected_players_pnl():
    """获取指定日期范围内选定玩家的每日PnL（用于多选曲线图）"""
    start_date = request.args.get('start')
    end_date = request.args.get('end')
    players_param = request.args.get('players')  # 逗号分隔的玩家列表

    if not start_date or not end_date:
        return jsonify({'error': 'start and end dates are required'}), 400

    if not players_param:
        return jsonify({'error': 'players is required'}), 400

    selected_players = [p.strip() for p in players_param.split(',') if p.strip()]
    if not selected_players:
        return jsonify({'error': 'no valid players selected'}), 400

    placeholders = ','.join(['?' for _ in selected_players])
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        # 获取选定玩家在日期范围内的每日数据
        cursor.execute(f"""
            SELECT date, player_nickname, total_net
            FROM daily_pnl
            WHERE date >= ? AND date <= ? AND player_nickname IN ({placeholders})
            ORDER BY date, player_nickname
        """, [start_date, end_date] + selected_players)

        raw_records = [dict(row) for row in cursor.fetchall()]

        # 获取所有日期（没有包含数据的日期）
        cursor.execute("""
            SELECT DISTINCT date FROM daily_pnl
            WHERE date >= ? AND date <= ?
            ORDER BY date
        """, (start_date, end_date))
        all_dates = [row['date'] for row in cursor.fetchall()]

        # 按玩家分组，计算每个玩家的累计
        player_data = {}
        for p in selected_players:
            player_data[p] = []

        for r in raw_records:
            player = r['player_nickname']
            player_data[player].append(r)

        # 构建返回数据
        result = {}
        for player, records in player_data.items():
            if not records:
                continue
            records.sort(key=lambda x: x['date'])
            cumulative = 0
            for r in records:
                cumulative += r['total_net']
                r['cumulative_net'] = cumulative
            result[player] = records

        return jsonify({
            'dates': all_dates,
            'players': result
        })
    finally:
        conn.close()


@app.route('/api/dates', methods=['GET'])
def get_dates():
    """获取所有有数据的日期"""
    dates = db.GetAllDates()
    return jsonify(dates)


# ========== Hand Tags 接口 ==========

@app.route('/api/hand_tags/rebuild', methods=['POST'])
def rebuild_hand_tags():
    """重建 hand_tags 表"""
    try:
        logger.info("开始重建 hand_tags")
        count = db.rebuild_hand_tags()
        logger.info(f"重建完成，共 {count} 条标签")
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        logger.exception(f"重建 hand_tags 失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/hand_tags/count', methods=['GET'])
def get_hand_tags_count():
    """查询满足条件的 hand 数量"""
    nickname = request.args.get('nickname')
    tags_param = request.args.get('tags')
    operator = request.args.get('operator', 'AND')

    if not nickname:
        return jsonify({'error': 'nickname is required'}), 400

    tags = []
    if tags_param:
        tags = [t.strip() for t in tags_param.split(',') if t.strip()]

    try:
        count = db.query_player_hands(nickname, tags, operator)
        return jsonify({'nickname': nickname, 'count': count, 'tags': tags, 'operator': operator})
    except Exception as e:
        logger.exception(f"查询 hand_tags 失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/players/stats', methods=['GET'])
def get_player_stats():
    """获取玩家统计指标"""
    nickname = request.args.get('nickname')

    if not nickname:
        return jsonify({'error': 'nickname is required'}), 400

    try:
        stats = db.get_player_stats(nickname)
        return jsonify({'nickname': nickname, 'stats': stats})
    except Exception as e:
        logger.exception(f"查询玩家统计失败: {e}")
        return jsonify({'error': str(e)}), 500


# ========== 对局记录接口 ==========

@app.route('/api/ledger/<date>', methods=['GET'])
def get_ledger(date):
    """获取指定日期的对局记录"""
    player_id = request.args.get('player_id')
    records = db.QueryLedger(date, player_id)
    return jsonify(records)


# ========== 上传接口 ==========

@app.route('/api/ledger/precheck', methods=['POST'])
def precheck_ledger():
    """预检查 ledger CSV 文件中的玩家是否已映射"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    try:
        stream = io.StringIO(file.stream.read().decode('UTF-8'), newline=None)
        reader = csv.DictReader(stream)

        aliases = set()
        for row in reader:
            alias = row.get('player_nickname', '')
            if alias:
                aliases.add(alias)

        # 检查哪些 alias 没有映射
        unmapped = db.CheckPlayerMapping(list(aliases))

        return jsonify({
            'unmapped_players': unmapped,
            'has_unmapped': len(unmapped) > 0
        })

    except Exception as e:
        logger.exception(f"预检查失败: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ledger/upload', methods=['POST'])
def upload_ledger():
    """上传 ledger CSV 文件"""
    if 'file' not in request.files:
        logger.warning("上传文件失败: 没有文件")
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    date = request.form.get('date')

    if not file:
        logger.warning("上传文件失败: 文件为空")
        return jsonify({'error': 'No file selected'}), 400

    if not date:
        logger.warning("上传文件失败: 日期为空")
        return jsonify({'error': 'Date is required'}), 400

    # 解析 CSV
    try:
        logger.info(f"上传文件: {file.filename}, 日期: {date}")
        stream = io.StringIO(file.stream.read().decode('UTF-8'), newline=None)
        reader = csv.DictReader(stream)

        records = []
        nicknames = set()
        unmapped_players = []
        for row in reader:
            # 标准化数据
            alias = row.get('player_nickname', '')
            # 将 alias 解析为真实的 nickname
            nickname = db.ResolvePlayerNickname(alias)

            if nickname is None:
                # alias 不存在，记录下来继续处理其他记录
                if alias and alias not in unmapped_players:
                    unmapped_players.append(alias)
                continue

            record = {
                'player_nickname': nickname,
                'player_id': row.get('player_id', ''),
                'session_start_at': row.get('session_start_at'),
                'session_end_at': row.get('session_end_at'),
                'buy_in': int(float(row.get('buy_in', 0) or 0)),
                'buy_out': int(float(row.get('buy_out', 0) or 0)),
                'stack': int(float(row.get('stack', 0) or 0)),
                'net': int(float(row.get('net', 0) or 0)),
            }
            records.append(record)
            nicknames.add(nickname)

        # 如果有没有映射的玩家，报错
        if unmapped_players:
            logger.warning(f"上传文件失败: 以下玩家未找到映射 {unmapped_players}")
            return jsonify({
                'error': f"以下玩家未在映射表中: {', '.join(unmapped_players)}",
                'unmapped_players': unmapped_players
            }), 400

        if not records:
            return jsonify({'error': '没有有效的记录'}), 400

        # 检查并自动添加新玩家
        if nicknames:
            new_players = db.EnsurePlayersExist(list(nicknames))
            if new_players:
                logger.info(f"自动添加新玩家: {new_players}")

        # 保存到数据库
        if db.SaveLedger(date, records, file.filename):
            # 计算每日 PnL
            db.CalculateDailyPnl(date)
            logger.info(f"上传成功: {len(records)} 条记录, 日期: {date}")
            return jsonify({'success': True, 'count': len(records), 'new_players': new_players})

        logger.error(f"保存失败: {file.filename}, 日期: {date}")
        return jsonify({'error': 'Failed to save data'}), 500

    except Exception as e:
        logger.exception(f"上传文件异常: {e}")
        return jsonify({'error': str(e)}), 500


# ========== 删除接口 ==========

@app.route('/api/delete', methods=['POST'])
def delete_records():
    """删除指定日期范围内的 PnL 和对局记录"""
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    delete_pnl = data.get('delete_pnl', True)
    delete_ledger = data.get('delete_ledger', True)

    if not start_date or not end_date:
        logger.warning(f"删除记录失败: 日期范围为空")
        return jsonify({'error': 'start_date and end_date are required'}), 400

    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        deleted_pnl = 0
        deleted_ledger = 0

        if delete_pnl:
            cursor.execute("""
                DELETE FROM daily_pnl WHERE date >= ? AND date <= ?
            """, (start_date, end_date))
            deleted_pnl = cursor.rowcount

        if delete_ledger:
            cursor.execute("""
                DELETE FROM ledger WHERE date >= ? AND date <= ?
            """, (start_date, end_date))
            deleted_ledger = cursor.rowcount

        conn.commit()
        logger.info(f"删除记录: {start_date} ~ {end_date}, PNL: {deleted_pnl}, Ledger: {deleted_ledger}")
        return jsonify({
            'success': True,
            'deleted_pnl': deleted_pnl,
            'deleted_ledger': deleted_ledger
        })

    except Exception as e:
        conn.rollback()
        logger.exception(f"删除记录异常: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ========== 静态文件服务 ==========

@app.route('/')
def index():
    """返回前端页面"""
    return send_from_directory('../frontend', 'index.html')


if __name__ == '__main__':
    import configparser
    port = 8080
    if args.config and os.path.exists(args.config):
        config = configparser.ConfigParser()
        config.read(args.config)
        port = config.getint('server', 'port', fallback=8080)
    else:
        port = int(os.environ.get('PORT', 8080))
    print(f"启动德州扑克数据管理系统: http://localhost:{port}")
    print(f"数据库路径: {db.DB_PATH}")
    app.run(host='0.0.0.0', port=port, debug=True)
