import os
import mysql.connector
from dotenv import load_dotenv

# Carga las variables de entorno
load_dotenv()

def get_db_connection():
    """Establece y retorna una conexión a la base de datos."""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_DATABASE"),
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None