import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('tracker.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Logs diários
    conn.execute('''CREATE TABLE IF NOT EXISTS logs 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, calories INTEGER, protein INTEGER, timestamp TEXT, date TEXT)''')
    # Biblioteca de Favoritos
    conn.execute('''CREATE TABLE IF NOT EXISTS favorites 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, calories INTEGER, protein INTEGER)''')
    # Configurações (Para o objetivo diário)
    conn.execute('''CREATE TABLE IF NOT EXISTS settings 
                    (key TEXT PRIMARY KEY, value TEXT)''')
    # Define um objetivo de 2000 kcal por defeito se não existir
    conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_goal', '2000')")
    conn.commit()
    conn.close()

init_db()

# --- ESTILOS GLOBAIS ---
CSS = """
<style>
    body { font-family: -apple-system, sans-serif; background: #000; color: #fff; padding: 20px; text-align: center; padding-bottom: 90px; }
    .card { background: #1c1c1e; border-radius: 20px; padding: 20px; margin-bottom: 20px; border: 1px solid #2c2c2e; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
    .nav-bar { position: fixed; bottom: 0; left: 0; right: 0; background: rgba(28, 28, 30, 0.95); backdrop-filter: blur(10px); display: flex; justify-content: space-around; padding: 15px 0; border-top: 0.5px solid #3a3a3c; z-index: 100; }
    .nav-item { color: #8e8e93; text-decoration: none; font-size: 0.75rem; font-weight: 600; flex: 1; display: flex; flex-direction: column; align-items: center; }
    .nav-item.active { color: #0a84ff; }
    input { background: #2c2c2e; border: none; border-radius: 12px; color: #fff; padding: 15px; margin: 8px 0; width: 90%; font-size: 16px; -webkit-appearance: none; }
    .btn-main { background: #0a84ff; color: #fff; border: none; border-radius: 15px; padding: 16px; width: 100%; font-weight: bold; font-size: 16px; margin-top: 10px; cursor: pointer; }
    .sug-container { display: flex; overflow-x: auto; gap: 10px; padding: 10px 0; -webkit-overflow-scrolling: touch; scrollbar-width: none; }
    .sug-item { background: #2c2c2e; color: #0a84ff; padding: 12px 18px; border-radius: 18px; text-decoration: none; min-width: 110px; font-size: 0.85rem; border: 1px solid #3a3a3c; flex-shrink: 0; }
    .log-item { display: flex; justify-content: space-between; align-items: center; background: #1c1c1e; padding: 16px; border-radius: 18px; margin-bottom: 12px; border: 1px solid #2c2c2e; }
    .day-header { text-align: left; color: #8e8e93; font-size: 0.8rem; text-transform: uppercase; margin: 10px 5px; letter-spacing: 1px; }
    .fav-checkbox { display: flex; align-items: center; justify-content: center; gap: 10px; margin: 10px 0; color: #8e8e93; font-size: 0.9rem; }
    input[type="checkbox"] { width: 22px; height: 22px; accent-color: #0a84ff; }
    .badge-success { display: none; background: #30d158; color: #000; padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; margin-left: 10px; animation: popIn 0.3s ease; }
    @keyframes popIn { 0% { transform: scale(0); } 100% { transform: scale(1); } }
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
    goal = conn.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()['value']
    
    total_c = sum(log['calories'] for log in logs)
    total_p = sum(log['protein'] for log in logs)
    conn.close()

    # Muda a cor se passares do objetivo
    color_c = "#ff453a" if total_c > int(goal) else "#fff"

    return f"""
    <!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <meta name="apple-mobile-web-app-capable" content="yes">
        {CSS}
    </head>
    <body>
        <div class="card" style="background: linear-gradient(145deg, #1c1c1e, #000); border: none;">
            <p style="color: #8e8e93; margin: 0; font-size: 0.8rem;">HOJE</p>
            <h1 style="font-size: 3rem; margin: 5px 0; color: {color_c};">
                {total_c} <span style="font-size: 1.2rem; color: #8e8e93; font-weight: normal;">/ {goal} kcal</span>
            </h1>
            <p style="color: #30d158; font-weight: bold; font-size: 1.1rem; margin: 0;">{total_p}g Proteína</p>
        </div>

        <h3 class="day-header">Biblioteca</h3>
        <div class="sug-container">
            {"".join([f'<a href="/quick_add/{f["food_name"]}/{f["calories"]}/{f["protein"]}" class="sug-item"><b>{f["food_name"]}</b><br><span style="color:#8e8e93;">{f["calories"]}k</span></a>' for f in favs]) or '<p style="color:#444; font-size:0.8rem; margin-left:10px;">Sem favoritos guardados.</p>'}
        </div>

        <div class="card">
            <form method="POST">
                <input type="text" name="food_name" placeholder="O que comeste?">
                <div style="display: flex; gap: 10px;">
                    <input type="number" name="calories" placeholder="Kcal" required>
                    <input type="number" name="protein" placeholder="Proteína" required>
                </div>
                <div class="fav-checkbox">
                    <input type="checkbox" id="save_fav" name="save_fav" onchange="document.getElementById('badge').style.display = this.checked ? 'inline-block' : 'none';"> 
                    <label for="save_fav">Guardar na Biblioteca</label>
                    <span id="badge" class="badge-success">A GRAVAR! ✅</span>
                </div>
                <button type="submit" class="btn-main">ADICIONAR</button>
            </form>
        </div>

        <h3 class="day-header">Diário de Hoje</h3>
        {"".join([f'<div class="log-item"><div style="text-align:left;"><b>{l["food_name"]}</b><br><small style="color:#8e8e93;">{l["timestamp"]}</small></div><div>{l["calories"]}k | {l["protein"]}g <a href="/delete/{l["id"]}" style="color:#ff453a; text-decoration:none; margin-left:12px; font-weight:bold;">✕</a></div></div>' for l in logs])}

        <div class="nav-bar">
            <a href="/" class="nav-item active"><span>🏠</span><br>HOJE</a>
            <a href="/history" class="nav-item"><span>📅</span><br>HISTÓRICO</a>
            <a href="/manage_favs" class="nav-item"><span>⚙️</span><br>DEFINIÇÕES</a>
        </div>
    </body>
    </html>
    """

@app.route('/history')
def history():
    conn = get_db_connection()
    days = conn.execute('''SELECT date, SUM(calories) as total_c, SUM(protein) as total_p 
                           FROM logs GROUP BY date ORDER BY date DESC LIMIT 30''').fetchall()
    goal = conn.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()['value']
    conn.close()
    
    html_content = ""
    for d in days:
        date_obj = datetime.strptime(d['date'], "%Y-%m-%d")
        formatted_date = date_obj.strftime("%d %b")
        html_content += f"""
        <div class="log-item">
            <div style="text-align:left;"><b style="color: #0a84ff;">{formatted_date}</b></div>
            <div style="font-weight: bold;">{d['total_c']} <span style="font-size: 0.8rem; color: #8e8e93;">/ {goal}k</span> | {d['total_p']}g P</div>
        </div>
        """

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color: #8e8e93; margin-bottom: 30px;">DIAS PASSADOS</h2>
        {html_content or '<p style="color:#444;">Ainda não tens histórico.</p>'}
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
        new_goal = request.form.get('new_goal')
        if new_goal:
            conn.execute("UPDATE settings SET value = ? WHERE key = 'daily_goal'", (new_goal,))
            conn.commit()

    goal = conn.execute("SELECT value FROM settings WHERE key='daily_goal'").fetchone()['value']
    favs = conn.execute('SELECT * FROM favorites').fetchall()
    conn.close()
    
    html_favs = "".join([f'''
        <div class="log-item">
            <div style="text-align:left;"><b>{f["food_name"]}</b><br><small style="color:#8e8e93;">{f["calories"]}k | {f["protein"]}g</small></div>
            <div>
                <a href="/edit_fav/{f["id"]}" style="color:#0a84ff; text-decoration:none; font-weight:bold; margin-right: 15px;">EDITAR</a>
                <a href="/delete_fav/{f["id"]}" style="color:#ff453a; text-decoration:none; font-weight:bold;">✕</a>
            </div>
        </div>
    ''' for f in favs])

    return f"""
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <div class="card">
            <h3 style="margin-top:0; color:#8e8e93;">OBJETIVO DIÁRIO</h3>
            <form method="POST" style="display:flex; gap:10px;">
                <input type="number" name="new_goal" value="{goal}" style="margin:0;">
                <button type="submit" class="btn-main" style="margin:0; width:auto; padding:0 20px;">ATUALIZAR</button>
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
    <!DOCTYPE html><html lang="pt"><head><meta name="viewport" content="width=device-width, initial-scale=1.0">{CSS}</head><body>
        <h2 style="color: #8e8e93;">EDITAR ITEM</h2>
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