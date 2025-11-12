import sys
import serial
import time
import json
import csv
import os
import serial.tools.list_ports


def initSerial():
    """
    Inizializza automaticamente la connessione seriale con il dispositivo.
    Rileva la prima porta disponibile e tenta la connessione.
    
    Returns:
        serial.Serial | None: oggetto seriale se la connessione riesce, None in caso di errore.
    """
    try:
        ports = list(serial.tools.list_ports.comports())

        if not ports:
            print("Nessuna porta seriale trovata.", file=sys.stderr)
            return None

        # Usa la prima porta disponibile
        for port in ports:
            try:
                ser = serial.Serial(port.device, 115200, timeout=1)
                time.sleep(2)  # attesa breve per stabilizzare la connessione
                if ser.is_open:
                    print(f"sono connesso ({port.device})")
                    return ser
            except Exception as e:
                print(f"Errore connessione su {port.device}: {e}", file=sys.stderr)
                continue

        print("Errore: nessun dispositivo connesso.", file=sys.stderr)
        return None

    except Exception as e:
        print(f"Errore durante l'inizializzazione seriale: {e}", file=sys.stderr)
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
    ser.reset_input_buffer()
    line = ser.readline().decode('UTF-8', errors='ignore').strip()

    try:
        data = json.loads(line)
        list_title = []
        list_value = []
        print(data)

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


def main():
    # Inizializza la connessione seriale
    ser = initSerial()
    if ser is None:
        print("Impossibile stabilire la connessione seriale. Esco.")
        return

    # Avvia comunicazione
    time.sleep(1)
    ser.write("begin".encode('UTF-8'))

    while True:
        read_data(ser)


if __name__ == '__main__':
    main()