import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGURATION ---
# REPLACE THESE WITH YOUR REAL VALUES!
DB_HOST = "34.154.141.2"  # The "Public IP" from your Cloud SQL Overview page
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "runapp123"   # The password you created

def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    return conn

@app.route('/')
def home():
    return "RunApp Database Server is Online!"

# --- 1. SAVE USER ---
@app.route('/create_user', methods=['POST'])
def create_user():
    data = request.get_json()
    uid = data.get('uid')
    name = data.get('name')
    weight = data.get('weight')
    height = data.get('height')

    if not uid:
        return jsonify({"error": "Missing User ID"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # LOGIC CHANGE: 
        # ON CONFLICT (user_id) -> DO UPDATE
        # This updates the existing row instead of doing nothing.
        cur.execute("""
            INSERT INTO users (user_id, name, weight, height) 
            VALUES (%s, %s, %s, %s) 
            ON CONFLICT (user_id) 
            DO UPDATE SET 
                name = EXCLUDED.name,
                weight = EXCLUDED.weight,
                height = EXCLUDED.height
        """, (uid, name, weight, height))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ USER SYNCED: {name} (W:{weight} / H:{height})")
        return jsonify({"status": "success"}), 201

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        return jsonify({"error": str(e)}), 500
    
# --- 2. SAVE RUN ---
@app.route('/create_run', methods=['POST'])
def create_run():
    data = request.get_json()
    
    # Extract data
    uid = data.get('uid')
    timestamp = data.get('timestamp')
    duration = data.get('duration')
    distance = data.get('distance')
    calories = data.get('calories')
    speed = data.get('speed')
    path = str(data.get('path_points')) # Store as string (JSON)
    image_url = data.get('image_url')   # The link from Firebase Storage
    
    if not uid:
        return jsonify({"error": "Missing User ID"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            """
            INSERT INTO runs 
            (user_id, timestamp, duration, distance_km, calories, avg_speed, path_points, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (uid, timestamp, duration, distance, calories, speed, path, image_url)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ RUN SAVED: {distance}km for User {uid}")
        return jsonify({"status": "success"}), 201

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get_runs', methods=['GET'])
def get_runs():
    uid = request.args.get('uid')
    
    if not uid:
        return jsonify({"error": "Missing User ID"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get runs sorted by newest first
        cur.execute("""
            SELECT run_id, timestamp, duration, distance_km, calories, avg_speed, image_url 
            FROM runs 
            WHERE user_id = %s 
            ORDER BY timestamp DESC
        """, (uid,))
        
        rows = cur.fetchall()
        
        # Convert SQL rows to JSON list
        runs_list = []
        for row in rows:
            runs_list.append({
                "id": row[0],
                "timestamp": row[1],
                "duration": row[2],
                "distance": row[3],
                "calories": row[4],
                "speed": row[5],
                "image_url": row[6]
            })
            
        cur.close()
        conn.close()
        
        return jsonify(runs_list), 200

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        return jsonify({"error": str(e)}), 500
    
# --- 4. DELETE RUN ---
@app.route('/delete_run', methods=['DELETE'])
def delete_run():
    run_id = request.args.get('run_id')

    if not run_id:
        return jsonify({"error": "Missing Run ID"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # SQL DELETE Command
        cur.execute("DELETE FROM runs WHERE run_id = %s", (run_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"🗑️ RUN DELETED: ID {run_id}")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        return jsonify({"error": str(e)}), 500
 
# --- 5. SET/UPDATE WEEKLY GOAL ---
@app.route('/set_weekly_goal', methods=['POST'])
def set_weekly_goal():
    data = request.get_json()
    uid = data.get('uid')
    week_start = data.get('week_start_date') # Format: "YYYY-MM-DD"
    km = data.get('target_km')
    cal = data.get('target_calories')

    if not uid or not week_start:
        return jsonify({"error": "Missing User ID or Date"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Try to UPDATE first
        cur.execute("""
            UPDATE weekly_goals 
            SET target_km = %s, target_calories = %s 
            WHERE user_id = %s AND week_start_date = %s
        """, (km, cal, uid, week_start))
        
        # 2. If no row was updated, INSERT a new one
        if cur.rowcount == 0:
            cur.execute("""
                INSERT INTO weekly_goals (user_id, week_start_date, target_km, target_calories)
                VALUES (%s, %s, %s, %s)
            """, (uid, week_start, km, cal))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"🎯 GOAL SAVED: {km}km / {cal}kcal for {uid}")
        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        return jsonify({"error": str(e)}), 500

# --- 6. GET WEEKLY GOAL ---
@app.route('/get_weekly_goal', methods=['GET'])
def get_weekly_goal():
    uid = request.args.get('uid')
    week_start = request.args.get('week_start_date')

    if not uid:
        return jsonify({"error": "Missing User ID"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT target_km, target_calories 
            FROM weekly_goals 
            WHERE user_id = %s AND week_start_date = %s
        """, (uid, week_start))
        
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if row:
            return jsonify({
                "target_km": row[0],
                "target_calories": row[1]
            }), 200
        else:
            # --- CHANGED HERE ---
            # Return 404 so the Android App knows this user is new/has no goals!
            return jsonify({"error": "No goals found"}), 404 

    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/get_user', methods=['GET'])
def get_user():
    uid = request.args.get('uid')
    if not uid:
        return jsonify({"error": "Missing UID"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT name, weight, height FROM users WHERE user_id = %s", (uid,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            return jsonify({
                "name": row[0],
                "weight": float(row[1]) if row[1] else 70.0,
                "height": float(row[2]) if row[2] else 175.0
            }), 200
        else:
            return jsonify({"error": "User not found"}), 404
            
    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)