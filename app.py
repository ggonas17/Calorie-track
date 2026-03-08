import sqlite3
import os
import json
import calendar
from datetime import datetime, timedelta
from flask import Flask, request, redirect, url_for, send_file

app = Flask(__name__)

# ==========================================
# DATABASE & CORE FUNCTIONS
# ==========================================

def get_db_connection():
    conn = sqlite3.connect('tracker.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, qty REAL DEFAULT 1, unit TEXT DEFAULT "qty", calories INTEGER, protein INTEGER, timestamp TEXT, date TEXT, recipe TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, qty REAL DEFAULT 1, unit TEXT DEFAULT "qty", calories INTEGER, protein INTEGER, recipe TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS daily_stats (date TEXT PRIMARY KEY, steps INTEGER, calories INTEGER, protein INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS routines (id INTEGER PRIMARY KEY AUTOINCREMENT, start_date TEXT, end_date TEXT, schedule TEXT)''')
    
    columns_daily = ['calories INTEGER', 'protein INTEGER', 'water REAL', 'reading INTEGER', 'money REAL', 'sleep REAL', 'gym INTEGER DEFAULT 0', 'run INTEGER DEFAULT 0', 'notes TEXT', 'bible INTEGER DEFAULT 0', 'goal_c INTEGER', 'goal_p INTEGER', 'goal_s INTEGER', 'goal_w REAL', 'planned_g TEXT', 'planned_r TEXT', 'overridden INTEGER DEFAULT 0']
    for col in columns_daily:
        try: conn.execute(f'ALTER TABLE daily_stats ADD COLUMN {col}')
        except: pass
        
    for t in ['logs', 'favorites']:
        for col in ['qty REAL DEFAULT 1', 'unit TEXT DEFAULT "qty"', 'recipe TEXT']:
            try: conn.execute(f'ALTER TABLE {t} ADD COLUMN {col}')
            except: pass
            
    defaults = [('daily_goal','2100'), ('protein_goal','160'), ('step_goal','10000'), ('water_goal','2.5'), ('money_goal','300'), ('sleep_goal','7.5'), ('macro_mode','static'), ('cal_gym','2500'), ('prot_gym','160'), ('cal_run','2300'), ('prot_run','150'), ('cal_both','2800'), ('prot_both','180'), ('cal_rest','2000'), ('prot_rest','140')]
    for k, v in defaults:
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        
    if not conn.execute("SELECT 1 FROM routines").fetchone():
        empty_plan = {str(i): {"g": "", "r": ""} for i in range(7)}
        conn.execute("INSERT INTO routines (start_date, end_date, schedule) VALUES (?, ?, ?)", ("2000-01-01", "2099-12-31", json.dumps(empty_plan)))

    conn.commit()
    conn.close()

init_db()

def get_routine_for_date(conn, d_str):
    rt = conn.execute("SELECT schedule FROM routines WHERE start_date <= ? AND end_date >= ? ORDER BY start_date DESC LIMIT 1", (d_str, d_str)).fetchone()
    return json.loads(rt['schedule']) if rt else {str(i): {"g": "", "r": ""} for i in range(7)}

def ensure_daily_goals(date_str):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date_str,)).fetchone()
    s = {r['key']: r['value'] for r in conn.execute("SELECT * FROM settings").fetchall()}
    routine = get_routine_for_date(conn, date_str)
    wd = str(datetime.strptime(date_str, "%Y-%m-%d").weekday())
    
    overridden = row['overridden'] if row and 'overridden' in row.keys() else 0
    p_g = row['planned_g'] if overridden and row['planned_g'] is not None else routine.get(wd, {}).get("g", "")
    p_r = row['planned_r'] if overridden and row['planned_r'] is not None else routine.get(wd, {}).get("r", "")
    
    if s.get('macro_mode', 'static') == 'dynamic':
        has_g, has_r = bool(p_g), bool(p_r)
        if has_g and has_r: g_c, g_p = int(float(s.get('cal_both', 2800))), int(float(s.get('prot_both', 180)))
        elif has_g: g_c, g_p = int(float(s.get('cal_gym', 2500))), int(float(s.get('prot_gym', 160)))
        elif has_r: g_c, g_p = int(float(s.get('cal_run', 2300))), int(float(s.get('prot_run', 150)))
        else: g_c, g_p = int(float(s.get('cal_rest', 2000))), int(float(s.get('prot_rest', 140)))
    else:
        g_c, g_p = int(float(s.get('daily_goal', 2100))), int(float(s.get('protein_goal', 160)))
        
    g_s, g_w = int(float(s.get('step_goal', 10000))), float(str(s.get('water_goal', 2.5)).replace(',', '.'))
    
    if not row:
        conn.execute('INSERT INTO daily_stats (date, goal_c, goal_p, goal_s, goal_w, planned_g, planned_r, overridden) VALUES (?, ?, ?, ?, ?, ?, ?, 0)', (date_str, g_c, g_p, g_s, g_w, p_g, p_r))
    elif date_str >= datetime.now().strftime("%Y-%m-%d"):
        conn.execute('UPDATE daily_stats SET goal_c=?, goal_p=?, goal_s=?, goal_w=?, planned_g=?, planned_r=? WHERE date=?', (g_c, g_p, g_s, g_w, p_g, p_r, date_str))
    
    conn.commit()
    conn.close()

def get_streak(conn):
    s = {r['key']: r['value'] for r in conn.execute("SELECT * FROM settings").fetchall()}
    g_sl = float(str(s.get('sleep_goal', 7.5)).replace(',', '.'))
    stats_dict = {row['date']: dict(row) for row in conn.execute("SELECT * FROM daily_stats").fetchall()}
    logs_dict = {row['date']: row['p'] for row in conn.execute("SELECT date, SUM(protein) as p FROM logs GROUP BY date").fetchall()}
    min_date = min(conn.execute("SELECT MIN(date) as md FROM daily_stats").fetchone()['md'] or "2099", conn.execute("SELECT MIN(date) as md FROM logs").fetchone()['md'] or "2099")
    
    if min_date == "2099": return 0
    streak = 0; check_date = datetime.now(); is_first_day = True
    
    while True:
        d_str = check_date.strftime("%Y-%m-%d")
        if d_str < min_date: break
        
        sr = stats_dict.get(d_str, {})
        limit_m = 0
        y, m, d = map(int, d_str.split('-'))
        days_left = calendar.monthrange(y, m)[1] - d + 1
        if days_left > 0:
            limit_m = (float(str(s.get(f'money_goal_{y}-{m:02d}', 300)).replace(',', '.')) - sum(stats_dict.get(f"{y}-{m:02d}-{i:02d}", {}).get('money', 0) or 0 for i in range(1, d))) / days_left
            
        score = sum([
            ((sr.get('protein') if sr.get('protein') is not None else logs_dict.get(d_str, 0)) >= (sr.get('goal_p') or int(float(s.get('protein_goal', 160))))) * 3,
            ((sr.get('sleep') or 0) >= g_sl) * 2,
            ((sr.get('steps') or 0) >= (sr.get('goal_s') or int(float(s.get('step_goal', 10000))))) * 2,
            ((sr.get('water') or 0) >= (sr.get('goal_w') or float(str(s.get('water_goal', 2.5)).replace(',', '.')))) * 2,
            ((sr.get('money') or 0) <= limit_m) * 1,
            ((sr.get('gym') or 0) > 0 or (sr.get('run') or 0) > 0) * 2,
            ((sr.get('bible') or 0) > 0) * 1
        ])
        
        if score >= 9: streak += 1
        elif not is_first_day: break
        is_first_day = False; check_date -= timedelta(days=1)
        
    return streak

def update_daily_stat(date, field, value, add=False):
    if not value or str(value).strip() == "": return
    conn = get_db_connection()
    cv = float(str(value).replace(',', '.'))
    row = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone()
    if row:
        conn.execute(f'UPDATE daily_stats SET {field} = ? WHERE date = ?', ((row[field] or 0) + cv if add else cv, date))
    else:
        conn.execute(f'INSERT INTO daily_stats (date, {field}) VALUES (?, ?)', (date, cv))
    conn.commit(); conn.close()

def save_fav_db(conn, f_name, q_val, u_val, c_val, p_val, r_val):
    existing = conn.execute("SELECT id FROM favorites WHERE food_name=?", (f_name,)).fetchone()
    if existing:
        conn.execute("UPDATE favorites SET qty=?, unit=?, calories=?, protein=?, recipe=? WHERE id=?", (q_val, u_val, c_val, p_val, r_val, existing['id']))
    else:
        conn.execute("INSERT INTO favorites (food_name, qty, unit, calories, protein, recipe) VALUES (?, ?, ?, ?, ?, ?)", (f_name, q_val, u_val, c_val, p_val, r_val))

def get_badge(r): 
    return '<span style="background:#5e5ce6; color:#fff; padding:3px 8px; border-radius:8px; font-size:0.55rem; margin-left:6px; font-weight:900;">MEAL</span>' if r and r not in ('', '""', '[]') else '<span style="background:#3a3a3c; color:#8e8e93; padding:3px 8px; border-radius:8px; font-size:0.55rem; margin-left:6px; font-weight:900;">ITEM</span>'

def parse_val(v, is_float=False):
    if v is None: return None
    v = str(v).strip()
    if v == "": return "CLEAR"
    v = v.replace(',', '.')
    try: return float(v) if is_float else int(float(v))
    except: return "CLEAR"

def get_swipe_js(prev_url, next_url):
    return f"<script>let sx=0, ex=0; document.addEventListener('touchstart', e=>sx=e.changedTouches[0].screenX, {{passive:true}}); document.addEventListener('touchend', e=>{{ex=e.changedTouches[0].screenX; if(ex<sx-60)window.location.href='{next_url}'; if(ex>sx+60)window.location.href='{prev_url}';}}, {{passive:true}});</script>"

