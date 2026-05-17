from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random
import os

app = Flask(__name__)
app.secret_key = 'hex_casino_secret_change_in_production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hexcasino.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=1000.0)
    total_wagered = db.Column(db.Float, default=0.0)
    total_won = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game = db.Column(db.String(50), nullable=False)
    bet = db.Column(db.Float, nullable=False)
    result = db.Column(db.Float, nullable=False)
    balance_after = db.Column(db.Float, nullable=False)
    details = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 400
    user = User(username=username, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    session['user_id'] = user.id
    session['username'] = user.username
    return jsonify({'success': True, 'balance': user.balance})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid credentials'}), 401
    session['user_id'] = user.id
    session['username'] = user.username
    return jsonify({'success': True, 'balance': user.balance})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/api/user')
def get_user():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    user = User.query.get(session['user_id'])
    return jsonify({'username': user.username, 'balance': round(user.balance, 2),
                    'total_wagered': round(user.total_wagered, 2), 'total_won': round(user.total_won, 2)})

@app.route('/api/history')
def get_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    txns = Transaction.query.filter_by(user_id=session['user_id']).order_by(Transaction.created_at.desc()).limit(20).all()
    return jsonify([{'game': t.game, 'bet': t.bet, 'result': t.result,
                     'balance_after': t.balance_after, 'details': t.details,
                     'time': t.created_at.strftime('%H:%M:%S')} for t in txns])

@app.route('/api/leaderboard')
def leaderboard():
    users = User.query.order_by(User.balance.desc()).limit(10).all()
    return jsonify([{'rank': i+1, 'username': u.username, 'balance': round(u.balance, 2),
                     'total_wagered': round(u.total_wagered, 2)} for i, u in enumerate(users)])

def validate_bet(user, bet):
    if bet <= 0:
        return False, 'Bet must be greater than 0'
    if bet > user.balance:
        return False, 'Insufficient balance'
    if bet > 10000:
        return False, 'Maximum bet is 10,000 HEX'
    return True, None

def record_transaction(user, game, bet, result, details=''):
    user.balance += result
    user.total_wagered += bet
    if result > 0:
        user.total_won += result
    txn = Transaction(user_id=user.id, game=game, bet=bet, result=result,
                      balance_after=user.balance, details=details)
    db.session.add(txn)
    db.session.commit()

SYMBOLS = ['💀', '⚡', '🔮', '💎', '🎯', '🌀']
PAYOUTS = {'💀': 10, '⚡': 8, '🔮': 6, '💎': 5, '🎯': 3, '🌀': 2}

@app.route('/api/slots', methods=['POST'])
def play_slots():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.get_json()
    bet = float(data.get('bet', 0))
    user = User.query.get(session['user_id'])
    valid, err = validate_bet(user, bet)
    if not valid:
        return jsonify({'error': err}), 400
    reels = [random.choice(SYMBOLS) for _ in range(3)]
    multiplier = None
    if reels[0] == reels[1] == reels[2]:
        multiplier = PAYOUTS[reels[0]]
        result = bet * multiplier - bet
        outcome = 'WIN'
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        result = bet * 0.5 - bet
        outcome = 'PARTIAL'
    else:
        result = -bet
        outcome = 'LOSE'
    record_transaction(user, 'SLOTS', bet, result, f"{' '.join(reels)} | {outcome}")
    return jsonify({'reels': reels, 'outcome': outcome, 'result': round(result, 2),
                    'balance': round(user.balance, 2), 'multiplier': multiplier})

@app.route('/api/coinflip', methods=['POST'])
def play_coinflip():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.get_json()
    bet = float(data.get('bet', 0))
    choice = data.get('choice', '').upper()
    user = User.query.get(session['user_id'])
    valid, err = validate_bet(user, bet)
    if not valid:
        return jsonify({'error': err}), 400
    if choice not in ['HEADS', 'TAILS']:
        return jsonify({'error': 'Choose HEADS or TAILS'}), 400
    flip = random.choice(['HEADS', 'TAILS'])
    won = flip == choice
    result = bet if won else -bet
    record_transaction(user, 'COINFLIP', bet, result, f"{choice} vs {flip} | {'WIN' if won else 'LOSE'}")
    return jsonify({'flip': flip, 'choice': choice, 'won': won,
                    'result': round(result, 2), 'balance': round(user.balance, 2)})

def make_deck():
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
    deck = [{'rank': r, 'suit': s} for r in ranks for s in suits]
    random.shuffle(deck)
    return deck

def card_value(card):
    if card['rank'] in ['J','Q','K']:
        return 10
    if card['rank'] == 'A':
        return 11
    return int(card['rank'])

def hand_value(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c['rank'] == 'A')
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

@app.route('/api/blackjack/deal', methods=['POST'])
def blackjack_deal():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.get_json()
    bet = float(data.get('bet', 0))
    user = User.query.get(session['user_id'])
    valid, err = validate_bet(user, bet)
    if not valid:
        return jsonify({'error': err}), 400
    deck = make_deck()
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    session['bj_deck'] = deck
    session['bj_player'] = player
    session['bj_dealer'] = dealer
    session['bj_bet'] = bet
    player_val = hand_value(player)
    return jsonify({'player': player, 'dealer': [dealer[0], {'rank': '?', 'suit': '?'}],
                    'player_value': player_val, 'blackjack': player_val == 21})

@app.route('/api/blackjack/hit', methods=['POST'])
def blackjack_hit():
    if 'user_id' not in session or 'bj_deck' not in session:
        return jsonify({'error': 'No active game'}), 400
    deck = session['bj_deck']
    player = session['bj_player']
    card = deck.pop(0)
    player.append(card)
    session['bj_deck'] = deck
    session['bj_player'] = player
    val = hand_value(player)
    return jsonify({'card': card, 'player': player, 'player_value': val, 'bust': val > 21})

@app.route('/api/blackjack/stand', methods=['POST'])
def blackjack_stand():
    if 'user_id' not in session or 'bj_deck' not in session:
        return jsonify({'error': 'No active game'}), 400
    deck = session['bj_deck']
    player = session['bj_player']
    dealer = session['bj_dealer']
    bet = session['bj_bet']
    while hand_value(dealer) < 17:
        dealer.append(deck.pop(0))
    pv, dv = hand_value(player), hand_value(dealer)
    user = User.query.get(session['user_id'])
    if pv > 21:
        result, outcome = -bet, 'BUST'
    elif dv > 21 or pv > dv:
        result, outcome = bet, 'WIN'
    elif pv == dv:
        result, outcome = 0, 'PUSH'
    else:
        result, outcome = -bet, 'LOSE'
    record_transaction(user, 'BLACKJACK', bet, result, f"Player {pv} vs Dealer {dv} | {outcome}")
    for key in ['bj_deck','bj_player','bj_dealer','bj_bet']:
        session.pop(key, None)
    return jsonify({'dealer': dealer, 'player': player, 'dealer_value': dv, 'player_value': pv,
                    'outcome': outcome, 'result': round(result, 2), 'balance': round(user.balance, 2)})

@app.route('/api/mines/start', methods=['POST'])
def mines_start():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.get_json()
    bet = float(data.get('bet', 0))
    mine_count = int(data.get('mines', 3))
    user = User.query.get(session['user_id'])
    valid, err = validate_bet(user, bet)
    if not valid:
        return jsonify({'error': err}), 400
    if mine_count < 1 or mine_count > 24:
        return jsonify({'error': 'Mines must be between 1 and 24'}), 400
    mines = random.sample(range(25), mine_count)
    session['mines_grid'] = mines
    session['mines_bet'] = bet
    session['mines_revealed'] = []
    session['mines_count'] = mine_count
    user.balance -= bet
    db.session.commit()
    return jsonify({'success': True, 'balance': round(user.balance, 2), 'grid_size': 25})

@app.route('/api/mines/reveal', methods=['POST'])
def mines_reveal():
    if 'user_id' not in session or 'mines_grid' not in session:
        return jsonify({'error': 'No active game'}), 400
    data = request.get_json()
    cell = int(data.get('cell'))
    mines = session['mines_grid']
    revealed = session['mines_revealed']
    bet = session['mines_bet']
    mine_count = session['mines_count']
    if cell in revealed:
        return jsonify({'error': 'Already revealed'}), 400
    if cell in mines:
        user = User.query.get(session['user_id'])
        record_transaction(user, 'MINES', bet, 0, f"Hit mine at cell {cell} | LOSE")
        for key in ['mines_grid','mines_bet','mines_revealed','mines_count']:
            session.pop(key, None)
        return jsonify({'hit_mine': True, 'mines': mines, 'balance': round(user.balance, 2)})
    revealed.append(cell)
    session['mines_revealed'] = revealed
    safe_count = len(revealed)
    safe_cells = 25 - mine_count
    multiplier = round(1 + (safe_count * mine_count / safe_cells), 2)
    potential_win = round(bet * multiplier, 2)
    return jsonify({'hit_mine': False, 'safe_count': safe_count,
                    'multiplier': multiplier, 'potential_win': potential_win})

@app.route('/api/mines/cashout', methods=['POST'])
def mines_cashout():
    if 'user_id' not in session or 'mines_grid' not in session:
        return jsonify({'error': 'No active game'}), 400
    revealed = session['mines_revealed']
    bet = session['mines_bet']
    mine_count = session['mines_count']
    if not revealed:
        return jsonify({'error': 'Reveal at least one cell first'}), 400
    safe_cells = 25 - mine_count
    multiplier = round(1 + (len(revealed) * mine_count / safe_cells), 2)
    winnings = round(bet * multiplier, 2)
    result = winnings - bet
    user = User.query.get(session['user_id'])
    user.balance += winnings
    record_transaction(user, 'MINES', bet, result, f"{len(revealed)} safe cells | x{multiplier} | CASHOUT")
    for key in ['mines_grid','mines_bet','mines_revealed','mines_count']:
        session.pop(key, None)
    return jsonify({'winnings': winnings, 'multiplier': multiplier,
                    'result': round(result, 2), 'balance': round(user.balance, 2)})

POKER_PAYOUTS = {
    'Royal Flush': 800, 'Straight Flush': 50, 'Four of a Kind': 25,
    'Full House': 9, 'Flush': 6, 'Straight': 4,
    'Three of a Kind': 3, 'Two Pair': 2, 'Pair': 1, 'High Card': 0
}

def rank_order(rank):
    order = {'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14}
    return order.get(rank, 0)

def evaluate_poker(hand):
    ranks = sorted([rank_order(c['rank']) for c in hand], reverse=True)
    suits = [c['suit'] for c in hand]
    is_flush = len(set(suits)) == 1
    is_straight = (max(ranks) - min(ranks) == 4 and len(set(ranks)) == 5) or ranks == [14,5,4,3,2]
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    counts = sorted(rank_counts.values(), reverse=True)
    if is_flush and is_straight and max(ranks) == 14: return 'Royal Flush'
    if is_flush and is_straight: return 'Straight Flush'
    if counts[0] == 4: return 'Four of a Kind'
    if counts[0] == 3 and counts[1] == 2: return 'Full House'
    if is_flush: return 'Flush'
    if is_straight: return 'Straight'
    if counts[0] == 3: return 'Three of a Kind'
    if counts[0] == 2 and counts[1] == 2: return 'Two Pair'
    if counts[0] == 2: return 'Pair'
    return 'High Card'

@app.route('/api/poker/deal', methods=['POST'])
def poker_deal():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    data = request.get_json()
    bet = float(data.get('bet', 0))
    user = User.query.get(session['user_id'])
    valid, err = validate_bet(user, bet)
    if not valid:
        return jsonify({'error': err}), 400
    deck = make_deck()
    hand = [deck.pop() for _ in range(5)]
    session['poker_deck'] = deck
    session['poker_hand'] = hand
    session['poker_bet'] = bet
    return jsonify({'hand': hand, 'hand_value': evaluate_poker(hand)})

@app.route('/api/poker/draw', methods=['POST'])
def poker_draw():
    if 'user_id' not in session or 'poker_deck' not in session:
        return jsonify({'error': 'No active game'}), 400
    data = request.get_json()
    discard = data.get('discard', [])
    deck = session['poker_deck']
    hand = session['poker_hand']
    bet = session['poker_bet']
    for i in discard:
        hand[i] = deck.pop(0)
    hand_name = evaluate_poker(hand)
    multiplier = POKER_PAYOUTS[hand_name]
    result = bet * multiplier - bet if multiplier > 0 else -bet
    user = User.query.get(session['user_id'])
    record_transaction(user, 'POKER', bet, result, f"{hand_name} | x{multiplier}")
    for key in ['poker_deck','poker_hand','poker_bet']:
        session.pop(key, None)
    return jsonify({'hand': hand, 'hand_name': hand_name, 'multiplier': multiplier,
                    'result': round(result, 2), 'balance': round(user.balance, 2)})

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
