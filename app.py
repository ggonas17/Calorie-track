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
    
    # Tabela de estatísticas diárias melhorada (permite sobrescrever macros e passos)
    conn.execute('''CREATE TABLE IF NOT EXISTS daily_stats
                    (date TEXT PRIMARY KEY, steps INTEGER, calories INTEGER, protein INTEGER)''')
    
    # Prevenção de erros caso já tenhas a tabela daily_stats antiga
    try: conn.execute('ALTER TABLE daily_stats ADD COLUMN calories INTEGER')
    except: pass
    try: conn.execute('ALTER TABLE daily_stats ADD COLUMN protein INTEGER')
    except: pass
    
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_goal', '3000')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('protein_goal', '150')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('step_goal', '10000')")
    conn.commit()
    conn.close()

init_db()

def get_badge(recipe_str):
    if recipe_str and recipe_str not in ('', '""', '[]'):
        return '<span style="background:#5e5ce6; color:#fff; padding:3px 8px; border-radius:8px; font-size:0.55rem; margin-left:6px; vertical-align:middle; font-weight:900; letter-spacing:0.5px;">REFEIÇÃO</span>'
    return '<span style="background:#3a3a3c; color:#8e8e93; padding:3px 8px; border-radius:8px; font-size:0.55rem; margin-left:6px; vertical-align:middle; font-weight:900; letter-spacing:0.5px;">ITEM</span>'

