import math
from datetime import datetime, timedelta
from .db_connection import get_db_connection

def haversine(lat1, lon1, lat2, lon2):
    # distanza in km tra due coordinate
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * \
        math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def get_campi(current_user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM fields f, users u WHERE f.id_user = u.id_u AND u.username = %s", (current_user,))
    num_campi = cursor.fetchone()['COUNT(*)']
    conn.close()
    return num_campi

def get_info_campi(current_user):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT coordinate, comune FROM users u, fields f WHERE u.username = %s AND u.id_u = f.id_user ", (current_user,))
        risultato = cursor.fetchall()
        info = ""
        for i in range(0, len(risultato)):
            info += str(risultato[i]["coordinate"]) + "/" + str(risultato[i]
                                                                ["comune"]) + "|"
        return info
    
    
def get_sensor(current_user):
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id_u FROM users WHERE username = %s", (current_user,))
        result = cursor.fetchone()
        id_user = result['id_u']

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT s.nome_sens, s.Node_Id, s.stato_sens FROM sensor s, assoc_users_sens aus WHERE aus.id_utente = %s AND s.id_sens = aus.id_sens",
            (id_user,))
        risultato = cursor.fetchall()
        info = ""
        for i in range(len(risultato)):
            info += str(risultato[i]["nome_sens"]) + "/" + str(risultato[i]
                                                               ["Node_Id"]) + "/" + str(risultato[i]["stato_sens"]) + "|"
        print(f"Info: {info}")
        if info == '':
            return "nessuna info"
        else:
            return info

# FUNZIONANTE
def get_user_id(username): 
    #ritorna l'id dell'utente dallo username
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id_u FROM users "
        "WHERE username = %s ",
        (username,)
    )
    id = cursor.fetchone()
    cursor.close()
    conn.close()
    return id['id_u']

# DA TESTARE  
def get_data_info(id_user):
    # VERSIONE BASE
    # prende una sola ricerca, si può fare un'irrigazione alla volta
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT d.id_ricerca, d.id_t
        FROM data d
        WHERE d.id_u = %s
        AND d.data_fine_irr IS NULL
        ORDER BY d.data_inizio_irr DESC
        LIMIT 1;
        """,
        (id_user,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    id_ricerca = row['id_ricerca']
    id_field = row['id_t']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.Node_id
        FROM assoc_sens_data a, sensor s
        WHERE a.id_data = %s
        AND a.id_sens = s.id_sens;
        """,
        (id_ricerca,)
    )
    sensors = cursor.fetchall()
    cursor.close()
    conn.close()
    #if row is None:
        #return None, None
    return id_ricerca, id_field, sensors

def set_state_sensor(state, sensor_id):
    # setta lo stato del sensore
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sensor SET stato_sens = %s WHERE Node_ID = %s",
        (state, sensor_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    
# FUNZIONATE
def insert_sensor_data(data, sensors, id_data):
    # funzione per salvare su db le info
    # risultato di data --> {"Node_id":"ID010000","INDEX":0,"Bat":670"Humidity":57.00,"Temperature":22.80,"ADC":831}
    print(f"Sensore: {data['Node_id']}")
    print(f"Sensori tuoi: {sensors}")
    if any(s['Node_id'] == data['Node_id'] for s in sensors):
        print("INSERIMENTO")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE assoc_sens_data SET date_conc_sens = %s, idx = %s, Bat = %s,"
            "Humidity = %s, Temperature = %s, ADC = %s WHERE id_data = %s AND Node_id = %s",
            (datetime.now(), data['INDEX'], data['Bat'], data['Humidity'],
             data['Temperature'], data['ADC'], id_data, data['Node_id'])
        )
        conn.commit()
        cursor.close()
        set_state_sensor("C", data['Node_id'])
        
        
def get_coordinate(field_id):
    #ritorna le coordinate di un campo
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT coordinate FROM fields "
        "WHERE id_t = %s ",
        (field_id,)
    )
    coor = cursor.fetchone()
    cursor.close()
    conn.close()
    return coor['coordinate']