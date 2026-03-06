
import sqlite3
from flask import Flask, render_template, request

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('tracker.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS stats (calories INTEGER, protein INTEGER)')
    # Check if we have a row, if not, create one
    c.execute('SELECT count(*) FROM stats')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO stats VALUES (0, 0)')
    conn.commit()
    conn.close()

init_db()

total_calories = 0
total_protein = 0

@app.route('/', methods=['GET', 'POST'])
def home():
    global total_calories, total_protein

    if request.method == 'POST':
        # Grab the data from the form names we set: "calories" and "protein"
        c_input = request.form.get('calories')
        p_input = request.form.get('protein')
        
        # Add them to our totals (int() converts the text to numbers)
        total_calories += int(c_input)
        total_protein += int(p_input)

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <title>CP Tracker</title>
    </head>
    <body style="font-family: sans-serif; text-align: center; background: #121212; color: white; padding-top: 50px;">
        <h1>🔥 Calorie Tracker</h1>
        <form method="POST">
            <input type="number" name="calories" placeholder="Calories" required style="padding: 10px; margin: 5px; border-radius: 5px;">
            <input type="number" name="protein" placeholder="Protein (g)" required style="padding: 10px; margin: 5px; border-radius: 5px;">
            <br>
            <button type="submit" style="padding: 10px 20px; border-radius: 10px; border: none; background: #007aff; color: white; margin-top: 10px;">
                Add "CP" Data
            </button>
        </form>
        <hr style="margin: 40px 20px; border: 0.5px solid #333;">
        <h2>Daily Totals:</h2>
        <p>Calories: {total_calories} | Protein: {total_protein}g</p>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')