CSS = """
<style>
    body { font-family: -apple-system, sans-serif; background: #000; color: #fff; padding: 20px; text-align: center; padding-bottom: 90px; margin: 0; }
    .card { background: #1c1c1e; border-radius: 20px; padding: 20px; margin-bottom: 20px; border: 1px solid #2c2c2e; box-shadow: 0 4px 15px rgba(0,0,0,0.3); position: relative; overflow: hidden; }
    .nav-bar { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(28, 28, 30, 0.95); backdrop-filter: blur(10px); display: flex; justify-content: space-around; padding: 15px 0; border-top: 0.5px solid #3a3a3c; z-index: 100; }
    .nav-item { color: #8e8e93; text-decoration: none; font-size: 0.75rem; font-weight: 600; flex: 1; display: flex; flex-direction: column; align-items: center; }
    .nav-item.active { color: #0a84ff; }
    input { background: #2c2c2e; border: none; border-radius: 12px; color: #fff; padding: 15px; margin: 8px 0; width: 90%; font-size: 16px; -webkit-appearance: none; box-sizing: border-box; }
    .btn-main { background: #0a84ff; color: #fff; border: none; border-radius: 15px; padding: 16px; width: 100%; font-weight: bold; font-size: 16px; margin-top: 10px; cursor: pointer; }
    .btn-green { background: #30d158; color: #000; border: none; border-radius: 15px; padding: 16px; width: 100%; font-weight: bold; font-size: 16px; margin-top: 10px; cursor: pointer; text-decoration: none; display: block; }
    .btn-orange { background: #ff9f0a; color: #000; border: none; border-radius: 12px; padding: 14px; width: 100%; font-weight: bold; font-size: 16px; cursor: pointer; }
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
    @keyframes popIn { 0% { transform: scale(0.9); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
</style>
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    conn = get_db_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday_dt = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
    yesterday_display = yesterday_dt.strftime("%d/%m")
    
    if request.method == 'POST':
        y_steps = request.form.get('yesterday_steps')
        if y_steps:
            # Garante que cria a estatística de ontem sem apagar macros que possam lá estar
            row = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (yesterday_str,)).fetchone()
            if row: conn.execute('UPDATE daily_stats SET steps=? WHERE date=?', (int(y_steps), yesterday_str))
            else: conn.execute('INSERT INTO daily_stats (date, steps) VALUES (?, ?)', (yesterday_str, int(y_steps)))
            conn.commit()
            return redirect(url_for('home'))

        f_name = request.form.get('food_name') or "Refeição"
        c_val = request.form.get('calories')
        p_val = request.form.get('protein')
        wants_to_save = request.form.get('save_fav')
        
        if c_val and p_val:
            now_time = datetime.now().strftime("%H:%M")
            conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp, date) VALUES (?, ?, ?, ?, ?)',
                         (f_name, int(c_val), int(p_val), now_time, today))
            if wants_to_save:
                conn.execute('INSERT OR REPLACE INTO favorites (food_name, calories, protein, recipe) VALUES (?, ?, ?, ?)',
                             (f_name, int(c_val), int(p_val), ""))
            conn.commit()

    missing_steps_html = ""
    step_record = conn.execute('SELECT steps FROM daily_stats WHERE date = ?', (yesterday_str,)).fetchone()
    # Só chateia se o gajo tiver comido alguma cena ontem (para não aparecer a novatos absolutos)
    had_logs_yesterday = conn.execute('SELECT id FROM logs WHERE date = ? LIMIT 1', (yesterday_str,)).fetchone()
    
    if not step_record and had_logs_yesterday:
        missing_steps_html = f"""
        <div class="card" style="border: 2px solid #ff9f0a; animation: popIn 0.5s ease; background: rgba(255, 159, 10, 0.1);">
            <h3 style="color:#ff9f0a; margin-top:0;">👣 PASSOS DE ONTEM ({yesterday_display})</h3>
            <p style="font-size:0.85rem; color:#8e8e93; margin-top:0;">Máquina, esqueceste-te de registar o cardio de ontem. Manda aí os números!</p>
            <form method="POST" style="display:flex; gap:10px;">
                <input type="number" name="yesterday_steps" placeholder="Passos totais" required style="margin:0; width:65%; background:#000;">
                <button type="submit" class="btn-orange" style="margin:0; width:35%;">GRAVAR</button>
            </form>
        </div>
        """

    logs = conn.execute('SELECT * FROM logs WHERE date = ? ORDER BY id DESC', (today,)).fetchall()
    favs = conn.execute('SELECT * FROM favorites').fetchall()
    
    goal_c = int(conn.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()['value'] or 3000)
    goal_p = int(conn.execute("SELECT value FROM settings WHERE key='protein_goal'").fetchone()['value'] or 150)
    
    # Busca a possibilidade de teres editado o HOJE no calendário
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
            <div style="text-align:left;"><b>{l['food_name']}</b><br><small style="color:#8e8e93;">{l['timestamp']} • {l['calories']} kcal | {l['protein']}g Prot</small></div>
            <div>
                <a href="/edit_log/{l['id']}" style="color:#0a84ff; text-decoration:none; font-weight:bold; margin-right:15px; font-size:0.85rem;">EDITAR</a>
                <a href="/delete/{l['id']}" style="color:#ff453a; text-decoration:none; font-weight:bold; font-size:1.1rem;">✕</a>
            </div>
        </div>""" for l in logs])

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">{CSS}</head><body>
        {missing_steps_html}
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
        <a href="/build_meal" class="btn-green" style="margin-bottom: 20px;">🥗 CRIAR REFEIÇÃO COMPOSTA</a>
        <div class="card">
            <h3 class="day-header" style="margin-top:0;">Adição Rápida</h3>
            <div class="sug-container" style="margin-bottom: 15px;">
                {html_favs or '<p style="color:#444; font-size:0.8rem; margin-left:10px;">Sem favoritos.</p>'}
            </div>
            <form method="POST">
                <input type="text" name="food_name" placeholder="O que comeste?">
                <div style="display: flex; gap: 10px;">
                    <input type="number" name="calories" placeholder="Kcal" required style="width:50%;">
                    <input type="number" name="protein" placeholder="Prot" required style="width:50%;">
                </div>
                <label class="fav-toggle" id="fav_label">
                    <input type="checkbox" name="save_fav" class="hidden-check" onchange="document.getElementById('fav_label').classList.toggle('active'); document.getElementById('fav_text').innerText = this.checked ? 'A GRAVAR NA BIBLIOTECA ✅' : 'Gravar na Biblioteca?';">
                    <span id="fav_text">Gravar na Biblioteca?</span>
                </label>
                <button type="submit" class="btn-main">ADICIONAR</button>
            </form>
        </div>
        <h3 class="day-header">Diário de Hoje</h3>
        {html_logs}
        <div class="nav-bar">
            <a href="/" class="nav-item active"><span>🏠</span><br>HOJE</a>
            <a href="/history" class="nav-item"><span>📅</span><br>HISTÓRICO</a>
            <a href="/manage_favs" class="nav-item"><span>⚙️</span><br>DEFINIÇÕES</a>
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
    month_name = month_names[m-1]

    logs_data = conn.execute("SELECT date, SUM(calories) as c, SUM(protein) as p FROM logs GROUP BY date").fetchall()
    stats_data = conn.execute("SELECT * FROM daily_stats").fetchall()
    conn.close()

    logs_dict = {row['date']: {'c': row['c'], 'p': row['p']} for row in logs_data}
    stats_dict = {row['date']: row for row in stats_data}

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdatescalendar(y, m)

    cal_html = f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <a href="/history?month={prev_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&lt;</a>
        <h2 style="color:#fff; margin:0; font-size:1.2rem; text-transform:uppercase;">{month_name} {y}</h2>
        <a href="/history?month={next_m}" style="color:#0a84ff; text-decoration:none; font-size:1.8rem; font-weight:bold; padding:0 15px;">&gt;</a>
    </div>
    <div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:8px; text-align:center; color:#8e8e93; font-size:0.8rem; margin-bottom:10px; font-weight:bold;">
        <div>S</div><div>T</div><div>Q</div><div>Q</div><div>S</div><div>S</div><div>D</div>
    </div>
    <div style="display:grid; grid-template-columns: repeat(7, 1fr); gap:8px;">
    """

    today_str = datetime.now().strftime("%Y-%m-%d")

    for week in month_days:
        for day_date in week:
            d_str = day_date.strftime("%Y-%m-%d")
            d_num = day_date.day
            
            is_current_month = day_date.month == m
            bg_color = "#1c1c1e" if is_current_month else "transparent"
            text_color = "#fff" if is_current_month else "#444"
            
            logs_c = logs_dict.get(d_str, {}).get('c', 0)
            stats_row = stats_dict.get(d_str, {})
            stats_c = stats_row['calories'] if stats_row and 'calories' in stats_row.keys() and stats_row['calories'] is not None else None
            stats_s = stats_row['steps'] if stats_row and 'steps' in stats_row.keys() and stats_row['steps'] is not None else 0
            
            final_c = stats_c if stats_c is not None else logs_c
            
            border = "border: 1px solid #2c2c2e;"
            if d_str == today_str: border = "border: 2px solid #0a84ff;"
            elif final_c > 0 or stats_s > 0: border = "border: 1px solid #30d158;"
            if not is_current_month: border = "border: 1px solid transparent;"
            
            indic = ""
            if is_current_month and final_c > 0:
                indic = f'<div style="font-size:0.55rem; color:#8e8e93; margin-top:4px; font-weight:bold;">{final_c}k</div>'

            cal_html += f"""
            <a href="/edit_day/{d_str}" style="background:{bg_color}; {border} border-radius:12px; padding:12px 2px; text-decoration:none; color:{text_color}; display:flex; flex-direction:column; align-items:center; min-height:50px; box-sizing:border-box; transition:0.2s;">
                <span style="font-weight:bold; font-size:1rem;">{d_num}</span>
                {indic}
            </a>
            """
    cal_html += "</div>"

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head>
    <body>
        <h2 style="color:#8e8e93; margin-bottom:10px;">HISTÓRICO PERPÉTUO</h2>
        <div class="card" style="padding:15px;">
            {cal_html}
        </div>
        <p style="color:#8e8e93; font-size:0.8rem; margin-top:10px;">Clica em qualquer dia para ver ou editar as macros e os passos (mesmo no passado ou no futuro!).</p>
        <div class="nav-bar">
            <a href="/" class="nav-item"><span>🏠</span><br>HOJE</a>
            <a href="/history" class="nav-item active"><span>📅</span><br>HISTÓRICO</a>
            <a href="/manage_favs" class="nav-item"><span>⚙️</span><br>DEFINIÇÕES</a>
        </div>
    </body></html>
    """

