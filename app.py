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
    # Tabela principal
    conn.execute('''CREATE TABLE IF NOT EXISTS logs 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, calories INTEGER, protein INTEGER, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def home():
    conn = get_db_connection()
    if request.method == 'POST':
        f_name = request.form.get('food_name') or "Refeição"
        c_val = request.form.get('calories')
        p_val = request.form.get('protein')
        if c_val and p_val:
            now = datetime.now().strftime("%H:%M")
            conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp) VALUES (?, ?, ?, ?)',
                         (f_name, int(c_val), int(p_val), now))
            conn.commit()

    logs = conn.execute('SELECT * FROM logs ORDER BY id DESC').fetchall()
    # Puxa refeições únicas passadas para as sugestões
    suggestions = conn.execute('SELECT DISTINCT food_name, calories, protein FROM logs LIMIT 6').fetchall()
    
    total_c = sum(log['calories'] for log in logs)
    total_p = sum(log['protein'] for log in logs)
    conn.close()

    return f"""
    <!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <style>
            body {{ font-family: -apple-system, sans-serif; background: #000; color: #fff; padding: 20px; text-align: center; }}
            .card {{ background: #1c1c1e; border-radius: 20px; padding: 20px; margin-bottom: 20px; border: 1px solid #2c2c2e; }}
            .sug-container {{ display: flex; overflow-x: auto; gap: 10px; padding: 10px 0; }}
            .sug-item {{ background: #2c2c2e; color: #0a84ff; padding: 12px; border-radius: 15px; text-decoration: none; min-width: 100px; font-size: 0.8rem; border: 1px solid #3a3a3c; }}
            input {{ background: #2c2c2e; border: none; border-radius: 12px; color: #fff; padding: 15px; margin: 5px 0; width: 90%; font-size: 16px; }}
            button {{ background: #0a84ff; color: #fff; border: none; border-radius: 15px; padding: 18px; width: 100%; font-weight: bold; margin-top: 10px; }}
            .log-item {{ display: flex; justify-content: space-between; align-items: center; background: #1c1c1e; padding: 15px; border-radius: 15px; margin-bottom: 10px; border: 1px solid #2c2c2e; }}
        </style>
    </head>
    <body>
        <div class="card" style="background: linear-gradient(145deg, #1c1c1e, #000);">
            <h1 style="font-size: 3rem; margin: 0;">{total_c} <span style="font-size: 1rem; color: #8e8e93;">kcal</span></h1>
            <p style="color: #30d158; font-weight: bold; margin: 0;">{total_p}g Proteína</p>
        </div>

        <h3>Refeições Anteriores</h3>
        <div class="sug-container">
            {"".join([f'<a href="/quick_add/{s["food_name"]}/{s["calories"]}/{s["protein"]}" class="sug-item"><b>{s["food_name"]}</b><br>{s["calories"]}k</a>' for s in suggestions])}
        </div>

        <div class="card">
            <form method="POST">
                <input type="text" name="food_name" placeholder="Nome (ex: Frango)">
                <div style="display: flex; gap: 10px;">
                    <input type="number" name="calories" placeholder="Kcal" required>
                    <input type="number" name="protein" placeholder="Prot" required>
                </div>
                <button type="submit">ADICIONAR</button>
            </form>
        </div>

        <h3 style="text-align: left; color: #8e8e93;">Hoje</h3>
        {"".join([f'<div class="log-item"><div style="text-align:left;"><b>{l["food_name"]}</b><br><small style="color:#8e8e93;">{l["timestamp"]}</small></div><div>{l["calories"]}k | {l["protein"]}g <a href="/delete/{l["id"]}" style="color:#ff453a; text-decoration:none; margin-left:10px;">✕</a></div></div>' for l in logs])}
        
        <a href="/reset" style="color:#444; text-decoration:none; font-size:0.7rem; display:block; margin-top:30px;">Reset Total</a>
    </body>
    </html>
    """

@app.route('/quick_add/<name>/<int:c>/<int:p>')
def quick_add(name, c, p):
    conn = get_db_connection()
    now = datetime.now().strftime("%H:%M")
    conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp) VALUES (?, ?, ?, ?)', (name, c, p, now))
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

@app.route('/reset')
def reset():
    conn = get_db_connection()
    conn.execute('DELETE FROM logs')
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')