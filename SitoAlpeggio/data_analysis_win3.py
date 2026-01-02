import sys
import serial
import time
import json
import csv
import os
import serial.tools.list_ports
import threading
import requests
from flask import Flask, jsonify

# ==================== FLASK ====================
app = Flask(__name__)

# ==================== VARIABILI GLOBALI ====================
ser = None
should_continue = True

connection_status = {
    "connected": False,
    "port": None,
    "error": None,
    "last_check": None
}

latest_sensor_data = {}

# ==================== SERIALE ====================

def initSerial():
    global connection_status

    ports = list(serial.tools.list_ports.comports())
    connection_status["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")

    if not ports:
        connection_status.update({
            "connected": False,
            "port": None,
            "error": "Nessuna porta seriale trovata"
        })
        return None

    for port in ports:
        try:
            ser = serial.Serial(port.device, 115200, timeout=1)
            time.sleep(2)

            if ser.is_open:
                connection_status.update({
                    "connected": True,
                    "port": port.device,
                    "error": None
                })
                print(f"[SERIALE] Connesso a {port.device}")
                return ser

        except Exception as e:
            connection_status.update({
                "connected": False,
                "port": port.device,
                "error": str(e)
            })

    return None


def save_data(headers, values):
    filename = f"{values[0]}_data.csv"
    new_file = not os.path.exists(filename)

    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(headers)
        writer.writerow(values)


def read_data(ser):
    global latest_sensor_data

    try:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        data = json.loads(line)

        latest_sensor_data = data.copy()

        headers = list(data.keys()) + ["Time"]
        values = list(data.values()) + [time.strftime("%Y-%m-%d %H:%M:%S")]

        if headers[0] == "ID":
            save_data(headers, values)

    except json.JSONDecodeError:
        pass
    except Exception as e:
        print("[SERIALE] Errore lettura:", e)


def serial_reader_loop():
    global ser, should_continue

    while should_continue:
        if ser is None or not ser.is_open:
            print("[SERIALE] Tentativo connessione...")
            ser = initSerial()

            if ser:
                try:
                    ser.write(b"begin")
                except:
                    ser = None
            else:
                time.sleep(5)
                continue

        try:
            read_data(ser)
        except Exception:
            try:
                ser.close()
            except:
                pass
            ser = None
            time.sleep(5)

    if ser and ser.is_open:
        ser.close()

    print("[SERIALE] Thread terminato")

# ==================== API CONTROLLO ====================

def check_finish_session(api_url):
    global should_continue

    while should_continue:
        try:
            r = requests.get(api_url, timeout=3)
            if r.status_code == 200 and r.text.strip() == "Concluded":
                print("[API] Stop richiesto")
                should_continue = False
        except Exception:
            pass

        time.sleep(5)

# ==================== FLASK ENDPOINT ====================

@app.route("/")
def root():
    return jsonify({"service": "Serial Reader API", "status": "running"})


@app.route("/api/connection_status")
def api_connection_status():
    return jsonify(connection_status)


@app.route("/api/sensor_data")
def api_sensor_data():
    if latest_sensor_data:
        return jsonify({
            "status": "ok",
            "data": latest_sensor_data,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        })
    return jsonify({"status": "no_data"})


@app.route("/api/reconnect", methods=["POST"])
def api_reconnect():
    global ser

    try:
        if ser and ser.is_open:
            ser.close()
    except:
        pass

    ser = initSerial()
    if ser:
        try:
            ser.write(b"begin")
        except:
            pass

        return jsonify({"status": "ok"})
    return jsonify({"status": "error"})

# ==================== MAIN ====================

def main():
    finish_session_url = "http://localhost:5000/api/get_finish_session"

    print("[MAIN] Avvio thread seriale")
    serial_thread = threading.Thread(target=serial_reader_loop)
    serial_thread.start()

    print("[MAIN] Avvio thread controllo API")
    api_thread = threading.Thread(
        target=check_finish_session,
        args=(finish_session_url,)
    )
    api_thread.start()

    print("[MAIN] Avvio Flask su http://0.0.0.0:8000")

    try:
        app.run(
            host="0.0.0.0",
            port=8000,
            debug=False,
            use_reloader=False,
            threaded=False
        )
    finally:
        print("[MAIN] Arresto in corso...")
        global should_continue
        should_continue = False

        serial_thread.join()
        api_thread.join()

        if ser and ser.is_open:
            ser.close()

        print("[MAIN] Chiusura completa")

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    main()
