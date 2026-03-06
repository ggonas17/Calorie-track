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
    # Tabela do histórico diário
    conn.execute('''CREATE TABLE IF NOT EXISTS logs 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, food_name TEXT, calories INTEGER, protein INTEGER, timestamp TEXT)''')
    # Tabela para memória de refeições (Unique para não repetir nomes)
    conn.execute('''CREATE TABLE IF NOT EXISTS favorites 
                    (food_name TEXT PRIMARY KEY, calories INTEGER, protein INTEGER)''')
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def home():
    conn = get_db_connection()
    
    if request.method == 'POST':
        f_name = request.form.get('food_name') or "Refeição"
        c_input = request.form.get('calories')
        p_input = request.form.get('protein')
        
        if c_input and p_input:
            now = datetime.now().strftime("%H:%M")
            # Adiciona ao histórico
            conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp) VALUES (?, ?, ?, ?)',
                         (f_name, int(c_input), int(p_input), now))
            # Guarda nas favoritas/frequentes automaticamente
            conn.execute('INSERT OR REPLACE INTO favorites (food_name, calories, protein) VALUES (?, ?, ?)',
                         (f_name, int(c_input), int(p_input)))
            conn.commit()

    logs = conn.execute('SELECT * FROM logs ORDER BY id DESC').fetchall()
    favs = conn.execute('SELECT * FROM favorites LIMIT 5').fetchall() # Mostra as 5 mais recentes
    total_c = sum(log['calories'] for log in logs)
    total_p = sum(log['protein'] for log in logs)
    conn.close()

    return f"""
    <!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <title>Gona Tracker Elite</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; background: #000; color: #fff; text-align: center; padding: 20px; }}
            .card {{ background: #1c1c1e; border-radius: 20px; padding: 20px; margin-bottom: 20px; }}
            input {{ background: #2c2c2e; border: none; border-radius: 12px; color: #fff; padding: 15px; margin: 8px 0; width: 90%; font-size: 16px; }}
            button {{ background: #0a84ff; color: #fff; border: none; border-radius: 14px; padding: 18px; width: 100%; font-weight: bold; font-size: 16px; margin-top: 10px; }}
            .fav-chip {{ background: #3a3a3c; color: #0a84ff; padding: 10px 15px; border-radius: 20px; display: inline-block; margin: 5px; font-size: 13px; font-weight: 600; text-decoration: none; }}
            .log-item {{ display: flex; align-items: center; background: #1c1c1e; padding: 15px; border-radius: 15px; margin-bottom: 10px; border: 1px solid #2c2c2e; }}
            .log-info {{ flex-grow: 1; text-align: left; }}
            .del-btn {{ color: #ff453a; text-decoration: none; padding: 10px; font-size: 1.4rem; }}
            .total-val {{ font-size: 3rem; font-weight: 900; margin: 0; }}
            h3 {{ text-align: left; color: #8e8e93; font-size: 0.9rem; text-transform: uppercase; margin-left: 5px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <p style="color: #8e8e93; margin: 0;">Total de Hoje</p>
            <h1 class="total-val">{total_c} <span style="font-size: 1.2rem; font-weight: 400;">kcal</span></h1>
            <p style="color: #30d158; font-weight: bold; margin: 5px 0;">{total_p}g Proteína</p>
        </div>

        <div class="card">
            <h3>Refeições Frequentes</h3>
            <div style="text-align: left; margin-bottom: 15px;">
                {"".join([f'<a href="/quick_add/{f["food_name"]}/{f["calories"]}/{f["protein"]}" class="fav-chip">＋ {f["food_name"]}</a>' for f in favs])}
            </div>
            
            <form method="POST">
                <input type="text" name="food_name" placeholder="Nome (ex: Frango)">
                <div style="display: flex; gap: 10px;">
                    <input type="number" name="calories" placeholder="Kcal" required>
                    <input type="number" name="protein" placeholder="Prot" required>
                </div>
                <button type="submit">ADICIONAR NOVO</button>
            </form>
        </div>

        <h3>Histórico</h3>
        {"".join([f'''
            <div class="log-item">
                <div class="log-info">
                    <span style="font-weight: bold; display: block;">{log["food_name"]}</span>
                    <span style="font-size: 0.8rem; color: #8e8e93;">{log["timestamp"]} • {log["calories"]} kcal • {log["protein"]}g P</span>
                </div>
                <a href="/delete/{log["id"]}" class="del-btn">✕</a>
            </div>
        ''' for log in logs])}

        <a href="/reset" style="color: #444; text-decoration: none; font-size: 0.8rem; display: block; margin-top: 40px;">Reset Total</a>
    </body>
    </html>
    """

@app.route('/quick_add/<name>/<int:cal>/<int:prot>')
def quick_add(name, cal, prot):
    conn = get_db_connection()
    now = datetime.now().strftime("%H:%M")
    conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp) VALUES (?, ?, ?, ?)',
                 (name, cal, prot, now))
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
