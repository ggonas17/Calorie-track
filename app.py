import sqlite3
from flask import Flask, request, redirect, url_for
import json
import calendar
from datetime import datetime, timedelta

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('tracker.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS logs 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, calories INTEGER, protein INTEGER, timestamp TEXT, date TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS favorites 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, calories INTEGER, protein INTEGER, recipe TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS settings 
                    (key TEXT PRIMARY KEY, value TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS daily_stats
                    (date TEXT PRIMARY KEY, steps INTEGER, calories INTEGER, protein INTEGER)''')
    
    # Prevenção de updates para não perderes os dados
    try: conn.execute('ALTER TABLE daily_stats ADD COLUMN calories INTEGER')
    except: pass
    try: conn.execute('ALTER TABLE daily_stats ADD COLUMN protein INTEGER')
    except: pass
    try: conn.execute('ALTER TABLE logs ADD COLUMN recipe TEXT')
    except: pass
    try: conn.execute('ALTER TABLE daily_stats ADD COLUMN water REAL')
    except: pass
    try: conn.execute('ALTER TABLE daily_stats ADD COLUMN reading INTEGER')
    except: pass
    try: conn.execute('ALTER TABLE daily_stats ADD COLUMN money REAL')
    except: pass
    
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_goal', '3000')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('protein_goal', '150')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('step_goal', '10000')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('water_goal', '2.5')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('reading_goal', '20')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('money_goal', '500')")
    conn.commit()
    conn.close()

init_db()

def update_daily_stat(date, field, value, add=False):
    if not value: return
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone()
    if row:
        if add:
            current = row[field] if row[field] is not None else 0
            new_val = current + float(value)
            conn.execute(f'UPDATE daily_stats SET {field} = ? WHERE date = ?', (new_val, date))
        else:
            conn.execute(f'UPDATE daily_stats SET {field} = ? WHERE date = ?', (float(value), date))
    else:
        conn.execute(f'INSERT INTO daily_stats (date, {field}) VALUES (?, ?)', (date, float(value)))
    conn.commit(); conn.close()

def get_badge(recipe_str):
    if recipe_str and recipe_str not in ('', '""', '[]'):
        return '<span style="background:#5e5ce6; color:#fff; padding:3px 8px; border-radius:8px; font-size:0.55rem; margin-left:6px; vertical-align:middle; font-weight:900; letter-spacing:0.5px;">REFEIÇÃO</span>'
    return '<span style="background:#3a3a3c; color:#8e8e93; padding:3px 8px; border-radius:8px; font-size:0.55rem; margin-left:6px; vertical-align:middle; font-weight:900; letter-spacing:0.5px;">ITEM</span>'

CSS = """
<style>
    body { font-family: -apple-system, sans-serif; background: #000; color: #fff; padding: 20px; text-align: center; padding-bottom: 90px; margin: 0; }
    .card { background: #1c1c1e; border-radius: 20px; padding: 20px; margin-bottom: 20px; border: 1px solid #2c2c2e; box-shadow: 0 4px 15px rgba(0,0,0,0.3); position: relative; overflow: hidden; }
    .nav-bar { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(28, 28, 30, 0.95); backdrop-filter: blur(10px); display: flex; justify-content: space-around; padding: 15px 0; border-top: 0.5px solid #3a3a3c; z-index: 100; }
    .nav-item { color: #8e8e93; text-decoration: none; font-size: 0.70rem; font-weight: 600; flex: 1; display: flex; flex-direction: column; align-items: center; }
    .nav-item.active { color: #0a84ff; }
    input { background: #2c2c2e; border: none; border-radius: 12px; color: #fff; padding: 15px; margin: 8px 0; width: 90%; font-size: 16px; -webkit-appearance: none; box-sizing: border-box; }
    .btn-main { background: #0a84ff; color: #fff; border: none; border-radius: 15px; padding: 16px; width: 100%; font-weight: bold; font-size: 16px; margin-top: 10px; cursor: pointer; }
    .btn-green { background: #30d158; color: #000; border: none; border-radius: 15px; padding: 16px; width: 100%; font-weight: bold; font-size: 16px; margin-top: 10px; cursor: pointer; display: block; text-decoration: none; }
    .btn-red { background: #ff453a; color: #fff; border: none; border-radius: 12px; padding: 10px; font-weight: bold; font-size: 14px; cursor: pointer; margin-top: 10px; }
    .sug-container { display: flex; overflow-x: auto; gap: 10px; padding: 10px 0; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
    .sug-item { background: #2c2c2e; color: #0a84ff; padding: 15px 18px; border-radius: 18px; text-decoration: none; min-width: 140px; font-size: 0.85rem; border: 1px solid #3a3a3c; flex-shrink: 0; cursor: pointer; text-align: left; }
    .log-item { display: flex; justify-content: space-between; align-items: center; background: #1c1c1e; padding: 16px; border-radius: 18px; margin-bottom: 12px; border: 1px solid #2c2c2e; }
    .day-header { text-align: left; color: #8e8e93; font-size: 0.8rem; text-transform: uppercase; margin: 10px 5px; letter-spacing: 1px; }
    .fav-toggle { background: #2c2c2e; padding: 14px; border-radius: 12px; display: flex; align-items: center; justify-content: center; gap: 10px; color: #8e8e93; font-size: 0.9rem; margin: 10px 0; cursor: pointer; border: 2px solid transparent; transition: 0.2s; font-weight: bold; width: 100%; box-sizing: border-box; }
    .fav-toggle.active { border-color: #30d158; color: #30d158; background: rgba(48, 209, 88, 0.1); }
    input[type="checkbox"].hidden-check { display: none; }
    .progress-track { background: rgba(255,255,255,0.1); border-radius: 10px; height: 12px; width: 100%; margin: 8px 0 15px 0; overflow: hidden; }
    .progress-fill-c { background: linear-gradient(90deg, #0a84ff, #5e5ce6); height: 100%; border-radius: 10px; transition: width 0.8s cubic-bezier(0.2, 0.8, 0.2, 1); }
    .progress-fill-p { background: linear-gradient(90deg, #30d158, #32d74b); height: 100%; border-radius: 10px; transition: width 0.8s cubic-bezier(0.2, 0.8, 0.2, 1); }
    .recipe-list { text-align: left; color: #8e8e93; font-size: 0.85rem; margin-top: 10px; padding: 10px; background: #000; border-radius: 10px; min-height: 40px; max-height: 250px; overflow-y: auto; }
</style>
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    conn = get_db_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    
    if request.method == 'POST':
        if request.form.get('add_money'):
            update_daily_stat(today, 'money', request.form.get('add_money'), add=True)
            return redirect(url_for('home'))
        if request.form.get('add_water'):
            update_daily_stat(today, 'water', request.form.get('add_water'), add=True)
            return redirect(url_for('home'))

        f_name = request.form.get('food_name') or "Refeição"
        c_val = request.form.get('calories')
        p_val = request.form.get('protein')
        wants_to_save = request.form.get('save_fav')
        
        if c_val and p_val:
            now_time = datetime.now().strftime("%H:%M")
            conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp, date, recipe) VALUES (?, ?, ?, ?, ?, ?)',
                         (f_name, int(c_val), int(p_val), now_time, today, ""))
            if wants_to_save:
                conn.execute('INSERT OR REPLACE INTO favorites (food_name, calories, protein, recipe) VALUES (?, ?, ?, ?)',
                             (f_name, int(c_val), int(p_val), ""))
            conn.commit()

    logs = conn.execute('SELECT * FROM logs WHERE date = ? ORDER BY id DESC', (today,)).fetchall()
    favs = conn.execute('SELECT * FROM favorites').fetchall()
    
    goal_c = int(conn.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()['value'] or 3000)
    goal_p = int(conn.execute("SELECT value FROM settings WHERE key='protein_goal'").fetchone()['value'] or 150)
    
    today_stats = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (today,)).fetchone()
    today_stats_c = today_stats['calories'] if today_stats and 'calories' in today_stats.keys() and today_stats['calories'] is not None else None
    today_stats_p = today_stats['protein'] if today_stats and 'protein' in today_stats.keys() and today_stats['protein'] is not None else None
    
    calc_c = sum(log['calories'] for log in logs)
    calc_p = sum(log['protein'] for log in logs)
    
    total_c = today_stats_c if today_stats_c is not None else calc_c
    total_p = today_stats_p if today_stats_p is not None else calc_p
    conn.close()

    pct_c = min((total_c / goal_c) * 100, 100) if goal_c > 0 else 0
    pct_p = min((total_p / goal_p) * 100, 100) if goal_p > 0 else 0

    color_c = "#30d158" if total_c >= goal_c else "#fff"
    color_p = "#30d158" if total_p >= goal_p else "#fff"

    html_favs = "".join([f"""<a href="/quick_add/{f['id']}" class="sug-item"><div style="margin-bottom:5px;"><b>{f['food_name']}</b></div>{get_badge(f['recipe'])}<br><span style="color:#8e8e93; font-weight:normal; display:block; margin-top:8px;">{f['calories']} kcal | {f['protein']}g Prot</span></a>""" for f in favs])
    
    html_logs = "".join([f"""
        <div class="log-item">
            <div style="text-align:left;"><b>{l['food_name']}</b> {get_badge(l['recipe'])}<br><small style="color:#8e8e93;">{l['timestamp']} • {l['calories']} kcal | {l['protein']}g Prot</small></div>
            <div>
                <a href="/edit_log/{l['id']}" style="color:#0a84ff; text-decoration:none; font-weight:bold; margin-right:15px; font-size:0.85rem;">EDITAR</a>
                <a href="/delete/{l['id']}" style="color:#ff453a; text-decoration:none; font-weight:bold; font-size:1.1rem;">✕</a>
            </div>
        </div>""" for l in logs])

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">{CSS}</head><body>
        <div class="card" style="background: linear-gradient(145deg, #1c1c1e, #000); border: none; text-align: left;">
            <p style="color: #8e8e93; margin: 0; font-size: 0.8rem; font-weight: bold;">HOJE</p>
            <h1 style="font-size: 2.5rem; margin: 5px 0 0 0; color: {color_c}; transition: color 0.3s;">
                {total_c} <span style="font-size: 1rem; color: #8e8e93; font-weight: normal;">/ {goal_c} kcal</span>
            </h1>
            <div class="progress-track"><div class="progress-fill-c" style="width: {pct_c}%;"></div></div>
            <p style="color: {color_p}; font-weight: bold; font-size: 1.1rem; margin: 10px 0 0 0; transition: color 0.3s;">
                {total_p} <span style="font-size: 0.9rem; color: #8e8e93; font-weight: normal;">/ {goal_p}g Prot</span>
            </p>
            <div class="progress-track"><div class="progress-fill-p" style="width: {pct_p}%;"></div></div>
        </div>
        
        <div class="card" style="display:flex; gap:10px; padding:15px;">
            <form method="POST" style="flex:1;"><input type="number" step="0.1" name="add_water" placeholder="+ Água (L)" style="width:100%; margin:0; font-size:0.8rem;"><button class="btn-main" style="padding:10px; font-size:0.8rem;">ADD</button></form>
            <form method="POST" style="flex:1;"><input type="number" step="0.01" name="add_money" placeholder="+ Gasto (€)" style="width:100%; margin:0; font-size:0.8rem;"><button class="btn-main" style="padding:10px; font-size:0.8rem; background:#30d158; color:#000;">ADD</button></form>
        </div>

        <a href="/build_meal" class="btn-green" style="margin-bottom: 20px;">🥗 CRIAR REFEIÇÃO COMPOSTA</a>
        <div class="card">
            <h3 class="day-header" style="margin-top:0;">Adição Rápida</h3>
            <div class="sug-container" style="margin-bottom: 15px;">{html_favs or '<p style="color:#444; font-size:0.8rem; margin-left:10px;">Sem favoritos.</p>'}</div>
            <form method="POST">
                <input type="text" name="food_name" placeholder="O que comeste?">
                <div style="display: flex; gap: 10px;">
                    <input type="number" name="calories" placeholder="Kcal" required style="width:50%;">
                    <input type="number" name="protein" placeholder="Prot" required style="width:50%;">
                </div>
                <label class="fav-toggle" id="fav_label"><input type="checkbox" name="save_fav" class="hidden-check" onchange="document.getElementById('fav_label').classList.toggle('active'); document.getElementById('fav_text').innerText = this.checked ? 'A GRAVAR NA BIBLIOTECA ✅' : 'Gravar na Biblioteca?';"><span id="fav_text">Gravar na Biblioteca?</span></label>
                <button type="submit" class="btn-main">ADICIONAR</button>
            </form>
        </div>
        <h3 class="day-header">Diário de Hoje</h3>
        {html_logs}
        <div class="nav-bar">
            <a href="/" class="nav-item active"><span style="font-size:1.2rem;">🏠</span>HOJE</a>
            <a href="/history" class="nav-item"><span style="font-size:1.2rem;">📅</span>HISTÓRICO</a>
            <a href="/money" class="nav-item"><span style="font-size:1.2rem;">💸</span>DINHEIRO</a>
            <a href="/manage_favs" class="nav-item"><span style="font-size:1.2rem;">⚙️</span>DEFINIÇÕES</a>
        </div>
    </body></html>
    """

@app.route('/history')
def history():
    conn = get_db_connection()
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    try: target_date = datetime.strptime(month_str, '%Y-%m')
    except: target_date = datetime.now()
        
    y, m = target_date.year, target_date.month
    prev_m = (target_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    next_m = (target_date.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m')
    month_names = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    logs_data = conn.execute("SELECT date, SUM(calories) as c, SUM(protein) as p FROM logs GROUP BY date").fetchall()
    stats_data = conn.execute("SELECT * FROM daily_stats").fetchall()
    
    goal_p = int(conn.execute("SELECT value FROM settings WHERE key='protein_goal'").fetchone()['value'] or 150)
    goal_s = int(conn.execute("SELECT value FROM settings WHERE key='step_goal'").fetchone()['value'] or 10000)
    goal_w = float(conn.execute("SELECT value FROM settings WHERE key='water_goal'").fetchone()['value'] or 2.5)
    goal_r = int(conn.execute("SELECT value FROM settings WHERE key='reading_goal'").fetchone()['value'] or 20)
    conn.close()

    logs_dict = {row['date']: {'c': row['c'], 'p': row['p']} for row in logs_data}
    stats_dict = {row['date']: row for row in stats_data}
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(y, m)
    today_str = datetime.now().strftime("%Y-%m-%d")

    cal_html = f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;"><a href="/history?month={prev_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&lt;</a><h2 style="color:#fff; margin:0; font-size:1.2rem; text-transform:uppercase;">{month_names[m-1]} {y}</h2><a href="/history?month={next_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&gt;</a></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;"><div>S</div><div>T</div><div>Q</div><div>Q</div><div>S</div><div>S</div><div>D</div></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px;">'
    rot_html = '<div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;"><div>S</div><div>T</div><div>Q</div><div>Q</div><div>S</div><div>S</div><div>D</div></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px;">'

    for week in month_days:
        for day_date in week:
            d_str = day_date.strftime("%Y-%m-%d")
            d_num = day_date.day
            is_future = d_str > today_str
            is_current_month = day_date.month == m
            
            logs_c = logs_dict.get(d_str, {}).get('c', 0)
            logs_p = logs_dict.get(d_str, {}).get('p', 0)
            stats_row = stats_dict.get(d_str, {})
            
            stats_c = stats_row['calories'] if stats_row and 'calories' in stats_row.keys() and stats_row['calories'] is not None else None
            stats_p = stats_row['protein'] if stats_row and 'protein' in stats_row.keys() and stats_row['protein'] is not None else None
            stats_s = stats_row['steps'] if stats_row and 'steps' in stats_row.keys() and stats_row['steps'] is not None else 0
            stats_w = stats_row['water'] if stats_row and 'water' in stats_row.keys() and stats_row['water'] is not None else 0
            stats_r = stats_row['reading'] if stats_row and 'reading' in stats_row.keys() and stats_row['reading'] is not None else 0
            
            final_c = stats_c if stats_c is not None else logs_c
            final_p = stats_p if stats_p is not None else logs_p
            
            border_c = "transparent"
            if not is_future and is_current_month:
                p_met = final_p >= goal_p
                s_met = stats_s >= goal_s
                if not (final_c > 0 or final_p > 0 or stats_s > 0): border_c = "#ff453a"
                else:
                    if p_met and s_met: border_c = "#30d158"
                    elif p_met and not s_met: border_c = "#ffd60a"
                    elif not p_met and s_met: border_c = "#ff9f0a"
                    else: border_c = "#ff453a"

            border_r = "transparent"
            if not is_future and is_current_month:
                w_met = stats_w >= goal_w
                r_met = stats_r >= goal_r
                if w_met and r_met: border_r = "#30d158"
                elif not w_met and r_met: border_r = "#ff9f0a"
                elif w_met and not r_met: border_r = "#ffd60a"
                else: border_r = "#ff453a"

            day_color = "rgba(10, 132, 255, 0.15)" if d_str == today_str else "#2c2c2e"
            if d_str == today_str: border_c = "#0a84ff"; border_r = "#0a84ff"
            opacity = "1" if is_current_month else "0.3"
            
            stats_txt = f'<div style="font-size:0.5rem; color:#8e8e93; margin-top:2px; line-height:1.2;">{final_c} kcal<br>{final_p}p<br>👣{stats_s}</div>' if (final_c>0 or stats_s>0) else ""
            rot_txt = f'<div style="font-size:0.5rem; color:#8e8e93; margin-top:2px; line-height:1.2;">💧{stats_w}L<br>📖{stats_r}m</div>' if (stats_w>0 or stats_r>0) else ""
            
            if is_future:
                cal_html += f'<div style="background:{day_color}; border: 2px solid transparent; border-radius:10px; padding:8px 0; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d_num}</span></div>'
                rot_html += f'<div style="background:{day_color}; border: 2px solid transparent; border-radius:10px; padding:8px 0; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d_num}</span></div>'
            else:
                # O Truque: ?type=macros ou ?type=routines no link
                cal_html += f'<a href="/edit_day/{d_str}?type=macros" style="background:{day_color}; border: 2px solid {border_c}; border-radius:10px; padding:8px 0; text-decoration:none; color:#fff; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px; box-sizing:border-box; transition:0.2s;"><span style="font-weight:bold; font-size:0.9rem;">{d_num}</span>{stats_txt}</a>'
                rot_html += f'<a href="/edit_day/{d_str}?type=routines" style="background:{day_color}; border: 2px solid {border_r}; border-radius:10px; padding:8px 0; text-decoration:none; color:#fff; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px; box-sizing:border-box; transition:0.2s;"><span style="font-weight:bold; font-size:0.9rem;">{d_num}</span>{rot_txt}</a>'
                
    cal_html += "</div>"; rot_html += "</div>"

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color:#8e8e93; margin-bottom:10px;">DISCIPLINA & MACROS</h2>
        <div class="card" style="padding:15px;">{cal_html}
            <div style="display:flex; justify-content:center; gap:10px; font-size:0.65rem; color:#8e8e93; margin-top:20px; flex-wrap:wrap;">
                <div><span style="color:#30d158;">🟢</span> Prot + Passos</div><div><span style="color:#ffd60a;">🟡</span> Só Prot</div><div><span style="color:#ff9f0a;">🟠</span> Só Passos</div><div><span style="color:#ff453a;">🔴</span> Incompleto</div>
            </div>
        </div>
        <h2 style="color:#8e8e93; margin-bottom:10px;">ROTINAS DIÁRIAS</h2>
        <div class="card" style="padding:15px;">{rot_html}
            <div style="display:flex; justify-content:center; gap:10px; font-size:0.65rem; color:#8e8e93; margin-top:20px; flex-wrap:wrap;">
                <div><span style="color:#30d158;">🟢</span> Água + Ler</div><div><span style="color:#ffd60a;">🟡</span> Só Água</div><div><span style="color:#ff9f0a;">🟠</span> Só Ler</div><div><span style="color:#ff453a;">🔴</span> Incompleto</div>
            </div>
        </div>
        <div class="nav-bar"><a href="/" class="nav-item"><span style="font-size:1.2rem;">🏠</span>HOJE</a><a href="/history" class="nav-item active"><span style="font-size:1.2rem;">📅</span>HISTÓRICO</a><a href="/money" class="nav-item"><span style="font-size:1.2rem;">💸</span>DINHEIRO</a><a href="/manage_favs" class="nav-item"><span style="font-size:1.2rem;">⚙️</span>DEFINIÇÕES</a></div>
    </body></html>
    """

@app.route('/money')
def money():
    conn = get_db_connection()
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    try: target_date = datetime.strptime(month_str, '%Y-%m')
    except: target_date = datetime.now()
    
    y, m = target_date.year, target_date.month
    prev_m = (target_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    next_m = (target_date.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m')
    month_names = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    goal_m = float(conn.execute("SELECT value FROM settings WHERE key='money_goal'").fetchone()['value'] or 500)
    stats_data = conn.execute("SELECT date, money FROM daily_stats WHERE date LIKE ?", (f"{y}-{m:02d}-%",)).fetchall()
    conn.close()
    
    days_in_month = calendar.monthrange(y, m)[1]
    stats_dict = {row['date']: row['money'] or 0 for row in stats_data}
    
    # A MAGIA DO ORÇAMENTO DINÂMICO
    day_limits = {}
    cumulative_spent = 0
    today_str = datetime.now().strftime("%Y-%m-%d")
    current_dynamic_avg = 0
    
    for day_num in range(1, days_in_month + 1):
        d_str_loop = f"{y}-{m:02d}-{day_num:02d}"
        days_left = days_in_month - day_num + 1
        
        # A média é calculada com o que sobrou nos dias anteriores a dividir pelo que falta do mês!
        current_limit = (goal_m - cumulative_spent) / days_left if days_left > 0 else 0
        day_limits[d_str_loop] = current_limit
        
        if d_str_loop == today_str: current_dynamic_avg = current_limit
        cumulative_spent += stats_dict.get(d_str_loop, 0)
        
    total_spent_month = cumulative_spent
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(y, m)

    cal_html = f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;"><a href="/money?month={prev_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&lt;</a><h2 style="color:#fff; margin:0; font-size:1.2rem; text-transform:uppercase;">{month_names[m-1]} {y}</h2><a href="/money?month={next_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&gt;</a></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;"><div>S</div><div>T</div><div>Q</div><div>Q</div><div>S</div><div>S</div><div>D</div></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px;">'

    for week in month_days:
        for day_date in week:
            d_str = day_date.strftime("%Y-%m-%d")
            d_num = day_date.day
            is_future = d_str > today_str
            is_current_month = day_date.month == m
            
            spent = stats_dict.get(d_str, 0)
            daily_limit = day_limits.get(d_str, 0)
            
            border_c = "transparent"
            if not is_future and is_current_month:
                if spent == 0: border_c = "#30d158" # Verde (não gastou nada, aumentou a média de amanhã)
                elif spent <= daily_limit: border_c = "#30d158" # Verde (Abaixo da média limite do dia)
                else: border_c = "#ff453a" # Vermelho (Passou do orçamento para aquele dia)

            day_color = "rgba(10, 132, 255, 0.15)" if d_str == today_str else "#2c2c2e"
            opacity = "1" if is_current_month else "0.3"
            txt = f'<div style="font-size:0.6rem; color:#8e8e93; margin-top:2px; font-weight:bold;">{spent:.1f}€</div>' if spent > 0 else ""
            
            if is_future:
                cal_html += f'<div style="background:{day_color}; border: 2px solid transparent; border-radius:10px; padding:8px 0; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d_num}</span></div>'
            else:
                cal_html += f'<a href="/edit_day/{d_str}?type=money" style="background:{day_color}; border: 2px solid {border_c}; border-radius:10px; padding:8px 0; text-decoration:none; color:#fff; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px; box-sizing:border-box; transition:0.2s;"><span style="font-weight:bold; font-size:0.9rem;">{d_num}</span>{txt}</a>'
    cal_html += "</div>"

    color_total = "#ff453a" if total_spent_month > goal_m else "#30d158"
    if current_dynamic_avg == 0 and datetime.strptime(today_str, "%Y-%m-%d").month != m:
        current_dynamic_avg = goal_m / days_in_month # Mostra média fixa se vires meses passados

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <div class="card" style="background: linear-gradient(145deg, #1c1c1e, #000); border: none; text-align: center;">
            <p style="color: #8e8e93; margin: 0; font-size: 0.8rem; font-weight: bold; text-transform:uppercase;">TOTAL GASTO ESTE MÊS</p>
            <h1 style="font-size: 3.5rem; margin: 5px 0; color: {color_total};">{total_spent_month:.2f}€</h1>
            <p style="color: #8e8e93; font-size: 0.85rem; margin: 0;">Orçamento: {goal_m:.2f}€ | Resta: {(goal_m - total_spent_month):.2f}€</p>
            <div style="background:#2c2c2e; padding:10px; border-radius:10px; margin-top:15px;">
                <p style="margin:0; font-size:0.8rem; color:#8e8e93;">MÉDIA PERMITIDA PARA HOJE</p>
                <p style="margin:0; font-size:1.2rem; font-weight:bold; color:#0a84ff;">{current_dynamic_avg:.2f} € / dia</p>
            </div>
        </div>
        <div class="card" style="padding:15px;">{cal_html}</div>
        <div class="nav-bar"><a href="/" class="nav-item"><span style="font-size:1.2rem;">🏠</span>HOJE</a><a href="/history" class="nav-item"><span style="font-size:1.2rem;">📅</span>HISTÓRICO</a><a href="/money" class="nav-item active"><span style="font-size:1.2rem;">💸</span>DINHEIRO</a><a href="/manage_favs" class="nav-item"><span style="font-size:1.2rem;">⚙️</span>DEFINIÇÕES</a></div>
    </body></html>
    """

@app.route('/edit_day/<date>', methods=['GET', 'POST'])
def edit_day(date):
    edit_type = request.args.get('type', 'macros')
    conn = get_db_connection()
    if request.method == 'POST':
        # Vai buscar APENAS os campos do formulário submetido e atualiza sem mexer nos outros
        fields = ['calories', 'protein', 'steps', 'water', 'reading', 'money']
        row = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone()
        if not row: conn.execute('INSERT INTO daily_stats (date) VALUES (?)', (date,))
        for f in fields:
            if f in request.form:
                val = request.form.get(f)
                final_val = None if val.strip() == "" else (float(val) if f in ('water', 'money') else int(val))
                conn.execute(f'UPDATE daily_stats SET {f}=? WHERE date=?', (final_val, date))
        conn.commit(); conn.close()
        
        if edit_type == 'money': return redirect(url_for('money', month=date[:7]))
        return redirect(url_for('history', month=date[:7]))
        
    logs = conn.execute('SELECT * FROM logs WHERE date = ? ORDER BY id DESC', (date,)).fetchall()
    stats = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone()
    conn.close()
    
    logs_c = sum(l['calories'] for l in logs); logs_p = sum(l['protein'] for l in logs)
    s_c = stats['calories'] if stats and 'calories' in stats.keys() and stats['calories'] is not None else ""
    s_p = stats['protein'] if stats and 'protein' in stats.keys() and stats['protein'] is not None else ""
    s_s = stats['steps'] if stats and 'steps' in stats.keys() and stats['steps'] is not None else ""
    s_w = stats['water'] if stats and 'water' in stats.keys() and stats['water'] is not None else ""
    s_r = stats['reading'] if stats and 'reading' in stats.keys() and stats['reading'] is not None else ""
    s_m = stats['money'] if stats and 'money' in stats.keys() and stats['money'] is not None else ""
    
    display_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d %b %Y")
    html_logs = "".join([f'<div class="log-item"><div style="text-align:left;"><b>{l["food_name"]}</b> {get_badge(l["recipe"])}<br><small style="color:#8e8e93;">{l["timestamp"]} • {l["calories"]} kcal | {l["protein"]}g Prot</small></div><div><a href="/edit_log/{l["id"]}" style="color:#0a84ff; text-decoration:none; font-weight:bold; margin-right:15px; font-size:0.85rem;">EDITAR</a><a href="/delete/{l["id"]}" style="color:#ff453a; text-decoration:none; font-weight:bold; font-size:1.1rem;">✕</a></div></div>' for l in logs])
    
    # Render condicional dependendo de qual calendário clicaste
    if edit_type == 'macros':
        form_content = f"""
        <label style="color:#8e8e93; font-weight:bold; font-size:0.9rem;">Calorias (Kcal):</label><input type="number" name="calories" value="{s_c}" placeholder="Auto: {logs_c} kcal" style="margin:0; width:100%; margin-bottom:10px;">
        <label style="color:#8e8e93; font-weight:bold; font-size:0.9rem;">Proteína (g):</label><input type="number" name="protein" value="{s_p}" placeholder="Auto: {logs_p} g" style="margin:0; width:100%; margin-bottom:10px;">
        <label style="color:#ff9f0a; font-weight:bold; font-size:0.9rem;">Passos 👣:</label><input type="number" name="steps" value="{s_s}" placeholder="Ex: 10500" style="margin:0; width:100%;">
        """
        extra_html = f'<h3 class="day-header">DIÁRIO DESSE DIA</h3>{html_logs or "<p style=\'color:#444; font-size:0.9rem;\'>Nenhuma refeição registada.</p>"}'
        title_top = "MACROS E PASSOS"
    
    elif edit_type == 'routines':
        form_content = f"""
        <label style="color:#0a84ff; font-weight:bold; font-size:0.9rem;">Água 💧 (Litros):</label><input type="number" step="0.1" name="water" value="{s_w}" placeholder="Ex: 2.5" style="margin:0; width:100%; margin-bottom:10px;">
        <label style="color:#5e5ce6; font-weight:bold; font-size:0.9rem;">Leitura 📖 (Minutos):</label><input type="number" name="reading" value="{s_r}" placeholder="Ex: 20" style="margin:0; width:100%;">
        """
        extra_html = ""
        title_top = "ROTINAS"
        
    elif edit_type == 'money':
        form_content = f"""
        <label style="color:#30d158; font-weight:bold; font-size:0.9rem;">Dinheiro Gasto 💸 (€):</label><input type="number" step="0.01" name="money" value="{s_m}" placeholder="Ex: 15.50" style="margin:0; width:100%;">
        """
        extra_html = ""
        title_top = "FINANÇAS"

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color:#8e8e93; text-transform:uppercase;">{display_date}</h2>
        <div class="card"><h3 style="margin-top:0; color:#8e8e93;">EDITAR {title_top}</h3>
            <form method="POST" action="/edit_day/{date}?type={edit_type}">
                <div style="display:flex; flex-direction:column; align-items:flex-start;">{form_content}</div>
                <button type="submit" class="btn-main" style="margin-top:20px;">GRAVAR DIA</button>
            </form>
            <a href="javascript:history.back()" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Voltar atrás</a>
        </div>
        {extra_html}
    </body></html>
    """

@app.route('/build_meal', methods=['GET', 'POST'])
def build_meal():
    conn = get_db_connection()
    if request.method == 'POST':
        m_name = request.form.get('meal_name') or "Refeição Composta"
        m_cal = request.form.get('total_cal'); m_prot = request.form.get('total_prot'); m_recipe = request.form.get('recipe_json'); save_lib = request.form.get('save_lib')
        now_time = datetime.now().strftime("%H:%M"); today = datetime.now().strftime("%Y-%m-%d")
        conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp, date, recipe) VALUES (?, ?, ?, ?, ?, ?)', (m_name, int(m_cal), int(m_prot), now_time, today, m_recipe))
        if save_lib: conn.execute('INSERT OR REPLACE INTO favorites (food_name, calories, protein, recipe) VALUES (?, ?, ?, ?)', (m_name, int(m_cal), int(m_prot), m_recipe))
        conn.commit(); conn.close(); return redirect(url_for('home'))

    favs = conn.execute('SELECT * FROM favorites').fetchall(); conn.close()
    html_sugs = "".join([f'<div onclick="addItem(\'{f["food_name"]}\', {f["calories"]}, {f["protein"]})" class="sug-item"><b>+ {f["food_name"]}</b><br><span style="color:#8e8e93; font-weight:normal;">{f["calories"]} kcal | {f["protein"]}g Prot</span></div>' for f in favs])

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color: #8e8e93;">MONTAR PRATO</h2>
        <div class="card" style="border-color: #30d158;"><h1 style="margin:0; font-size:2.5rem;"><span id="t_cal">0</span> <span style="font-size:1rem; color:#8e8e93;">kcal</span></h1><p style="color:#30d158; font-weight:bold; margin:0;"><span id="t_prot">0</span>g Prot</p><div id="recipe_box" class="recipe-list">Prato vazio.</div><button type="button" onclick="undoItem()" class="btn-red" id="undo_btn" style="display:none; width:100%;">Desfazer Último Item</button></div>
        <h3 class="day-header">Cenas da Biblioteca</h3><div class="sug-container" style="margin-bottom:20px;">{html_sugs or '<p style="color:#444; font-size:0.8rem; margin-left:10px;">Sem favoritos.</p>'}</div>
        <div class="card"><h3 class="day-header" style="margin-top:0;">Adicionar Extra Manual</h3><div style="display:flex; gap:10px;"><input type="text" id="c_name" placeholder="Item" style="width:40%;"><input type="number" id="c_cal" placeholder="Kcal" style="width:30%;"><input type="number" id="c_prot" placeholder="Prot" style="width:30%;"></div><button type="button" onclick="addCustom()" class="btn-main" style="background:#2c2c2e; color:#0a84ff;">+ ADICIONAR AO PRATO</button></div>
        <form method="POST" style="margin-top:30px;"><input type="text" name="meal_name" placeholder="Nome da Refeição (ex: Almoço)" required><input type="hidden" id="form_cal" name="total_cal" value="0"><input type="hidden" id="form_prot" name="total_prot" value="0"><input type="hidden" id="form_recipe" name="recipe_json" value="[]"><label class="fav-toggle" id="meal_fav_label"><input type="checkbox" name="save_lib" class="hidden-check" onchange="document.getElementById('meal_fav_label').classList.toggle('active');"><span>Guardar Refeição na Biblioteca?</span></label><button type="submit" class="btn-green">CONFIRMAR REFEIÇÃO</button></form>
        <a href="/" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a>
        <script>
            let items = []; function addItem(name, cal, prot) {{ items.push({{name: name, cal: parseInt(cal), prot: parseInt(prot)}}); updateUI(); }} 
            function addCustom() {{ let n = document.getElementById('c_name').value || 'Extra'; let c = document.getElementById('c_cal').value || 0; let p = document.getElementById('c_prot').value || 0; if(c > 0 || p > 0) addItem(n, c, p); document.getElementById('c_name').value = ''; document.getElementById('c_cal').value = ''; document.getElementById('c_prot').value = ''; }} 
            function undoItem() {{ items.pop(); updateUI(); }}
            function updateUI() {{ let totalCal = 0; let totalProt = 0; let htmlList = ""; items.forEach((it, index) => {{ totalCal += it.cal; totalProt += it.prot; htmlList += `<div>• ${{it.name}} <span style="color:#444;">(${{it.cal}}kcal | ${{it.prot}}g)</span></div>`; }}); document.getElementById('t_cal').innerText = totalCal; document.getElementById('t_prot').innerText = totalProt; document.getElementById('form_cal').value = totalCal; document.getElementById('form_prot').value = totalProt; document.getElementById('form_recipe').value = JSON.stringify(items); document.getElementById('recipe_box').innerHTML = htmlList || "Prato vazio."; document.getElementById('undo_btn').style.display = items.length > 0 ? "block" : "none"; }}
        </script>
    </body></html>
    """

@app.route('/manage_favs', methods=['GET', 'POST'])
def manage_favs():
    conn = get_db_connection()
    if request.method == 'POST':
        updates = [('daily_goal', request.form.get('new_goal')), ('protein_goal', request.form.get('new_p_goal')), ('step_goal', request.form.get('new_s_goal')),
                   ('water_goal', request.form.get('new_w_goal')), ('reading_goal', request.form.get('new_r_goal')), ('money_goal', request.form.get('new_m_goal'))]
        for k, v in updates:
            if v: conn.execute("UPDATE settings SET value=? WHERE key=?", (v, k))
        conn.commit()
        
    goals = {row['key']: row['value'] for row in conn.execute("SELECT * FROM settings").fetchall()}
    favs = conn.execute('SELECT * FROM favorites').fetchall(); conn.close()
    html_favs = "".join([f'<div class="log-item"><div style="text-align:left;"><b>{f["food_name"]}</b> {get_badge(f["recipe"])}<br><small style="color:#8e8e93;">{f["calories"]} kcal | {f["protein"]}g Prot</small></div><div><a href="/edit_fav/{f["id"]}" style="color:#0a84ff; text-decoration:none; font-weight:bold; margin-right:15px;">EDITAR</a><a href="/delete_fav/{f["id"]}" style="color:#ff453a; text-decoration:none; font-weight:bold;">✕</a></div></div>' for f in favs])
        
    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <div class="card"><h3 style="margin-top:0; color:#8e8e93;">DEFINIÇÕES & METAS</h3><form method="POST">
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; text-align:left;">
                <div><label style="color:#8e8e93; font-size:0.75rem; margin-left:5px;">Calorias (Kcal)</label><input type="number" name="new_goal" value="{goals.get('daily_goal', 3000)}" style="margin:0; width:100%;"></div>
                <div><label style="color:#8e8e93; font-size:0.75rem; margin-left:5px;">Proteína (g)</label><input type="number" name="new_p_goal" value="{goals.get('protein_goal', 150)}" style="margin:0; width:100%;"></div>
                <div><label style="color:#8e8e93; font-size:0.75rem; margin-left:5px;">Passos (Dia)</label><input type="number" name="new_s_goal" value="{goals.get('step_goal', 10000)}" style="margin:0; width:100%;"></div>
                <div><label style="color:#8e8e93; font-size:0.75rem; margin-left:5px;">Água (Litros)</label><input type="number" step="0.1" name="new_w_goal" value="{goals.get('water_goal', 2.5)}" style="margin:0; width:100%;"></div>
                <div><label style="color:#8e8e93; font-size:0.75rem; margin-left:5px;">Ler (Minutos)</label><input type="number" name="new_r_goal" value="{goals.get('reading_goal', 20)}" style="margin:0; width:100%;"></div>
                <div><label style="color:#8e8e93; font-size:0.75rem; margin-left:5px;">Dinheiro (€/Mês)</label><input type="number" step="0.1" name="new_m_goal" value="{goals.get('money_goal', 500)}" style="margin:0; width:100%;"></div>
            </div><button type="submit" class="btn-main" style="margin-top:15px;">GRAVAR METAS</button>
        </form></div>
        <h3 class="day-header">EDITAR BIBLIOTECA</h3>{html_favs or "<p style='color:#444;'>Biblioteca vazia.</p>"}
        <div class="nav-bar"><a href="/" class="nav-item"><span style="font-size:1.2rem;">🏠</span>HOJE</a><a href="/history" class="nav-item"><span style="font-size:1.2rem;">📅</span>HISTÓRICO</a><a href="/money" class="nav-item"><span style="font-size:1.2rem;">💸</span>DINHEIRO</a><a href="/manage_favs" class="nav-item active"><span style="font-size:1.2rem;">⚙️</span>DEFINIÇÕES</a></div>
    </body></html>
    """

@app.route('/edit_fav/<int:fav_id>', methods=['GET', 'POST'])
def edit_fav(fav_id):
    conn = get_db_connection()
    if request.method == 'POST':
        f_name, c_val, p_val, r_val = request.form.get('food_name'), request.form.get('calories'), request.form.get('protein'), request.form.get('recipe_json', '')
        conn.execute('UPDATE favorites SET food_name=?, calories=?, protein=?, recipe=? WHERE id=?', (f_name, int(c_val), int(p_val), r_val, fav_id))
        conn.commit(); conn.close(); return redirect(url_for('manage_favs'))
    fav = conn.execute('SELECT * FROM favorites WHERE id=?', (fav_id,)).fetchone(); conn.close()
    is_meal = bool(fav['recipe'] and fav['recipe'] not in ('', '""', '[]')); recipe_data = fav['recipe'] if is_meal else "[]"
    
    if is_meal:
        editor_html = f'<h2 style="color:#8e8e93;">EDITAR REFEIÇÃO</h2><div class="card"><form method="POST"><input type="text" name="food_name" value="{fav["food_name"]}" required style="font-weight:bold; font-size:1.2rem; text-align:center;"><div style="background:#000; padding:15px; border-radius:15px; margin:15px 0;"><h1 style="margin:0; font-size:2rem;"><span id="total_cal_display">0</span> <span style="font-size:1rem; color:#8e8e93;">kcal</span></h1><p style="color:#30d158; font-weight:bold; margin:0;"><span id="total_prot_display">0</span>g Prot</p></div><h4 style="text-align:left; color:#8e8e93; margin-bottom:10px;">Ingredientes da Refeição:</h4><div id="recipe_list"></div><button type="button" onclick="addNewItem()" class="btn-main" style="background:#2c2c2e; color:#0a84ff; padding:10px; font-size:0.9rem; margin-top:10px;">+ ADICIONAR INGREDIENTE</button><input type="hidden" id="form_cal" name="calories" value="{fav["calories"]}"><input type="hidden" id="form_prot" name="protein" value="{fav["protein"]}"><input type="hidden" id="form_recipe" name="recipe_json" value=\'{recipe_data}\'><button type="submit" class="btn-green" style="margin-top:30px;">GUARDAR REFEIÇÃO</button></form><a href="/manage_favs" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a></div><script>let recipe = {recipe_data}; function renderRecipe() {{ let html = ""; let tCal = 0; let tProt = 0; recipe.forEach((it, idx) => {{ tCal += parseInt(it.cal) || 0; tProt += parseInt(it.prot) || 0; html += `<div style="display:flex; gap:5px; margin-bottom:10px; align-items:center;"><input type="text" value="${{it.name}}" onchange="updateItem(${{idx}}, \'name\', this.value)" style="width:45%; padding:10px; margin:0; font-size:0.9rem;"><input type="number" value="${{it.cal}}" onchange="updateItem(${{idx}}, \'cal\', this.value)" style="width:25%; padding:10px; margin:0; font-size:0.9rem;"><input type="number" value="${{it.prot}}" onchange="updateItem(${{idx}}, \'prot\', this.value)" style="width:25%; padding:10px; margin:0; font-size:0.9rem;"><button type="button" onclick="removeItem(${{idx}})" style="width:10%; background:transparent; border:none; color:#ff453a; font-weight:bold; font-size:1.2rem; cursor:pointer; padding:0;">✕</button></div>`; }}); document.getElementById("recipe_list").innerHTML = html; document.getElementById("total_cal_display").innerText = tCal; document.getElementById("total_prot_display").innerText = tProt; document.getElementById("form_cal").value = tCal; document.getElementById("form_prot").value = tProt; document.getElementById("form_recipe").value = JSON.stringify(recipe); }} function updateItem(idx, field, val) {{ if(field === "cal" || field === "prot") val = parseInt(val) || 0; recipe[idx][field] = val; renderRecipe(); }} function removeItem(idx) {{ recipe.splice(idx, 1); renderRecipe(); }} function addNewItem() {{ recipe.push({{name: "Novo Ingrediente", cal: 0, prot: 0}}); renderRecipe(); }} renderRecipe();</script>'
    else:
        editor_html = f'<h2 style="color:#8e8e93;">EDITAR ITEM SIMPLES</h2><div class="card"><form method="POST"><input type="text" name="food_name" value="{fav["food_name"]}" required><input type="number" name="calories" value="{fav["calories"]}" required><input type="number" name="protein" value="{fav["protein"]}" required><button type="submit" class="btn-main">GUARDAR ALTERAÇÕES</button></form><a href="/manage_favs" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a></div>'
    return f"<!DOCTYPE html><html lang='pt'><head><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{editor_html}</body></html>"

@app.route('/edit_log/<int:log_id>', methods=['GET', 'POST'])
def edit_log(log_id):
    conn = get_db_connection()
    if request.method == 'POST':
        f_name, c_val, p_val, r_val = request.form.get('food_name'), request.form.get('calories'), request.form.get('protein'), request.form.get('recipe_json', '')
        conn.execute('UPDATE logs SET food_name=?, calories=?, protein=?, recipe=? WHERE id=?', (f_name, int(c_val), int(p_val), r_val, log_id))
        conn.commit(); conn.close()
        ref = request.referrer; return redirect(ref) if ref else redirect(url_for('home'))
        
    log = conn.execute('SELECT * FROM logs WHERE id=?', (log_id,)).fetchone(); conn.close()
    is_meal = bool(log['recipe'] and log['recipe'] not in ('', '""', '[]')); recipe_data = log['recipe'] if is_meal else "[]"
    
    if is_meal:
        editor_html = f"""<h2 style="color:#8e8e93;">EDITAR DIÁRIO (REFEIÇÃO)</h2><p style="color:#8e8e93; font-size:0.8rem; margin-top:0;">Registado às {log['timestamp']}</p><div class="card"><form method="POST"><input type="text" name="food_name" value="{log['food_name']}" required style="font-weight:bold; font-size:1.2rem; text-align:center;"><div style="background:#000; padding:15px; border-radius:15px; margin:15px 0;"><h1 style="margin:0; font-size:2rem;"><span id="total_cal_display">0</span> <span style="font-size:1rem; color:#8e8e93;">kcal</span></h1><p style="color:#30d158; font-weight:bold; margin:0;"><span id="total_prot_display">0</span>g Prot</p></div><h4 style="text-align:left; color:#8e8e93; margin-bottom:10px;">Ingredientes:</h4><div id="recipe_list"></div><button type="button" onclick="addNewItem()" class="btn-main" style="background:#2c2c2e; color:#0a84ff; padding:10px; font-size:0.9rem; margin-top:10px;">+ ADICIONAR INGREDIENTE</button><input type="hidden" id="form_cal" name="calories" value="{log['calories']}"><input type="hidden" id="form_prot" name="protein" value="{log['protein']}"><input type="hidden" id="form_recipe" name="recipe_json" value='{recipe_data}'><button type="submit" class="btn-green" style="margin-top:30px;">ATUALIZAR DIÁRIO</button></form><a href="javascript:history.back()" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a></div><script>let recipe = {recipe_data}; function renderRecipe() {{ let html = ""; let tCal = 0; let tProt = 0; recipe.forEach((it, idx) => {{ tCal += parseInt(it.cal) || 0; tProt += parseInt(it.prot) || 0; html += `<div style="display:flex; gap:5px; margin-bottom:10px; align-items:center;"><input type="text" value="${{it.name}}" onchange="updateItem(${{idx}}, 'name', this.value)" style="width:45%; padding:10px; margin:0; font-size:0.9rem;"><input type="number" value="${{it.cal}}" onchange="updateItem(${{idx}}, 'cal', this.value)" style="width:25%; padding:10px; margin:0; font-size:0.9rem;"><input type="number" value="${{it.prot}}" onchange="updateItem(${{idx}}, 'prot', this.value)" style="width:25%; padding:10px; margin:0; font-size:0.9rem;"><button type="button" onclick="removeItem(${{idx}})" style="width:10%; background:transparent; border:none; color:#ff453a; font-weight:bold; font-size:1.2rem; cursor:pointer; padding:0;">✕</button></div>`; }}); document.getElementById('recipe_list').innerHTML = html; document.getElementById('total_cal_display').innerText = tCal; document.getElementById('total_prot_display').innerText = tProt; document.getElementById('form_cal').value = tCal; document.getElementById('form_prot').value = tProt; document.getElementById('form_recipe').value = JSON.stringify(recipe); }} function updateItem(idx, field, val) {{ if(field === 'cal' || field === 'prot') val = parseInt(val) || 0; recipe[idx][field] = val; renderRecipe(); }} function removeItem(idx) {{ recipe.splice(idx, 1); renderRecipe(); }} function addNewItem() {{ recipe.push({{name: 'Novo Ingrediente', cal: 0, prot: 0}}); renderRecipe(); }} renderRecipe();</script>"""
    else:
        editor_html = f'<h2 style="color:#8e8e93;">EDITAR DIÁRIO</h2><div class="card"><p style="color:#8e8e93; font-size:0.8rem; margin-top:0;">Registado às {log["timestamp"]}</p><form method="POST"><input type="text" name="food_name" value="{log["food_name"]}" required><input type="number" name="calories" value="{log["calories"]}" required><input type="number" name="protein" value="{log["protein"]}" required><button type="submit" class="btn-main">ATUALIZAR REFEIÇÃO</button></form><a href="javascript:history.back()" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a></div>'
    return f'<!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>{editor_html}</body></html>'

@app.route('/quick_add/<int:fav_id>')
def quick_add(fav_id):
    conn = get_db_connection(); fav = conn.execute('SELECT * FROM favorites WHERE id=?', (fav_id,)).fetchone()
    if fav:
        now_time, today = datetime.now().strftime("%H:%M"), datetime.now().strftime("%Y-%m-%d")
        conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp, date, recipe) VALUES (?, ?, ?, ?, ?, ?)', (fav['food_name'], fav['calories'], fav['protein'], now_time, today, fav['recipe']))
        conn.commit()
    conn.close(); return redirect(url_for('home'))

@app.route('/delete/<int:log_id>')
def delete_entry(log_id):
    conn = get_db_connection(); conn.execute('DELETE FROM logs WHERE id = ?', (log_id,)); conn.commit(); conn.close()
    ref = request.referrer; return redirect(ref) if ref else redirect(url_for('home'))

@app.route('/delete_fav/<int:fav_id>')
def delete_fav(fav_id):
    conn = get_db_connection(); conn.execute('DELETE FROM favorites WHERE id = ?', (fav_id,)); conn.commit(); conn.close(); return redirect(url_for('manage_favs'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')