@app.route('/edit_day/<date>', methods=['GET', 'POST'])
def edit_day(date):
    conn = get_db_connection()
    if request.method == 'POST':
        c_val = request.form.get('calories')
        p_val = request.form.get('protein')
        s_val = request.form.get('steps')
        
        c_val = int(c_val) if c_val and c_val.strip() != "" else None
        p_val = int(p_val) if p_val and p_val.strip() != "" else None
        s_val = int(s_val) if s_val and s_val.strip() != "" else None
        
        row = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone()
        if row: conn.execute('UPDATE daily_stats SET calories=?, protein=?, steps=? WHERE date=?', (c_val, p_val, s_val, date))
        else: conn.execute('INSERT INTO daily_stats (date, calories, protein, steps) VALUES (?, ?, ?, ?)', (date, c_val, p_val, s_val))
        conn.commit()
        conn.close()
        return redirect(url_for('history', month=date[:7]))
        
    logs = conn.execute('SELECT SUM(calories) as c, SUM(protein) as p FROM logs WHERE date = ?', (date,)).fetchone()
    stats = conn.execute('SELECT * FROM daily_stats WHERE date = ?', (date,)).fetchone()
    
    goal_c = int(conn.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()['value'] or 3000)
    goal_p = int(conn.execute("SELECT value FROM settings WHERE key='protein_goal'").fetchone()['value'] or 150)
    goal_s = int(conn.execute("SELECT value FROM settings WHERE key='step_goal'").fetchone()['value'] or 10000)
    conn.close()
    
    logs_c = logs['c'] if logs and logs['c'] else 0
    logs_p = logs['p'] if logs and logs['p'] else 0
    
    stats_c = stats['calories'] if stats and 'calories' in stats.keys() and stats['calories'] is not None else ""
    stats_p = stats['protein'] if stats and 'protein' in stats.keys() and stats['protein'] is not None else ""
    stats_s = stats['steps'] if stats and 'steps' in stats.keys() and stats['steps'] is not None else ""
    
    disp_c = stats_c if stats_c != "" else logs_c
    disp_p = stats_p if stats_p != "" else logs_p
    disp_s = stats_s if stats_s != "" else 0
    
    date_obj = datetime.strptime(date, "%Y-%m-%d")
    display_date = date_obj.strftime("%d %b %Y")
    
    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head>
    <body>
        <h2 style="color:#8e8e93; text-transform:uppercase;">{display_date}</h2>
        <div class="card" style="background: linear-gradient(145deg, #1c1c1e, #000); border: 1px solid #30d158;">
            <h1 style="font-size: 2.5rem; margin: 0; color: #fff;">{disp_c} <span style="font-size: 1rem; color: #8e8e93;">/ {goal_c} kcal</span></h1>
            <p style="color: #30d158; font-weight: bold; font-size: 1.1rem; margin: 5px 0;">{disp_p} <span style="font-size: 0.9rem; color: #8e8e93;">/ {goal_p}g Prot</span></p>
            <p style="color: #ff9f0a; font-weight: bold; font-size: 1.1rem; margin: 5px 0;">👣 {disp_s} <span style="font-size: 0.9rem; color: #8e8e93;">/ {goal_s} Passos</span></p>
        </div>
        <div class="card">
            <h3 style="margin-top:0; color:#8e8e93;">SOBRESCREVER VALORES</h3>
            <p style="font-size:0.8rem; color:#8e8e93; text-align:left; margin-bottom:15px;">Se preencheres estes campos, os valores calculados através do diário são ignorados para este dia. Deixa em branco para usar a soma automática dos registos.</p>
            <form method="POST">
                <div style="display:flex; flex-direction:column; gap:10px; align-items:flex-start;">
                    <label style="color:#8e8e93; font-weight:bold; font-size:0.9rem; margin-left:5px;">Calorias Totais (Kcal):</label>
                    <input type="number" name="calories" value="{stats_c}" placeholder="Automático: {logs_c} kcal" style="margin:0; width:100%;">
                    <label style="color:#8e8e93; font-weight:bold; font-size:0.9rem; margin-left:5px; margin-top:10px;">Proteína Total (g):</label>
                    <input type="number" name="protein" value="{stats_p}" placeholder="Automático: {logs_p} g" style="margin:0; width:100%;">
                    <label style="color:#ff9f0a; font-weight:bold; font-size:0.9rem; margin-left:5px; margin-top:10px;">Passos 👣:</label>
                    <input type="number" name="steps" value="{stats_s}" placeholder="Ex: 10500" style="margin:0; width:100%;">
                </div>
                <button type="submit" class="btn-main" style="margin-top:20px;">GRAVAR DIA</button>
            </form>
            <a href="/history" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Voltar ao Calendário</a>
        </div>
    </body></html>
    """

@app.route('/build_meal', methods=['GET', 'POST'])
def build_meal():
    conn = get_db_connection()
    if request.method == 'POST':
        m_name = request.form.get('meal_name') or "Refeição Composta"
        m_cal = request.form.get('total_cal')
        m_prot = request.form.get('total_prot')
        m_recipe = request.form.get('recipe_json')
        save_lib = request.form.get('save_lib')
        now_time = datetime.now().strftime("%H:%M")
        today = datetime.now().strftime("%Y-%m-%d")
        
        conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp, date) VALUES (?, ?, ?, ?, ?)', (m_name, int(m_cal), int(m_prot), now_time, today))
        if save_lib: conn.execute('INSERT OR REPLACE INTO favorites (food_name, calories, protein, recipe) VALUES (?, ?, ?, ?)', (m_name, int(m_cal), int(m_prot), m_recipe))
        conn.commit(); conn.close()
        return redirect(url_for('home'))

    favs = conn.execute('SELECT * FROM favorites').fetchall()
    conn.close()

    html_sugs = "".join([f"""<div onclick="addItem('{f['food_name']}', {f['calories']}, {f['protein']})" class="sug-item"><b>+ {f['food_name']}</b><br><span style="color:#8e8e93; font-weight:normal;">{f['calories']} kcal | {f['protein']}g Prot</span></div>""" for f in favs])

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color: #8e8e93;">MONTAR PRATO</h2>
        <div class="card" style="border-color: #30d158;">
            <h1 style="margin:0; font-size:2.5rem;"><span id="t_cal">0</span> <span style="font-size:1rem; color:#8e8e93;">kcal</span></h1>
            <p style="color:#30d158; font-weight:bold; margin:0;"><span id="t_prot">0</span>g Prot</p>
            <div id="recipe_box" class="recipe-list">Prato vazio.</div>
            <button type="button" onclick="undoItem()" class="btn-red" id="undo_btn" style="display:none; width:100%;">Desfazer Último Item</button>
        </div>
        <h3 class="day-header">Cenas da Biblioteca</h3>
        <div class="sug-container" style="margin-bottom:20px;">
            {html_sugs or '<p style="color:#444; font-size:0.8rem; margin-left:10px;">Sem favoritos.</p>'}
        </div>
        <div class="card">
            <h3 class="day-header" style="margin-top:0;">Adicionar Extra Manual</h3>
            <div style="display:flex; gap:10px;">
                <input type="text" id="c_name" placeholder="Item" style="width:40%;">
                <input type="number" id="c_cal" placeholder="Kcal" style="width:30%;">
                <input type="number" id="c_prot" placeholder="Prot" style="width:30%;">
            </div>
            <button type="button" onclick="addCustom()" class="btn-main" style="background:#2c2c2e; color:#0a84ff;">+ ADICIONAR AO PRATO</button>
        </div>
        <form method="POST" style="margin-top:30px;">
            <input type="text" name="meal_name" placeholder="Nome da Refeição (ex: Almoço)" required>
            <input type="hidden" id="form_cal" name="total_cal" value="0">
            <input type="hidden" id="form_prot" name="total_prot" value="0">
            <input type="hidden" id="form_recipe" name="recipe_json" value="[]">
            <label class="fav-toggle" id="meal_fav_label">
                <input type="checkbox" name="save_lib" class="hidden-check" onchange="document.getElementById('meal_fav_label').classList.toggle('active');">
                <span>Guardar Refeição na Biblioteca?</span>
            </label>
            <button type="submit" class="btn-green">CONFIRMAR REFEIÇÃO</button>
        </form>
        <a href="/" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a>
        <script>
            let items = []; 
            function addItem(name, cal, prot) {{ items.push({{name: name, cal: parseInt(cal), prot: parseInt(prot)}}); updateUI(); }} 
            function addCustom() {{
                let n = document.getElementById('c_name').value || 'Extra'; 
                let c = document.getElementById('c_cal').value || 0; 
                let p = document.getElementById('c_prot').value || 0; 
                if(c > 0 || p > 0) addItem(n, c, p); 
                document.getElementById('c_name').value = ''; document.getElementById('c_cal').value = ''; document.getElementById('c_prot').value = '';
            }} 
            function undoItem() {{ items.pop(); updateUI(); }}
            function updateUI() {{
                let totalCal = 0; let totalProt = 0; let htmlList = "";
                items.forEach((it, index) => {{
                    totalCal += it.cal; totalProt += it.prot;
                    htmlList += `<div>• ${{it.name}} <span style="color:#444;">(${{it.cal}}kcal | ${{it.prot}}g)</span></div>`;
                }});
                document.getElementById('t_cal').innerText = totalCal; document.getElementById('t_prot').innerText = totalProt; 
                document.getElementById('form_cal').value = totalCal; document.getElementById('form_prot').value = totalProt;
                document.getElementById('form_recipe').value = JSON.stringify(items);
                document.getElementById('recipe_box').innerHTML = htmlList || "Prato vazio.";
                document.getElementById('undo_btn').style.display = items.length > 0 ? "block" : "none";
            }}
        </script>
    </body></html>
    """

