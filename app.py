import sqlite3
from flask import Flask, request, redirect, url_for
from datetime import datetime

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
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, calories INTEGER, protein INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS settings 
                    (key TEXT PRIMARY KEY, value TEXT)''')
    
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_goal', '3000')")
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('protein_goal', '150')")
    conn.commit()
    conn.close()

init_db()

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
    .sug-container { display: flex; overflow-x: auto; gap: 10px; padding: 10px 0; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
    .sug-item { background: #2c2c2e; color: #0a84ff; padding: 12px 18px; border-radius: 18px; text-decoration: none; min-width: 110px; font-size: 0.85rem; border: 1px solid #3a3a3c; flex-shrink: 0; cursor: pointer; }
    .log-item { display: flex; justify-content: space-between; align-items: center; background: #1c1c1e; padding: 16px; border-radius: 18px; margin-bottom: 12px; border: 1px solid #2c2c2e; }
    .day-header { text-align: left; color: #8e8e93; font-size: 0.8rem; text-transform: uppercase; margin: 10px 5px; letter-spacing: 1px; }
    .fav-toggle { background: #2c2c2e; padding: 14px; border-radius: 12px; display: flex; align-items: center; justify-content: center; gap: 10px; color: #8e8e93; font-size: 0.9rem; margin: 10px 0; cursor: pointer; border: 2px solid transparent; transition: 0.2s; font-weight: bold; width: 100%; box-sizing: border-box; }
    .fav-toggle.active { border-color: #30d158; color: #30d158; background: rgba(48, 209, 88, 0.1); }
    input[type="checkbox"].hidden-check { display: none; }
    
    /* Progress Bars Elite */
    .progress-track { background: rgba(255,255,255,0.1); border-radius: 10px; height: 12px; width: 100%; margin: 8px 0 15px 0; overflow: hidden; }
    .progress-fill-c { background: linear-gradient(90deg, #0a84ff, #5e5ce6); height: 100%; border-radius: 10px; transition: width 0.8s cubic-bezier(0.2, 0.8, 0.2, 1); }
    .progress-fill-p { background: linear-gradient(90deg, #30d158, #32d74b); height: 100%; border-radius: 10px; transition: width 0.8s cubic-bezier(0.2, 0.8, 0.2, 1); }
</style>
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    conn = get_db_connection()
    today = datetime.now().strftime("%Y-%m-%d")
    
    if request.method == 'POST':
        f_name = request.form.get('food_name') or "Refeição"
        c_val = request.form.get('calories')
        p_val = request.form.get('protein')
        wants_to_save = request.form.get('save_fav')
        
        if c_val and p_val:
            now_time = datetime.now().strftime("%H:%M")
            conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp, date) VALUES (?, ?, ?, ?, ?)',
                         (f_name, int(c_val), int(p_val), now_time, today))
            if wants_to_save:
                conn.execute('INSERT OR REPLACE INTO favorites (food_name, calories, protein) VALUES (?, ?, ?)',
                             (f_name, int(c_val), int(p_val)))
            conn.commit()

    logs = conn.execute('SELECT * FROM logs WHERE date = ? ORDER BY id DESC', (today,)).fetchall()
    favs = conn.execute('SELECT * FROM favorites').fetchall()
    
    goal_c_row = conn.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()
    goal_p_row = conn.execute("SELECT value FROM settings WHERE key='protein_goal'").fetchone()
    
    goal_c = int(goal_c_row['value']) if goal_c_row else 3000
    goal_p = int(goal_p_row['value']) if goal_p_row else 150
    
    total_c = sum(log['calories'] for log in logs)
    total_p = sum(log['protein'] for log in logs)
    conn.close()

    pct_c = min((total_c / goal_c) * 100, 100) if goal_c > 0 else 0
    pct_p = min((total_p / goal_p) * 100, 100) if goal_p > 0 else 0

    color_c = "#30d158" if total_c >= goal_c else "#fff"
    color_p = "#30d158" if total_p >= goal_p else "#fff"

    html_favs = "".join([f"""<a href="/quick_add/{f['food_name']}/{f['calories']}/{f['protein']}" class="sug-item"><b>{f['food_name']}</b><br><span style="color:#8e8e93;">{f['calories']}k</span></a>""" for f in favs])
    html_logs = "".join([f"""
        <div class="log-item">
            <div style="text-align:left;"><b>{l['food_name']}</b><br><small style="color:#8e8e93;">{l['timestamp']}</small></div>
            <div>
                <a href="/edit_log/{l['id']}" style="color:#0a84ff; text-decoration:none; font-weight:bold; margin-right:15px; font-size:0.85rem;">EDITAR</a>
                <a href="/delete/{l['id']}" style="color:#ff453a; text-decoration:none; font-weight:bold; font-size:1.1rem;">✕</a>
            </div>
        </div>""" for l in logs])

    return f"""
    <!DOCTYPE html><html lang="pt">
    <head><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">{CSS}</head>
    <body>
        <div class="card" style="background: linear-gradient(145deg, #1c1c1e, #000); border: none; text-align: left;">
            <p style="color: #8e8e93; margin: 0; font-size: 0.8rem; font-weight: bold;">HOJE</p>
            
            <h1 style="font-size: 2.5rem; margin: 5px 0 0 0; color: {color_c}; transition: color 0.3s;">
                {total_c} <span style="font-size: 1rem; color: #8e8e93; font-weight: normal;">/ {goal_c} kcal</span>
            </h1>
            <div class="progress-track">
                <div class="progress-fill-c" style="width: {pct_c}%;"></div>
            </div>

            <p style="color: {color_p}; font-weight: bold; font-size: 1.1rem; margin: 10px 0 0 0; transition: color 0.3s;">
                {total_p} <span style="font-size: 0.9rem; color: #8e8e93; font-weight: normal;">/ {goal_p}g Proteína</span>
            </p>
            <div class="progress-track">
                <div class="progress-fill-p" style="width: {pct_p}%;"></div>
            </div>
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

@app.route('/edit_log/<int:log_id>', methods=['GET', 'POST'])
def edit_log(log_id):
    conn = get_db_connection()
    if request.method == 'POST':
        f_name = request.form.get('food_name')
        c_val = request.form.get('calories')
        p_val = request.form.get('protein')
        conn.execute('UPDATE logs SET food_name=?, calories=?, protein=? WHERE id=?', (f_name, int(c_val), int(p_val), log_id))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
        
    log = conn.execute('SELECT * FROM logs WHERE id=?', (log_id,)).fetchone()
    conn.close()
    
    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color: #8e8e93;">EDITAR DIÁRIO</h2>
        <div class="card">
            <p style="color:#8e8e93; font-size:0.8rem; margin-top:0;">Registado às {log['timestamp']}</p>
            <form method="POST">
                <input type="text" name="food_name" value="{log['food_name']}" required>
                <input type="number" name="calories" value="{log['calories']}" required>
                <input type="number" name="protein" value="{log['protein']}" required>
                <button type="submit" class="btn-main">ATUALIZAR REFEIÇÃO</button>
            </form>
            <a href="/" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a>
        </div>
    </body></html>
    """

@app.route('/build_meal', methods=['GET', 'POST'])
def build_meal():
    conn = get_db_connection()
    if request.method == 'POST':
        m_name = request.form.get('meal_name') or "Refeição"
        m_cal = request.form.get('total_cal')
        m_prot = request.form.get('total_prot')
        save_lib = request.form.get('save_lib')
        now_time = datetime.now().strftime("%H:%M")
        today = datetime.now().strftime("%Y-%m-%d")
        conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp, date) VALUES (?, ?, ?, ?, ?)', (m_name, int(m_cal), int(m_prot), now_time, today))
        if save_lib:
            conn.execute('INSERT OR REPLACE INTO favorites (food_name, calories, protein) VALUES (?, ?, ?)', (m_name, int(m_cal), int(m_prot)))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))

    favs = conn.execute('SELECT * FROM favorites').fetchall()
    conn.close()

    html_sugs = "".join([f"""<div onclick="addItem('{f['food_name']}', {f['calories']}, {f['protein']})" class="sug-item"><b>+ {f['food_name']}</b></div>""" for f in favs])

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color: #8e8e93;">MONTAR PRATO</h2>
        <div class="card" style="border-color: #30d158;">
            <h1 style="margin:0; font-size:2.5rem;"><span id="t_cal">0</span> <span style="font-size:1rem; color:#8e8e93;">kcal</span></h1>
            <p style="color:#30d158; font-weight:bold; margin:0;"><span id="t_prot">0</span>g Proteína</p>
            <p id="item_list" style="color:#8e8e93; font-size:0.8rem; margin-top:10px; min-height: 15px;"></p>
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
            <label class="fav-toggle" id="meal_fav_label">
                <input type="checkbox" name="save_lib" class="hidden-check" onchange="document.getElementById('meal_fav_label').classList.toggle('active');">
                <span>Guardar Refeição na Biblioteca?</span>
            </label>
            <button type="submit" class="btn-green">CONFIRMAR REFEIÇÃO</button>
        </form>
        <a href="/" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a>
        <script>
            let totalCal = 0; let totalProt = 0; let items = []; 
            function addItem(name, cal, prot) {{
                totalCal += parseInt(cal); totalProt += parseInt(prot); items.push(name); updateUI();
            }} 
            function addCustom() {{
                let n = document.getElementById('c_name').value || 'Extra'; 
                let c = document.getElementById('c_cal').value || 0; 
                let p = document.getElementById('c_prot').value || 0; 
                if(c > 0 || p > 0) addItem(n, c, p); 
                document.getElementById('c_name').value = ''; 
                document.getElementById('c_cal').value = ''; 
                document.getElementById('c_prot').value = '';
            }} 
            function updateUI() {{
                document.getElementById('t_cal').innerText = totalCal; 
                document.getElementById('t_prot').innerText = totalProt; 
                document.getElementById('form_cal').value = totalCal; 
                document.getElementById('form_prot').value = totalProt; 
                document.getElementById('item_list').innerText = items.join(' + ');
            }}
        </script>
    </body></html>
    """

@app.route('/history')
def history():
    conn = get_db_connection()
    days = conn.execute('''SELECT date, SUM(calories) as total_c, SUM(protein) as total_p FROM logs GROUP BY date ORDER BY date DESC LIMIT 30''').fetchall()
    
    goal_c_row = conn.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()
    goal_c = goal_c_row['value'] if goal_c_row else 3000
    
    conn.close()
    
    html_content = "".join([f"""
        <div class="log-item">
            <div style="text-align:left;"><b style="color:#0a84ff;">{datetime.strptime(d['date'], "%Y-%m-%d").strftime("%d %b")}</b></div>
            <div style="font-weight:bold;">{d['total_c']} <span style="font-size:0.8rem; color:#8e8e93;">/ {goal_c}k</span> | {d['total_p']}g P</div>
        </div>""" for d in days])
        
    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head>
    <body>
        <h2 style="color:#8e8e93; margin-bottom:30px;">DIAS PASSADOS</h2>
        {html_content or '<p style="color:#444;">Sem histórico.</p>'}
        <div class="nav-bar">
            <a href="/" class="nav-item"><span>🏠</span><br>HOJE</a>
            <a href="/history" class="nav-item active"><span>📅</span><br>HISTÓRICO</a>
            <a href="/manage_favs" class="nav-item"><span>⚙️</span><br>DEFINIÇÕES</a>
        </div>
    </body></html>
    """

@app.route('/manage_favs', methods=['GET', 'POST'])
def manage_favs():
    conn = get_db_connection()
    if request.method == 'POST':
        new_c = request.form.get('new_goal')
        new_p = request.form.get('new_p_goal')
        if new_c: conn.execute("UPDATE settings SET value=? WHERE key='daily_goal'", (new_c,))
        if new_p: conn.execute("UPDATE settings SET value=? WHERE key='protein_goal'", (new_p,))
        conn.commit()
        
    goal_c_row = conn.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()
    goal_p_row = conn.execute("SELECT value FROM settings WHERE key='protein_goal'").fetchone()
    
    goal_c = goal_c_row['value'] if goal_c_row else 3000
    goal_p = goal_p_row['value'] if goal_p_row else 150
    
    favs = conn.execute('SELECT * FROM favorites').fetchall()
    conn.close()
    
    html_favs = "".join([f"""
        <div class="log-item">
            <div style="text-align:left;"><b>{f['food_name']}</b><br><small style="color:#8e8e93;">{f['calories']}k | {f['protein']}g</small></div>
            <div>
                <a href="/edit_fav/{f['id']}" style="color:#0a84ff; text-decoration:none; font-weight:bold; margin-right:15px;">EDITAR</a>
                <a href="/delete_fav/{f['id']}" style="color:#ff453a; text-decoration:none; font-weight:bold;">✕</a>
            </div>
        </div>""" for f in favs])
        
    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head>
    <body>
        <div class="card">
            <h3 style="margin-top:0; color:#8e8e93;">OBJETIVOS (BULKING)</h3>
            <form method="POST">
                <div style="display:flex; gap:10px; margin-bottom:10px;">
                    <input type="number" name="new_goal" value="{goal_c}" placeholder="Meta Kcal" style="margin:0; width:50%;">
                    <input type="number" name="new_p_goal" value="{goal_p}" placeholder="Meta Prot" style="margin:0; width:50%;">
                </div>
                <button type="submit" class="btn-main" style="margin:0;">ATUALIZAR METAS</button>
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
        conn.execute('UPDATE favorites SET food_name=?, calories=?, protein=? WHERE id=?', (f_name, int(c_val), int(p_val), fav_id))
        conn.commit()
        conn.close()
        return redirect(url_for('manage_favs'))
        
    fav = conn.execute('SELECT * FROM favorites WHERE id=?', (fav_id,)).fetchone()
    conn.close()
    
    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head>
    <body>
        <h2 style="color:#8e8e93;">EDITAR ITEM</h2>
        <div class="card">
            <form method="POST">
                <input type="text" name="food_name" value="{fav['food_name']}" required>
                <input type="number" name="calories" value="{fav['calories']}" required>
                <input type="number" name="protein" value="{fav['protein']}" required>
                <button type="submit" class="btn-main">GUARDAR ALTERAÇÕES</button>
            </form>
            <a href="/manage_favs" style="display:block; margin-top:20px; color:#8e8e93; text-decoration:none;">Cancelar</a>
        </div>
    </body></html>
    """

@app.route('/quick_add/<name>/<int:c>/<int:p>')
def quick_add(name, c, p):
    conn = get_db_connection()
    now_time = datetime.now().strftime("%H:%M")
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp, date) VALUES (?, ?, ?, ?, ?)', (name, c, p, now_time, today))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/delete/<int:log_id>')
def delete_entry(log_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM logs WHERE id = ?', (log_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/delete_fav/<int:fav_id>')
def delete_fav(fav_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM favorites WHERE id = ?', (fav_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manage_favs'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')