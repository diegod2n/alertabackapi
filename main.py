import os
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import mysql.connector
import datetime
import json
from werkzeug.utils import secure_filename
from database import get_db_connection

# Carga las variables de entorno
load_dotenv()
app = Flask(__name__)

# Configura los orígenes que pueden acceder a tu API
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS(app, resources={r"/*": {"origins": origins}})

# Directorio para guardar las imágenes subidas
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Funciones de Ayuda ---

def format_user_data(user_data):
    """
    Formatea los datos del usuario de un diccionario a un formato estandarizado.
    """
    return {
        "id": user_data["id"],
        "name": user_data["name"],
        "house_number": user_data["house_number"],
        "phone": user_data["phone"],
        "lat": user_data["lat"],
        "lng": user_data["lng"]
    }

@app.get("/")
def read_root():
    return jsonify({"message": "API is running"})

# Endpoint para iniciar sesión
@app.post("/login/")
def login_user():
    data = request.json
    house_number = data.get("houseNumber")#type: ignore
    phone = data.get("phone")#type: ignore
    password = data.get("password")#type: ignore

    if not all([house_number, phone, password]):
        return jsonify({"detail": "Faltan datos de credenciales"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"detail": "Error de conexión a la base de datos"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT id, name, house_number, phone, password, lat, lng FROM users WHERE house_number = %s AND phone = %s",
            (house_number, phone)
        )
        user_data = cursor.fetchone()

        if user_data is None or user_data['password'] != password:#type: ignore
            return jsonify({"detail": "Credenciales incorrectas"}), 401
        
        formatted_user = format_user_data(user_data)

        return jsonify(formatted_user)
    except mysql.connector.Error as err:
        return jsonify({"detail": f"Error de base de datos: {str(err)}"}), 500
    finally:
        cursor.close()
        conn.close()

# Endpoint para obtener un solo usuario por ID
@app.get("/users/<string:user_id>")
def get_user(user_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({"detail": "Error de conexión a la base de datos"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name, house_number, phone, lat, lng FROM users WHERE id = %s", (f"user-{user_id}",))
        user_data = cursor.fetchone()
        
        if user_data is None:
            return jsonify({"detail": "User not found"}), 404
        
        formatted_user = format_user_data(user_data)

        return jsonify(formatted_user)
    except mysql.connector.Error as err:
        return jsonify({"detail": f"Error de base de datos: {str(err)}"}), 500
    finally:
        cursor.close()
        conn.close()

# Endpoint para crear un nuevo usuario
@app.post("/users/")
def create_user():
    data = request.json
    
    if not all([data.get("id"), data.get("name"), data.get("houseNumber"), data.get("phone"), data.get("password"), data.get("location")]):#type: ignore
        return jsonify({"detail": "Datos de usuario incompletos"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"detail": "Error de conexión a la base de datos"}), 500
    
    cursor = conn.cursor()
    try:
        query = """
        INSERT INTO users (id, name, house_number, phone, password, lat, lng)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        user_data = (
            data.get('id'),#type: ignore
            data.get("name"),#type: ignore
            data.get("houseNumber"),#type: ignore
            data.get("phone"),#type: ignore
            data.get("password"),#type: ignore
            data.get("location").get("lat"),#type: ignore
            data.get("location").get("lng"),#type: ignore
        )
        cursor.execute(query, user_data)
        conn.commit()
        
        return jsonify({
            "id": data.get('id'),#type: ignore
            "name": data.get('name'),#type: ignore
            "houseNumber": data.get('houseNumber'),#type: ignore
            "phone": data.get('phone'),#type: ignore
            "location": data.get('location')#type: ignore
        }), 201
    
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"detail": str(err)}), 400
    finally:
        cursor.close()
        conn.close()
        
# Endpoint para obtener todos los usuarios
@app.get("/users/")
def get_all_users():
    conn = get_db_connection()
    if conn is None:
        return jsonify({"detail": "Error de conexión a la base de datos"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, name, house_number, phone, lat, lng FROM users")
        users = cursor.fetchall()
        
        formatted_users = []
        for user_data in users:
            formatted_user = {
                "id": user_data["id"],#type: ignore
                "name": user_data["name"],#type: ignore
                "houseNumber": user_data["house_number"],#type: ignore
                "phone": user_data["phone"],#type: ignore
                "location": {"lat": user_data["lat"], "lng": user_data["lng"]}#type: ignore
            }
            formatted_users.append(formatted_user)
        return jsonify(formatted_users)
    except mysql.connector.Error as err:
        return jsonify({"detail": f"Error de base de datos: {str(err)}"}), 500
    finally:
        cursor.close()
        conn.close()

# Endpoint para crear una alerta
@app.post("/alerts/")
def create_alert():
    # ✅ Lógica correcta para manejar la carga de archivos y datos
    alert_type = request.form.get("type")
    description = request.form.get("description")
    user_id = request.form.get("user_id")
    location_json = request.form.get("location")
    image_file = request.files.get('image')

    if not all([alert_type, user_id, location_json]):
        return jsonify({"detail": "Faltan datos para crear la alerta"}), 400

    try:
        location = json.loads(location_json)#type: ignore
    except json.JSONDecodeError:
        return jsonify({"detail": "Datos de ubicación inválidos"}), 400
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({"detail": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        image_url = None
        if image_file:
            filename = secure_filename(image_file.filename)#type: ignore
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            
            image_url = f"http://127.0.0.1:5173/uploads/{filename}"

        query_alert = """
        INSERT INTO alerts (type, description, lat, lng, image, user_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        insert_data = (
            alert_type,
            description,
            location.get("lat"),
            location.get("lng"),
            image_url,
            user_id,
        )
        
        cursor.execute(query_alert, insert_data)
        conn.commit()
        last_id = cursor.lastrowid
        
        cursor.execute("SELECT id, name, house_number, phone, lat, lng FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            return jsonify({"detail": "User not found"}), 404
        
        formatted_user = format_user_data(user_data)
        
        response_data = {
            "id": last_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "type": alert_type,
            "description": description,
            "location": location,
            "image": image_url,
            "user_id": user_id,
            "user": formatted_user
        }
        return jsonify(response_data), 201
    
    except mysql.connector.Error as err:
        conn.rollback()
        return jsonify({"detail": f"Error de base de datos: {str(err)}"}), 400
    except Exception as e:
        return jsonify({"detail": f"Ocurrió un error inesperado: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Endpoint para obtener alertas por grupo
@app.get("/groups/<int:group_id>/alerts/")
def get_alerts_by_group(group_id):
    conn = get_db_connection()
    if conn is None:
        return jsonify({"detail": "Error de conexión a la base de datos"}), 500
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT user_id FROM user_group WHERE group_id = %s", (group_id,))
        user_ids_data = cursor.fetchall()
        
        if not user_ids_data:
            return jsonify([]), 200

        user_ids = [member['user_id'] for member in user_ids_data] #type: ignore

        placeholders = ', '.join(['%s'] * len(user_ids))
        query = f"""
            SELECT
                a.id, a.type, a.description, a.lat, a.lng, a.image, a.timestamp,
                u.id AS user_id, u.name, u.house_number, u.phone, u.lat AS user_lat, u.lng AS user_lng
            FROM alerts a
            JOIN users u ON a.user_id = u.id
            WHERE a.user_id IN ({placeholders})
            ORDER BY a.timestamp DESC
        """
        cursor.execute(query, tuple(user_ids))#type: ignore
        alerts_data = cursor.fetchall()
        
        if not alerts_data:
            return jsonify([]), 200
            
        formatted_alerts = []
        for alert_data in alerts_data:
            formatted_user = {
                "id": alert_data["user_id"],#type: ignore
                "name": alert_data["name"],#type: ignore
                "houseNumber": alert_data["house_number"],#type: ignore
                "phone": alert_data["phone"],#type: ignore
                "location": {"lat": alert_data["user_lat"], "lng": alert_data["user_lng"]}#type: ignore
            }
            
            formatted_alert = {
                "id": alert_data["id"],#type: ignore
                "type": alert_data["type"],#type: ignore
                "description": alert_data["description"],#type: ignore
                "location": {"lat": alert_data["lat"], "lng": alert_data["lng"]},#type: ignore
                "image": alert_data["image"],#type: ignore
                "user_id": alert_data["user_id"],#type: ignore
                "timestamp": alert_data["timestamp"],#type: ignore
                "user": formatted_user
            }
            formatted_alerts.append(formatted_alert)

        return jsonify(formatted_alerts)
            
    except mysql.connector.Error as err:
        return jsonify({"detail": f"Error de base de datos: {str(err)}"}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5173)