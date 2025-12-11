import sys
import serial
import time
import json
import csv
import os
import serial.tools.list_ports
import threading
import requests
from flask import Flask, jsonify, request


"""
STATO CONNESSIONE SERIALE:
Connesso: False
Porta: None
Errore: Nessuna porta seriale trovata.
Ultimo controllo: 2025-12-10 19:20:51
"""

# Inizializza Flask
app = Flask(__name__)

# Variabili globali
ser = None
connection_status = {
    "connected": False,
    "port": None,
    "error": None,
    "last_check": None
}
latest_sensor_data = {}
should_continue = True  # Flag per controllare l'esecuzione


def initSerial():
    """
    Inizializza automaticamente la connessione seriale con il dispositivo.
    Rileva la prima porta disponibile e tenta la connessione.
    
    Returns:
        serial.Serial | None: oggetto seriale se la connessione riesce, None in caso di errore.
    """
    global connection_status
    
    try:
        ports = list(serial.tools.list_ports.comports())

        if not ports:
            error_msg = "Nessuna porta seriale trovata."
            print(error_msg, file=sys.stderr)
            connection_status.update({
                "connected": False,
                "port": None,
                "error": error_msg,
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            return None

        # Usa la prima porta disponibile
        for port in ports:
            try:
                ser = serial.Serial(port.device, 115200, timeout=1)
                time.sleep(2)  # attesa breve per stabilizzare la connessione
                if ser.is_open:
                    print(f"sono connesso ({port.device})")
                    connection_status.update({
                        "connected": True,
                        "port": port.device,
                        "error": None,
                        "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    return ser
            except Exception as e:
                error_msg = f"Errore connessione su {port.device}: {e}"
                print(error_msg, file=sys.stderr)
                connection_status.update({
                    "connected": False,
                    "port": port.device,
                    "error": str(e),
                    "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                continue

        error_msg = "Errore: nessun dispositivo connesso."
        print(error_msg, file=sys.stderr)
        connection_status.update({
            "connected": False,
            "port": None,
            "error": error_msg,
            "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        return None

    except Exception as e:
        error_msg = f"Errore durante l'inizializzazione seriale: {e}"
        print(error_msg, file=sys.stderr)
        connection_status.update({
            "connected": False,
            "port": None,
            "error": str(e),
            "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        return None


def save_data(list_title, list_value):
    filename = str(list_value[0]) + "_data.csv"
    title_flag = 0

    if os.path.exists(filename):
        print('Old sensor')
    else:
        print('New sensor')
        title_flag = 1

    with open(filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        if title_flag == 1:
            writer.writerow(list_title)
        writer.writerow(list_value)


def read_data(ser):
    global latest_sensor_data
    
    ser.reset_input_buffer()
    line = ser.readline().decode('UTF-8', errors='ignore').strip()

    try:
        data = json.loads(line)
        list_title = []
        list_value = []
        print(data)

        # Salva gli ultimi dati del sensore
        latest_sensor_data = data.copy()

        for key in data:
            list_title.append(key)
            list_value.append(data[key])

        time_str = time.strftime("%Y-%m-%d %H:%M:%S ", time.localtime())
        print(time_str)
        print(list_title)
        print(list_value)

        list_value.append(time_str)
        list_title.append("Time")

        if list_title[0] == "ID":
            save_data(list_title, list_value)

    except json.JSONDecodeError:
        print("LOG:", line)
        with open("log.csv", "a", encoding="utf-8") as file:
            file.write(line + "\n")


def check_finish_session(api_url):
    """
    Controlla l'API finish_session ogni 5 secondi.
    Se ritorna qualcosa diverso da "Continue", ferma l'esecuzione.
    """
    global should_continue
    
    while should_continue:
        try:
            response = requests.get(api_url, timeout=3)
            if response.status_code == 200:
                result = response.text.strip()
                print(f"[CHECK API] Risposta: {result}")
                
                if result == "Concluded":
                    print("=" * 60)
                    print(f"STOP RICHIESTO! API ha ritornato: {result}")
                    print("Chiusura del programma in corso...")
                    print("=" * 60)
                    should_continue = False
                    
                    # Chiudi la connessione seriale
                    global ser
                    if ser and ser.is_open:
                        ser.close()
                        print("Connessione seriale chiusa.")
                    
                    # Termina il programma
                    os._exit(0)
            else:
                print(f"[CHECK API] Errore HTTP: {response.status_code}")
        
        except requests.exceptions.RequestException as e:
            print(f"[CHECK API] Errore nella chiamata: {e}")
        
        # Aspetta 5 secondi prima del prossimo controllo
        time.sleep(5)


def serial_reader_loop():
    """Loop che legge continuamente dalla porta seriale"""
    global ser, should_continue
    
    # Inizializza la connessione seriale
    ser = initSerial()
    if ser is None:
        print("Impossibile stabilire la connessione seriale.")
        return

    # Avvia comunicazione
    time.sleep(1)
    ser.write("begin".encode('UTF-8'))

    while should_continue:
        try:
            if ser and ser.is_open:
                read_data(ser)
            else:
                # Tenta di riconnettersi
                print("Connessione persa, tentativo di riconnessione...")
                time.sleep(5)
                ser = initSerial()
                if ser:
                    ser.write("begin".encode('UTF-8'))
        except Exception as e:
            print(f"Errore nel loop di lettura: {e}")
            connection_status.update({
                "connected": False,
                "error": str(e),
                "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            time.sleep(5)
    
    # Chiudi la porta seriale quando esce dal loop
    if ser and ser.is_open:
        ser.close()
    print("Thread seriale terminato.")


# ==================== API ENDPOINTS ====================

@app.route('/api/connection_status', methods=['GET'])
def get_connection_status():
    """
    Ritorna lo stato della connessione seriale
    
    Returns:
        JSON con:
        - connected: bool (True se connesso)
        - port: str (porta COM utilizzata)
        - error: str (messaggio di errore se presente)
        - last_check: str (timestamp ultimo controllo)
    """
    return jsonify(connection_status)


@app.route('/api/sensor_data', methods=['GET'])
def get_sensor_data():
    """
    Ritorna gli ultimi dati ricevuti dal sensore
    """
    if latest_sensor_data:
        return jsonify({
            "status": "ok",
            "data": latest_sensor_data,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    else:
        return jsonify({
            "status": "no_data",
            "message": "Nessun dato disponibile",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })


@app.route('/api/reconnect', methods=['POST'])
def reconnect_serial():
    """
    Forza un tentativo di riconnessione alla porta seriale
    """
    global ser
    
    if ser and ser.is_open:
        ser.close()
    
    ser = initSerial()
    
    if ser:
        ser.write("begin".encode('UTF-8'))
        return jsonify({
            "status": "ok",
            "message": "Riconnessione riuscita",
            "connection_status": connection_status
        })
    else:
        return jsonify({
            "status": "error",
            "message": "Riconnessione fallita",
            "connection_status": connection_status
        })


@app.route('/', methods=['GET'])
def root():
    """Endpoint root con informazioni base"""
    return jsonify({
        "service": "Serial Reader API",
        "status": "running",
        "endpoints": {
            "connection_status": "/api/connection_status",
            "sensor_data": "/api/sensor_data",
            "reconnect": "/api/reconnect (POST)"
        }
    })


def main():
    """Avvia il server Flask"""
    # URL dell'API da controllare (MODIFICA QUESTO con il tuo URL)
    finish_session_url = "http://localhost:5000/api/get_finish_session"
    
    print("Avvio thread seriale...")
    serial_thread = threading.Thread(target=serial_reader_loop, daemon=True)
    serial_thread.start()
    
    print("Avvio thread controllo API finish_session...")
    check_thread = threading.Thread(target=check_finish_session, args=(finish_session_url,), daemon=True)
    check_thread.start()
    
    print("Avvio server Flask su http://0.0.0.0:8000")
    # Avvia il server Flask
    try:
        app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\nInterruzione da tastiera ricevuta.")
        should_continue = False
        if ser and ser.is_open:
            ser.close()
        sys.exit(0)


if __name__ == '__main__':
    main()