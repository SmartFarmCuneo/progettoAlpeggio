from .db_connection import get_db_connection

def get_sensor2(user_id):
    # DA RICONTROLLARE SIMILE AL get_sensor()
    # ritorna i sensori dell'utente
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
                        SELECT *
                        FROM sensor s
                        JOIN assoc_users_sens aus ON s.id_sens = aus.id_sens
                        WHERE aus.id_utente = %s
                    """, (user_id,))
    sensori = cursor.fetchall()
    cursor.close()
    conn.close()
    return sensori

def get_campi(current_user):
    """Restituisce il numero di campi dell'utente"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM fields f 
                INNER JOIN users u ON f.id_user = u.id_u 
                WHERE u.username = %s
            """, (current_user,))
            result = cursor.fetchone()
            return result['count'] if result else 0
    except Exception as e:
        print(f"Errore nel conteggio campi: {e}")
        return 0
    finally:
        conn.close()

def get_info_campi(current_user):
    """Restituisce informazioni sui campi dell'utente"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT f.coordinate, f.comune 
                FROM fields f 
                INNER JOIN users u ON f.id_user = u.id_u 
                WHERE u.username = %s 
                ORDER BY f.id_t
            """, (current_user,))
            risultato = cursor.fetchall()

            info_parts = []
            for campo in risultato:
                coord = campo["coordinate"] if campo["coordinate"] else "N/A"
                comune = campo["comune"] if campo["comune"] else "N/A"
                info_parts.append(f"{coord}/{comune}")

            return "|".join(info_parts)
    except Exception as e:
        print(f"Errore nel recupero info campi: {e}")
        return ""
    finally:
        conn.close()