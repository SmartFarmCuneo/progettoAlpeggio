import sys
import serial
import time
import json
import csv
import os
import serial.tools.list_ports
import threading
import requests
from datetime import datetime

SERVER_URL = "http://192.168.1.6:5000/api/init_receiver"
FINISH_SESSION_URL = "http://192.168.1.6:5000/api/get_finish_session"
API_KEY = "CHIAVE_SEGRETA_CLIENT"

SEND_INTERVAL = 2  # secondi tra invii
CHECK_FINISH_INTERVAL = 5
MAX_WAIT_TIME = 10  # 300 tempo massimo per inserire il ricevitore
FIRST_SEND_CONNECTION = True
MAX_TIME_SESSION = 60 # 7200 due ore massime dall'ultima ricezione di un sensore

BOT_TOKEN = "8303477409:AAEzEvqwd5-NZEG2WOlCJvA9J4DWRVBcaTA"

# URL API PER BOT
# https://api.telegram.org/bot8303477409:AAEzEvqwd5-NZEG2WOlCJvA9J4DWRVBcaTA/getMe
# https://api.telegram.org/bot8303477409:AAEzEvqwd5-NZEG2WOlCJvA9J4DWRVBcaTA/getUpdates

ser = None
should_continue = True
latest_sensor_data = {}

connection_status = {
    "type": "Connection", #tipo connection e sending_data
    "connected": False,
    "port": None,
    "error": None,
    "last_check": None
}

def get_chat_id():
    """
    Recupera automaticamente il CHAT_ID dell'ultimo utente che ha scritto al bot.
    Scrivi un messaggio al bot prima di eseguire questa funzione.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        
        if not data["result"]:
            print("Nessun messaggio trovato. Scrivi qualcosa al bot prima di chiamare questa funzione.")
            return None
        
        # Prende l'ultimo messaggio ricevuto
        last_msg = data["result"][-1]
        chat_id = last_msg["message"]["chat"]["id"]
        first_name = last_msg["message"]["chat"].get("first_name", "Unknown")
        
        print(f"CHAT_ID trovato: {chat_id} (utente: {first_name})")
        return chat_id
    
    except Exception as e:
        print("Errore nel recupero del CHAT_ID:", e)
        return None
    
CHAT_ID = get_chat_id()

def initSerial():
    global connection_status

    try:
        ports = list(serial.tools.list_ports.comports())

        if not ports:
            raise Exception("Nessuna porta seriale trovata")

        for port in ports:
            try:
                ser = serial.Serial(port.device, 115200, timeout=1)
                time.sleep(2)
                if ser.is_open:
                    print(f"[SERIALE] Connesso a {port.device}")
                    connection_status.update({
                        "type": "Connection",
                        "connected": True,
                        "port": port.device,
                        "error": None,
                        "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    return ser
            except Exception as e:
                continue

        raise Exception("Nessun dispositivo seriale valido")

    except Exception as e:
        connection_status.update({
            "type": "Connection",
            "connected": False,
            "port": None,
            "error": str(e),
            "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        print("[SERIALE] ERRORE:", e)
        return None

def send_to_server(data):
    try:
        requests.post(
            SERVER_URL,
            json=data,
            headers={"X-API-KEY": API_KEY},
            timeout=5
        )
        print("[SERVER] Dati inviati")
    except Exception as e:
        print("[SERVER] Errore invio:", e)

def send_desktop_notification(title, message):
    print("Invio notifica Telegram...")
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": message},
        timeout=5
    )
    print("Risposta Telegram:", r.status_code, r.text)

def serial_reader_loop():
    global ser, should_continue, MAX_WAIT_TIME, FIRST_SEND_CONNECTION, MAX_TIME_SESSION

    ser = initSerial()
    start_time = time.time()
    start_session_time = time.time()
    data = {}

    if ser:
        ser.write(b"begin")
    time.sleep(1)

    while should_continue:
        try:
            if ser and ser.is_open:
                if time.time() - start_session_time > MAX_TIME_SESSION: # DA PROVARE
                    print("Interruzione sessione dopo due ore dall'ultimo ricevimento")
                    data['type'] = 'Failed'
                    data['description'] = 'Mancata conclusione di tutti i sensori nella durata della sessione'
                    send_to_server(data)
                    should_continue = False
                    os._exit(0)

                if FIRST_SEND_CONNECTION:
                    send_to_server(connection_status)
                    FIRST_SEND_CONNECTION = False
                read_data(ser)
                time.sleep(SEND_INTERVAL)
            else:
                if time.time() - start_time > MAX_WAIT_TIME:
                    print('Dispositivo non rilevato entro 5 minuti')
                    data['type'] = 'Failed'
                    data['description'] = 'Dispositivo non rilevato entro 5 minuti'
                    send_to_server(data)
                    should_continue = False
                    os._exit(0)
                else:
                    print("[SERIALE] Riconnessione...")
                    time.sleep(5)
                    ser = initSerial()
                    send_to_server(connection_status)
                    if ser:
                        ser.write(b"begin")
        except Exception as e:
            print("[SERIALE] Errore:", e)
            time.sleep(5)

def read_data(ser):
    global latest_sensor_data

    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if not line:
        return

    try:
        data = json.loads(line)

        data['type'] = 'sending_data'
        data['date_conc_sens'] = datetime.now()

        latest_sensor_data = data.copy()

        print("[DATI]", data)

        #save_data(data) SALVATAGGIO SU FILE CSV
        #if data['ADC'] < 700: versione base invia solamente quando intercetta acqua
        #send_desktop_notification("⚠️ ALLARME SENSORE", "Acqua rilevata!")
        send_to_server(data)

    except json.JSONDecodeError:
        print("[LOG]", line)
        with open("log.csv", "a", encoding="utf-8") as f:
            f.write(line + "\n")

def check_finish_session():
    global should_continue

    while should_continue:
        try:
            r = requests.get(FINISH_SESSION_URL, timeout=3)
            if r.status_code == 200 and r.text.strip() == "Concluded":
                print("[SERVER] STOP ricevuto")
                should_continue = False
                if ser and ser.is_open:
                    ser.close()
                os._exit(0)
        except Exception as e:
            print("[SERVER] Errore check:", e)

        time.sleep(CHECK_FINISH_INTERVAL)

def main():
    print("[CLIENT] Avvio client sensore")
    #get_chat_id()

    t1 = threading.Thread(target=serial_reader_loop, daemon=True)
    t2 = threading.Thread(target=check_finish_session, daemon=True)

    t1.start()
    t2.start()

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