@app.route('/manage_favs', methods=['GET', 'POST'])
def manage_favs():
    conn = get_db_connection()
    if request.method == 'POST':
        new_c = request.form.get('new_goal')
        new_p = request.form.get('new_p_goal')
        new_s = request.form.get('new_s_goal')
        if new_c: conn.execute("UPDATE settings SET value=? WHERE key='daily_goal'", (new_c,))
        if new_p: conn.execute("UPDATE settings SET value=? WHERE key='protein_goal'", (new_p,))
        if new_s: conn.execute("UPDATE settings SET value=? WHERE key='step_goal'", (new_s,))
        conn.commit()
        
    goal_c = int(conn.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()['value'] or 3000)
    goal_p = int(conn.execute("SELECT value FROM settings WHERE key='protein_goal'").fetchone()['value'] or 150)
    goal_s = int(conn.execute("SELECT value FROM settings WHERE key='step_goal'").fetchone()['value'] or 10000)
    
    favs = conn.execute('SELECT * FROM favorites').fetchall()
    conn.close()
    
    html_favs = "".join([f"""
        <div class="log-item">
            <div style="text-align:left;">
                <b>{f['food_name']}</b> {get_badge(f['recipe'])}<br>
                <small style="color:#8e8e93;">{f['calories']} kcal | {f['protein']}g Prot</small>
            </div>
            <div>
                <a href="/edit_fav/{f['id']}" style="color:#0a84ff; text-decoration:none; font-weight:bold; margin-right:15px;">EDITAR</a>
                <a href="/delete_fav/{f['id']}" style="color:#ff453a; text-decoration:none; font-weight:bold;">✕</a>
            </div>
        </div>""" for f in favs])
        
    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <div class="card">
            <h3 style="margin-top:0; color:#8e8e93;">OBJETIVOS GERAIS</h3>
            <form method="POST">
                <div style="display:flex; gap:10px; margin-bottom:10px;">
                    <input type="number" name="new_goal" value="{goal_c}" placeholder="Kcal" style="margin:0; width:33%;">
                    <input type="number" name="new_p_goal" value="{goal_p}" placeholder="Prot" style="margin:0; width:33%;">
                    <input type="number" name="new_s_goal" value="{goal_s}" placeholder="Passos" style="margin:0; width:33%;">
                </div>
                <button type="submit" class="btn-main" style="margin:0;">ATUALIZAR OBJETIVOS</button>
            </form>
        </div>
        <h3 class="day-header">EDITAR BIBLIOTECA</h3>
        {html_favs or '<p style="color:#444;">Biblioteca vazia.</p>'}
        <div class="nav-bar">
            <a href="/" class="nav-item"><span>🏠</span><br>HOJE</a>
            <a href="/history" class="nav-item"><span>📅</span><br>HISTÓRICO</a>
            <a href="/manage_favs" class="nav-item active"><span>⚙️</span><br>DEFINIÇÕES</a>
        </div>
    </body></html>
    """

@app.route('/edit_fav/<int:fav_id>', methods=['GET', 'POST'])
def edit_fav(fav_id):
    conn = get_db_connection()
    if request.method == 'POST':
        f_name = request.form.get('food_name')
        c_val = request.form.get('calories')
        p_val = request.form.get('protein')
        r_val = request.form.get('recipe_json', '')
        conn.execute('UPDATE favorites SET food_name=?, calories=?, protein=?, recipe=? WHERE id=?', (f_name, int(c_val), int(p_val), r_val, fav_id))
        conn.commit(); conn.close()
        return redirect(url_for('manage_favs'))
        
    fav = conn.execute('SELECT * FROM favorites WHERE id=?', (fav_id,)).fetchone()
    conn.close()
    
    is_meal = bool(fav['recipe'] and fav['recipe'] not in ('', '""', '[]'))
    recipe_data = fav['recipe'] if is_meal else "[]"
    
    if is_meal:
        editor_html = f"""
        <h2 style="color:#8e8e93;">EDITAR REFEIÇÃO</h2>
        <div class="card">
            <form method="POST">
                <input type="text" name="food_name" value="{fav['food_name']}" required style="font-weight:bold; font-size:1.2rem; text-align:center;">
                <div style="background:#000; padding:15px; border-radius:15px; margin:15px 0;">
                    <h1 style="margin:0; font-size:2rem;"><span id="total_cal_display">0</span> <span style="font-size:1rem; color:#8e8e93;">kcal</span></h1>
                    <p style="color:#30d158; font-weight:bold; margin:0;"><span id="total_prot_display">0</span>g Prot</p>
                </div>
                <h4 style="text-align:left; color:#8e8e93; margin-bottom:10px;">Ingredientes da Refeição:</h4>
                <div id="recipe_list"></div>
                <button type="button" onclick="addNewItem()" class="btn-main" style="background:#2c2c2e; color:#0a84ff; padding:10px; font-size:0.9rem; margin-top:10px;">+ ADICIONAR INGREDIENTE</button>
                <input type="hidden" id="form_cal" name="calories" value="{fav['calories']}">
                <input type="hidden" id="form_prot" name="protein" value="{fav['protein']}">
                <input type="hidden" id="form_recipe" name="recipe_json" value='{recipe_data}'>
                <button type="submit" class="btn-green" style="margin-top:30px;">GUARDAR REFEIÇÃO</button>
            </form>
            <a href="/manage_favs" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a>
        </div>
        <script>
            let recipe = {recipe_data};
            function renderRecipe() {{
                let html = ""; let tCal = 0; let tProt = 0;
                recipe.forEach((it, idx) => {{
                    tCal += parseInt(it.cal) || 0; tProt += parseInt(it.prot) || 0;
                    html += `<div style="display:flex; gap:5px; margin-bottom:10px; align-items:center;">
                        <input type="text" value="${{it.name}}" onchange="updateItem(${{idx}}, 'name', this.value)" style="width:45%; padding:10px; margin:0; font-size:0.9rem;">
                        <input type="number" value="${{it.cal}}" onchange="updateItem(${{idx}}, 'cal', this.value)" style="width:25%; padding:10px; margin:0; font-size:0.9rem;">
                        <input type="number" value="${{it.prot}}" onchange="updateItem(${{idx}}, 'prot', this.value)" style="width:25%; padding:10px; margin:0; font-size:0.9rem;">
                        <button type="button" onclick="removeItem(${{idx}})" style="width:10%; background:transparent; border:none; color:#ff453a; font-weight:bold; font-size:1.2rem; cursor:pointer; padding:0;">✕</button>
                    </div>`;
                }});
                document.getElementById('recipe_list').innerHTML = html; document.getElementById('total_cal_display').innerText = tCal; document.getElementById('total_prot_display').innerText = tProt;
                document.getElementById('form_cal').value = tCal; document.getElementById('form_prot').value = tProt; document.getElementById('form_recipe').value = JSON.stringify(recipe);
            }}
            function updateItem(idx, field, val) {{ if(field === 'cal' || field === 'prot') val = parseInt(val) || 0; recipe[idx][field] = val; renderRecipe(); }}
            function removeItem(idx) {{ recipe.splice(idx, 1); renderRecipe(); }}
            function addNewItem() {{ recipe.push({{name: 'Novo Ingrediente', cal: 0, prot: 0}}); renderRecipe(); }}
            renderRecipe();
        </script>
        """
    else:
        editor_html = f"""
        <h2 style="color:#8e8e93;">EDITAR ITEM SIMPLES</h2>
        <div class="card">
            <form method="POST">
                <input type="text" name="food_name" value="{fav['food_name']}" required>
                <input type="number" name="calories" value="{fav['calories']}" required>
                <input type="number" name="protein" value="{fav['protein']}" required>
                <button type="submit" class="btn-main">GUARDAR ALTERAÇÕES</button>
            </form>
            <a href="/manage_favs" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a>
        </div>
        """
        
    return f"<!DOCTYPE html><html lang='pt'><head><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head><body>{editor_html}</body></html>"

@app.route('/edit_log/<int:log_id>', methods=['GET', 'POST'])
def edit_log(log_id):
    conn = get_db_connection()
    if request.method == 'POST':
        f_name, c_val, p_val = request.form.get('food_name'), request.form.get('calories'), request.form.get('protein')
        conn.execute('UPDATE logs SET food_name=?, calories=?, protein=? WHERE id=?', (f_name, int(c_val), int(p_val), log_id))
        conn.commit(); conn.close()
        return redirect(url_for('home'))
        
    log = conn.execute('SELECT * FROM logs WHERE id=?', (log_id,)).fetchone(); conn.close()
    return f'<!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body><h2 style="color:#8e8e93;">EDITAR DIÁRIO</h2><div class="card"><p style="color:#8e8e93; font-size:0.8rem; margin-top:0;">Registado às {log["timestamp"]}</p><form method="POST"><input type="text" name="food_name" value="{log["food_name"]}" required><input type="number" name="calories" value="{log["calories"]}" required><input type="number" name="protein" value="{log["protein"]}" required><button type="submit" class="btn-main">ATUALIZAR REFEIÇÃO</button></form><a href="/" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a></div></body></html>'

@app.route('/quick_add/<int:fav_id>')
def quick_add(fav_id):
    conn = get_db_connection()
    fav = conn.execute('SELECT * FROM favorites WHERE id=?', (fav_id,)).fetchone()
    if fav:
        now_time, today = datetime.now().strftime("%H:%M"), datetime.now().strftime("%Y-%m-%d")
        conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp, date) VALUES (?, ?, ?, ?, ?)', (fav['food_name'], fav['calories'], fav['protein'], now_time, today))
        conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/delete/<int:log_id>')
def delete_entry(log_id):
    conn = get_db_connection(); conn.execute('DELETE FROM logs WHERE id = ?', (log_id,)); conn.commit(); conn.close(); return redirect(url_for('home'))

@app.route('/delete_fav/<int:fav_id>')
def delete_fav(fav_id):
    conn = get_db_connection(); conn.execute('DELETE FROM favorites WHERE id = ?', (fav_id,)); conn.commit(); conn.close(); return redirect(url_for('manage_favs'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')