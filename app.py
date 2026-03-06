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
    # Adicionamos 'food_name' à tabela
    conn.execute('''CREATE TABLE IF NOT EXISTS logs 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     food_name TEXT, 
                     calories INTEGER, 
                     protein INTEGER, 
                     timestamp TEXT)''')
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
            conn.execute('INSERT INTO logs (food_name, calories, protein, timestamp) VALUES (?, ?, ?, ?)',
                         (f_name, int(c_input), int(p_input), now))
            conn.commit()

    logs = conn.execute('SELECT * FROM logs ORDER BY id DESC').fetchall()
    total_c = sum(log['calories'] for log in logs)
    total_p = sum(log['protein'] for log in logs)
    conn.close()

    # O HTML com o novo input e o botão de apagar
    return f"""
    <!DOCTYPE html>
    <html lang="pt">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <title>CP Tracker Pro</title>
        <style>
            body {{ font-family: -apple-system, system-ui, sans-serif; background: #000; color: #fff; text-align: center; padding: 20px; }}
            .card {{ background: #1c1c1e; border-radius: 15px; padding: 20px; margin-bottom: 20px; }}
            input {{ background: #2c2c2e; border: none; border-radius: 10px; color: #fff; padding: 12px; margin: 5px; width: 85%; font-size: 16px; }}
            button {{ background: #0a84ff; color: #fff; border: none; border-radius: 12px; padding: 15px; width: 90%; font-weight: bold; margin-top: 10px; }}
            .log-item {{ display: flex; align-items: center; background: #1c1c1e; padding: 15px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #2c2c2e; }}
            .log-info {{ flex-grow: 1; text-align: left; }}
            .food-title {{ font-weight: bold; display: block; }}
            .food-stats {{ font-size: 0.8rem; color: #8e8e93; }}
            .del-btn {{ color: #ff453a; text-decoration: none; font-weight: bold; padding: 10px; font-size: 1.2rem; }}
            .total-val {{ font-size: 2.8rem; font-weight: bold; }}
            .reset-link {{ color: #8e8e93; text-decoration: none; font-size: 0.8rem; display: block; margin-top: 30px; opacity: 0.5; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2 style="margin:0; color: #8e8e93; font-size: 0.9rem; text-transform: uppercase;">Total do Dia</h2>
            <div class="total-val">{total_c} <span style="font-size: 1.2rem;">kcal</span></div>
            <div style="color: #30d158; font-weight: bold;">{total_p}g Proteína</div>
        </div>

        <div class="card">
            <form method="POST">
                <input type="text" name="food_name" placeholder="O que comeste? (ex: Frango)">
                <input type="number" name="calories" placeholder="Calorias" required>
                <input type="number" name="protein" placeholder="Proteína (g)" required>
                <button type="submit">ADICIONAR</button>
            </form>
        </div>

        <h3 style="text-align: left; margin-left: 10px; color: #8e8e93;">HISTÓRICO</h3>
        {"".join([f'''
            <div class="log-item">
                <div class="log-info">
                    <span class="food-title">{log["food_name"]}</span>
                    <span class="food-stats">{log["timestamp"]} • {log["calories"]} kcal • {log["protein"]}g P</span>
                </div>
                <a href="/delete/{log["id"]}" class="del-btn">✕</a>
            </div>
        ''' for log in logs])}

        <a href="/reset" class="reset-link" onclick="return confirm('Limpar tudo?')">Limpar Tudo</a>
    </body>
    </html>
    """

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