import sqlite3
import os
from flask import Flask, request, redirect, url_for, send_file
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
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, qty REAL DEFAULT 1, unit TEXT DEFAULT "qty", calories INTEGER, protein INTEGER, timestamp TEXT, date TEXT, recipe TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS favorites 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, qty REAL DEFAULT 1, unit TEXT DEFAULT "qty", calories INTEGER, protein INTEGER, recipe TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS settings 
                    (key TEXT PRIMARY KEY, value TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS daily_stats
                    (date TEXT PRIMARY KEY, steps INTEGER, calories INTEGER, protein INTEGER)''')
    
    columns_daily = [
        'calories INTEGER', 'protein INTEGER', 'water REAL', 'reading INTEGER', 
        'money REAL', 'sleep REAL', 'gym INTEGER DEFAULT 0', 'run INTEGER DEFAULT 0',
        'notes TEXT', 'bible INTEGER DEFAULT 0',
        'goal_c INTEGER', 'goal_p INTEGER', 'goal_s INTEGER', 'goal_w REAL',
        'planned_g TEXT', 'planned_r TEXT'
    ]
    for col in columns_daily:
        try: conn.execute(f'ALTER TABLE daily_stats ADD COLUMN {col}')
        except: pass
        
    for col in ['qty REAL DEFAULT 1', 'unit TEXT DEFAULT "qty"', 'recipe TEXT']:
        try: conn.execute(f'ALTER TABLE logs ADD COLUMN {col}')
        except: pass
    for col in ['qty REAL DEFAULT 1', 'unit TEXT DEFAULT "qty"', 'recipe TEXT']:
        try: conn.execute(f'ALTER TABLE favorites ADD COLUMN {col}')
        except: pass
    
    conn.execute('''CREATE TABLE IF NOT EXISTS routines (id INTEGER PRIMARY KEY AUTOINCREMENT, start_date TEXT, end_date TEXT, schedule TEXT)''')
    
    defaults = [('daily_goal', '2100'), ('protein_goal', '160'), ('step_goal', '10000'), 
                ('water_goal', '2.5'), ('money_goal', '300'), ('sleep_goal', '7.5')]
    for k, v in defaults:
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        
    if not conn.execute("SELECT 1 FROM routines").fetchone():
        empty_plan = {str(i): {"g": "", "r": ""} for i in range(7)}
        conn.execute("INSERT INTO routines (start_date, end_date, schedule) VALUES (?, ?, ?)", ("2000-01-01", "2099-12-31", json.dumps(empty_plan)))

    conn.commit(); conn.close()

init_db()

def get_routine_for_date(conn, d_str):
    rt = conn.execute("SELECT schedule FROM routines WHERE start_date <= ? AND end_date >= ? ORDER BY start_date DESC LIMIT 1", (d_str, d_str)).fetchone()
    return json.loads(rt['schedule']) if rt else {str(i): {"g": "", "r": ""} for i in range(7)}

def ensure_daily_goals(date_str):
    conn = get_db_connection()
    row = conn.execute('SELECT goal_p, planned_g FROM daily_stats WHERE date = ?', (date_str,)).fetchone()
    if not row or row['goal_p'] is None or row['planned_g'] is None:
        settings = {r['key']: r['value'] for r in conn.execute("SELECT * FROM settings").fetchall()}
        g_c = int(settings.get('daily_goal', 2100)); g_p = int(settings.get('protein_goal', 160))
        g_s = int(settings.get('step_goal', 10000)); g_w = float(str(settings.get('water_goal', 2.5)).replace(',', '.'))
        
        routine = get_routine_for_date(conn, date_str)
        wd = str(datetime.strptime(date_str, "%Y-%m-%d").weekday())
        p_g = routine.get(wd, {}).get("g", ""); p_r = routine.get(wd, {}).get("r", "")
        
        if not row: conn.execute('INSERT INTO daily_stats (date, goal_c, goal_p, goal_s, goal_w, planned_g, planned_r) VALUES (?, ?, ?, ?, ?, ?, ?)', (date_str, g_c, g_p, g_s, g_w, p_g, p_r))
        else: conn.execute('UPDATE daily_stats SET goal_c=?, goal_p=?, goal_s=?, goal_w=?, planned_g=?, planned_r=? WHERE date=?', (g_c, g_p, g_s, g_w, p_g, p_r, date_str))
        conn.commit()
    conn.close()

def get_streak(conn):
    settings = {row['key']: row['value'] for row in conn.execute("SELECT * FROM settings").fetchall()}
    g_sl = 7.5
    stats_data = conn.execute("SELECT * FROM daily_stats").fetchall()
    logs_data = conn.execute("SELECT date, SUM(protein) as p FROM logs GROUP BY date").fetchall()
    stats_dict = {row['date']: dict(row) for row in stats_data}
    logs_dict = {row['date']: row['p'] for row in logs_data}
    
    min_d1 = conn.execute("SELECT MIN(date) as md FROM daily_stats").fetchone()['md'] or "2099"
    min_d2 = conn.execute("SELECT MIN(date) as md FROM logs").fetchone()['md'] or "2099"
    min_date = min(min_d1, min_d2)
    if min_date == "2099": return 0

    streak = 0; check_date = datetime.now(); is_first_day = True
    while True:
        d_str = check_date.strftime("%Y-%m-%d")
        if d_str < min_date: break
        
        s_row = stats_dict.get(d_str, {}); l_p = logs_dict.get(d_str, 0)
        g_p = s_row.get('goal_p') or int(settings.get('protein_goal', 160))
        g_s = s_row.get('goal_s') or int(settings.get('step_goal', 10000))
        g_w = s_row.get('goal_w') or float(str(settings.get('water_goal', 2.5)).replace(',', '.'))
        f_p = s_row.get('protein') if s_row.get('protein') is not None else l_p
        s_s = s_row.get('steps') or 0; s_w = s_row.get('water') or 0; s_sl = s_row.get('sleep') or 0
        s_m = s_row.get('money') or 0; gym_d = s_row.get('gym') or 0; run_d = s_row.get('run') or 0
        bible_d = s_row.get('bible') or 0
        
        y, m, d = map(int, d_str.split('-'))
        days_in_month = calendar.monthrange(y, m)[1]
        g_m = float(str(settings.get(f'money_goal_{y}-{m:02d}', 300)).replace(',', '.'))
        spent = sum(stats_dict.get(f"{y}-{m:02d}-{i:02d}", {}).get('money', 0) or 0 for i in range(1, d))
        days_left = days_in_month - d + 1
        limit_m = (g_m - spent) / days_left if days_left > 0 else 0
        
        score = 0
        if f_p >= g_p: score += 3
        if s_sl >= g_sl: score += 2
        if s_s >= g_s: score += 2
        if s_w >= g_w: score += 2
        if s_m <= limit_m: score += 1
        if gym_d > 0 or run_d > 0: score += 2
        if bible_d > 0: score += 1
        
        if score >= 9: streak += 1
        else:
            if not is_first_day: break
        is_first_day = False; check_date -= timedelta(days=1)
    return streak

def update_daily_stat(date, field, value, add=False):
    if not value or str(value).strip() == "": return
    conn = get_db_connection()
    clean_val = float(str(value).replace(',', '.'))
    row = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone()
    if row:
        if add:
            current = row[field] if row[field] is not None else 0
            conn.execute(f'UPDATE daily_stats SET {field} = ? WHERE date = ?', (current + clean_val, date))
        else:
            conn.execute(f'UPDATE daily_stats SET {field} = ? WHERE date = ?', (clean_val, date))
    else:
        conn.execute(f'INSERT INTO daily_stats (date, {field}) VALUES (?, ?)', (date, clean_val))
    conn.commit(); conn.close()

def save_fav_db(conn, f_name, q_val, u_val, c_val, p_val, r_val):
    existing = conn.execute("SELECT id FROM favorites WHERE food_name=?", (f_name,)).fetchone()
    if existing:
        conn.execute("UPDATE favorites SET qty=?, unit=?, calories=?, protein=?, recipe=? WHERE id=?", (q_val, u_val, c_val, p_val, r_val, existing['id']))
    else:
        conn.execute("INSERT INTO favorites (food_name, qty, unit, calories, protein, recipe) VALUES (?, ?, ?, ?, ?, ?)", (f_name, q_val, u_val, c_val, p_val, r_val))

def get_badge(recipe_str):
    if recipe_str and recipe_str not in ('', '""', '[]'): return '<span style="background:#5e5ce6; color:#fff; padding:3px 8px; border-radius:8px; font-size:0.55rem; margin-left:6px; vertical-align:middle; font-weight:900; letter-spacing:0.5px;">MEAL</span>'
    return '<span style="background:#3a3a3c; color:#8e8e93; padding:3px 8px; border-radius:8px; font-size:0.55rem; margin-left:6px; vertical-align:middle; font-weight:900; letter-spacing:0.5px;">ITEM</span>'

def get_swipe_js(prev_url, next_url):
    return f"""
    <script>
        let touchstartX = 0; let touchendX = 0;
        document.addEventListener('touchstart', e => {{ touchstartX = e.changedTouches[0].screenX; }}, {{passive: true}});
        document.addEventListener('touchend', e => {{
            touchendX = e.changedTouches[0].screenX;
            if (touchendX < touchstartX - 60) window.location.href = '{next_url}';
            if (touchendX > touchstartX + 60) window.location.href = '{prev_url}';
        }}, {{passive: true}});
    </script>
    """

CSS = """
<style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, sans-serif; background: #000; color: #fff; padding: 15px; text-align: center; padding-bottom: 90px; overflow-x: hidden; }
    .card { background: #1c1c1e; border-radius: 20px; padding: 20px; margin-bottom: 20px; border: 1px solid #2c2c2e; width: 100%; box-shadow: 0 4px 15px rgba(0,0,0,0.4); }
    .nav-bar { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(28, 28, 30, 0.95); backdrop-filter: blur(10px); display: flex; justify-content: space-around; padding: 15px 0; border-top: 0.5px solid #3a3a3c; z-index: 100; }
    .nav-item { color: #8e8e93; text-decoration: none; font-size: 0.70rem; font-weight: 600; flex: 1; display: flex; flex-direction: column; align-items: center; }
    .nav-item.active { color: #0a84ff; }
    input, textarea, select { background: #2c2c2e; border: none; border-radius: 12px; color: #fff; padding: 15px; width: 100%; font-size: 16px; -webkit-appearance: none; font-family:inherit; }
    .input-label { color: #8e8e93; font-size: 0.65rem; display: block; text-align: left; margin-left: 5px; margin-bottom: 4px; font-weight:bold; text-transform:uppercase; letter-spacing:0.5px; }
    .btn-main { background: #0a84ff; color: #fff; border: none; border-radius: 15px; padding: 16px; width: 100%; font-weight: bold; font-size: 16px; cursor: pointer; transition:0.2s; }
    .btn-green { background: #30d158; color: #000; border: none; border-radius: 15px; padding: 16px; width: 100%; font-weight: bold; font-size: 16px; cursor: pointer; display: block; text-decoration: none; transition:0.2s; }
    .btn-orange { background: #ff9f0a; color: #000; border: none; border-radius: 12px; padding: 16px; width: 100%; font-weight: bold; font-size: 16px; cursor: pointer; transition:0.2s; }
    .btn-red { background: rgba(255, 69, 58, 0.15); color: #ff453a; border: 1px solid #ff453a; border-radius: 12px; padding: 10px; font-weight: bold; font-size: 14px; cursor: pointer; margin-top: 10px; }
    .sug-container { display: flex; overflow-x: auto; gap: 10px; padding: 10px 0; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
    .sug-item { background: #2c2c2e; color: #0a84ff; padding: 15px 18px; border-radius: 18px; text-decoration: none; min-width: 130px; font-size: 0.85rem; border: 1px solid #3a3a3c; flex-shrink: 0; cursor: pointer; text-align: left; }
    .log-item { display: flex; justify-content: space-between; align-items: center; background: #1c1c1e; padding: 12px 16px; border-radius: 18px; margin-bottom: 12px; border: 1px solid #2c2c2e; transition: 0.2s; width: 100%; }
    .log-item:active { transform: scale(0.98); background: #2c2c2e; }
    .day-header { text-align: left; color: #8e8e93; font-size: 0.8rem; text-transform: uppercase; margin: 10px 5px; letter-spacing: 1px; }
    .progress-track { background: rgba(255,255,255,0.1); border-radius: 10px; height: 12px; width: 100%; margin: 8px 0 15px 0; overflow: hidden; }
    .progress-fill-c { background: linear-gradient(90deg, #0a84ff, #5e5ce6); height: 100%; border-radius: 10px; transition: width 0.8s cubic-bezier(0.2, 0.8, 0.2, 1); }
    .progress-fill-p { background: linear-gradient(90deg, #30d158, #32d74b); height: 100%; border-radius: 10px; transition: width 0.8s cubic-bezier(0.2, 0.8, 0.2, 1); }
    .recipe-list { text-align: left; color: #8e8e93; font-size: 0.85rem; margin-top: 10px; padding: 10px; background: #000; border-radius: 10px; min-height: 40px; max-height: 350px; overflow-y: auto; }
    @keyframes popIn { 0% { transform: scale(0.9); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
    .checkbox-wrapper { display: flex; align-items: center; justify-content: center; gap: 10px; background: #2c2c2e; padding: 20px; border-radius: 15px; cursor: pointer; border: 2px solid #3a3a3c; transition: 0.2s; width:100%; margin-bottom:15px; -webkit-tap-highlight-color: transparent; user-select: none; }
    .checkbox-wrapper.checked { background: #30d158; border-color: #30d158; color: #000; }
    .checkbox-wrapper span { font-weight: bold; color: #fff; pointer-events: none; transition: 0.2s; }
    .checkbox-wrapper.checked span { color: #000; }
    .checkbox-wrapper input { display: none; }
</style>
<script>
    function updateDailyStat(id, chkId) {
        let cb = document.getElementById(chkId);
        cb.checked = !cb.checked;
        document.getElementById(id).classList.toggle('checked', cb.checked);
    }
</script>
"""

@app.route('/ajax_save_fav', methods=['POST'])
def ajax_save_fav():
    conn = get_db_connection()
    f_name = request.form.get('food_name') or "Item"
    existing = conn.execute("SELECT id FROM favorites WHERE food_name=?", (f_name,)).fetchone()
    
    if existing:
        conn.close()
        return "EXISTS"
        
    c_val = request.form.get('calories')
    p_val = request.form.get('protein')
    q_val = request.form.get('qty') or 1
    u_val = request.form.get('unit') or 'qty'
    
    if c_val and p_val:
        conn.execute("INSERT INTO favorites (food_name, qty, unit, calories, protein, recipe) VALUES (?, ?, ?, ?, ?, ?)", 
                     (f_name, float(q_val), u_val, int(float(c_val)), int(float(p_val)), ""))
        conn.commit()
    conn.close()
    return "OK"

@app.route('/', methods=['GET', 'POST'])
def home():
    today = datetime.now().strftime("%Y-%m-%d")
    ensure_daily_goals(today)
    conn = get_db_connection()
    yesterday_dt = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
    
    if request.method == 'POST':
        if 'yesterday_steps' in request.form:
            update_daily_stat(yesterday_str, 'steps', request.form.get('yesterday_steps'))
            update_daily_stat(yesterday_str, 'water', request.form.get('yesterday_water'))
            update_daily_stat(yesterday_str, 'sleep', request.form.get('yesterday_sleep'))
            y_bib = 1 if request.form.get('yesterday_bible') == 'on' else 0
            conn.execute('UPDATE daily_stats SET bible=? WHERE date=?', (y_bib, yesterday_str))
            conn.commit()
            return redirect(url_for('home'))
            
        if request.form.get('add_money'):
            update_daily_stat(today, 'money', request.form.get('add_money'), add=True)
            return redirect(url_for('home'))

        action = request.form.get('action')
        if action == 'add_log' and request.form.get('calories') and request.form.get('protein'):
            f_name = request.form.get('food_name') or "Item"
            c_val = request.form.get('calories')
            p_val = request.form.get('protein')
            q_val = request.form.get('qty') or 1
            u_val = request.form.get('unit') or 'qty'
            r_val = request.form.get('recipe_json') or ""
            
            now_time_str = datetime.now().strftime("%H:%M")
            recent_log = conn.execute('SELECT * FROM logs WHERE date = ? AND food_name = ? AND unit = ? ORDER BY id DESC LIMIT 1', (today, f_name, u_val)).fetchone()
            merged = False
            if recent_log:
                try:
                    log_time = datetime.strptime(recent_log['timestamp'], "%H:%M")
                    now_time_parsed = datetime.strptime(now_time_str, "%H:%M")
                    diff = (now_time_parsed - log_time).total_seconds() / 60
                    if 0 <= diff <= 5: 
                        new_qty = float(recent_log['qty'] or 1) + float(q_val)
                        new_cal = recent_log['calories'] + int(float(c_val))
                        new_prot = recent_log['protein'] + int(float(p_val))
                        conn.execute('UPDATE logs SET qty=?, calories=?, protein=?, timestamp=? WHERE id=?', (new_qty, new_cal, new_prot, now_time_str, recent_log['id']))
                        merged = True
                except: pass
            
            if not merged:
                conn.execute('INSERT INTO logs (food_name, qty, unit, calories, protein, timestamp, date, recipe) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (f_name, float(q_val), u_val, int(float(c_val)), int(float(p_val)), now_time_str, today, r_val))
            conn.commit()
            return redirect(url_for('home'))

    has_history = conn.execute("SELECT 1 FROM daily_stats WHERE date <= ?", (yesterday_str,)).fetchone() or conn.execute("SELECT 1 FROM logs WHERE date <= ?", (yesterday_str,)).fetchone()
    missing_routines_html = ""
    step_record = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (yesterday_str,)).fetchone()
    
    if (step_record is None or step_record['steps'] is None) and has_history:
        missing_routines_html = f"""
        <div class="card" style="border: 2px solid #ff9f0a; animation: popIn 0.5s ease; background: rgba(255, 159, 10, 0.1);">
            <h3 style="color:#ff9f0a; margin-top:0;">📋 YESTERDAY'S REPORT ({yesterday_dt.strftime("%d/%m")})</h3>
            <form method="POST" style="display:flex; flex-direction:column; gap:10px;">
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
                    <div><span class="input-label">Steps 👣</span><input type="number" name="yesterday_steps" placeholder="10000" style="margin:0;"></div>
                    <div><span class="input-label">Sleep 💤 (h)</span><input type="text" inputmode="decimal" name="yesterday_sleep" placeholder="7.5" style="margin:0;"></div>
                    <div><span class="input-label">Water 💧 (L)</span><input type="text" inputmode="decimal" name="yesterday_water" placeholder="2.5" style="margin:0;"></div>
                    <div class="checkbox-wrapper" id="y_bible_lbl" onclick="updateDailyStat('y_bible_lbl', 'y_bible_chk')" style="margin:0; padding:15px;">
                        <input type="checkbox" id="y_bible_chk" name="yesterday_bible"> 
                        <span style="font-size:0.85rem;">📖 Bible</span>
                    </div>
                </div>
                <button type="submit" class="btn-orange" style="margin:0;">SAVE ROUTINES</button>
            </form>
        </div>
        """

    streak = get_streak(conn)
    streak_html = f'<span style="background:rgba(255, 159, 10, 0.2); color:#ff9f0a; padding:4px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; margin-left:10px; border: 1px solid #ff9f0a;">🔥 {streak} DAYS</span>' if streak > 0 else ''

    logs = conn.execute('SELECT * FROM logs WHERE date = ? ORDER BY id DESC', (today,)).fetchall()
    
    top_4 = conn.execute('SELECT f.*, COUNT(l.id) as uses FROM favorites f LEFT JOIN logs l ON f.food_name = l.food_name GROUP BY f.id ORDER BY uses DESC LIMIT 4').fetchall()
    top_4_ids = [str(f['id']) for f in top_4]
    if top_4_ids:
        id_list = ",".join(top_4_ids)
        recent_2 = conn.execute(f'SELECT f.*, MAX(l.id) as last_used FROM favorites f JOIN logs l ON f.food_name = l.food_name WHERE f.id NOT IN ({id_list}) GROUP BY f.id ORDER BY last_used DESC LIMIT 2').fetchall()
    else:
        recent_2 = conn.execute('SELECT f.*, MAX(l.id) as last_used FROM favorites f JOIN logs l ON f.food_name = l.food_name GROUP BY f.id ORDER BY last_used DESC LIMIT 2').fetchall()
        
    display_favs = list(top_4) + list(recent_2)
    
    today_stats = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (today,)).fetchone()
    goal_c = today_stats['goal_c'] if today_stats and today_stats['goal_c'] else 2100
    goal_p = today_stats['goal_p'] if today_stats and today_stats['goal_p'] else 160
    
    calc_c = sum(log['calories'] for log in logs); calc_p = sum(log['protein'] for log in logs)
    total_c = today_stats['calories'] if today_stats and today_stats['calories'] is not None else calc_c
    total_p = today_stats['protein'] if today_stats and today_stats['protein'] is not None else calc_p
    conn.close()

    pct_c = min((total_c / goal_c) * 100, 100) if goal_c > 0 else 0
    pct_p = min((total_p / goal_p) * 100, 100) if goal_p > 0 else 0
    color_c = "#30d158" if total_c >= goal_c else "#fff"
    color_p = "#30d158" if total_p >= goal_p else "#fff"

    html_favs = ""
    for f in display_favs:
        safe_name = f['food_name'].replace('"', '&quot;').replace("'", "&#39;")
        recipe_safe = (f['recipe'] or "").replace('"', '&quot;').replace("'", "&#39;")
        html_favs += f"""
        <div class="sug-item" onclick="quickAddPrompt(this)" data-name="{safe_name}" data-qty="{f['qty'] or 1}" data-unit="{f['unit'] or 'qty'}" data-cal="{f['calories']}" data-prot="{f['protein']}" data-recipe="{recipe_safe}">
            <div style="margin-bottom:5px;"><b>{f['food_name']}</b></div>{get_badge(f['recipe'])}<br>
            <span style="color:#8e8e93; font-weight:normal; display:block; margin-top:8px;">{f['qty'] or 1} {f['unit'] or 'qty'} | {f['calories']} kcal</span>
        </div>"""
    
    html_logs = "".join([f"""
    <div class="log-item" style="cursor:pointer;" onclick="window.location.href='/edit_log/{l['id']}'">
        <div style="text-align:left; flex:1;">
            <b>{l['food_name']}</b> <span style="color:#8e8e93; font-size:0.7rem;">({l['qty'] or 1}{l['unit'] or 'qty'})</span> {get_badge(l['recipe'])}<br>
            <small style="color:#8e8e93;">{l['timestamp']} • {l['calories']} kcal | {l['protein']}g Prot</small>
        </div>
        <button onclick="event.stopPropagation(); window.location.href='/delete/{l['id']}'" style="background:rgba(255,69,58,0.15); border:1px solid #ff453a; color:#ff453a; font-weight:bold; font-size:1.1rem; padding:10px 15px; border-radius:12px; margin-left:10px; cursor:pointer;">✕</button>
    </div>""" for l in logs])

    return f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">{CSS}</head><body>
        {missing_routines_html}
        <div class="card" style="background: linear-gradient(145deg, #1c1c1e, #000); border: none; text-align: left;">
            <div style="display:flex; align-items:center; margin-bottom:5px;"><p style="color: #8e8e93; margin: 0; font-size: 0.8rem; font-weight: bold;">TODAY</p>{streak_html}</div>
            <h1 style="font-size: 2.5rem; margin: 5px 0 0 0; color: {color_c}; transition: color 0.3s;">{total_c} <span style="font-size: 1rem; color: #8e8e93; font-weight: normal;">/ {goal_c} kcal</span></h1>
            <div class="progress-track"><div class="progress-fill-c" style="width: {pct_c}%;"></div></div>
            <p style="color: {color_p}; font-weight: bold; font-size: 1.1rem; margin: 10px 0 0 0; transition: color 0.3s;">{total_p} <span style="font-size: 0.9rem; color: #8e8e93; font-weight: normal;">/ {goal_p}g Prot</span></p>
            <div class="progress-track"><div class="progress-fill-p" style="width: {pct_p}%;"></div></div>
        </div>
        <div class="card" style="padding:15px;"><h3 class="day-header" style="margin-top:0; color:#8e8e93;">MONEY SPENT TODAY 💸</h3><form method="POST" style="display:flex; gap:10px;"><input type="text" inputmode="decimal" name="add_money" placeholder="E.g., 1.50" style="flex:7; margin:0; font-size:1rem;"><button class="btn-main" style="margin:0; flex:3; padding:12px; font-size:0.9rem; background:#30d158; color:#000;">LOG</button></form></div>
        <a href="/build_meal" class="btn-green" style="margin-bottom: 20px;">🥗 BUILD MEAL</a>
        <div class="card">
            <h3 class="day-header" style="margin-top:0;">Quick Add</h3>
            <div class="sug-container" id="quick_add_container" style="margin-bottom: 15px;">
                {html_favs or '<p style="color:#444; font-size:0.8rem; margin-left:10px;">No favorites.</p>'}
                <a href="/library" class="sug-item" style="display:flex; align-items:center; justify-content:center; background:#1c1c1e; color:#fff; border:1px solid #3a3a3c;"><b>SEE ALL 📚</b></a>
            </div>
            <h3 class="day-header" style="margin-top:20px;">Manual Add</h3>
            <form method="POST" id="manual_add_form">
                <div style="margin-bottom:10px;"><span class="input-label">Name</span><input type="text" name="food_name" placeholder="Item Name" style="margin:0; padding:12px;"></div>
                <div style="display: flex; gap: 8px; margin-bottom:10px;">
                    <div style="flex:1;"><span class="input-label">Qty/Amt</span><input type="number" step="0.1" name="qty" placeholder="1" value="1" required style="margin:0; padding:12px;"></div>
                    <div style="flex:1;"><span class="input-label">Unit</span><select name="unit" style="margin:0; padding:12px;"><option value="qty">Qty</option><option value="g">g</option></select></div>
                </div>
                <div style="display: flex; gap: 8px;">
                    <div style="flex:1;"><span class="input-label">Calories</span><input type="number" name="calories" placeholder="Kcal" required style="margin:0; padding:12px;"></div>
                    <div style="flex:1;"><span class="input-label">Protein (g)</span><input type="number" name="protein" placeholder="Prot" required style="margin:0; padding:12px;"></div>
                </div>
                <div style="display:flex; gap:10px; margin-top:15px;">
                    <button type="button" onclick="saveToLibAjax()" id="save_lib_btn" class="btn-orange" style="flex:1; margin:0; padding:14px; font-size:0.85rem; transition:0.3s;">💾 TO LIBRARY</button>
                    <button type="submit" name="action" value="add_log" class="btn-main" style="flex:2; margin:0; padding:14px; background:#30d158; color:#000;">➕ ADD TO LOG</button>
                </div>
            </form>
        </div>
        <h3 class="day-header">Today's Log</h3>{html_logs}
        <div class="nav-bar"><a href="/" class="nav-item active"><span style="font-size:1.2rem;">🏠</span>TODAY</a><a href="/history" class="nav-item"><span style="font-size:1.2rem;">📅</span>ROUTINES</a><a href="/money" class="nav-item"><span style="font-size:1.2rem;">💸</span>MONEY</a><a href="/manage_favs" class="nav-item"><span style="font-size:1.2rem;">⚙️</span>SETTINGS</a></div>
        
        <form id="scaled_form" method="POST" style="display:none;">
            <input type="hidden" name="action" value="add_log">
            <input type="hidden" name="food_name" id="final_food_name">
            <input type="hidden" name="qty" id="final_qty">
            <input type="hidden" name="unit" id="final_unit">
            <input type="hidden" name="calories" id="final_cal">
            <input type="hidden" name="protein" id="final_prot">
            <input type="hidden" name="recipe_json" id="final_recipe">
        </form>
        
        <script>
            function saveToLibAjax() {{
                let fd = new FormData(document.getElementById('manual_add_form'));
                if(!fd.get('calories') || !fd.get('protein')) {{ alert("Fill Calories and Protein first!"); return; }}
                if(!fd.get('food_name')) fd.set('food_name', 'Item');
                
                fetch('/ajax_save_fav', {{method: 'POST', body: fd}}).then(res => res.text()).then(text => {{
                    let btn = document.getElementById('save_lib_btn');
                    if(text === "EXISTS") {{
                        btn.innerText = "ALREADY EXISTS ❌"; btn.style.background = "#ff453a"; btn.style.color = "#fff";
                        setTimeout(() => {{ btn.innerText = "💾 TO LIBRARY"; btn.style.background = "#ff9f0a"; btn.style.color = "#000"; }}, 1000);
                    }} else {{
                        btn.innerText = "SAVED ✅"; btn.style.background = "#30d158"; btn.style.color = "#000";
                        document.getElementById('manual_add_form').reset();
                        document.querySelector('input[name="qty"]').value="1";
                        setTimeout(() => {{ window.location.reload(); }}, 500);
                    }}
                }});
            }}
            
            function quickAddPrompt(el) {{
                let n = el.getAttribute('data-name'); let q = el.getAttribute('data-qty'); let u = el.getAttribute('data-unit');
                let new_q = prompt("How much did you eat?\\n" + n + " (Saved as " + q + " " + u + ")", q);
                if (new_q !== null && new_q.trim() !== "") {{
                    new_q = parseFloat(new_q.replace(',', '.'));
                    if (!isNaN(new_q) && new_q > 0) {{
                        let base_q = parseFloat(q) || 1; let multi = new_q / base_q;
                        document.getElementById('final_food_name').value = n;
                        document.getElementById('final_qty').value = new_q;
                        document.getElementById('final_unit').value = u;
                        document.getElementById('final_cal').value = Math.round(parseFloat(el.getAttribute('data-cal')) * multi);
                        document.getElementById('final_prot').value = Math.round(parseFloat(el.getAttribute('data-prot')) * multi);
                        
                        let recipe = el.getAttribute('data-recipe');
                        if (recipe && recipe !== '""' && recipe !== '[]') {{
                            let parsed = JSON.parse(recipe);
                            parsed = parsed.map(item => {{ return {{ ...item, qty: item.qty ? parseFloat((item.qty * multi).toFixed(2)) : null, cal: Math.round(item.cal * multi), prot: Math.round(item.prot * multi) }}; }});
                            recipe = JSON.stringify(parsed);
                        }}
                        document.getElementById('final_recipe').value = recipe;
                        document.getElementById('scaled_form').submit();
                    }}
                }}
            }}
        </script>
    </body></html>
    """

@app.route('/library')
def library():
    conn = get_db_connection()
    favs = conn.execute('SELECT * FROM favorites ORDER BY food_name ASC').fetchall()
    conn.close()
    
    html_favs = ""
    for f in favs:
        safe_name = f['food_name'].replace('"', '&quot;').replace("'", "&#39;")
        recipe_safe = (f['recipe'] or "").replace('"', '&quot;').replace("'", "&#39;")
        html_favs += f"""
        <div class="log-item fav-search-item" style="cursor:pointer; display:flex;" onclick="window.location.href='/edit_fav/{f['id']}'" data-name="{f['food_name'].lower()}">
            <div style="text-align:left; flex:1;">
                <b>{f["food_name"]}</b> {get_badge(f["recipe"])}<br>
                <small style="color:#8e8e93;">Base: {f["qty"] or 1}{f["unit"] or "qty"} | {f["calories"]} kcal</small>
            </div>
            <div style="display:flex; gap:5px;">
                <button style="background:#0a84ff; color:#fff; font-weight:bold; font-size:1.5rem; padding:5px 15px; border-radius:12px; border:none; cursor:pointer;" onclick="event.stopPropagation(); quickAddPrompt(this)" data-name="{safe_name}" data-qty="{f['qty'] or 1}" data-unit="{f['unit'] or 'qty'}" data-cal="{f['calories']}" data-prot="{f['protein']}" data-recipe="{recipe_safe}">+</button>
                <button style="background:rgba(255,69,58,0.15); color:#ff453a; font-weight:bold; font-size:1.2rem; padding:5px 15px; border-radius:12px; border:1px solid #ff453a; cursor:pointer;" onclick="event.stopPropagation(); window.location.href='/delete_fav/{f['id']}'">✕</button>
            </div>
        </div>"""

    return f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <a href="javascript:history.back()" style="color:#0a84ff; text-decoration:none; font-weight:bold; font-size:1.2rem;">&lt; Back</a>
            <h2 style="color:#fff; margin:0; font-size:1.2rem;">LIBRARY 📚</h2>
            <div style="width:50px;"></div>
        </div>
        <input type="text" id="search_bar" placeholder="Search library..." onkeyup="filterLibrary()" style="margin-bottom:20px;">
        <div id="library_list">{html_favs or "<p style='color:#444;'>Empty library.</p>"}</div>
        
        <form id="scaled_form" method="POST" action="/" style="display:none;">
            <input type="hidden" name="action" value="add_log">
            <input type="hidden" name="food_name" id="final_food_name"><input type="hidden" name="qty" id="final_qty"><input type="hidden" name="unit" id="final_unit"><input type="hidden" name="calories" id="final_cal"><input type="hidden" name="protein" id="final_prot"><input type="hidden" name="recipe_json" id="final_recipe">
        </form>
        <script>
            function filterLibrary() {{
                let input = document.getElementById('search_bar').value.toLowerCase();
                let items = document.getElementsByClassName('fav-search-item');
                for (let i = 0; i < items.length; i++) {{
                    let name = items[i].getAttribute('data-name');
                    items[i].style.display = name.includes(input) ? "flex" : "none";
                }}
            }}
            function quickAddPrompt(el) {{
                let n = el.getAttribute('data-name'); let q = el.getAttribute('data-qty'); let u = el.getAttribute('data-unit');
                let new_q = prompt("How much did you eat?\\n" + n + " (Saved as " + q + " " + u + ")", q);
                if (new_q !== null && new_q.trim() !== "") {{
                    new_q = parseFloat(new_q.replace(',', '.'));
                    if (!isNaN(new_q) && new_q > 0) {{
                        let base_q = parseFloat(q) || 1; let multi = new_q / base_q;
                        document.getElementById('final_food_name').value = n;
                        document.getElementById('final_qty').value = new_q;
                        document.getElementById('final_unit').value = u;
                        document.getElementById('final_cal').value = Math.round(parseFloat(el.getAttribute('data-cal')) * multi);
                        document.getElementById('final_prot').value = Math.round(parseFloat(el.getAttribute('data-prot')) * multi);
                        let recipe = el.getAttribute('data-recipe');
                        if (recipe && recipe !== '""' && recipe !== '[]') {{
                            let parsed = JSON.parse(recipe);
                            parsed = parsed.map(item => {{ return {{ ...item, qty: item.qty ? parseFloat((item.qty * multi).toFixed(2)) : null, cal: Math.round(item.cal * multi), prot: Math.round(item.prot * multi) }}; }});
                            recipe = JSON.stringify(parsed);
                        }}
                        document.getElementById('final_recipe').value = recipe;
                        document.getElementById('scaled_form').submit();
                    }}
                }}
            }}
        </script>
    </body></html>
    """

@app.route('/history')
def history():
    conn = get_db_connection()
    settings = {row['key']: row['value'] for row in conn.execute("SELECT * FROM settings").fetchall()}
    global_g_c = int(settings.get('daily_goal', 2100)); global_g_p = int(settings.get('protein_goal', 160))
    global_g_s = int(settings.get('step_goal', 10000)); global_g_w = float(str(settings.get('water_goal', 2.5)).replace(',', '.'))
    goal_sl = 7.5
    
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    try: target_date = datetime.strptime(month_str, '%Y-%m')
    except: target_date = datetime.now()
        
    y, m = target_date.year, target_date.month
    prev_m = (target_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    next_m = (target_date.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m')
    month_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    logs_data = conn.execute("SELECT date, SUM(calories) as c, SUM(protein) as p FROM logs GROUP BY date").fetchall()
    stats_data = conn.execute("SELECT * FROM daily_stats").fetchall()

    logs_dict = {row['date']: {'c': row['c'], 'p': row['p']} for row in logs_data}
    stats_dict = {row['date']: dict(row) for row in stats_data}
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(y, m)
    today_str = datetime.now().strftime("%Y-%m-%d")

    cal_html = f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;"><a href="/history?month={prev_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&lt;</a><h2 style="color:#fff; margin:0; font-size:1.2rem; text-transform:uppercase;">{month_names[m-1]} {y}</h2><a href="/history?month={next_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&gt;</a></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:3px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;"><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div><div>S</div></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:3px;">'
    rot_html = '<div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:3px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;"><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div><div>S</div></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:3px;">'
    work_html = '<div style="display:flex; flex-direction:column; gap:15px;">'

    for week in month_days:
        week_planned_so_far = 0; week_done = 0; has_current_month_days = False
        
        for day_date in week:
            d_str = day_date.strftime("%Y-%m-%d"); d_num = day_date.day; wd = str(day_date.weekday())
            is_future = d_str > today_str; is_current_month = day_date.month == m
            if is_current_month: has_current_month_days = True
            
            l_c = logs_dict.get(d_str, {}).get('c', 0); l_p = logs_dict.get(d_str, {}).get('p', 0)
            s_row = stats_dict.get(d_str, {})
            
            g_c = s_row.get('goal_c') or global_g_c; g_p = s_row.get('goal_p') or global_g_p
            g_s = s_row.get('goal_s') or global_g_s; g_w = s_row.get('goal_w') or global_g_w
            
            s_c = s_row.get('calories'); s_p = s_row.get('protein'); s_s = s_row.get('steps') or 0; s_w = s_row.get('water') or 0; s_sl = s_row.get('sleep') or 0
            s_n = s_row.get('notes'); bible_d = int(s_row.get('bible') or 0)
            gym_d = int(s_row.get('gym') or 0); run_d = int(s_row.get('run') or 0)
            
            p_g = s_row.get('planned_g'); p_r = s_row.get('planned_r')
            if p_g is None or p_r is None:
                routine = get_routine_for_date(conn, d_str)
                if p_g is None: p_g = routine.get(wd, {}).get("g", "")
                if p_r is None: p_r = routine.get(wd, {}).get("r", "")
            
            if d_str <= today_str:
                if p_g: week_planned_so_far += 1
                if p_r: week_planned_so_far += 1
                if gym_d: week_done += 1
                if run_d: week_done += 1
            
            final_c = s_c if s_c is not None else l_c; final_p = s_p if s_p is not None else l_p
            border_c = "transparent"
            if not is_future and is_current_month:
                p_met = final_p >= g_p; s_met = s_s >= g_s
                if not (final_c > 0 or final_p > 0 or s_s > 0): border_c = "#ff453a"
                else: border_c = "#30d158" if (p_met and s_met) else ("#ffd60a" if p_met else ("#ff9f0a" if s_met else "#ff453a"))

            border_r = "transparent"
            if not is_future and is_current_month:
                w_met = s_w >= g_w; sl_met = s_sl >= goal_sl
                if not (s_w > 0 or s_sl > 0 or bible_d > 0): border_r = "#ff453a"
                else: border_r = "#30d158" if (w_met and sl_met) else ("#ffd60a" if sl_met else ("#ff9f0a" if w_met else "#ff453a"))

            day_color = "rgba(10, 132, 255, 0.15)" if d_str == today_str else "#2c2c2e"
            if d_str == today_str: border_c = "#0a84ff"; border_r = "#0a84ff"
            opacity = "1" if is_current_month else "0.3"
            
            note_icon = ' <span style="font-size:0.6rem;">📝</span>' if s_n else ''
            stats_txt = f'<div style="font-size:0.5rem; color:#8e8e93; margin-top:2px; line-height:1.2;">{final_c} kcal<br>{final_p}p<br>👣{s_s}</div>' if (final_c>0 or s_s>0) else ""
            
            rot_txt = ""
            if s_w > 0 or s_sl > 0 or bible_d > 0:
                rot_txt = f'<div style="font-size:0.5rem; color:#8e8e93; margin-top:2px; line-height:1.2;">💤{s_sl}h<br>💧{s_w}L'
                if bible_d: rot_txt += '<br>📖'
                rot_txt += '</div>'
            
            if is_future:
                cal_html += f'<div style="background:{day_color}; border: 2px solid transparent; border-radius:10px; padding:5px 0; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d_num}</span></div>'
                rot_html += f'<div style="background:{day_color}; border: 2px solid transparent; border-radius:10px; padding:5px 0; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d_num}</span></div>'
            else:
                cal_html += f'<a href="/edit_day/{d_str}?type=macros" style="background:{day_color}; border: 2px solid {border_c}; border-radius:10px; padding:5px 0; text-decoration:none; color:#fff; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px; box-sizing:border-box; transition:0.2s;"><span style="font-weight:bold; font-size:0.9rem;">{d_num}{note_icon}</span>{stats_txt}</a>'
                rot_html += f'<a href="/edit_day/{d_str}?type=routines" style="background:{day_color}; border: 2px solid {border_r}; border-radius:10px; padding:5px 0; text-decoration:none; color:#fff; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px; box-sizing:border-box; transition:0.2s;"><span style="font-weight:bold; font-size:0.9rem;">{d_num}</span>{rot_txt}</a>'

        if has_current_month_days:
            border_wk = "#2c2c2e"
            if week[0].strftime("%Y-%m-%d") <= today_str:
                if week_planned_so_far == 0: border_wk = "#30d158" if week_done > 0 else "#2c2c2e"
                else:
                    ratio = week_done / week_planned_so_far
                    border_wk = "#30d158" if ratio >= 0.8 else ("#ffd60a" if ratio >= 0.5 else "#ff453a")
                
            work_html += f'<div style="border: 2px solid {border_wk}; border-radius:15px; padding:10px; background:#1c1c1e; margin-bottom:10px;"><div style="display:flex; justify-content:center; margin-bottom:10px; font-size:0.85rem; font-weight:bold; color:#fff; padding: 0 5px;"><span>Volume: {week_done} / {week_planned_so_far}</span></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:3px;">'
            
            for day_date in week:
                d_str = day_date.strftime("%Y-%m-%d"); d_num = day_date.day; wd = str(day_date.weekday())
                is_future = d_str > today_str; is_current_month = day_date.month == m
                s_row = stats_dict.get(d_str, {})
                gym_d = int(s_row.get('gym') or 0); run_d = int(s_row.get('run') or 0)
                
                p_g = s_row.get('planned_g')
                if p_g is None: p_g = routine.get(wd, {}).get("g", "")
                p_r = s_row.get('planned_r')
                if p_r is None: p_r = routine.get(wd, {}).get("r", "")
                
                day_color = "#2c2c2e"; border_c_work = "1px solid #3a3a3c"
                if d_str == today_str: day_color = "rgba(10, 132, 255, 0.15)"; border_c_work = "1px solid #0a84ff"
                if gym_d > 0 or run_d > 0: day_color = "rgba(10, 132, 255, 0.2)"; border_c_work = "1px solid #0a84ff"
                    
                opacity = "1" if is_current_month else "0.3"
                icons = ""
                
                if gym_d: icons += f'<div style="color:#30d158; font-weight:bold; font-size:0.55rem; margin-top:3px; line-height:1;">🏋️‍♂️ {p_g or "Gym"}</div>'
                elif p_g and not is_future: icons += f'<div style="color:#ff453a; font-weight:bold; font-size:0.55rem; margin-top:3px; line-height:1;">🏋️‍♂️ {p_g}</div>'
                elif p_g and is_future: icons += f'<div style="color:#8e8e93; font-weight:bold; font-size:0.55rem; margin-top:3px; line-height:1;">🏋️‍♂️ {p_g}</div>'
                
                if run_d: icons += f'<div style="color:#30d158; font-weight:bold; font-size:0.55rem; margin-top:3px; line-height:1;">🏃 {p_r or "Run"}</div>'
                elif p_r and not is_future: icons += f'<div style="color:#ff453a; font-weight:bold; font-size:0.55rem; margin-top:3px; line-height:1;">🏃 {p_r}</div>'
                elif p_r and is_future: icons += f'<div style="color:#8e8e93; font-weight:bold; font-size:0.55rem; margin-top:3px; line-height:1;">🏃 {p_r}</div>'
                
                if not icons: icons = '<div style="color:#444; font-size:0.6rem; margin-top:3px;">Rest</div>'
                
                if is_future: work_html += f'<div style="background:{day_color}; border: {border_c_work}; border-radius:10px; padding:5px 0; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px; box-sizing:border-box;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d_num}</span>{icons}</div>'
                else: work_html += f'<a href="/edit_day/{d_str}?type=workout" style="background:{day_color}; border: {border_c_work}; border-radius:10px; padding:5px 0; text-decoration:none; color:#fff; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px; box-sizing:border-box; transition:0.2s;"><span style="font-weight:bold; font-size:0.9rem;">{d_num}</span>{icons}</a>'
            work_html += "</div></div>"

    conn.close()
    cal_html += "</div>"; rot_html += "</div>"; work_html += "</div>"

    return f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color:#8e8e93; margin-bottom:10px;">MACROS & DIARY</h2><div class="card" style="padding:15px;">{cal_html}<div style="display:flex; justify-content:center; gap:10px; font-size:0.65rem; color:#8e8e93; margin-top:20px; flex-wrap:wrap;"><div><span style="color:#30d158;">🟢</span> Prot + Steps</div><div><span style="color:#ffd60a;">🟡</span> Only Prot</div><div><span style="color:#ff9f0a;">🟠</span> Only Steps</div><div><span style="color:#ff453a;">🔴</span> Incomplete</div><div>📝 Notes</div></div></div>
        <h2 style="color:#8e8e93; margin-bottom:10px;">WELL BEING</h2><div class="card" style="padding:15px;">{rot_html}<div style="display:flex; justify-content:center; gap:10px; font-size:0.65rem; color:#8e8e93; margin-top:20px; flex-wrap:wrap;"><div><span style="color:#30d158;">🟢</span> Sleep + Water</div><div><span style="color:#ffd60a;">🟡</span> Only Sleep</div><div><span style="color:#ff9f0a;">🟠</span> Only Water</div><div><span style="color:#ff453a;">🔴</span> Incomplete</div></div></div>
        <h2 style="color:#8e8e93; margin-bottom:10px;">WEEKLY WORKOUTS</h2><div class="card" style="padding:15px; border:none; background:transparent;"><p style="font-size:0.8rem; color:#8e8e93; margin-top:0;">Flexible Plan (Green > 80% Volume)</p>{work_html}</div>
        <div class="nav-bar"><a href="/" class="nav-item"><span style="font-size:1.2rem;">🏠</span>TODAY</a><a href="/history" class="nav-item active"><span style="font-size:1.2rem;">📅</span>ROUTINES</a><a href="/money" class="nav-item"><span style="font-size:1.2rem;">💸</span>MONEY</a><a href="/manage_favs" class="nav-item"><span style="font-size:1.2rem;">⚙️</span>SETTINGS</a></div>
        {get_swipe_js(f"/history?month={prev_m}", f"/history?month={next_m}")}
    </body></html>
    """

@app.route('/money', methods=['GET', 'POST'])
def money():
    conn = get_db_connection()
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    try: target_date = datetime.strptime(month_str, '%Y-%m')
    except: target_date = datetime.now()
    y, m = target_date.year, target_date.month
    
    if request.method == 'POST':
        new_b = request.form.get('new_budget')
        if new_b: conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f'money_goal_{y}-{m:02d}', new_b.replace(',', '.'))); conn.commit()
        return redirect(url_for('money', month=month_str))

    prev_m = (target_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    next_m = (target_date.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m')
    month_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    goal_m_raw = conn.execute("SELECT value FROM settings WHERE key=?", (f'money_goal_{y}-{m:02d}',)).fetchone()
    if not goal_m_raw: goal_m_raw = conn.execute("SELECT value FROM settings WHERE key='money_goal'").fetchone()
    goal_m = float(goal_m_raw['value'].replace(',', '.')) if goal_m_raw else 300.0
    
    stats_data = conn.execute("SELECT * FROM daily_stats WHERE date LIKE ?", (f"{y}-{m:02d}-%",)).fetchall()
    conn.close()
    
    days_in_month = calendar.monthrange(y, m)[1]
    stats_dict = {row['date']: dict(row) for row in stats_data}
    day_limits = {}; cumulative_spent = 0; today_str = datetime.now().strftime("%Y-%m-%d"); current_dynamic_avg = 0
    
    for day_num in range(1, days_in_month + 1):
        d_str_loop = f"{y}-{m:02d}-{day_num:02d}"
        days_left = days_in_month - day_num + 1
        current_limit = (goal_m - cumulative_spent) / days_left if days_left > 0 else 0
        day_limits[d_str_loop] = current_limit
        if d_str_loop == today_str: current_dynamic_avg = current_limit
        cumulative_spent += (stats_dict.get(d_str_loop, {}).get('money') or 0)
        
    total_spent_month = cumulative_spent
    today_spent = stats_dict.get(today_str, {}).get('money') or 0
    left_today = current_dynamic_avg - today_spent
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(y, m)

    cal_html = f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;"><a href="/money?month={prev_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&lt;</a><h2 style="color:#fff; margin:0; font-size:1.2rem; text-transform:uppercase;">{month_names[m-1]} {y}</h2><a href="/money?month={next_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&gt;</a></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;"><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div><div>S</div></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px;">'

    for week in month_days:
        for day_date in week:
            d_str = day_date.strftime("%Y-%m-%d"); d_num = day_date.day
            is_future = d_str > today_str; is_current_month = day_date.month == m
            spent = stats_dict.get(d_str, {}).get('money') or 0; daily_limit = day_limits.get(d_str, 0)
            border_c = "transparent"
            if not is_future and is_current_month:
                border_c = "#30d158" if spent <= daily_limit else "#ff453a"
                if spent == 0: border_c = "#30d158"

            day_color = "rgba(10, 132, 255, 0.15)" if d_str == today_str else "#2c2c2e"
            opacity = "1" if is_current_month else "0.3"
            txt = f'<div style="font-size:0.6rem; color:#8e8e93; margin-top:2px; font-weight:bold;">{spent:.1f}€</div>' if spent > 0 else ""
            if is_future: cal_html += f'<div style="background:{day_color}; border: 2px solid transparent; border-radius:10px; padding:8px 0; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d_num}</span></div>'
            else: cal_html += f'<a href="/edit_day/{d_str}?type=money" style="background:{day_color}; border: 2px solid {border_c}; border-radius:10px; padding:8px 0; text-decoration:none; color:#fff; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; min-height:55px; box-sizing:border-box; transition:0.2s;"><span style="font-weight:bold; font-size:0.9rem;">{d_num}</span>{txt}</a>'
    cal_html += "</div>"

    color_total = "#ff453a" if total_spent_month > goal_m else "#30d158"
    if current_dynamic_avg == 0 and datetime.strptime(today_str, "%Y-%m-%d").month != m: current_dynamic_avg = goal_m / days_in_month

    return f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <div class="card" style="background: linear-gradient(145deg, #1c1c1e, #000); border: none; text-align: center;">
            <p style="color: #8e8e93; margin: 0; font-size: 0.8rem; font-weight: bold; text-transform:uppercase;">TOTAL SPENT THIS MONTH</p>
            <h1 style="font-size: 3.5rem; margin: 5px 0; color: {color_total};">{total_spent_month:.2f}€</h1>
            <form method="POST" style="margin-bottom:15px; display:flex; align-items:center; justify-content:center; gap:5px;">
                <span style="color:#8e8e93; font-size:0.85rem;">Budget:</span>
                <input type="text" inputmode="decimal" name="new_budget" value="{str(goal_m).replace('.', ',')}" style="width:70px; padding:5px; margin:0; text-align:center; background:#2c2c2e; border-radius:8px; font-size:0.85rem; color:#fff;">
                <button type="submit" style="background:transparent; border:none; color:#0a84ff; font-weight:bold; cursor:pointer;">💾</button>
            </form>
            <div style="background:#2c2c2e; padding:15px; border-radius:15px; margin-top:5px; display:flex; justify-content:space-around;">
                <div><p style="margin:0; font-size:0.75rem; color:#8e8e93;">DAILY AVERAGE</p><p style="margin:0; font-size:1.1rem; font-weight:bold; color:#0a84ff;">{current_dynamic_avg:.2f}€</p></div>
                <div style="border-left: 1px solid #3a3a3c; padding-left: 15px;"><p style="margin:0; font-size:0.75rem; color:#8e8e93;">LEFT FOR TODAY</p><p style="margin:0; font-size:1.1rem; font-weight:bold; color:{'#30d158' if left_today >= 0 else '#ff453a'};">{left_today:.2f}€</p></div>
            </div>
        </div>
        <div class="card" style="padding:15px;">{cal_html}</div>
        <div class="nav-bar"><a href="/" class="nav-item"><span style="font-size:1.2rem;">🏠</span>TODAY</a><a href="/history" class="nav-item"><span style="font-size:1.2rem;">📅</span>ROUTINES</a><a href="/money" class="nav-item active"><span style="font-size:1.2rem;">💸</span>MONEY</a><a href="/manage_favs" class="nav-item"><span style="font-size:1.2rem;">⚙️</span>SETTINGS</a></div>
        {get_swipe_js(f"/money?month={prev_m}", f"/money?month={next_m}")}
    </body></html>
    """

@app.route('/rank')
def rank():
    conn = get_db_connection()
    settings = {row['key']: row['value'] for row in conn.execute("SELECT * FROM settings").fetchall()}
    global_g_p = int(settings.get('protein_goal', 160))
    global_g_s = int(settings.get('step_goal', 10000))
    global_g_w = float(str(settings.get('water_goal', 2.5)).replace(',', '.'))
    g_sl = 7.5
    
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    try: target_date = datetime.strptime(month_str, '%Y-%m')
    except: target_date = datetime.now()
    y, m = target_date.year, target_date.month
    prev_m = (target_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    next_m = (target_date.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m')
    month_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    logs_data = conn.execute("SELECT date, SUM(protein) as p FROM logs GROUP BY date").fetchall()
    stats_data = conn.execute("SELECT * FROM daily_stats").fetchall()
    
    goal_m_raw = conn.execute("SELECT value FROM settings WHERE key=?", (f'money_goal_{y}-{m:02d}',)).fetchone()
    if not goal_m_raw: goal_m_raw = conn.execute("SELECT value FROM settings WHERE key='money_goal'").fetchone()
    g_m = float(goal_m_raw['value'].replace(',', '.')) if goal_m_raw else 300.0
    
    days_in_month = calendar.monthrange(y, m)[1]
    conn.close()

    logs_dict = {row['date']: {'p': row['p']} for row in logs_data}
    stats_dict = {row['date']: dict(row) for row in stats_data}
    
    day_limits = {}; cumulative_spent = 0; today_str = datetime.now().strftime("%Y-%m-%d")
    for day_num in range(1, days_in_month + 1):
        d_str_loop = f"{y}-{m:02d}-{day_num:02d}"
        days_left = days_in_month - day_num + 1
        current_limit = (g_m - cumulative_spent) / days_left if days_left > 0 else 0
        day_limits[d_str_loop] = current_limit
        cumulative_spent += (stats_dict.get(d_str_loop, {}) or {}).get('money', 0) or 0

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(y, m)

    cal_html = f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;"><a href="/rank?month={prev_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&lt;</a><h2 style="color:#fff; margin:0; font-size:1.2rem; text-transform:uppercase;">{month_names[m-1]} {y}</h2><a href="/rank?month={next_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&gt;</a></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;"><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div><div>S</div></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px;">'

    for week in month_days:
        for day_date in week:
            d_str = day_date.strftime("%Y-%m-%d"); d_num = day_date.day
            is_future = d_str > today_str; is_current_month = day_date.month == m
            
            l_p = logs_dict.get(d_str, {}).get('p', 0)
            s_row = stats_dict.get(d_str, {})
            
            g_p = s_row.get('goal_p') or global_g_p
            s_p = s_row.get('protein'); s_s = s_row.get('steps') or 0; s_w = s_row.get('water') or 0; s_sl = s_row.get('sleep') or 0; s_m = s_row.get('money') or 0
            s_n = s_row.get('notes'); bible_d = int(s_row.get('bible') or 0)
            gym_d = int(s_row.get('gym') or 0); run_d = int(s_row.get('run') or 0)
            
            f_p = s_p if s_p is not None else l_p
            limit_m = day_limits.get(d_str, 0)
            
            score = 0
            if not is_future:
                if f_p >= g_p: score += 3
                if s_sl >= g_sl: score += 2
                if s_s >= 10000: score += 2
                if s_w >= 2.5: score += 2
                if s_m <= limit_m: score += 1
                if gym_d > 0 or run_d > 0: score += 2
                if bible_d > 0: score += 1

            bg_color = "transparent"; txt_color = "#fff"
            if not is_future and is_current_month:
                has_any_data = f_p > 0 or s_sl > 0 or s_m > 0 or s_w > 0 or s_s > 0 or gym_d > 0 or run_d > 0 or bible_d > 0
                if not has_any_data: bg_color = "transparent"; score_display = "-"
                else:
                    if score == 0: bg_color = "rgba(255, 69, 58, 0.4)"; txt_color = "#fff"
                    elif score <= 4: bg_color = "rgba(255, 159, 10, 0.5)"; txt_color = "#fff"
                    elif score <= 8: bg_color = "rgba(255, 214, 10, 0.5)"; txt_color = "#000"
                    elif score <= 12: bg_color = "rgba(48, 209, 88, 0.6)"; txt_color = "#000"
                    else: bg_color = "rgba(10, 132, 255, 0.8)"; txt_color = "#fff"
                    score_display = f"{score}"
            else: score_display = "-"
                
            opacity = "1" if is_current_month else "0.2"
            border = "2px solid #0a84ff" if d_str == today_str else "2px solid transparent"
            note_icon = ' <span style="font-size:0.6rem;">📝</span>' if s_n else ''
            cal_html += f'<div style="background:{bg_color}; border:{border}; border-radius:10px; padding:8px 0; color:{txt_color}; opacity:{opacity}; display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:55px; box-sizing:border-box;"><span style="font-size:0.6rem; margin-bottom:2px;">{d_num}{note_icon}</span><span style="font-weight:900; font-size:1.2rem;">{score_display}</span></div>'
    cal_html += "</div>"

    return f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <div class="card" style="background: linear-gradient(145deg, #1c1c1e, #000); border: 1px solid #0a84ff; padding-bottom:10px;">
            <h2 style="color:#0a84ff; margin-top:0;">GOD RANK 🏆</h2>
            <p style="font-size:0.8rem; color:#8e8e93; margin-bottom:0;">Daily Score (0 to 13):<br>Prot (3) | Sleep (2) | Steps (2)<br>Water (2) | Workout (2) | € Avg (1) | Bible (1)</p>
        </div>
        <div class="card" style="padding:15px;">{cal_html}</div>
        <a href="/manage_favs" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Back to Settings</a>
        {get_swipe_js(f"/rank?month={prev_m}", f"/rank?month={next_m}")}
    </body></html>
    """

def parse_val(v, is_float=False):
    if v is None: return None
    v = str(v).strip()
    if v == "": return "CLEAR"
    v = v.replace(',', '.')
    try: return float(v) if is_float else int(float(v))
    except: return "CLEAR"

@app.route('/edit_day/<date>', methods=['GET', 'POST'])
def edit_day(date):
    edit_type = request.args.get('type', 'macros')
    conn = get_db_connection()
    if request.method == 'POST':
        row = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone()
        if not row: ensure_daily_goals(date)
        
        if edit_type == 'macros':
            c = parse_val(request.form.get('calories'), False)
            p = parse_val(request.form.get('protein'), False)
            s = parse_val(request.form.get('steps'), False)
            n = request.form.get('notes')
            if n is not None: conn.execute('UPDATE daily_stats SET notes=? WHERE date=?', (n.strip(), date))
            if c is not None: conn.execute('UPDATE daily_stats SET calories=? WHERE date=?', (None if c == "CLEAR" else c, date))
            if p is not None: conn.execute('UPDATE daily_stats SET protein=? WHERE date=?', (None if p == "CLEAR" else p, date))
            if s is not None: conn.execute('UPDATE daily_stats SET steps=? WHERE date=?', (None if s == "CLEAR" else s, date))
            
        elif edit_type == 'routines':
            w = parse_val(request.form.get('water'), True)
            sl = parse_val(request.form.get('sleep'), True)
            b = 1 if request.form.get('bible') == 'on' else 0
            if w is not None: conn.execute('UPDATE daily_stats SET water=? WHERE date=?', (None if w == "CLEAR" else w, date))
            if sl is not None: conn.execute('UPDATE daily_stats SET sleep=? WHERE date=?', (None if sl == "CLEAR" else sl, date))
            if 'bible' in request.form or 'water' in request.form: conn.execute('UPDATE daily_stats SET bible=? WHERE date=?', (b, date))
            
        elif edit_type == 'money':
            m = parse_val(request.form.get('money'), True)
            if m is not None: conn.execute('UPDATE daily_stats SET money=? WHERE date=?', (None if m == "CLEAR" else m, date))
            
        elif edit_type == 'workout':
            g = 1 if request.form.get('gym') == 'on' else 0
            ru = 1 if request.form.get('run') == 'on' else 0
            if request.form.get('override_routine') == 'on':
                p_g = request.form.get('planned_g', "")
                p_r = request.form.get('planned_r', "")
                conn.execute('UPDATE daily_stats SET gym=?, run=?, planned_g=?, planned_r=? WHERE date=?', (g, ru, p_g, p_r, date))
            else:
                conn.execute('UPDATE daily_stats SET gym=?, run=? WHERE date=?', (g, ru, date))

        conn.commit(); conn.close()
        if edit_type == 'money': return redirect(url_for('money', month=date[:7]))
        return redirect(url_for('history', month=date[:7]))
        
    logs = conn.execute('SELECT * FROM logs WHERE date = ? ORDER BY id DESC', (date,)).fetchall()
    stats = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone()
    
    routine = get_routine_for_date(conn, date)
    conn.close()
    
    wd = str(datetime.strptime(date, "%Y-%m-%d").weekday())
    logs_c = sum(l['calories'] for l in logs); logs_p = sum(l['protein'] for l in logs)
    s_c = stats['calories'] if stats and 'calories' in stats.keys() and stats['calories'] is not None else ""
    s_p = stats['protein'] if stats and 'protein' in stats.keys() and stats['protein'] is not None else ""
    s_s = stats['steps'] if stats and 'steps' in stats.keys() and stats['steps'] is not None else ""
    s_w = stats['water'] if stats and 'water' in stats.keys() and stats['water'] is not None else ""
    s_m = stats['money'] if stats and 'money' in stats.keys() and stats['money'] is not None else ""
    s_sl = stats['sleep'] if stats and 'sleep' in stats.keys() and stats['sleep'] is not None else ""
    s_n = stats['notes'] if stats and 'notes' in stats.keys() and stats['notes'] is not None else ""
    
    p_g = stats['planned_g'] if stats and 'planned_g' in stats.keys() and stats['planned_g'] is not None else routine.get(wd, {}).get("g", "")
    p_r = stats['planned_r'] if stats and 'planned_r' in stats.keys() and stats['planned_r'] is not None else routine.get(wd, {}).get("r", "")
    
    s_gym = 'checked' if stats and 'gym' in stats.keys() and stats['gym'] == 1 else ""
    s_run = 'checked' if stats and 'run' in stats.keys() and stats['run'] == 1 else ""
    s_b = 'checked' if stats and 'bible' in stats.keys() and stats['bible'] == 1 else ""
    
    display_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d %b %Y")
    
    html_logs = "".join([f"""
    <div class="log-item" style="cursor:pointer; display:flex;" onclick="window.location.href='/edit_log/{l['id']}'">
        <div style="text-align:left; flex:1;">
            <b>{l["food_name"]}</b> <span style="color:#8e8e93; font-size:0.7rem;">({l["qty"] or 1}{l["unit"] or 'qty'})</span> {get_badge(l["recipe"])}<br>
            <small style="color:#8e8e93;">{l["timestamp"]} • {l["calories"]} kcal | {l["protein"]}g Prot</small>
        </div>
        <button onclick="event.stopPropagation(); window.location.href='/delete/{l["id"]}'" style="background:rgba(255,69,58,0.15); border:1px solid #ff453a; color:#ff453a; font-weight:bold; font-size:1.1rem; cursor:pointer; padding:10px 15px; border-radius:12px; margin-left:10px;">✕</button>
    </div>""" for l in logs])
    
    if edit_type == 'macros':
        form_content = f'<div style="margin-bottom:10px;"><span class="input-label">Calories (Kcal)</span><input type="number" name="calories" value="{s_c}" placeholder="Auto: {logs_c} kcal" style="margin:0;"></div><div style="margin-bottom:10px;"><span class="input-label">Protein (g)</span><input type="number" name="protein" value="{s_p}" placeholder="Auto: {logs_p} g" style="margin:0;"></div><div style="margin-bottom:10px;"><span class="input-label">Steps 👣</span><input type="number" name="steps" value="{s_s}" placeholder="E.g., 10500" style="margin:0;"></div><div><span class="input-label">Daily Notes 📝</span><textarea name="notes" rows="3" placeholder="Today went wrong because..." style="margin:0; resize:none;">{s_n}</textarea></div>'
        extra_html = f'<h3 class="day-header">DAY\'S LOG</h3>{html_logs or "<p style=\'color:#444; font-size:0.9rem;\'>No meals logged.</p>"}'
        title_top = "MACROS AND NOTES"
    elif edit_type == 'workout':
        gym_opts = ["", "Push", "Pull", "Legs", "Upper", "Lower"]
        run_opts = ["", "Tempo", "Easy", "Hard"]
        g_sel = "".join([f'<option value="{o}" {"selected" if o==p_g else ""}>{o if o else "Rest"}</option>' for o in gym_opts])
        r_sel = "".join([f'<option value="{o}" {"selected" if o==p_r else ""}>{o if o else "Rest"}</option>' for o in run_opts])
        
        form_content = f"""
        <div class="checkbox-wrapper {s_gym}" id="gym_lbl" onclick="updateDailyStat('gym_lbl', 'gym_chk')">
            <input type="checkbox" id="gym_chk" name="gym" {'checked' if s_gym else ''} style="display:none;"> 
            <span style="font-size:1.2rem; pointer-events: none;">🏋️‍♂️ Went to Gym</span>
        </div>
        <div class="checkbox-wrapper {s_run}" id="run_lbl" onclick="updateDailyStat('run_lbl', 'run_chk')">
            <input type="checkbox" id="run_chk" name="run" {'checked' if s_run else ''} style="display:none;"> 
            <span style="font-size:1.2rem; pointer-events: none;">🏃 Went Running</span>
        </div>
        
        <div class="checkbox-wrapper" id="override_lbl" onclick="let cb=document.getElementById('override_chk'); cb.checked=!cb.checked; this.classList.toggle('checked', cb.checked); document.getElementById('override_box').style.display = cb.checked ? 'block' : 'none';">
            <input type="checkbox" name="override_routine" id="override_chk" style="display:none;">
            <span style="font-size:1.1rem; pointer-events:none;">Override Planned Routine?</span>
        </div>
        
        <div id="override_box" style="display:none; background:#1c1c1e; padding:15px; border-radius:12px; margin-top:5px; width:100%; box-sizing:border-box; border:1px solid #ff9f0a;">
            <p style="color:#8e8e93; font-size:0.8rem; margin-top:0;">Change the plan just for this day.</p>
            <div style="display:flex; gap:10px; width:100%;">
                <select name="planned_g" style="flex:1; padding:10px; font-weight:bold; margin:0;">{g_sel}</select>
                <select name="planned_r" style="flex:1; padding:10px; font-weight:bold; margin:0;">{r_sel}</select>
            </div>
        </div>
        """
        extra_html = ""
        title_top = "WORKOUT"
    elif edit_type == 'routines':
        form_content = f"""
        <div style="margin-bottom:10px;"><span class="input-label">Sleep 💤 (Hours)</span><input type="text" inputmode="decimal" name="sleep" value="{str(s_sl).replace(".", ",") if s_sl else ""}" placeholder="E.g., 7.5" style="margin:0;"></div>
        <div style="margin-bottom:15px;"><span class="input-label">Water 💧 (Liters)</span><input type="text" inputmode="decimal" name="water" value="{str(s_w).replace(".", ",") if s_w else ""}" placeholder="E.g., 2.5" style="margin:0;"></div>
        <div class="checkbox-wrapper {s_b}" id="bible_lbl" onclick="updateDailyStat('bible_lbl', 'bible_chk')">
            <input type="checkbox" id="bible_chk" name="bible" {'checked' if s_b else ''} style="display:none;"> 
            <span style="font-size:1.2rem; pointer-events: none;">📖 Read Bible</span>
        </div>
        """
        extra_html = ""
        title_top = "ROUTINES"
    elif edit_type == 'money':
        form_content = f'<div><span class="input-label">Money Spent 💸 (€)</span><input type="text" inputmode="decimal" name="money" value="{str(s_m).replace(".", ",") if s_m else ""}" placeholder="E.g., 15.50" style="margin:0;"></div>'
        extra_html = ""
        title_top = "FINANCES"

    return f'<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><h2 style="color:#8e8e93; text-transform:uppercase;">{display_date}</h2><div class="card"><h3 style="margin-top:0; color:#8e8e93;">EDIT {title_top}</h3><form method="POST" action="/edit_day/{date}?type={edit_type}"><div style="display:flex; flex-direction:column; align-items:flex-start;">{form_content}</div><button type="submit" class="btn-main" style="margin:top:20px;">SAVE DAY</button></form><a href="javascript:history.back()" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Go Back</a></div>{extra_html}</body></html>'

@app.route('/routine', methods=['GET', 'POST'])
def routine():
    conn = get_db_connection()
    if request.method == 'POST':
        new_routine = {}
        for i in range(7):
            new_routine[str(i)] = {"g": request.form.get(f"g_{i}", ""), "r": request.form.get(f"r_{i}", "")}
        s_date = request.form.get('start_date') or "2000-01-01"
        e_date = request.form.get('end_date') or "2099-12-31"
        conn.execute("INSERT INTO routines (start_date, end_date, schedule) VALUES (?, ?, ?)", (s_date, e_date, json.dumps(new_routine)))
        conn.commit(); conn.close()
        return redirect(url_for('manage_favs'))

    # O RADAR DE OVERLAP PARA O JAVASCRIPT
    ex_rt = conn.execute("SELECT start_date, end_date FROM routines").fetchall()
    overlap_data = json.dumps([{"s": r["start_date"], "e": r["end_date"]} for r in ex_rt])

    latest_rt = conn.execute("SELECT schedule FROM routines ORDER BY id DESC LIMIT 1").fetchone()
    routines = json.loads(latest_rt['schedule']) if latest_rt else {str(i): {"g": "", "r": ""} for i in range(7)}
    conn.close()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    gym_opts = ["", "Push", "Pull", "Legs", "Upper", "Lower"]
    run_opts = ["", "Tempo", "Easy", "Hard"]
    rows_html = ""
    for i, day in enumerate(days):
        g_val = routines.get(str(i), {}).get("g", "")
        r_val = routines.get(str(i), {}).get("r", "")
        g_sel = "".join([f'<option value="{o}" {"selected" if o==g_val else ""}>{o if o else "Rest"}</option>' for o in gym_opts])
        r_sel = "".join([f'<option value="{o}" {"selected" if o==r_val else ""}>{o if o else "Rest"}</option>' for o in run_opts])
        
        rows_html += f"""
        <div style="background:#2c2c2e; padding:15px; border-radius:12px; margin-bottom:10px; text-align:left; border: 2px solid #3a3a3c;">
            <div style="color:#8e8e93; font-weight:bold; margin-bottom:8px; text-transform:uppercase; font-size:0.85rem;">{day}</div>
            <div style="display:flex; gap:10px;">
                <div style="flex:1;"><span class="input-label">🏋️‍♂️ Gym</span><select name="g_{i}" style="margin:0; padding:12px; font-weight:bold; color:#0a84ff; background:#1c1c1e; border:1px solid #3a3a3c; border-radius:8px; text-align:center;">{g_sel}</select></div>
                <div style="flex:1;"><span class="input-label">🏃 Run</span><select name="r_{i}" style="margin:0; padding:12px; font-weight:bold; color:#ff9f0a; background:#1c1c1e; border:1px solid #3a3a3c; border-radius:8px; text-align:center;">{r_sel}</select></div>
            </div>
        </div>
        """

    return f'''
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color:#8e8e93;">NEW WORKOUT ROUTINE 🗓️</h2>
        <form method="POST" onsubmit="return checkOverlap(event)">
            <div class="card" style="padding:15px;">
                <div style="display:flex; gap:10px; margin-bottom:15px;">
                    <div style="flex:1;"><span class="input-label">Start Date</span><input type="date" id="start_date" name="start_date" value="{datetime.now().strftime("%Y-%m-%d")}" style="margin:0; padding:10px;"></div>
                    <div style="flex:1;"><span class="input-label">End Date</span><input type="date" id="end_date" name="end_date" value="2099-12-31" style="margin:0; padding:10px;"></div>
                </div>
                {rows_html}
                <button type="submit" class="btn-main" style="margin-top:10px; background:#30d158; color:#000;">SAVE ROUTINE</button>
            </div>
        </form>
        <a href="/manage_favs" style="display:block; margin-top:10px; color:#8e8e93; text-decoration:none;">Cancel</a>
        <script>
            const existing = {overlap_data};
            function checkOverlap(e) {{
                let s = document.getElementById('start_date').value;
                let end = document.getElementById('end_date').value;
                if(!s) s = "2000-01-01"; if(!end) end = "2099-12-31";
                
                let hasOverlap = existing.some(r => {{ return (s <= r.e && end >= r.s); }});
                
                if(hasOverlap) {{
                    if(!confirm("⚠️ AVISO: Já tens uma rotina a passar por estes dias. Queres mesmo sobrepor as datas e criar esta nova?")) {{
                        e.preventDefault();
                        return false;
                    }}
                }}
                return true;
            }}
        </script>
    </body></html>
    '''

@app.route('/manage_favs', methods=['GET', 'POST'])
def manage_favs():
    conn = get_db_connection()
    if request.method == 'POST':
        updates = [('daily_goal', request.form.get('new_goal')), ('protein_goal', request.form.get('new_p_goal')), ('step_goal', request.form.get('new_s_goal')), ('water_goal', request.form.get('new_w_goal'))]
        for k, v in updates:
            if v: conn.execute("UPDATE settings SET value=? WHERE key=?", (v.replace(',', '.'), k))
        conn.commit()
    goals = {row['key']: row['value'] for row in conn.execute("SELECT * FROM settings").fetchall()}
    conn.close()
        
    return f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <a href="/rank" class="btn-main" style="display:block; text-decoration:none; background:linear-gradient(90deg, #0a84ff, #5e5ce6); color:#fff; font-size:1.2rem; margin-bottom:20px; padding:20px; box-shadow: 0 4px 15px rgba(10,132,255,0.4);">SEE GOD RANK 🏆</a>
        <a href="/routine" class="btn-main" style="display:block; text-decoration:none; background:#ff9f0a; color:#000; margin-bottom:15px;">🗓️ CREATE WORKOUT ROUTINE</a>
        <a href="/library" class="btn-main" style="display:block; text-decoration:none; background:#2c2c2e; color:#fff; border: 1px solid #3a3a3c; margin-bottom:20px;">📚 OPEN LIBRARY</a>
        
        <div class="card"><h3 style="margin-top:0; color:#8e8e93;">GENERAL GOALS</h3><form method="POST">
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
                <div><span class="input-label">Kcal</span><input type="number" name="new_goal" value="{goals.get('daily_goal', 2100)}" style="margin:0;"></div>
                <div><span class="input-label">Prot (g)</span><input type="number" name="new_p_goal" value="{goals.get('protein_goal', 160)}" style="margin:0;"></div>
                <div><span class="input-label">Steps</span><input type="number" name="new_s_goal" value="{goals.get('step_goal', 10000)}" style="margin:0;"></div>
                <div><span class="input-label">Water (L)</span><input type="text" inputmode="decimal" name="new_w_goal" value="{str(goals.get('water_goal', 2.5)).replace('.', ',')}" style="margin:0;"></div>
            </div><button type="submit" class="btn-main" style="margin-top:15px; background:#0a84ff; color:#fff;">SAVE GOALS</button>
        </form></div>
        <div class="card"><h3 style="margin-top:0; color:#8e8e93;">BACKUP & RESTORE 💾</h3><a href="/export_db" class="btn-main" style="display:block; text-decoration:none; background:#5e5ce6; margin-bottom:15px;">📥 DOWNLOAD APP BACKUP</a><form method="POST" action="/import_db" enctype="multipart/form-data" style="border-top: 1px solid #2c2c2e; padding-top: 15px;"><p style="font-size:0.8rem; color:#8e8e93; text-align:left; margin-top:0;">Changed phones? Upload your '.db' file here.</p><input type="file" name="db_file" accept=".db" required style="width:100%; margin-bottom:10px; background:#000;"><button type="submit" class="btn-red" style="margin:0; width:100%; background:rgba(255, 159, 10, 0.15); color:#ff9f0a; border: 1px solid #ff9f0a;">📤 RESTORE BACKUP</button></form></div>
        <div class="nav-bar"><a href="/" class="nav-item"><span style="font-size:1.2rem;">🏠</span>TODAY</a><a href="/history" class="nav-item"><span style="font-size:1.2rem;">📅</span>ROUTINES</a><a href="/money" class="nav-item"><span style="font-size:1.2rem;">💸</span>MONEY</a><a href="/manage_favs" class="nav-item active"><span style="font-size:1.2rem;">⚙️</span>SETTINGS</a></div>
    </body></html>
    """

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')