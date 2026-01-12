import sys
import serial
import time
import json
import csv
import os
import serial.tools.list_ports
import threading
import requests

# =========================
# CONFIGURAZIONE
# =========================

SERVER_URL = "http://192.168.1.6:5000/api/init_receiver"
FINISH_SESSION_URL = "http://192.168.1.6:5000/api/get_finish_session"
API_KEY = "CHIAVE_SEGRETA_CLIENT"

SEND_INTERVAL = 2  # secondi tra invii
CHECK_FINISH_INTERVAL = 5
MAX_WAIT_TIME = 5  # 300 tempo massimo per inserire il ricevitore

# =========================
# VARIABILI GLOBALI
# =========================

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

# =========================
# SERIAL INIT
# =========================

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

def serial_reader_loop():
    global ser, should_continue, MAX_WAIT_TIME

    ser = initSerial()
    send_to_server(connection_status)
    start_time = time.time()

    if not ser:
        return

    ser.write(b"begin")
    time.sleep(1)

    while should_continue:
        try:
            if ser and ser.is_open:
                send_to_server(connection_status)
                should_continue = False 
                time.sleep(SEND_INTERVAL)
            else:
                if time.time() - start_time > MAX_WAIT_TIME:
                    send_to_server('Dispositivo non rilevato entro 5 minuti')
                    should_continue = False
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

# =========================
# LETTURA SERIALE
# =========================

def read_data(ser):
    global latest_sensor_data

    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if not line:
        return

    try:
        data = json.loads(line)

        # ASSICURA ID
        data.setdefault("ID", "sensore_001")

        latest_sensor_data = data.copy()

        print("[DATI]", data)

        #save_data(data) SALVATAGGIO SU FILE CSV
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

    t1 = threading.Thread(target=serial_reader_loop, daemon=True)
    t2 = threading.Thread(target=check_finish_session, daemon=True)

    t1.start()
    t2.start()

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