# ==========================================
# CSS STYLES
# ==========================================
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
    .checkbox-wrapper { display: flex; align-items: center; justify-content: center; gap: 10px; background: #2c2c2e; padding: 20px; border-radius: 15px; cursor: pointer; border: 2px solid #3a3a3c; transition: 0.2s; width:100%; margin-bottom:15px; user-select: none; }
    .checkbox-wrapper.checked { background: #30d158; border-color: #30d158; color: #000; }
    .checkbox-wrapper span { font-weight: bold; color: #fff; pointer-events: none; }
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

# ==========================================
# ROUTES
# ==========================================

@app.route('/ajax_save_fav', methods=['POST'])
def ajax_save_fav():
    conn = get_db_connection()
    fn = request.form.get('food_name') or "Item"
    if conn.execute("SELECT id FROM favorites WHERE food_name=?", (fn,)).fetchone(): 
        conn.close()
        return "EXISTS"
    c, p = request.form.get('calories'), request.form.get('protein')
    if c and p: 
        conn.execute("INSERT INTO favorites (food_name, qty, unit, calories, protein, recipe) VALUES (?, ?, ?, ?, ?, ?)", 
                     (fn, float(request.form.get('qty') or 1), request.form.get('unit') or 'qty', int(float(c)), int(float(p)), ""))
        conn.commit()
    conn.close()
    return "OK"

@app.route('/', methods=['GET', 'POST'])
def home():
    today = datetime.now().strftime("%Y-%m-%d")
    ensure_daily_goals(today)
    conn = get_db_connection()
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    if request.method == 'POST':
        # Smart Morning Pop-up
        if request.form.get('morning_update'):
            if not conn.execute('SELECT * FROM daily_stats WHERE date = ?', (yesterday_str,)).fetchone(): 
                conn.execute('INSERT INTO daily_stats (date) VALUES (?)', (yesterday_str,))
            if 'yesterday_steps' in request.form: conn.execute('UPDATE daily_stats SET steps=? WHERE date=?', (int(request.form.get('yesterday_steps') or 0), yesterday_str))
            if 'yesterday_water' in request.form: conn.execute('UPDATE daily_stats SET water=? WHERE date=?', (float(request.form.get('yesterday_water').replace(',','.') or 0), yesterday_str))
            if 'yesterday_sleep' in request.form: conn.execute('UPDATE daily_stats SET sleep=? WHERE date=?', (float(request.form.get('yesterday_sleep').replace(',','.') or 0), yesterday_str))
            if 'yesterday_bible_present' in request.form: conn.execute('UPDATE daily_stats SET bible=? WHERE date=?', (1 if request.form.get('yesterday_bible') == 'on' else 0, yesterday_str))
            if 'yesterday_notes' in request.form: conn.execute('UPDATE daily_stats SET notes=? WHERE date=?', (request.form.get('yesterday_notes', '').strip(), yesterday_str))
            conn.commit(); return redirect(url_for('home'))
            
        if request.form.get('add_money'): 
            update_daily_stat(today, 'money', request.form.get('add_money'), add=True)
            return redirect(url_for('home'))

        # Log Add & 5-Min Merge
        if request.form.get('action') == 'add_log' and request.form.get('calories'):
            fn, u = request.form.get('food_name') or "Item", request.form.get('unit') or 'qty'
            q, c, p = float(request.form.get('qty') or 1), int(float(request.form.get('calories'))), int(float(request.form.get('protein')))
            nt = datetime.now().strftime("%H:%M")
            r_log = conn.execute('SELECT * FROM logs WHERE date=? AND food_name=? AND unit=? ORDER BY id DESC LIMIT 1', (today, fn, u)).fetchone()
            if r_log and 0 <= (datetime.strptime(nt, "%H:%M") - datetime.strptime(r_log['timestamp'], "%H:%M")).total_seconds() / 60 <= 5:
                conn.execute('UPDATE logs SET qty=?, calories=?, protein=?, timestamp=? WHERE id=?', (float(r_log['qty'] or 1)+q, r_log['calories']+c, r_log['protein']+p, nt, r_log['id']))
            else: 
                conn.execute('INSERT INTO logs (food_name, qty, unit, calories, protein, timestamp, date, recipe) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (fn, q, u, c, p, nt, today, request.form.get('recipe_json') or ""))
            conn.commit()
            return redirect(url_for('home'))

    missing_routines_html = ""
    if conn.execute("SELECT 1 FROM daily_stats WHERE date <= ?", (yesterday_str,)).fetchone() or conn.execute("SELECT 1 FROM logs WHERE date <= ?", (yesterday_str,)).fetchone():
        sr = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (yesterday_str,)).fetchone()
        if not sr or sr['steps'] is None or sr['sleep'] is None or sr['water'] is None or sr['notes'] is None or sr['notes'] == "":
            ih = ""
            if not sr or sr['steps'] is None: ih += '<div><span class="input-label">Steps 👣</span><input type="number" name="yesterday_steps" placeholder="10000" style="margin:0;"></div>'
            if not sr or sr['sleep'] is None: ih += '<div><span class="input-label">Sleep 💤 (h)</span><input type="text" inputmode="decimal" name="yesterday_sleep" placeholder="7.5" style="margin:0;"></div>'
            if not sr or sr['water'] is None: ih += '<div><span class="input-label">Water 💧 (L)</span><input type="text" inputmode="decimal" name="yesterday_water" placeholder="2.5" style="margin:0;"></div>'
            if not sr or sr.get('bible') == 0: ih += '<input type="hidden" name="yesterday_bible_present" value="1"><div class="checkbox-wrapper" id="y_bible_lbl" onclick="updateDailyStat(\'y_bible_lbl\', \'y_bible_chk\')" style="margin:0; padding:15px;"><input type="checkbox" id="y_bible_chk" name="yesterday_bible" style="display:none;"><span style="font-size:0.85rem;">📖 Bible</span></div>'
            nh = '<div style="grid-column: 1 / -1;"><span class="input-label">Diary 📝</span><textarea name="yesterday_notes" rows="2" placeholder="How was your day?" style="margin:0; resize:none;"></textarea></div>' if not sr or sr['notes'] is None or sr['notes'] == "" else ""
            missing_routines_html = f'<div class="card" style="border:2px solid #ff9f0a; animation:popIn 0.5s ease; background:rgba(255,159,10,0.1);"><h3 style="color:#ff9f0a; margin-top:0;">📋 YESTERDAY\'S REPORT</h3><form method="POST" style="display:flex; flex-direction:column; gap:10px;"><input type="hidden" name="morning_update" value="1"><div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">{ih}{nh}</div><button type="submit" class="btn-orange" style="margin:0;">SAVE ROUTINES</button></form></div>'

    logs = conn.execute('SELECT * FROM logs WHERE date = ? ORDER BY id DESC', (today,)).fetchall()
    t4 = conn.execute('SELECT f.*, COUNT(l.id) as uses FROM favorites f LEFT JOIN logs l ON f.food_name = l.food_name GROUP BY f.id ORDER BY uses DESC LIMIT 4').fetchall()
    t4_ids = [str(f['id']) for f in t4]
    r2 = conn.execute(f'SELECT f.*, MAX(l.id) as last_used FROM favorites f JOIN logs l ON f.food_name = l.food_name WHERE f.id NOT IN ({",".join(t4_ids)}) GROUP BY f.id ORDER BY last_used DESC LIMIT 2').fetchall() if t4_ids else conn.execute('SELECT f.*, MAX(l.id) as last_used FROM favorites f JOIN logs l ON f.food_name = l.food_name GROUP BY f.id ORDER BY last_used DESC LIMIT 2').fetchall()
    
    ts = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (today,)).fetchone()
    gc, gp = (ts['goal_c'], ts['goal_p']) if ts and ts['goal_c'] else (2100, 160)
    tc = ts['calories'] if ts and ts['calories'] is not None else sum(l['calories'] for l in logs)
    tp = ts['protein'] if ts and ts['protein'] is not None else sum(l['protein'] for l in logs)
    streak = get_streak(conn)
    conn.close()

    hf = "".join([f'<div class="sug-item" onclick="quickAddPrompt(this)" data-name="{f["food_name"].replace("'", "&#39;").replace('"', '&quot;')}" data-qty="{f["qty"] or 1}" data-unit="{f["unit"] or "qty"}" data-cal="{f["calories"]}" data-prot="{f["protein"]}" data-recipe="{(f["recipe"] or "").replace("'", "&#39;").replace('"', '&quot;')}"><div style="margin-bottom:5px;"><b>{f["food_name"]}</b></div>{get_badge(f["recipe"])}<br><span style="color:#8e8e93; font-weight:normal; display:block; margin-top:8px;">{f["qty"] or 1} {f["unit"] or "qty"} | {f["calories"]} kcal</span></div>' for f in list(t4) + list(r2)])
    hl = "".join([f'<div class="log-item" style="cursor:pointer;" onclick="window.location.href=\'/edit_log/{l["id"]}\'"><div style="text-align:left; flex:1;"><b>{l["food_name"]}</b> <span style="color:#8e8e93; font-size:0.7rem;">({l["qty"] or 1}{l["unit"] or "qty"})</span> {get_badge(l["recipe"])}<br><small style="color:#8e8e93;">{l["timestamp"]} • {l["calories"]} kcal | {l["protein"]}g Prot</small></div><button onclick="event.stopPropagation(); window.location.href=\'/delete/{l["id"]}\'" style="background:rgba(255,69,58,0.15); border:1px solid #ff453a; color:#ff453a; font-weight:bold; font-size:1.1rem; padding:10px 15px; border-radius:12px; margin-left:10px;">✕</button></div>' for l in logs])

    return f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">{CSS}</head><body>
        {missing_routines_html}
        <div class="card" style="background:linear-gradient(145deg, #1c1c1e, #000); border:none; text-align:left;">
            <div style="display:flex; align-items:center; margin-bottom:5px;"><p style="color:#8e8e93; margin:0; font-size:0.8rem; font-weight:bold;">TODAY</p>{f'<span style="background:rgba(255,159,10,0.2); color:#ff9f0a; padding:4px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold; margin-left:10px; border:1px solid #ff9f0a;">🔥 {streak} DAYS</span>' if streak>0 else ''}</div>
            <h1 style="font-size:2.5rem; margin:5px 0 0 0; color:{'#30d158' if tc>=gc else '#fff'};">{tc} <span style="font-size:1rem; color:#8e8e93; font-weight:normal;">/ {gc} kcal</span></h1>
            <div class="progress-track"><div class="progress-fill-c" style="width:{min((tc/gc)*100,100) if gc>0 else 0}%;"></div></div>
            <p style="color:{'#30d158' if tp>=gp else '#fff'}; font-weight:bold; font-size:1.1rem; margin:10px 0 0 0;">{tp} <span style="font-size:0.9rem; color:#8e8e93; font-weight:normal;">/ {gp}g Prot</span></p>
            <div class="progress-track"><div class="progress-fill-p" style="width:{min((tp/gp)*100,100) if gp>0 else 0}%;"></div></div>
        </div>
        
        <div class="card" style="padding:15px;">
            <h3 class="day-header" style="margin-top:0;">MONEY SPENT TODAY 💸</h3>
            <form method="POST" style="display:flex; gap:10px;">
                <input type="text" inputmode="decimal" name="add_money" placeholder="E.g., 1.50" style="flex:7; margin:0; font-size:1rem;">
                <button class="btn-main" style="margin:0; flex:3; padding:12px; font-size:0.9rem; background:#30d158; color:#000;">LOG</button>
            </form>
        </div>
        
        <a href="/build_meal" class="btn-green" style="margin-bottom:20px;">🥗 BUILD MEAL</a>
        
        <div class="card">
            <h3 class="day-header" style="margin-top:0;">Quick Add</h3>
            <div class="sug-container" id="quick_add_container" style="margin-bottom:15px;">
                {hf or '<p style="color:#444; font-size:0.8rem; margin-left:10px;">No favorites.</p>'}
                <a href="/library" class="sug-item" style="display:flex; align-items:center; justify-content:center; background:#1c1c1e; color:#fff; border:1px solid #3a3a3c;"><b>SEE ALL 📚</b></a>
            </div>
            <h3 class="day-header" style="margin-top:20px;">Manual Add</h3>
            <form method="POST" id="manual_add_form">
                <div style="margin-bottom:10px;"><span class="input-label">Name</span><input type="text" name="food_name" placeholder="Item Name" style="margin:0; padding:12px;"></div>
                <div style="display:flex; gap:8px; margin-bottom:10px;">
                    <div style="flex:1;"><span class="input-label">Qty/Amt</span><input type="number" step="0.1" name="qty" placeholder="1" value="1" required style="margin:0; padding:12px;"></div>
                    <div style="flex:1;"><span class="input-label">Unit</span><select name="unit" style="margin:0; padding:12px;"><option value="qty">Qty</option><option value="g">g</option></select></div>
                </div>
                <div style="display:flex; gap:8px;">
                    <div style="flex:1;"><span class="input-label">Calories</span><input type="number" name="calories" placeholder="Kcal" required style="margin:0; padding:12px;"></div>
                    <div style="flex:1;"><span class="input-label">Protein (g)</span><input type="number" name="protein" placeholder="Prot" required style="margin:0; padding:12px;"></div>
                </div>
                <div style="display:flex; gap:10px; margin-top:15px;">
                    <button type="button" onclick="saveToLibAjax()" id="save_lib_btn" class="btn-orange" style="flex:1; margin:0; padding:14px; font-size:0.85rem;">💾 TO LIBRARY</button>
                    <button type="submit" name="action" value="add_log" class="btn-main" style="flex:2; margin:0; padding:14px; background:#30d158; color:#000;">➕ ADD TO LOG</button>
                </div>
            </form>
        </div>
        <h3 class="day-header">Today's Log</h3>{hl}
        <div class="nav-bar"><a href="/" class="nav-item active"><span style="font-size:1.2rem;">🏠</span>TODAY</a><a href="/history" class="nav-item"><span style="font-size:1.2rem;">📅</span>ROUTINES</a><a href="/money" class="nav-item"><span style="font-size:1.2rem;">💸</span>MONEY</a><a href="/manage_favs" class="nav-item"><span style="font-size:1.2rem;">⚙️</span>SETTINGS</a></div>
        
        <form id="scaled_form" method="POST" style="display:none;"><input type="hidden" name="action" value="add_log"><input type="hidden" name="food_name" id="final_food_name"><input type="hidden" name="qty" id="final_qty"><input type="hidden" name="unit" id="final_unit"><input type="hidden" name="calories" id="final_cal"><input type="hidden" name="protein" id="final_prot"><input type="hidden" name="recipe_json" id="final_recipe"></form>
        
        <script>
            function saveToLibAjax() {{ 
                let fd = new FormData(document.getElementById('manual_add_form')); 
                if(!fd.get('calories') || !fd.get('protein')) return alert("Fill Calories and Protein!"); 
                fetch('/ajax_save_fav', {{method: 'POST', body: fd}}).then(r=>r.text()).then(t=>{{ 
                    let b = document.getElementById('save_lib_btn'); 
                    if(t==="EXISTS"){{
                        b.innerText="ALREADY EXISTS ❌"; b.style.background="#ff453a"; b.style.color="#fff"; 
                        setTimeout(()=>{{b.innerText="💾 TO LIBRARY"; b.style.background="#ff9f0a"; b.style.color="#000";}}, 1000);
                    }}else{{
                        b.innerText="SAVED ✅"; b.style.background="#30d158"; b.style.color="#000"; 
                        setTimeout(()=>window.location.reload(), 500);
                    }} 
                }}); 
            }}
            function quickAddPrompt(el) {{ 
                let n=el.getAttribute('data-name'), q=el.getAttribute('data-qty'), u=el.getAttribute('data-unit'), c=el.getAttribute('data-cal'), p=el.getAttribute('data-prot'), r=el.getAttribute('data-recipe'); 
                let nq=prompt(`How much did you eat?\\n${{n}} (Saved as ${{q}} ${{u}})`, q); 
                if(nq!==null && nq.trim()!==""){{ 
                    nq=parseFloat(nq.replace(',','.')); 
                    if(!isNaN(nq) && nq>0){{ 
                        let m=nq/parseFloat(q||1); 
                        document.getElementById('final_food_name').value=n; 
                        document.getElementById('final_qty').value=nq; 
                        document.getElementById('final_unit').value=u; 
                        document.getElementById('final_cal').value=Math.round(parseFloat(c)*m); 
                        document.getElementById('final_prot').value=Math.round(parseFloat(p)*m); 
                        if(r && r!=='""' && r!=='[]'){{ 
                            let p_r=JSON.parse(r).map(i=>({{...i, qty:i.qty?parseFloat((i.qty*m).toFixed(2)):null, cal:Math.round(i.cal*m), prot:Math.round(i.prot*m)}})); 
                            r=JSON.stringify(p_r); 
                        }} 
                        document.getElementById('final_recipe').value=r; 
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
    html_favs = "".join([f'<div class="log-item fav-search-item" style="cursor:pointer; display:flex;" onclick="window.location.href=\'/edit_fav/{f["id"]}\'" data-name="{f["food_name"].lower()}"><div style="text-align:left; flex:1;"><b>{f["food_name"]}</b> {get_badge(f["recipe"])}<br><small style="color:#8e8e93;">Base: {f["qty"] or 1}{f["unit"] or "qty"} | {f["calories"]} kcal</small></div><div style="display:flex; gap:5px;"><button style="background:#0a84ff; color:#fff; font-weight:bold; font-size:1.5rem; padding:5px 15px; border-radius:12px; border:none;" onclick="event.stopPropagation(); quickAddPrompt(this)" data-name="{f["food_name"].replace("'", "&#39;").replace('"', '&quot;')}" data-qty="{f["qty"] or 1}" data-unit="{f["unit"] or "qty"}" data-cal="{f["calories"]}" data-prot="{f["protein"]}" data-recipe="{(f["recipe"] or "").replace("'", "&#39;").replace('"', '&quot;')}">+</button><button style="background:rgba(255,69,58,0.15); color:#ff453a; font-weight:bold; font-size:1.2rem; padding:5px 15px; border-radius:12px; border:1px solid #ff453a;" onclick="event.stopPropagation(); window.location.href=\'/delete_fav/{f["id"]}\'">✕</button></div></div>' for f in favs])
    
    return f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;"><button onclick="history.back()" style="background:transparent; border:none; color:#0a84ff; font-weight:bold; font-size:1.2rem;">&lt; Back</button><h2 style="color:#fff; margin:0; font-size:1.2rem;">LIBRARY 📚</h2><div style="width:50px;"></div></div>
        <input type="text" id="search_bar" placeholder="Search library..." onkeyup="let v=this.value.toLowerCase(), i=document.getElementsByClassName('fav-search-item'); for(let el of i) el.style.display=el.getAttribute('data-name').includes(v)?'flex':'none';" style="margin-bottom:20px;">
        <div id="library_list">{html_favs or "<p style='color:#444;'>Empty library.</p>"}</div>
        <form id="scaled_form" method="POST" action="/" style="display:none;"><input type="hidden" name="action" value="add_log"><input type="hidden" name="food_name" id="final_food_name"><input type="hidden" name="qty" id="final_qty"><input type="hidden" name="unit" id="final_unit"><input type="hidden" name="calories" id="final_cal"><input type="hidden" name="protein" id="final_prot"><input type="hidden" name="recipe_json" id="final_recipe"></form>
        <script>
            function quickAddPrompt(el) {{ 
                let n=el.getAttribute("data-name"), q=el.getAttribute("data-qty"), u=el.getAttribute("data-unit"), c=el.getAttribute("data-cal"), p=el.getAttribute("data-prot"), r=el.getAttribute("data-recipe"); 
                let nq=prompt(`How much did you eat?\\n${{n}} (Saved as ${{q}} ${{u}})`, q); 
                if(nq!==null && nq.trim()!==""){{ 
                    nq=parseFloat(nq.replace(",",".")); 
                    if(!isNaN(nq) && nq>0){{ 
                        let m=nq/parseFloat(q||1); 
                        document.getElementById("final_food_name").value=n; 
                        document.getElementById("final_qty").value=nq; 
                        document.getElementById("final_unit").value=u; 
                        document.getElementById("final_cal").value=Math.round(parseFloat(c)*m); 
                        document.getElementById("final_prot").value=Math.round(parseFloat(p)*m); 
                        if(r && r!=="\\"\\"" && r!=="[]"){{ 
                            let p_r=JSON.parse(r).map(i=>({{...i, qty:i.qty?parseFloat((i.qty*m).toFixed(2)):null, cal:Math.round(i.cal*m), prot:Math.round(i.prot*m)}})); 
                            r=JSON.stringify(p_r); 
                        }} 
                        document.getElementById("final_recipe").value=r; 
                        document.getElementById("scaled_form").submit(); 
                    }} 
                }} 
            }}
        </script>
    </body></html>
    """

@app.route('/history')
def history():
    conn = get_db_connection()
    s = {r['key']: r['value'] for r in conn.execute("SELECT * FROM settings").fetchall()}
    g_sl = float(str(s.get('sleep_goal', 7.5)).replace(',', '.'))
    
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    try: target_date = datetime.strptime(month_str, '%Y-%m')
    except: target_date = datetime.now()
    y, m = target_date.year, target_date.month
    prev_m, next_m = (target_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m'), (target_date.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m')
    mn = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    ld = {row['date']: {'c': row['c'], 'p': row['p']} for row in conn.execute("SELECT date, SUM(calories) as c, SUM(protein) as p FROM logs GROUP BY date").fetchall()}
    sd = {row['date']: dict(row) for row in conn.execute("SELECT * FROM daily_stats").fetchall()}
    
    cal = f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;"><a href="/history?month={prev_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&lt;</a><h2 style="color:#fff; margin:0; font-size:1.2rem; text-transform:uppercase;">{mn[m-1]} {y}</h2><a href="/history?month={next_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&gt;</a></div><div style="display:grid; grid-template-columns:repeat(7,1fr); gap:3px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;"><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div><div>S</div></div><div style="display:grid; grid-template-columns:repeat(7,1fr); gap:3px;">'
    rot, work = cal, '<div style="display:flex; flex-direction:column; gap:15px;">'
    today_str = datetime.now().strftime("%Y-%m-%d")

    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(y, m):
        wps, wd, has_cur = 0, 0, False
        for d in week:
            d_str, d_num = d.strftime("%Y-%m-%d"), d.day
            is_f = d_str > today_str; has_cur = has_cur or d.month == m
            s_row, l_row = sd.get(d_str, {}), ld.get(d_str, {})
            
            p_g, p_r = s_row.get('planned_g'), s_row.get('planned_r')
            if p_g is None or p_r is None: 
                rt = get_routine_for_date(conn, d_str)
                p_g, p_r = p_g if p_g is not None else rt.get(str(d.weekday()), {}).get("g", ""), p_r if p_r is not None else rt.get(str(d.weekday()), {}).get("r", "")
            
            if d_str <= today_str: 
                wps += bool(p_g) + bool(p_r); wd += bool(s_row.get('gym')) + bool(s_row.get('run'))
            
            f_c = s_row.get('calories') if s_row.get('calories') is not None else l_row.get('c',0)
            f_p = s_row.get('protein') if s_row.get('protein') is not None else l_row.get('p',0)
            
            bc, br = "transparent", "transparent"
            if not is_f and d.month == m:
                pm, sm = f_p >= (s_row.get('goal_p') or int(float(s.get('protein_goal', 160)))), (s_row.get('steps') or 0) >= (s_row.get('goal_s') or int(float(s.get('step_goal', 10000))))
                bc = "#30d158" if pm and sm else ("#ffd60a" if pm else ("#ff9f0a" if sm else "#ff453a")) if f_c>0 or f_p>0 or (s_row.get('steps') or 0)>0 else "#ff453a"
                wm, slm = (s_row.get('water') or 0) >= (s_row.get('goal_w') or float(str(s.get('water_goal', 2.5)).replace(',','.'))), (s_row.get('sleep') or 0) >= g_sl
                br = "#30d158" if wm and slm else ("#ffd60a" if slm else ("#ff9f0a" if wm else "#ff453a")) if (s_row.get('water') or 0)>0 or (s_row.get('sleep') or 0)>0 or (s_row.get('bible') or 0)>0 else "#ff453a"

            dc = "rgba(10,132,255,0.15)" if d_str == today_str else "#2c2c2e"
            bc, br = "#0a84ff" if d_str == today_str else bc, "#0a84ff" if d_str == today_str else br
            op = "1" if d.month == m else "0.3"
            ni = ' <span style="font-size:0.6rem;">📝</span>' if s_row.get('notes') else ''
            
            if is_f:
                cal += f'<div style="background:{dc}; border-radius:10px; padding:5px 0; opacity:{op}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d_num}</span></div>'
                rot += f'<div style="background:{dc}; border-radius:10px; padding:5px 0; opacity:{op}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d_num}</span></div>'
            else:
                st = f'<div style="font-size:0.5rem; color:#8e8e93; margin-top:2px; line-height:1.2;">{f_c}k<br>{f_p}p<br>👣{s_row.get("steps") or 0}</div>' if f_c>0 or (s_row.get('steps') or 0)>0 else ""
                rt_t = f'<div style="font-size:0.5rem; color:#8e8e93; margin-top:2px; line-height:1.2;">💤{s_row.get("sleep") or 0}h<br>💧{s_row.get("water") or 0}L{"<br>📖" if s_row.get("bible") else ""}</div>' if (s_row.get('water') or 0)>0 or (s_row.get('sleep') or 0)>0 or (s_row.get('bible') or 0)>0 else ""
                cal += f'<a href="/edit_day/{d_str}?type=macros" style="background:{dc}; border:2px solid {bc}; border-radius:10px; padding:5px 0; text-decoration:none; color:#fff; opacity:{op}; display:flex; flex-direction:column; align-items:center; min-height:55px;">{d_num}{ni}{st}</a>'
                rot += f'<a href="/edit_day/{d_str}?type=routines" style="background:{dc}; border:2px solid {br}; border-radius:10px; padding:5px 0; text-decoration:none; color:#fff; opacity:{op}; display:flex; flex-direction:column; align-items:center; min-height:55px;">{d_num}{rt_t}</a>'

        if has_cur:
            bwk = "#30d158" if week[0].strftime("%Y-%m-%d") <= today_str and wps > 0 and wd/wps >= 0.8 else ("#ffd60a" if wps > 0 and wd/wps >= 0.5 else "#ff453a" if wps>0 else ("#30d158" if wd>0 else "#2c2c2e"))
            work += f'<div style="border:2px solid {bwk}; border-radius:15px; padding:10px; background:#1c1c1e; margin-bottom:10px;"><div style="display:flex; justify-content:center; margin-bottom:10px; font-size:0.85rem; font-weight:bold;">Volume: {wd} / {wps}</div><div style="display:grid; grid-template-columns:repeat(7,1fr); gap:3px;">'
            for d in week:
                d_str, d_num = d.strftime("%Y-%m-%d"), d.day
                is_f = d_str > today_str
                sr = sd.get(d_str, {}); gy, ru = sr.get('gym') or 0, sr.get('run') or 0
                pg, pr = sr.get('planned_g'), sr.get('planned_r')
                if pg is None or pr is None: 
                    rt = get_routine_for_date(conn, d_str)
                    pg, pr = pg if pg is not None else rt.get(str(d.weekday()), {}).get("g", ""), pr if pr is not None else rt.get(str(d.weekday()), {}).get("r", "")
                
                dc = "rgba(10,132,255,0.15)" if d_str == today_str else ("rgba(10,132,255,0.2)" if gy or ru else "#2c2c2e")
                bcw = "1px solid #0a84ff" if d_str == today_str or gy or ru else "1px solid #3a3a3c"
                ic = ""
                if gy: ic += f'<div style="color:#30d158; font-size:0.55rem; font-weight:bold;">🏋️‍♂️ {pg or "Gym"}</div>'
                elif pg: ic += f'<div style="color:{"#ff453a" if not is_f else "#8e8e93"}; font-size:0.55rem; font-weight:bold;">🏋️‍♂️ {pg}</div>'
                if ru: ic += f'<div style="color:#30d158; font-size:0.55rem; font-weight:bold;">🏃 {pr or "Run"}</div>'
                elif pr: ic += f'<div style="color:{"#ff453a" if not is_f else "#8e8e93"}; font-size:0.55rem; font-weight:bold;">🏃 {pr}</div>'
                if not ic: ic = '<div style="color:#444; font-size:0.6rem;">Rest</div>'
                
                if is_f: work += f'<div style="background:{dc}; border:{bcw}; border-radius:10px; padding:5px 0; opacity:{"1" if d.month==m else "0.3"}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d_num}</span>{ic}</div>'
                else: work += f'<a href="/edit_day/{d_str}?type=workout" style="background:{dc}; border:{bcw}; border-radius:10px; padding:5px 0; text-decoration:none; color:#fff; opacity:{"1" if d.month==m else "0.3"}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem;">{d_num}</span>{ic}</a>'
            work += "</div></div>"
            
    conn.close()
    return f'<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><h2 style="color:#8e8e93;">MACROS & DIARY</h2><div class="card" style="padding:15px;">{cal}</div></div><h2 style="color:#8e8e93;">WELL BEING</h2><div class="card" style="padding:15px;">{rot}</div></div><h2 style="color:#8e8e93;">WEEKLY WORKOUTS</h2><div class="card" style="padding:15px; border:none; background:transparent;">{work}</div><div class="nav-bar"><a href="/" class="nav-item"><span style="font-size:1.2rem;">🏠</span>TODAY</a><a href="/history" class="nav-item active"><span style="font-size:1.2rem;">📅</span>ROUTINES</a><a href="/money" class="nav-item"><span style="font-size:1.2rem;">💸</span>MONEY</a><a href="/manage_favs" class="nav-item"><span style="font-size:1.2rem;">⚙️</span>SETTINGS</a></div>{get_swipe_js(f"/history?month={prev_m}", f"/history?month={next_m}")}</body></html>'

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

    prev_m, next_m = (target_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m'), (target_date.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m')
    mn = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    g_m = float((conn.execute("SELECT value FROM settings WHERE key=?", (f'money_goal_{y}-{m:02d}',)).fetchone() or conn.execute("SELECT value FROM settings WHERE key='money_goal'").fetchone() or {'value':'300.0'})['value'].replace(',', '.'))
    sd = {row['date']: dict(row) for row in conn.execute("SELECT * FROM daily_stats WHERE date LIKE ?", (f"{y}-{m:02d}-%",)).fetchall()}; conn.close()
    
    days_in_month = calendar.monthrange(y, m)[1]
    dl = {}; cum = 0; today_str = datetime.now().strftime("%Y-%m-%d"); cda = 0
    for i in range(1, days_in_month + 1):
        ds = f"{y}-{m:02d}-{i:02d}"; rem = days_in_month - i + 1; clim = (g_m - cum) / rem if rem > 0 else 0
        dl[ds] = clim; 
        if ds == today_str: cda = clim
        cum += (sd.get(ds, {}).get('money') or 0)
        
    tsm, ts = cum, sd.get(today_str, {}).get('money') or 0; lft = cda - ts
    cal = f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;"><a href="/money?month={prev_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&lt;</a><h2 style="color:#fff; margin:0; font-size:1.2rem; text-transform:uppercase;">{mn[m-1]} {y}</h2><a href="/money?month={next_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&gt;</a></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;"><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div><div>S</div></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px;">'

    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(y, m):
        for d in week:
            ds = d.strftime("%Y-%m-%d"); is_f = ds > today_str; is_c = d.month == m; sp = sd.get(ds, {}).get('money') or 0; lim = dl.get(ds, 0)
            bc = "transparent"
            if not is_f and is_c: bc = "#30d158" if sp <= lim or sp == 0 else "#ff453a"
            cal += f'<div style="background:{"rgba(10,132,255,0.15)" if ds==today_str else "#2c2c2e"}; border: 2px solid transparent; border-radius:10px; padding:8px 0; opacity:{"1" if is_c else "0.3"}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem; color:#444;">{d.day}</span></div>' if is_f else f'<a href="/edit_day/{ds}?type=money" style="background:{"rgba(10,132,255,0.15)" if ds==today_str else "#2c2c2e"}; border: 2px solid {bc}; border-radius:10px; padding:8px 0; text-decoration:none; color:#fff; opacity:{"1" if is_c else "0.3"}; display:flex; flex-direction:column; align-items:center; min-height:55px;"><span style="font-weight:bold; font-size:0.9rem;">{d.day}</span>{f"<div style=font-size:0.6rem;color:#8e8e93;margin-top:2px;font-weight:bold;>{sp:.1f}€</div>" if sp>0 else ""}</a>'
    
    cda = cda if cda > 0 else g_m / days_in_month
    return f'<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><div class="card" style="background:linear-gradient(145deg, #1c1c1e, #000); border:none;"><p style="color:#8e8e93; font-size:0.8rem; font-weight:bold;">TOTAL SPENT THIS MONTH</p><h1 style="font-size:3.5rem; margin:5px 0; color:{"#ff453a" if tsm>g_m else "#30d158"};">{tsm:.2f}€</h1><form method="POST" style="display:flex; justify-content:center; gap:5px; margin-bottom:15px;"><span style="color:#8e8e93; font-size:0.85rem;">Budget:</span><input type="text" inputmode="decimal" name="new_budget" value="{str(g_m).replace(".", ",")}" style="width:70px; padding:5px; text-align:center; margin:0;"><button type="submit" style="background:transparent; border:none; color:#0a84ff; font-weight:bold;">💾</button></form><div style="background:#2c2c2e; padding:15px; border-radius:15px; display:flex; justify-content:space-around;"><div><p style="font-size:0.75rem; color:#8e8e93;">DAILY AVG</p><p style="font-size:1.1rem; color:#0a84ff; font-weight:bold;">{cda:.2f}€</p></div><div style="border-left:1px solid #3a3a3c; padding-left:15px;"><p style="font-size:0.75rem; color:#8e8e93;">LEFT FOR TODAY</p><p style="font-size:1.1rem; color:{"#30d158" if lft>=0 else "#ff453a"}; font-weight:bold;">{lft:.2f}€</p></div></div></div><div class="card" style="padding:15px;">{cal}</div></div><div class="nav-bar"><a href="/" class="nav-item"><span style="font-size:1.2rem;">🏠</span>TODAY</a><a href="/history" class="nav-item"><span style="font-size:1.2rem;">📅</span>ROUTINES</a><a href="/money" class="nav-item active"><span style="font-size:1.2rem;">💸</span>MONEY</a><a href="/manage_favs" class="nav-item"><span style="font-size:1.2rem;">⚙️</span>SETTINGS</a></div>{get_swipe_js(f"/money?month={prev_m}", f"/money?month={next_m}")}</body></html>'

@app.route('/rank')
def rank():
    conn = get_db_connection()
    s = {r['key']: r['value'] for r in conn.execute("SELECT * FROM settings").fetchall()}
    g_sl = float(str(s.get('sleep_goal', 7.5)).replace(',', '.'))
    
    month_str = request.args.get('month', datetime.now().strftime('%Y-%m'))
    try: target_date = datetime.strptime(month_str, '%Y-%m')
    except: target_date = datetime.now()
    y, m = target_date.year, target_date.month
    prev_m, next_m = (target_date.replace(day=1) - timedelta(days=1)).strftime('%Y-%m'), (target_date.replace(day=28) + timedelta(days=4)).replace(day=1).strftime('%Y-%m')
    mn = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    ld = {row['date']: {'p': row['p']} for row in conn.execute("SELECT date, SUM(protein) as p FROM logs GROUP BY date").fetchall()}
    sd = {row['date']: dict(row) for row in conn.execute("SELECT * FROM daily_stats").fetchall()}
    g_m = float(str(s.get(f'money_goal_{y}-{m:02d}', s.get('money_goal', 300))).replace(',', '.'))
    
    days_in_month = calendar.monthrange(y, m)[1]; dl = {}; cum = 0; today_str = datetime.now().strftime("%Y-%m-%d")
    for i in range(1, days_in_month + 1):
        ds = f"{y}-{m:02d}-{i:02d}"; rem = days_in_month - i + 1; clim = (g_m - cum) / rem if rem > 0 else 0
        dl[ds] = clim; cum += (sd.get(ds, {}) or {}).get('money', 0) or 0

    cal = f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;"><a href="/rank?month={prev_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&lt;</a><h2 style="color:#fff; margin:0; font-size:1.2rem; text-transform:uppercase;">{mn[m-1]} {y}</h2><a href="/rank?month={next_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&gt;</a></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;"><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div><div>S</div></div><div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:6px;">'

    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(y, m):
        for d in week:
            ds = d.strftime("%Y-%m-%d"); is_f = ds > today_str; is_c = d.month == m
            sr = sd.get(ds, {}); f_p = sr.get('protein') if sr.get('protein') is not None else ld.get(ds, {}).get('p', 0)
            score = 0; bd = []
            
            if not is_f:
                if f_p >= (sr.get('goal_p') or int(float(s.get('protein_goal', 160)))): score+=3; bd.append("✅ Prot (+3)")
                else: bd.append("❌ Prot (0)")
                if (sr.get('sleep') or 0) >= g_sl: score+=2; bd.append("✅ Sleep (+2)")
                else: bd.append("❌ Sleep (0)")
                if (sr.get('steps') or 0) >= (sr.get('goal_s') or int(float(s.get('step_goal', 10000)))): score+=2; bd.append("✅ Steps (+2)")
                else: bd.append("❌ Steps (0)")
                if (sr.get('water') or 0) >= (sr.get('goal_w') or float(str(s.get('water_goal', 2.5)).replace(',', '.'))): score+=2; bd.append("✅ Water (+2)")
                else: bd.append("❌ Water (0)")
                if (sr.get('money') or 0) <= dl.get(ds, 0): score+=1; bd.append("✅ Finance (+1)")
                else: bd.append("❌ Finance (0)")
                if (sr.get('gym') or 0)>0 or (sr.get('run') or 0)>0: score+=2; bd.append("✅ Workout (+2)")
                else: bd.append("❌ Workout (0)")
                if (sr.get('bible') or 0)>0: score+=1; bd.append("✅ Bible (+1)")
                else: bd.append("❌ Bible (0)")

            bc = "transparent"; tc = "#fff"; sd_disp = "-"
            if not is_f and is_c:
                if f_p>0 or (sr.get('sleep') or 0)>0 or (sr.get('money') or 0)>0 or (sr.get('water') or 0)>0 or (sr.get('steps') or 0)>0 or (sr.get('gym') or 0)>0 or (sr.get('run') or 0)>0 or (sr.get('bible') or 0)>0:
                    if score == 0: bc, tc = "rgba(255,69,58,0.4)", "#fff"
                    elif score <= 4: bc, tc = "rgba(255,159,10,0.5)", "#fff"
                    elif score <= 8: bc, tc = "rgba(255,214,10,0.5)", "#000"
                    elif score <= 12: bc, tc = "rgba(48,209,88,0.6)", "#000"
                    else: bc, tc = "rgba(10,132,255,0.8)", "#fff"
                    sd_disp = f"{score}"
                
            oncl = f'onclick="openRankModal(\'{d.day} {mn[m-1][:3]}\', \'{score}\', \'{"<br>".join(bd)}\', \'{(sr.get("notes") or "No diary entry for this day.").replace("'", "&#39;").replace('"', "&quot;").replace(chr(10), "<br>")}\')"' if not is_f else ""
            cal += f'<div {oncl} style="{"cursor:pointer;" if not is_f else ""} background:{bc}; border:{"2px solid #0a84ff" if ds==today_str else "2px solid transparent"}; border-radius:10px; padding:8px 0; color:{tc}; opacity:{"1" if is_c else "0.2"}; display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:55px; box-sizing:border-box;"><span style="font-size:0.6rem; margin-bottom:2px;">{d.day}{" <span style=font-size:0.6rem;>📝</span>" if sr.get("notes") else ""}</span><span style="font-weight:900; font-size:1.2rem;">{sd_disp}</span></div>'
    conn.close()
    
    return f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <div class="card" style="background:linear-gradient(145deg, #1c1c1e, #000); border:1px solid #0a84ff; padding-bottom:10px;">
            <h2 style="color:#0a84ff; margin-top:0;">GOD RANK 🏆</h2>
            <p style="font-size:0.8rem; color:#8e8e93; margin-bottom:0;">Daily Score (0 to 13):<br>Prot (3) | Sleep (2) | Steps (2)<br>Water (2) | Workout (2) | € Avg (1) | Bible (1)</p>
        </div>
        <div class="card" style="padding:15px;">{cal}</div></div>
        <a href="/manage_favs" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Back to Settings</a>
        {get_swipe_js(f"/rank?month={prev_m}", f"/rank?month={next_m}")}
        <div id="rank_modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:999; align-items:center; justify-content:center; padding:20px;">
            <div class="card" style="background:#1c1c1e; width:100%; max-width:400px; text-align:left; border:1px solid #0a84ff; max-height:80vh; overflow-y:auto;">
                <div style="display:flex; justify-content:space-between; border-bottom:1px solid #3a3a3c; padding-bottom:10px; margin-bottom:15px;">
                    <h2 id="modal_date" style="margin:0; color:#0a84ff;">Date</h2>
                    <h2 style="margin:0; color:#fff;"><span id="modal_score">0</span><span style="font-size:1rem; color:#8e8e93;">/13</span></h2>
                </div>
                <h4 style="color:#8e8e93; margin-top:0; margin-bottom:10px;">🏆 Score Breakdown</h4>
                <div id="modal_breakdown" style="font-size:0.9rem; line-height:1.6; margin-bottom:20px; background:#000; padding:15px; border-radius:12px; color:#fff;"></div>
                <h4 style="color:#8e8e93; margin-top:0; margin-bottom:10px;">📝 Diary</h4>
                <div id="modal_diary" style="font-size:0.9rem; line-height:1.5; color:#fff; background:#2c2c2e; padding:15px; border-radius:12px; font-style:italic;"></div>
                <button type="button" onclick="document.getElementById('rank_modal').style.display='none'" class="btn-main" style="margin-top:20px;">CLOSE</button>
            </div>
        </div>
        <script>
            function openRankModal(d, s, b, di) {{ document.getElementById("modal_date").innerText=d; document.getElementById("modal_score").innerText=s; document.getElementById("modal_breakdown").innerHTML=b; document.getElementById("modal_diary").innerHTML=di; document.getElementById("rank_modal").style.display="flex"; }}
        </script>
    </body></html>
    """

@app.route('/edit_day/<date>', methods=['GET', 'POST'])
def edit_day(date):
    edit_type = request.args.get('type', 'macros'); conn = get_db_connection()
    if request.method == 'POST':
        if not conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone(): ensure_daily_goals(date)
        if edit_type == 'macros':
            c, p, s, n = parse_val(request.form.get('calories')), parse_val(request.form.get('protein')), parse_val(request.form.get('steps')), request.form.get('notes')
            if n is not None: conn.execute('UPDATE daily_stats SET notes=? WHERE date=?', (n.strip(), date))
            for f, v in [('calories', c), ('protein', p), ('steps', s)]:
                if v is not None: conn.execute(f'UPDATE daily_stats SET {f}=? WHERE date=?', (None if v=="CLEAR" else v, date))
        elif edit_type == 'routines':
            w, sl, b = parse_val(request.form.get('water'), True), parse_val(request.form.get('sleep'), True), 1 if request.form.get('bible') == 'on' else 0
            if w is not None: conn.execute('UPDATE daily_stats SET water=? WHERE date=?', (None if w=="CLEAR" else w, date))
            if sl is not None: conn.execute('UPDATE daily_stats SET sleep=? WHERE date=?', (None if sl=="CLEAR" else sl, date))
            if 'bible' in request.form or 'water' in request.form: conn.execute('UPDATE daily_stats SET bible=? WHERE date=?', (b, date))
        elif edit_type == 'money':
            m = parse_val(request.form.get('money'), True)
            if m is not None: conn.execute('UPDATE daily_stats SET money=? WHERE date=?', (None if m=="CLEAR" else m, date))
        elif edit_type == 'workout':
            g, ru = 1 if request.form.get('gym') == 'on' else 0, 1 if request.form.get('run') == 'on' else 0
            if request.form.get('override_routine') == 'on': conn.execute('UPDATE daily_stats SET gym=?, run=?, planned_g=?, planned_r=?, overridden=1 WHERE date=?', (g, ru, request.form.get('planned_g', ""), request.form.get('planned_r', ""), date))
            else: conn.execute('UPDATE daily_stats SET gym=?, run=?, overridden=0 WHERE date=?', (g, ru, date))
        conn.commit(); conn.close()
        return redirect(url_for('money', month=date[:7])) if edit_type == 'money' else redirect(url_for('history', month=date[:7]))
        
    logs = conn.execute('SELECT * FROM logs WHERE date = ? ORDER BY id DESC', (date,)).fetchall()
    stats = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone()
    rt = get_routine_for_date(conn, date); conn.close()
    
    logs_c, logs_p = sum(l['calories'] for l in logs), sum(l['protein'] for l in logs)
    s_c = stats['calories'] if stats and stats['calories'] is not None else ""
    s_p = stats['protein'] if stats and stats['protein'] is not None else ""
    s_s = stats['steps'] if stats and stats['steps'] is not None else ""
    s_w = stats['water'] if stats and stats['water'] is not None else ""
    s_m = stats['money'] if stats and stats['money'] is not None else ""
    s_sl = stats['sleep'] if stats and stats['sleep'] is not None else ""
    s_n = stats['notes'] if stats and stats['notes'] is not None else ""
    
    overridden = stats['overridden'] if stats and 'overridden' in stats.keys() else 0
    p_g = stats['planned_g'] if overridden and stats['planned_g'] is not None else rt.get(str(datetime.strptime(date, "%Y-%m-%d").weekday()), {}).get("g", "")
    p_r = stats['planned_r'] if overridden and stats['planned_r'] is not None else rt.get(str(datetime.strptime(date, "%Y-%m-%d").weekday()), {}).get("r", "")
    
    html_logs = "".join([f'<div class="log-item" style="cursor:pointer;" onclick="window.location.href=\'/edit_log/{l["id"]}\'"><div style="text-align:left; flex:1;"><b>{l["food_name"]}</b> <span style="color:#8e8e93; font-size:0.7rem;">({l["qty"] or 1}{l["unit"] or "qty"})</span> {get_badge(l["recipe"])}<br><small style="color:#8e8e93;">{l["timestamp"]} • {l["calories"]} kcal | {l["protein"]}g Prot</small></div><button onclick="event.stopPropagation(); window.location.href=\'/delete/{l["id"]}\'" style="background:rgba(255,69,58,0.15); border:1px solid #ff453a; color:#ff453a; font-weight:bold; font-size:1.1rem; padding:10px 15px; border-radius:12px; margin-left:10px;">✕</button></div>' for l in logs])
    
    if edit_type == 'macros':
        fc = f'<div style="margin-bottom:10px;"><span class="input-label">Calories (Kcal)</span><input type="number" name="calories" value="{s_c}" placeholder="Auto: {logs_c} kcal" style="margin:0;"></div><div style="margin-bottom:10px;"><span class="input-label">Protein (g)</span><input type="number" name="protein" value="{s_p}" placeholder="Auto: {logs_p} g" style="margin:0;"></div><div style="margin-bottom:10px;"><span class="input-label">Steps 👣</span><input type="number" name="steps" value="{s_s}" placeholder="E.g., 10500" style="margin:0;"></div><div><span class="input-label">Daily Notes / Diary 📝</span><textarea name="notes" rows="4" placeholder="How was your day?" style="margin:0; resize:none;">{s_n}</textarea></div>'
        eh = f'<h3 class="day-header">DAY\'S LOG</h3>{html_logs or "<p style=\'color:#444; font-size:0.9rem;\'>No meals logged.</p>"}'
    elif edit_type == 'workout':
        g_sel = "".join([f'<option value="{o}" {"selected" if o==p_g else ""}>{o if o else "Rest"}</option>' for o in ["", "Push", "Pull", "Legs", "Upper", "Lower"]])
        r_sel = "".join([f'<option value="{o}" {"selected" if o==p_r else ""}>{o if o else "Rest"}</option>' for o in ["", "Tempo", "Easy", "Hard"]])
        fc = f'<div class="checkbox-wrapper {"checked" if stats and stats.get("gym") else ""}" id="gym_lbl" onclick="updateDailyStat(\'gym_lbl\', \'gym_chk\')"><input type="checkbox" id="gym_chk" name="gym" {"checked" if stats and stats.get("gym") else ""} style="display:none;"><span style="font-size:1.2rem;">🏋️‍♂️ Went to Gym</span></div><div class="checkbox-wrapper {"checked" if stats and stats.get("run") else ""}" id="run_lbl" onclick="updateDailyStat(\'run_lbl\', \'run_chk\')"><input type="checkbox" id="run_chk" name="run" {"checked" if stats and stats.get("run") else ""} style="display:none;"><span style="font-size:1.2rem;">🏃 Went Running</span></div><div class="checkbox-wrapper {"checked" if overridden else ""}" id="override_lbl" onclick="let cb=document.getElementById(\'override_chk\'); cb.checked=!cb.checked; this.classList.toggle(\'checked\', cb.checked); document.getElementById(\'override_box\').style.display = cb.checked ? \'block\' : \'none\';"><input type="checkbox" name="override_routine" id="override_chk" style="display:none;" {"checked" if overridden else ""}><span style="font-size:1.1rem; pointer-events:none;">Override Planned Routine?</span></div><div id="override_box" style="display:{"block" if overridden else "none"}; background:#1c1c1e; padding:15px; border-radius:12px; margin-top:5px; border:1px solid #ff9f0a;"><p style="color:#8e8e93; font-size:0.8rem; margin-top:0;">Change the plan just for this day.</p><div style="display:flex; gap:10px;"><select name="planned_g" style="flex:1; padding:10px; font-weight:bold; margin:0;">{g_sel}</select><select name="planned_r" style="flex:1; padding:10px; font-weight:bold; margin:0;">{r_sel}</select></div></div>'
        eh = ""
    elif edit_type == 'routines':
        fc = f'<div style="margin-bottom:10px;"><span class="input-label">Sleep 💤 (h)</span><input type="text" inputmode="decimal" name="sleep" value="{str(s_sl).replace(".", ",") if s_sl else ""}" placeholder="E.g., 7.5" style="margin:0;"></div><div style="margin-bottom:15px;"><span class="input-label">Water 💧 (Liters)</span><input type="text" inputmode="decimal" name="water" value="{str(s_w).replace(".", ",") if s_w else ""}" placeholder="E.g., 2.5" style="margin:0;"></div><div class="checkbox-wrapper {"checked" if stats and stats.get("bible") else ""}" id="bible_lbl" onclick="updateDailyStat(\'bible_lbl\', \'bible_chk\')"><input type="checkbox" id="bible_chk" name="bible" {"checked" if stats and stats.get("bible") else ""} style="display:none;"><span style="font-size:1.2rem;">📖 Read Bible</span></div>'
        eh = ""
    else:
        fc = f'<div><span class="input-label">Money Spent 💸 (€)</span><input type="text" inputmode="decimal" name="money" value="{str(s_m).replace(".", ",") if s_m else ""}" placeholder="E.g., 15.50" style="margin:0;"></div>'
        eh = ""
        
    return f'<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><h2 style="color:#8e8e93; text-transform:uppercase;">{datetime.strptime(date, "%Y-%m-%d").strftime("%d %b %Y")}</h2><div class="card"><h3 style="margin-top:0; color:#8e8e93;">EDIT {edit_type.upper()}</h3><form method="POST"><div style="display:flex; flex-direction:column; align-items:stretch;">{fc}</div><button type="submit" class="btn-main" style="margin-top:20px;">SAVE DAY</button></form><a href="javascript:history.back()" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Go Back</a></div>{eh}</body></html>'

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

    ex_rt = conn.execute("SELECT start_date, end_date FROM routines").fetchall()
    overlap_data = json.dumps([{"s": r["start_date"], "e": r["end_date"]} for r in ex_rt])

    latest_rt = conn.execute("SELECT schedule FROM routines ORDER BY id DESC LIMIT 1").fetchone()
    routines = json.loads(latest_rt['schedule']) if latest_rt else {str(i): {"g": "", "r": ""} for i in range(7)}
    conn.close()

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    rows_html = ""
    for i, day in enumerate(days):
        g_sel = "".join([f'<option value="{o}" {"selected" if o==routines.get(str(i), {}).get("g", "") else ""}>{o if o else "Rest"}</option>' for o in ["", "Push", "Pull", "Legs", "Upper", "Lower"]])
        r_sel = "".join([f'<option value="{o}" {"selected" if o==routines.get(str(i), {}).get("r", "") else ""}>{o if o else "Rest"}</option>' for o in ["", "Tempo", "Easy", "Hard"]])
        rows_html += f'<div style="background:#2c2c2e; padding:15px; border-radius:12px; margin-bottom:10px; text-align:left; border: 2px solid #3a3a3c;"><div style="color:#8e8e93; font-weight:bold; margin-bottom:8px; text-transform:uppercase; font-size:0.85rem;">{day}</div><div style="display:flex; gap:10px;"><div style="flex:1;"><span class="input-label">🏋️‍♂️ Gym</span><select name="g_{i}" style="margin:0; padding:12px; font-weight:bold; color:#0a84ff; background:#1c1c1e; border:1px solid #3a3a3c; border-radius:8px; text-align:center;">{g_sel}</select></div><div style="flex:1;"><span class="input-label">🏃 Run</span><select name="r_{i}" style="margin:0; padding:12px; font-weight:bold; color:#ff9f0a; background:#1c1c1e; border:1px solid #3a3a3c; border-radius:8px; text-align:center;">{r_sel}</select></div></div></div>'

    return f'<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><h2 style="color:#8e8e93;">NEW WORKOUT ROUTINE 🗓️</h2><form method="POST" onsubmit="return checkOverlap(event)"><div class="card" style="padding:15px;"><div style="display:flex; gap:10px; margin-bottom:15px;"><div style="flex:1;"><span class="input-label">Start Date</span><input type="date" id="start_date" name="start_date" value="{datetime.now().strftime("%Y-%m-%d")}" style="margin:0; padding:10px;"></div><div style="flex:1;"><span class="input-label">End Date</span><input type="date" id="end_date" name="end_date" value="2099-12-31" style="margin:0; padding:10px;"></div></div>{rows_html}<button type="submit" class="btn-main" style="margin-top:10px; background:#30d158; color:#000;">SAVE ROUTINE</button></div></form><a href="/manage_favs" style="display:block; margin-top:10px; color:#8e8e93; text-decoration:none;">Cancel</a><script>const existing={overlap_data}; function checkOverlap(e){{let s=document.getElementById("start_date").value, end=document.getElementById("end_date").value; if(!s)s="2000-01-01"; if(!end)end="2099-12-31"; if(existing.some(r=>s<=r.e && end>=r.s)) {{ if(!confirm("⚠️ AVISO: Já tens uma rotina a passar por estes dias. Queres mesmo sobrepor as datas e criar esta nova?")) {{ e.preventDefault(); return false; }} }} return true;}}</script></body></html>'

@app.route('/manage_favs', methods=['GET', 'POST'])
def manage_favs():
    conn = get_db_connection()
    if request.method == 'POST':
        updates = [('cal_mode', request.form.get('cal_mode')), ('daily_goal', request.form.get('new_goal')), 
                   ('cal_gym', request.form.get('cal_gym')), ('cal_run', request.form.get('cal_run')),
                   ('cal_both', request.form.get('cal_both')), ('cal_rest', request.form.get('cal_rest')),
                   ('protein_goal', request.form.get('new_p_goal')), ('prot_gym', request.form.get('prot_gym')), 
                   ('prot_run', request.form.get('prot_run')), ('prot_both', request.form.get('prot_both')), 
                   ('prot_rest', request.form.get('prot_rest')), ('step_goal', request.form.get('new_s_goal')), 
                   ('water_goal', request.form.get('new_w_goal')), ('sleep_goal', request.form.get('sleep_goal'))]
        for k, v in updates:
            if v is not None and v != "": conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v.replace(',', '.')))
        conn.execute('UPDATE daily_stats SET goal_c=NULL, goal_p=NULL, goal_s=NULL, goal_w=NULL WHERE date >= ?', (datetime.now().strftime("%Y-%m-%d"),))
        conn.commit()
        
    g = {row['key']: row['value'] for row in conn.execute("SELECT * FROM settings").fetchall()}
    conn.close()
    cm = g.get('macro_mode', 'static')
        
    return f"""<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><a href="/rank" class="btn-main" style="display:block; text-decoration:none; background:linear-gradient(90deg, #0a84ff, #5e5ce6); color:#fff; font-size:1.2rem; margin-bottom:20px; padding:20px;">SEE GOD RANK 🏆</a><a href="/routine" class="btn-main" style="display:block; text-decoration:none; background:#ff9f0a; color:#000; margin-bottom:15px;">🗓️ CREATE WORKOUT ROUTINE</a><a href="/library" class="btn-main" style="display:block; text-decoration:none; background:#2c2c2e; color:#fff; border: 1px solid #3a3a3c; margin-bottom:20px;">📚 OPEN LIBRARY</a><div class="card"><h3 style="margin-top:0; color:#8e8e93;">MACRO GOALS 🎯</h3><form method="POST"><div style="margin-bottom:15px;"><span class="input-label">Mode</span><select name="macro_mode" onchange="document.getElementById('static_box').style.display=this.value==='static'?'block':'none'; document.getElementById('dynamic_box').style.display=this.value==='dynamic'?'block':'none';" style="margin:0;"><option value="static" {"selected" if cm=='static' else ""}>Static (Same Every Day)</option><option value="dynamic" {"selected" if cm=='dynamic' else ""}>Dynamic (Varies by Routine)</option></select></div><div id="static_box" style="display:{'block' if cm=='static' else 'none'}; margin-bottom:15px;"><div style="display:flex; gap:10px;"><div style="flex:1;"><span class="input-label">Daily Kcal</span><input type="number" name="new_goal" value="{g.get('daily_goal', 2100)}" style="margin:0;"></div><div style="flex:1;"><span class="input-label">Daily Prot (g)</span><input type="number" name="new_p_goal" value="{g.get('protein_goal', 160)}" style="margin:0;"></div></div></div><div id="dynamic_box" style="display:{'block' if cm=='dynamic' else 'none'}; margin-bottom:15px;"><div style="display:flex; gap:10px; margin-bottom:10px;"><div style="flex:1;"><span class="input-label">Gym Kcal</span><input type="number" name="cal_gym" value="{g.get('cal_gym', 2500)}" style="margin:0;"></div><div style="flex:1;"><span class="input-label">Gym Prot</span><input type="number" name="prot_gym" value="{g.get('prot_gym', 160)}" style="margin:0;"></div></div><div style="display:flex; gap:10px; margin-bottom:10px;"><div style="flex:1;"><span class="input-label">Run Kcal</span><input type="number" name="cal_run" value="{g.get('cal_run', 2300)}" style="margin:0;"></div><div style="flex:1;"><span class="input-label">Run Prot</span><input type="number" name="prot_run" value="{g.get('prot_run', 150)}" style="margin:0;"></div></div><div style="display:flex; gap:10px; margin-bottom:10px;"><div style="flex:1;"><span class="input-label">Both Kcal</span><input type="number" name="cal_both" value="{g.get('cal_both', 2800)}" style="margin:0;"></div><div style="flex:1;"><span class="input-label">Both Prot</span><input type="number" name="prot_both" value="{g.get('prot_both', 180)}" style="margin:0;"></div></div><div style="display:flex; gap:10px;"><div style="flex:1;"><span class="input-label">Rest Kcal</span><input type="number" name="cal_rest" value="{g.get('cal_rest', 2000)}" style="margin:0;"></div><div style="flex:1;"><span class="input-label">Rest Prot</span><input type="number" name="prot_rest" value="{g.get('prot_rest', 140)}" style="margin:0;"></div></div></div><h3 style="margin-top:20px; color:#8e8e93; border-top:1px solid #2c2c2e; padding-top:15px;">OTHER GOALS</h3><div style="display:flex; gap:5px;"><div><span class="input-label">Steps</span><input type="number" name="new_s_goal" value="{g.get('step_goal', 10000)}" style="margin:0; padding:10px;"></div><div><span class="input-label">Water (L)</span><input type="text" inputmode="decimal" name="new_w_goal" value="{str(g.get('water_goal', 2.5)).replace('.', ',')}" style="margin:0; padding:10px;"></div><div><span class="input-label">Sleep (h)</span><input type="text" inputmode="decimal" name="sleep_goal" value="{str(g.get('sleep_goal', 7.5)).replace('.', ',')}" style="margin:0; padding:10px;"></div></div><button type="submit" class="btn-main" style="margin-top:15px;">SAVE GOALS</button></form></div><div class="card"><h3 style="margin-top:0; color:#8e8e93;">BACKUP 💾</h3><a href="/export_db" class="btn-main" style="display:block; text-decoration:none; background:#5e5ce6; margin-bottom:15px;">📥 DOWNLOAD BACKUP</a><form method="POST" action="/import_db" enctype="multipart/form-data" style="border-top: 1px solid #2c2c2e; padding-top: 15px;"><input type="file" name="db_file" accept=".db" required style="width:100%; margin-bottom:10px; background:#000;"><button type="submit" class="btn-red" style="margin:0; width:100%; border:1px solid #ff9f0a; color:#ff9f0a;">📤 RESTORE BACKUP</button></form></div><div class="nav-bar"><a href="/" class="nav-item"><span style="font-size:1.2rem;">🏠</span>TODAY</a><a href="/history" class="nav-item"><span style="font-size:1.2rem;">📅</span>ROUTINES</a><a href="/money" class="nav-item"><span style="font-size:1.2rem;">💸</span>MONEY</a><a href="/manage_favs" class="nav-item active"><span style="font-size:1.2rem;">⚙️</span>SETTINGS</a></div></body></html>"""

@app.route('/edit_fav/<int:fav_id>', methods=['GET', 'POST'])
def edit_fav(fav_id):
    conn = get_db_connection()
    if request.method == 'POST':
        conn.execute('UPDATE favorites SET food_name=?, qty=?, unit=?, calories=?, protein=?, recipe=? WHERE id=?', 
                     (request.form.get('food_name'), float(request.form.get('qty') or 1), request.form.get('unit') or 'qty', int(float(request.form.get('calories') or 0)), int(float(request.form.get('protein') or 0)), request.form.get('recipe_json', ''), fav_id))
        conn.commit(); conn.close(); return redirect(url_for('library'))
        
    fav = conn.execute('SELECT * FROM favorites WHERE id=?', (fav_id,)).fetchone(); conn.close()
    if not fav: return redirect(url_for('library'))
    
    safe_fname = (fav["food_name"] or "Item").replace('"', '&quot;')
    is_meal = bool(fav['recipe'] and fav['recipe'] not in ('', '""', '[]'))
    recipe_data = fav['recipe'] if is_meal else "[]"
    
    if is_meal: 
        return f"""<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><h2 style="color:#8e8e93;">EDIT MEAL</h2><div class="card"><form method="POST"><span class="input-label">Name</span><input type="text" name="food_name" value="{safe_fname}" required style="font-weight:bold; font-size:1.2rem; text-align:center; margin:0;"><div style="background:#000; padding:15px; border-radius:15px; margin:15px 0;"><h1 style="margin:0; font-size:2rem;"><span id="total_cal_display">0</span> <span style="font-size:1rem; color:#8e8e93;">kcal</span></h1><p style="color:#30d158; font-weight:bold; margin:0;"><span id="total_prot_display">0</span>g Prot</p></div><h4 style="text-align:left; color:#8e8e93; margin-bottom:10px;">Meal Ingredients:</h4><div id="recipe_list"></div><button type="button" onclick="addNewItem()" class="btn-main" style="background:#2c2c2e; color:#0a84ff; padding:10px; margin-top:10px;">+ ADD INGREDIENT</button><input type="hidden" id="form_cal" name="calories" value="{fav["calories"]}"><input type="hidden" id="form_prot" name="protein" value="{fav["protein"]}"><input type="hidden" name="qty" value="1"><input type="hidden" name="unit" value="qty"><input type="hidden" id="form_recipe" name="recipe_json" value='{recipe_data}'><button type="submit" class="btn-main" style="margin-top:30px;">SAVE MEAL</button></form><a href="/library" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancel</a></div><script>let items={recipe_data}; function updateUI(){{let tc=0,tp=0,hl=""; items.forEach((it,idx)=>{{let m=(parseFloat(it.current_qty)||1)/(parseFloat(it.base_qty)||1); let cc=Math.round((it.base_cal||it.cal)*m); let cp=Math.round((it.base_prot||it.prot)*m); tc+=cc; tp+=cp; it.qty=it.current_qty; it.cal=cc; it.prot=cp; hl+=`<div style="display:flex; justify-content:space-between; align-items:center; background:#1c1c1e; padding:10px; border-radius:10px; margin-bottom:5px; border:1px solid #3a3a3c;"><div style="text-align:left; flex:1;"><b>${{it.name}}</b><br><span style="font-size:0.7rem; color:#8e8e93;">${{cc}} kcal | ${{cp}}g</span></div><div style="display:flex; gap:5px; align-items:center;"><input type="number" step="0.1" value="${{it.current_qty||it.qty}}" onchange="items[${{idx}}].current_qty=parseFloat(this.value)||0; updateUI();" style="width:60px; padding:5px; margin:0;"><span style="font-size:0.8rem; color:#8e8e93;">${{it.unit||"qty"}}</span><button type="button" onclick="items.splice(${{idx}},1); updateUI();" style="background:transparent; border:none; color:#ff453a; font-weight:bold; font-size:1.2rem;">✕</button></div></div>`;}}); document.getElementById("recipe_list").innerHTML=hl||"<p style='color:#444; font-size:0.8rem;'>Empty.</p>"; document.getElementById("total_cal_display").innerText=tc; document.getElementById("total_prot_display").innerText=tp; document.getElementById("form_cal").value=tc; document.getElementById("form_prot").value=tp; document.getElementById("form_recipe").value=JSON.stringify(items);}} function addNewItem(){{items.push({{name:"New Item", base_qty:1, current_qty:1, base_cal:0, base_prot:0, unit:"qty"}}); updateUI();}} items.forEach(it=>{{it.base_qty=it.qty||1; it.current_qty=it.qty||1; it.base_cal=it.cal||0; it.base_prot=it.prot||0;}}); updateUI();</script></body></html>"""
    else: 
        return f"""<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><h2 style="color:#8e8e93;">EDIT ITEM</h2><div class="card"><form method="POST"><div style="margin-bottom:10px;"><span class="input-label">Name</span><input type="text" name="food_name" value="{safe_fname}" required style="margin:0;"></div><div style="display:flex; gap:5px; margin-bottom:10px;"><div style="flex:1;"><span class="input-label">Amount</span><input type="number" step="0.1" name="qty" value="{fav["qty"] or 1}" required style="margin:0;"></div><div style="flex:1;"><span class="input-label">Unit</span><select name="unit" style="margin:0;"><option value="qty" {"selected" if fav["unit"]=="qty" else ""}>Qty</option><option value="g" {"selected" if fav["unit"]=="g" else ""}>g</option></select></div></div><div style="display:flex; gap:5px;"><div style="flex:1;"><span class="input-label">Calories</span><input type="number" name="calories" value="{fav["calories"]}" required style="margin:0;"></div><div style="flex:1;"><span class="input-label">Protein (g)</span><input type="number" name="protein" value="{fav["protein"]}" required style="margin:0;"></div></div><button type="submit" class="btn-main" style="margin-top:15px;">SAVE CHANGES</button></form><a href="/library" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancel</a></div></body></html>"""

@app.route('/edit_log/<int:log_id>', methods=['GET', 'POST'])
def edit_log(log_id):
    conn = get_db_connection()
    if request.method == 'POST':
        conn.execute('UPDATE logs SET food_name=?, qty=?, unit=?, calories=?, protein=?, recipe=? WHERE id=?', 
                     (request.form.get('food_name'), float(request.form.get('qty') or 1), request.form.get('unit') or 'qty', int(float(request.form.get('calories') or 0)), int(float(request.form.get('protein') or 0)), request.form.get('recipe_json', ''), log_id))
        if request.form.get('save_lib') == 'on': 
            save_fav_db(conn, request.form.get('food_name'), float(request.form.get('qty') or 1), request.form.get('unit') or 'qty', int(float(request.form.get('calories') or 0)), int(float(request.form.get('protein') or 0)), request.form.get('recipe_json', ''))
        conn.commit(); conn.close(); return redirect(url_for('home'))
        
    log = conn.execute('SELECT * FROM logs WHERE id=?', (log_id,)).fetchone(); conn.close()
    if not log: return redirect(url_for('home'))
    
    safe_fname = (log["food_name"] or "Item").replace('"', '&quot;')
    is_meal = bool(log['recipe'] and log['recipe'] not in ('', '""', '[]'))
    rd = log['recipe'] if is_meal else "[]"
    
    if is_meal: 
        return f"""<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><h2 style="color:#8e8e93;">EDIT LOG (MEAL)</h2><p style="color:#8e8e93; font-size:0.8rem; margin-top:0;">Logged at {log['timestamp'] or ""}</p><div class="card"><form method="POST"><span class="input-label">Name</span><input type="text" name="food_name" value="{safe_fname}" required style="font-weight:bold; font-size:1.2rem; text-align:center; margin:0;"><div style="background:#000; padding:15px; border-radius:15px; margin:15px 0;"><h1 style="margin:0; font-size:2rem;"><span id="total_cal_display">0</span> <span style="font-size:1rem; color:#8e8e93;">kcal</span></h1><p style="color:#30d158; font-weight:bold; margin:0;"><span id="total_prot_display">0</span>g Prot</p></div><h4 style="text-align:left; color:#8e8e93; margin-bottom:10px;">Ingredients:</h4><div id="recipe_list"></div><button type="button" onclick="addNewItem()" class="btn-main" style="background:#2c2c2e; color:#0a84ff; padding:10px; font-size:0.9rem; margin-top:10px;">+ ADD INGREDIENT</button><input type="hidden" id="form_cal" name="calories" value="{log['calories']}"><input type="hidden" id="form_prot" name="protein" value="{log['protein']}"><input type="hidden" name="qty" value="1"><input type="hidden" name="unit" value="qty"><input type="hidden" id="form_recipe" name="recipe_json" value='{rd}'><div class="checkbox-wrapper" id="fav_lbl" onclick="updateDailyStat('fav_lbl', 'fav_chk')" style="margin-top:20px;"><input type="checkbox" id="fav_chk" name="save_lib" style="display:none;"><span style="font-size:1.1rem; pointer-events:none;">💾 Save to Library?</span></div><button type="submit" class="btn-green" style="margin-top:15px;">UPDATE LOG</button></form><a href="javascript:history.back()" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancel</a></div><script>let items={rd}; function updateUI(){{let tc=0,tp=0,hl=""; items.forEach((it,idx)=>{{let m=(parseFloat(it.current_qty)||1)/(parseFloat(it.base_qty)||1); let cc=Math.round((it.base_cal||it.cal)*m); let cp=Math.round((it.base_prot||it.prot)*m); tc+=cc; tp+=cp; it.qty=it.current_qty; it.cal=cc; it.prot=cp; hl+=`<div style="display:flex; justify-content:space-between; align-items:center; background:#1c1c1e; padding:10px; border-radius:10px; margin-bottom:5px; border:1px solid #3a3a3c;"><div style="text-align:left; flex:1;"><b>${{it.name}}</b><br><span style="font-size:0.7rem; color:#8e8e93;">${{cc}} kcal | ${{cp}}g</span></div><div style="display:flex; gap:5px; align-items:center;"><input type="number" step="0.1" value="${{it.current_qty||it.qty}}" onchange="items[${{idx}}].current_qty=parseFloat(this.value)||0; updateUI();" style="width:60px; padding:5px; margin:0;"><span style="font-size:0.8rem; color:#8e8e93;">${{it.unit||"qty"}}</span><button type="button" onclick="items.splice(${{idx}},1); updateUI();" style="background:transparent; border:none; color:#ff453a; font-weight:bold; font-size:1.2rem;">✕</button></div></div>`;}}); document.getElementById("recipe_list").innerHTML=hl||"<p style='color:#444; font-size:0.8rem;'>Empty.</p>"; document.getElementById("total_cal_display").innerText=tc; document.getElementById("total_prot_display").innerText=tp; document.getElementById("form_cal").value=tc; document.getElementById("form_prot").value=tp; document.getElementById("form_recipe").value=JSON.stringify(items);}} function addNewItem(){{items.push({{name:"New Item", base_qty:1, current_qty:1, base_cal:0, base_prot:0, unit:"qty"}}); updateUI();}} items.forEach(it=>{{it.base_qty=it.qty||1; it.current_qty=it.qty||1; it.base_cal=it.cal||0; it.base_prot=it.prot||0;}}); updateUI();</script></body></html>"""
    else: 
        return f"""<!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><h2 style="color:#8e8e93;">EDIT LOG</h2><div class="card"><p style="color:#8e8e93; font-size:0.8rem; margin-top:0;">Logged at {log["timestamp"] or ""}</p><form method="POST"><div style="margin-bottom:10px;"><span class="input-label">Name</span><input type="text" name="food_name" value="{safe_fname}" required style="margin:0;"></div><div style="display:flex; gap:5px; margin-bottom:10px;"><div style="flex:1;"><span class="input-label">Amount</span><input type="number" step="0.1" name="qty" value="{log["qty"] or 1}" required style="margin:0;"></div><div style="flex:1;"><span class="input-label">Unit</span><select name="unit" style="margin:0;"><option value="qty" {"selected" if log["unit"]=="qty" else ""}>Qty</option><option value="g" {"selected" if log["unit"]=="g" else ""}>g</option></select></div></div><div style="display:flex; gap:5px;"><div style="flex:1;"><span class="input-label">Calories</span><input type="number" name="calories" value="{log["calories"]}" required style="margin:0;"></div><div style="flex:1;"><span class="input-label">Protein (g)</span><input type="number" name="protein" value="{log["protein"]}" required style="margin:0;"></div></div><div class="checkbox-wrapper" id="fav_lbl" onclick="updateDailyStat('fav_lbl', 'fav_chk')" style="margin-top:20px;"><input type="checkbox" id="fav_chk" name="save_lib" style="display:none;"><span style="font-size:1.1rem; pointer-events:none;">💾 Save to Library?</span></div><button type="submit" class="btn-green" style="margin-top:15px;">UPDATE LOG</button></form><a href="javascript:history.back()" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancel</a></div></body></html>"""

@app.route('/delete/<int:log_id>', methods=['GET'])
def delete_entry(log_id): 
    conn = get_db_connection(); conn.execute('DELETE FROM logs WHERE id = ?', (log_id,)); conn.commit(); conn.close(); return redirect(url_for('home'))

@app.route('/delete_fav/<int:fav_id>', methods=['GET'])
def delete_fav(fav_id): 
    conn = get_db_connection(); conn.execute('DELETE FROM favorites WHERE id = ?', (fav_id,)); conn.commit(); conn.close(); return redirect(url_for('library'))

@app.route('/build_meal', methods=['GET', 'POST'])
def build_meal():
    conn = get_db_connection()
    if request.method == 'POST':
        m_name = request.form.get('meal_name') or "Compound Meal"
        m_cal = int(float(request.form.get('total_cal') or 0)); m_prot = int(float(request.form.get('total_prot') or 0))
        m_rec = request.form.get('recipe_json'); today = datetime.now().strftime("%Y-%m-%d"); nt = datetime.now().strftime("%H:%M")
        conn.execute('INSERT INTO logs (food_name, qty, unit, calories, protein, timestamp, date, recipe) VALUES (?, 1, "qty", ?, ?, ?, ?, ?)', (m_name, m_cal, m_prot, nt, today, m_rec))
        if request.form.get('save_lib') == 'on': save_fav_db(conn, m_name, 1, "qty", m_cal, m_prot, m_rec)
        conn.commit(); conn.close(); return redirect(url_for('home'))

    favs = conn.execute('SELECT * FROM favorites').fetchall(); conn.close()
    
    html_sugs = ""
    for f in favs:
        safe_name = f['food_name'].replace('"', '&quot;').replace("'", "\\'")
        recipe_safe = (f['recipe'] or "").replace('"', '&quot;').replace("'", "\\'")
        html_sugs += f"""<div onclick="buildMealPrompt(this)" data-name="{safe_name}" data-qty="{f['qty'] or 1}" data-unit="{f['unit'] or 'qty'}" data-cal="{f['calories']}" data-prot="{f['protein']}" data-recipe="{recipe_safe}" class="sug-item"><b>{f["food_name"]}</b><br><span style="color:#8e8e93; font-weight:normal;">{f["qty"] or 1} {f["unit"] or "qty"} | {f["calories"]} kcal</span></div>"""

    return f"""
    <!DOCTYPE html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color: #8e8e93;">🥗 BUILD MEAL</h2>
        <div class="card" style="border-color: #30d158;"><h1 style="margin:0; font-size:2.5rem;"><span id="t_cal">0</span> <span style="font-size:1rem; color:#8e8e93;">kcal</span></h1><p style="color:#30d158; font-weight:bold; margin:0;"><span id="t_prot">0</span>g Prot</p>
        <div id="recipe_box" class="recipe-list">Empty plate.</div></div>
        
        <h3 class="day-header">Library Items</h3><div class="sug-container" style="margin-bottom:20px;">{html_sugs or '<p style="color:#444; font-size:0.8rem; margin-left:10px;">No favorites.</p>'}</div>
        
        <div class="card"><h3 class="day-header" style="margin-top:0;">Add Manually</h3>
        <div style="display:flex; gap:5px; margin-bottom:10px;">
            <div style="flex:2;"><span class="input-label">Name</span><input type="text" id="c_name" placeholder="Item" style="width:100%; margin:0; padding:12px;"></div>
            <div style="flex:1;"><span class="input-label">Qty/Amt</span><input type="number" step="0.1" id="c_qty" placeholder="1" value="1" style="width:100%; margin:0; padding:12px;"></div>
            <div style="flex:1;"><span class="input-label">Unit</span><select id="c_unit" style="width:100%; margin:0; padding:12px;"><option value="qty">Qty</option><option value="g">g</option></select></div>
        </div>
        <div style="display:flex; gap:5px;">
            <div style="flex:1;"><span class="input-label">Kcal</span><input type="number" id="c_cal" placeholder="Kcal" style="width:100%; margin:0; padding:12px;"></div>
            <div style="flex:1;"><span class="input-label">Prot</span><input type="number" id="c_prot" placeholder="Prot" style="width:100%; margin:0; padding:12px;"></div>
        </div>
        <button type="button" onclick="addCustom()" class="btn-main" style="background:#2c2c2e; color:#0a84ff; margin-top:15px;">+ ADD TO PLATE</button></div>
        
        <form method="POST" style="margin-top:30px;">
            <div style="margin-bottom:15px;">
                <span class="input-label" style="text-align:center;">Meal Name</span>
                <input type="text" name="meal_name" placeholder="E.g., Lunch" required style="margin:0; text-align:center; font-weight:bold; font-size:1.2rem;">
            </div>
            <input type="hidden" id="form_cal" name="total_cal" value="0">
            <input type="hidden" id="form_prot" name="total_prot" value="0">
            <input type="hidden" id="form_recipe" name="recipe_json" value="[]">
            
            <div class="checkbox-wrapper" id="meal_fav_label" onclick="updateDailyStat('meal_fav_label', 'meal_fav_chk')">
                <input type="checkbox" id="meal_fav_chk" name="save_lib" style="display:none;">
                <span style="font-size:1.1rem; pointer-events:none;">💾 Save Meal to Library?</span>
            </div>
            
            <button type="submit" class="btn-green" style="font-size:1.1rem; padding:18px;">✅ CONFIRM MEAL</button>
        </form>
        <a href="/" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancel</a>
        
        <script>
            let items = []; 
            function addItem(name, cal, prot, qty, unit) {{ 
                let q = parseFloat(qty) || 1; let c = parseInt(cal) || 0; let p = parseInt(prot) || 0;
                let existing = items.find(i => i.name === name && i.unit === unit);
                if(existing) {{ existing.base_qty += q; existing.current_qty += q; existing.base_cal += c; existing.base_prot += p; }}
                else {{ items.push({{name: name, base_qty: q, current_qty: q, base_cal: c, base_prot: p, unit: unit || 'qty'}}); }}
                updateUI(); 
            }} 
            function addCustom() {{ let n = document.getElementById('c_name').value || 'Extra'; let c = document.getElementById('c_cal').value || 0; let p = document.getElementById('c_prot').value || 0; let q = document.getElementById('c_qty').value || 1; let u = document.getElementById('c_unit').value || 'qty'; if(c > 0 || p > 0) addItem(n, c, p, q, u); document.getElementById('c_name').value = ''; document.getElementById('c_cal').value = ''; document.getElementById('c_prot').value = ''; document.getElementById('c_qty').value = '1'; }} 
            function buildMealPrompt(el) {{
                let n = el.getAttribute('data-name'); let q = el.getAttribute('data-qty'); let u = el.getAttribute('data-unit');
                let new_q = prompt("How much did you eat?\\n" + n + " (Saved as " + q + " " + u + ")", q);
                if (new_q !== null && new_q.trim() !== "") {{
                    new_q = parseFloat(new_q.replace(',', '.'));
                    if (!isNaN(new_q) && new_q > 0) {{
                        let base_q = parseFloat(q) || 1; let multi = new_q / base_q;
                        let cal = Math.round(parseFloat(el.getAttribute('data-cal')) * multi);
                        let prot = Math.round(parseFloat(el.getAttribute('data-prot')) * multi);
                        addItem(n, cal, prot, new_q, u);
                    }}
                }}
            }}
            function updatePlateItemQty(idx, newQty) {{ items[idx].current_qty = parseFloat(newQty) || 0; updateUI(); }}
            function removePlateItem(idx) {{ items.splice(idx, 1); updateUI(); }}
            function updateUI() {{ let totalCal = 0; let totalProt = 0; let htmlList = ""; items.forEach((it, index) => {{ let multi = it.current_qty / it.base_qty; let curCal = Math.round(it.base_cal * multi); let curProt = Math.round(it.base_prot * multi); totalCal += curCal; totalProt += curProt; it.qty = it.current_qty; it.cal = curCal; it.prot = curProt; htmlList += `<div style="display:flex; justify-content:space-between; align-items:center; background:#2c2c2e; padding:10px; border-radius:10px; margin-bottom:5px;"><div style="text-align:left; flex:1;"><b>${{it.name}}</b><br><span style="font-size:0.7rem; color:#8e8e93;">${{curCal}} kcal | ${{curProt}}g</span></div><div style="display:flex; gap:5px; align-items:center;"><input type="number" step="0.1" value="${{it.current_qty}}" onchange="updatePlateItemQty(${{index}}, this.value)" style="width:60px; padding:5px; margin:0; font-size:0.9rem;"><span style="font-size:0.8rem; color:#8e8e93;">${{it.unit}}</span><button type="button" onclick="removePlateItem(${{index}})" style="background:transparent; border:none; color:#ff453a; font-weight:bold; font-size:1.2rem; cursor:pointer;">✕</button></div></div>`; }}); document.getElementById('t_cal').innerText = totalCal; document.getElementById('t_prot').innerText = totalProt; document.getElementById('form_cal').value = totalCal; document.getElementById('form_prot').value = totalProt; document.getElementById('form_recipe').value = JSON.stringify(items); document.getElementById('recipe_box').innerHTML = htmlList || "<p style='color:#444; font-size:0.8rem; margin:0;'>Empty plate.</p>"; }}
        </script>
    </body></html>
    """

@app.route('/export_db')
def export_db(): 
    return send_file('tracker.db', as_attachment=True, download_name=f'tracker_backup_{datetime.now().strftime("%Y%m%d")}.db')

@app.route('/import_db', methods=['POST'])
def import_db():
    if 'db_file' not in request.files: return redirect(url_for('manage_favs'))
    file = request.files['db_file']
    if file.filename != '': file.save('tracker.db')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')