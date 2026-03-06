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
    # Tabela para o histórico
    conn.execute('CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, calories INTEGER, protein INTEGER, timestamp TEXT)')
    conn.commit()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def home():
    conn = get_db_connection()
    
    if request.method == 'POST':
        c_input = request.form.get('calories')
        p_input = request.form.get('protein')
        if c_input and p_input:
            now = datetime.now().strftime("%H:%M")
            conn.execute('INSERT INTO logs (calories, protein, timestamp) VALUES (?, ?, ?)',
                         (int(c_input), int(p_input), now))
            conn.commit()

    # Buscar tudo para calcular os totais e mostrar a lista
    logs = conn.execute('SELECT * FROM logs ORDER BY id DESC').fetchall()
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
        <title>CP Tracker</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica; background: #000; color: #fff; text-align: center; padding: 20px; }}
            .card {{ background: #1c1c1e; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); }}
            input {{ background: #2c2c2e; border: none; border-radius: 10px; color: #fff; padding: 12px; margin: 5px; width: 80%; font-size: 16px; }}
            button {{ background: #0a84ff; color: #fff; border: none; border-radius: 12px; padding: 15px; width: 85%; font-weight: bold; font-size: 16px; margin-top: 10px; }}
            .log-item {{ display: flex; justify-content: space-between; background: #2c2c2e; padding: 10px 15px; border-radius: 10px; margin-bottom: 8px; font-size: 14px; }}
            .total-val {{ font-size: 2.5rem; font-weight: bold; color: #fff; }}
            .reset-btn {{ color: #ff453a; text-decoration: none; font-size: 0.9rem; display: block; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2 style="margin-top:0; color: #8e8e93;">TOTAIS DE HOJE</h2>
            <div class="total-val">{total_c} <span style="font-size: 1rem; color: #8e8e93;">kcal</span></div>
            <div style="color: #30d158; font-weight: bold; font-size: 1.2rem;">{total_p}g Proteína</div>
        </div>

        <div class="card">
            <form method="POST">
                <input type="number" name="calories" placeholder="Calorias" required>
                <input type="number" name="protein" placeholder="Proteína (g)" required>
                <button type="submit">ADICIONAR REFEIÇÃO</button>
            </form>
        </div>

        <h3 style="text-align: left; margin-left: 10px; color: #8e8e93;">HISTÓRICO</h3>
        {"".join([f'<div class="log-item"><span>{log["timestamp"]}</span> <span>{log["calories"]} kcal</span> <span>{log["protein"]}g P</span></div>' for log in logs])}

        <a href="/reset" class="reset-btn">Limpar Histórico do Dia</a>
    </body>
    </html>
    """

@app.route('/reset')
def reset():
    conn = get_db_connection()
    conn.execute('DELETE FROM logs')
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')