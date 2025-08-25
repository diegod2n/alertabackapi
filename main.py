import os
import sys  # Importa sys para manejar rutas de importación
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import mysql.connector
import datetime
import json
from werkzeug.utils import secure_filename
from database import get_db_connection

# --- Configuración para PythonAnywhere ---
# Añade la ruta del proyecto al path de Python si no está
project_path = '/home/dagahitone/alertabackapi'
if project_path not in sys.path:
    sys.path.append(project_path)

# Carga las variables de entorno
load_dotenv()
app = Flask(__name__)

# Configura los orígenes que pueden acceder a tu API
# En producción, solo deberías permitir el dominio de tu frontend
# Si el front y el back están en el mismo dominio (ej. myapp.com), no necesitas CORS
origins = [
    "http://localhost:5173",  # Para desarrollo local
    "http://127.0.0.1:5173",  # Para desarrollo local
    # Si tu frontend se despliega en 'tu-dominio.com', añade esa URL aquí
]
CORS(app, resources={r"/*": {"origins": origins}})

# Directorio para guardar las imágenes subidas
UPLOAD_FOLDER = 'uploads'
# En PythonAnywhere, la ruta de uploads debe ser absoluta
# y accesible desde el directorio de la aplicación web
full_upload_path = os.path.join(project_path, UPLOAD_FOLDER)
if not os.path.exists(full_upload_path):
    os.makedirs(full_upload_path)
app.config['UPLOAD_FOLDER'] = full_upload_path

# --- Funciones de Ayuda ---

def format_user_data(user_data):
    """
    Formatea los datos del usuario de un diccionario a un formato estandarizado.
    """
    # Se añade validación para evitar errores si los datos no existen
    if not user_data:
        return None
    return {
        "id": user_data.get("id"),
        "name": user_data.get("name"),
        "house_number": user_data.get("house_number"),
        "phone": user_data.get("phone"),
        "lat": user_data.get("lat"),
        "lng": user_data.get("lng")
    }

@app.get("/")
def read_root():
    return jsonify({"message": "API is running"})

# Endpoint para iniciar sesión
@app.post("/login/")
def login_user():
    data = request.json
    house_number = data.get("houseNumber") if data else None
    phone = data.get("phone") if data else None
    password = data.get("password") if data else None

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

        # Usar una verificación de hash para la contraseña es más seguro
        if user_data is None or user_data['password'] != password:
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
        # La consulta a la base de datos no usa 'user-'. Se corrige el valor
        cursor.execute("SELECT id, name, house_number, phone, lat, lng FROM users WHERE id = %s", (user_id,))
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
    
    if not data or not all([data.get("id"), data.get("name"), data.get("houseNumber"), data.get("phone"), data.get("password"), data.get("location")]):
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
            data.get('id'),
            data.get("name"),
            data.get("houseNumber"),
            data.get("phone"),
            data.get("password"),
            data.get("location").get("lat"),
            data.get("location").get("lng"),
        )
        cursor.execute(query, user_data)
        conn.commit()
        
        return jsonify({
            "id": data.get('id'),
            "name": data.get('name'),
            "houseNumber": data.get('houseNumber'),
            "phone": data.get('phone'),
            "location": data.get('location')
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
                "id": user_data["id"],
                "name": user_data["name"],
                "houseNumber": user_data["house_number"],
                "phone": user_data["phone"],
                "location": {"lat": user_data["lat"], "lng": user_data["lng"]}
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
    alert_type = request.form.get("type")
    description = request.form.get("description")
    user_id = request.form.get("user_id")
    location_json = request.form.get("location")
    image_file = request.files.get('image')

    if not all([alert_type, user_id, location_json]):
        return jsonify({"detail": "Faltan datos para crear la alerta"}), 400

    try:
        location = json.loads(location_json)
    except (json.JSONDecodeError, TypeError):
        return jsonify({"detail": "Datos de ubicación inválidos"}), 400
    
    conn = get_db_connection()
    if conn is None:
        return jsonify({"detail": "Error de conexión a la base de datos"}), 500

    cursor = conn.cursor(dictionary=True)
    try:
        image_url = None
        if image_file:
            filename = secure_filename(image_file.filename)
            # Usa la ruta de subida configurada para el entorno de producción
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)
            
            # La URL para acceder a la imagen debe ser relativa al dominio
            # Por ejemplo: https://dagahitone.pythonanywhere.com/uploads/imagen.jpg
            # Si tu app está en un subdominio: https://tusubdominio.pythonanywhere.com/uploads/imagen.jpg
            # La URL de PythonAnywhere es: http://dagahitone.pythonanywhere.com/
            image_url = f"/uploads/{filename}"

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

# Manejo de la ruta para servir imágenes estáticas
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

        user_ids = [member['user_id'] for member in user_ids_data]

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
        cursor.execute(query, tuple(user_ids))
        alerts_data = cursor.fetchall()
        
        if not alerts_data:
            return jsonify([]), 200
            
        formatted_alerts = []
        for alert_data in alerts_data:
            formatted_user = {
                "id": alert_data["user_id"],
                "name": alert_data["name"],
                "houseNumber": alert_data["house_number"],
                "phone": alert_data["phone"],
                "location": {"lat": alert_data["user_lat"], "lng": alert_data["user_lng"]}
            }
            
            # Ajusta la URL de la imagen para que sea relativa y funcione en producción
            image_url = alert_data["image"]
            if image_url and 'http://127.0.0.1:5173' in image_url:
                image_url = image_url.replace('http://127.0.0.1:5173', '')

            formatted_alert = {
                "id": alert_data["id"],
                "type": alert_data["type"],
                "description": alert_data["description"],
                "location": {"lat": alert_data["lat"], "lng": alert_data["lng"]},
                "image": image_url,
                "user_id": alert_data["user_id"],
                "timestamp": alert_data["timestamp"],
                "user": formatted_user
            }
            formatted_alerts.append(formatted_alert)

        return jsonify(formatted_alerts)
            
    except mysql.connector.Error as err:
        return jsonify({"detail": f"Error de base de datos: {str(err)}"}), 500
    finally:
        cursor.close()
        conn.close()

# Esto solo se usa en desarrollo local. PythonAnywhere no lo usa.
if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=5173)