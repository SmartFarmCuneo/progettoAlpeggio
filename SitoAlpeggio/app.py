from flask import Flask, render_template, redirect, url_for, request, make_response
from flask import session, jsonify, render_template_string, current_app
from functools import wraps, lru_cache
import jwt
import requests
import subprocess
import os
import json
import smtplib
import random
import re
import stripe
import sys
import time
from dotenv import load_dotenv
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from flask_mail import Message, Mail

from utils.db_connection import get_db_connection
from utils.hash_password import hash_password
from utils.stripe_function import *
from utils.sensor_function import *
from utils.field_function import *

load_dotenv()

############### GLOBALI ####################
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_DIR = os.path.join(BASE_DIR, "static", "json")

############################################

############################ Flask app setup ######################################
app = Flask(__name__)
# SECRET_KEY
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "default_secret")

# Config mail
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['MAIL_DEFAULT_SENDER'] = (
    os.getenv("MAIL_SENDER_NAME", "Agritech"),
    os.getenv("MAIL_SENDER_EMAIL", "tuoaccount@gmail.com")
)

app.config['STRIPE_PUBLIC_KEY'] = os.getenv('STRIPE_PUBLIC_KEY', 'pk_test_...')
app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY', 'sk_test_...')
app.config['STRIPE_WEBHOOK_SECRET'] = os.getenv(
    'STRIPE_WEBHOOK_SECRET', 'whsec_...')

stripe.api_key = app.config['STRIPE_SECRET_KEY']

###############################################################################
# -----------------------------------------------------
# Context processor per passare il consenso a tutti i template
# -----------------------------------------------------
@app.context_processor
def inject_cookie_consent():
    consent_cookie = request.cookies.get("cookie_consent")
    if consent_cookie:
        try:
            consent = json.loads(consent_cookie)
        except Exception:
            consent = None
    else:
        consent = None
    return {"cookie_consent": consent}

# -----------------------------------------------------
# Endpoint per settare il consenso (chiamato dal banner)
# -----------------------------------------------------
@app.route("/set-consent", methods=["POST"])
def set_consent():
    # semplice validazione della richiesta
    if not request.is_json:
        return jsonify({"error": "Richiesta non valida"}), 400
    data = request.get_json()

    # Expected structure: {"necessary": true, "analytics": false, "ads": false}
    # Normalizza
    consent = {
        "necessary": bool(data.get("necessary", False)),
        "analytics": bool(data.get("analytics", False)),
        "ads": bool(data.get("ads", False)),
        "timestamp": datetime.now().isoformat() + "Z"
    }

    resp = make_response(jsonify({"status": "ok", "consent": consent}))

    # In sviluppo usa secure=False per lavorare su http locale.
    # In produzione DEVI settare secure=True (cookie inviabili su HTTP non sicuro).
    secure_flag = False if current_app.debug else True

    resp.set_cookie(
        "cookie_consent",
        json.dumps(consent),
        max_age=60 * 60 * 24 * 7,  # 1 settimana
        httponly=False,   # deve essere leggibile da JS per mostrare/nascondere banner
        secure=secure_flag,
        samesite="Lax"
    )
    return resp

# -----------------------------------------------------
# Endpoint per leggere lo stato del consenso (opzionale, utile per JS)
# -----------------------------------------------------
@app.route("/get-consent", methods=["GET"])
def get_consent():
    consent_cookie = request.cookies.get("cookie_consent")
    if consent_cookie:
        try:
            consent = json.loads(consent_cookie)
        except Exception:
            consent = {"necessary": False, "analytics": False, "ads": False}
    else:
        consent = {"necessary": False, "analytics": False, "ads": False}
    return jsonify(consent)

# -----------------------------------------------------
# Endpoint per revocare il consenso (utile nel footer “Gestisci cookie”)
# -----------------------------------------------------
@app.route("/revoke-consent", methods=["POST"])
def revoke_consent():
    resp = make_response(jsonify({"status": "revoked"}))
    secure_flag = False if current_app.debug else True
    resp.set_cookie(
        "cookie_consent",
        "",
        max_age=0,
        httponly=False,
        secure=secure_flag,
        samesite="Lax"
    )
    return resp

def get_user_data(username):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cursor.fetchone()
    conn.close()


def plan_feature_required(feature):
    """Decorator per controllare se l'utente ha accesso a una funzionalità"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                return redirect(url_for('login'))

            limits = get_user_plan_limits(current_user)
            if not limits:
                return redirect(url_for('pagamenti'))

            # Controlla se l'utente ha accesso alla funzionalità
            if not limits.get(feature, False):
                return render_template('upgrade_required.html',
                                       feature=feature,
                                       current_plan=limits.get('plan_name', 'free'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

############################## FUNZIONE INVIO MAIL #############################
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True

mail = Mail(app)

def send_reset_email(user_email, code):
    msg = Message("Agrinnov - Reset Password", recipients=[user_email])

    msg.html = render_template_string("""
    <!DOCTYPE html>
    <html lang="it">
    <head>
      <meta charset="UTF-8" />
      <style>
        body {
          font-family: "Segoe UI", Arial, sans-serif;
          background-color: #1a202c;
          color: #fff;
          margin: 0;
          padding: 0;
        }
        .container {
          max-width: 600px;
          margin: 0 auto;
          background: #2d3748;
          border-radius: 12px;
          overflow: hidden;
          box-shadow: 0 4px 15px rgba(0,0,0,0.4);
        }
        .header {
          background: linear-gradient(135deg, #2d3748, #1a202c);
          padding: 20px;
          text-align: center;
        }
        .header img {
          max-width: 100px;
          margin-bottom: 10px;
        }
        .content {
          padding: 30px;
          text-align: center;
        }
        h1 {
          color: #48bb78;
          font-size: 22px;
          margin-bottom: 20px;
        }
        p {
          color: #cbd5e0;
          font-size: 16px;
          line-height: 1.5;
        }
        .code {
          display: inline-block;
          background: #1a202c;
          color: #48bb78;
          font-size: 24px;
          font-weight: bold;
          padding: 15px 25px;
          margin: 20px 0;
          border-radius: 8px;
          border: 2px solid #48bb78;
        }
        .footer {
          background: #1a202c;
          text-align: center;
          padding: 15px;
          font-size: 12px;
          color: #cbd5e0;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
            <img rel="icon" href="../static/image/logo.png" />
        </div>
        <div class="content">
          <h1>Richiesta reset password</h1>
          <p>Ciao, abbiamo ricevuto la tua richiesta di reimpostare la password.</p>
          <p>Usa questo codice per procedere:</p>
          <div class="code">{{ code }}</div>
          <p>Se non hai richiesto tu il reset, ignora questa email.</p>
        </div>
        <div class="footer">
          &copy; 2024 Agrinnov - Innovazione per l'agricoltura del futuro
        </div>
      </div>
    </body>
    </html>
    """, code=code)

    try:
        mail.send(msg)
        print("✅ Email inviata correttamente")
        return True
    except Exception as e:
        print("❌ Errore invio mail:", e)
        return False
########################### Context Processor #########################
@app.context_processor
def inject_user():
    token = request.cookies.get("token")
    if not token:
        return {"user": None}
    try:
        decoded = jwt.decode(
            token, app.config["SECRET_KEY"], algorithms=["HS256"])
        current_user = decoded["user"]
        user = get_user_data(current_user)
        return {"user": user}
    except Exception:
        return {"user": None}
########################################################################

########################### Login-Create account #########################

@app.route('/login', methods=['GET', 'POST'])
def login():

    error = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        remember_me = request.form.get("rememberMe") is not None
        psw = hash_password(password)

        conn = get_db_connection()
        with conn.cursor() as cursor:
            try:
                cursor.execute(
                    "SELECT password_hash FROM users WHERE username = %s", (username,))
                p_user = cursor.fetchone()
            finally:
                conn.close()

        if p_user and p_user["password_hash"] == psw:
            # session['id_data'] = 0
            response = make_response(redirect(url_for("home")))
            if remember_me:
                return generate_and_set_token(response, username, durata=24*7)
            else:
                return generate_and_set_token(response, username)
        else:
            error = "Nome utente o password errati."

    return render_template("login.html", error=error)

# IMPLEMENTARE FUNZIONE PREMIUM TELEGRAM
@app.route('/registrati', methods=['GET', 'POST'])
def registrati():
    error = ""
    if request.method == 'POST':
        nome = request.form['nome']
        cognome = request.form['cognome']
        email = request.form['email']
        cod_fiscale = request.form['cod_fiscale']
        telefono = request.form['telefono']
        anno = request.form['birthYear']
        mese = request.form['birthMonth']
        giorno = request.form['birthDay']
        data_nascita = f"{anno}-{mese}-{giorno}"
        username = request.form['username']
        password = request.form['password']
        # username_tg = request.form['tg_username']

        psw = hash_password(password)

        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                if user:
                    error = "Username già presente"
                else:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, email, telefono, nome, cognome, cod_fiscale, DataDiNascita) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (username, psw, email, telefono, nome,
                         cognome, cod_fiscale, data_nascita)
                    )
                    connection.commit()

                return redirect(url_for('login'))
        except Exception as e:
            error = "Errore del database"
        finally:
            connection.close()

    return render_template('registrati.html', error=error)


#Login API per app mobile (ritorna JSON invece di fare redirect)
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"status": "error", "message": "Dati mancanti"}), 400

    username = data['username']
    password = data['password']
    psw = hash_password(password)

    conn = get_db_connection()
    with conn.cursor() as cursor:
        try:
            cursor.execute(
                "SELECT password_hash FROM users WHERE username = %s", (username,))
            p_user = cursor.fetchone()
        finally:
            conn.close()

    if p_user and p_user["password_hash"] == psw:
        return jsonify({
            "status": "success",
            "message": "Login effettuato",
            "user": username
        }), 200
    else:
        return jsonify({"status": "error", "message": "Credenziali errate"}), 401
    
# Implementazione API per registrazione android
@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"status": "error", "message": "Dati mancanti"}), 400

    username = data['username']
    password = data['password']
    email = data['email']
    telefono = data['telefono']
    nome = data['nome']
    cognome = data['cognome']
    cod_fiscale = data['cod_fiscale']
    data_nascita = data['data_nascita']

    psw = hash_password(password)

    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if user:
                return jsonify({"status": "error", "message": "Username già presente"}), 400
            else:
                cursor.execute(
                    "INSERT INTO users (username, password_hash, email, telefono, nome, cognome, cod_fiscale, DataDiNascita) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (username, psw, email, telefono, nome,
                     cognome, cod_fiscale, data_nascita)
                )
                connection.commit()

        return jsonify({"status": "success", "message": "Registrazione effettuata"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": "Errore del database"}), 500
    finally:
        connection.close()

##################################################################################

################################ Cookie-Token ####################################
def generate_token(username):
    payload = {
        "user": username,
        "exp": datetime.now() + timedelta(hours=1)
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

def generate_and_set_token(response, username, durata=1):
    token = generate_token(username)
    response.set_cookie("token", token, max_age=3600, httponly=True)
    return response

def token_required(f):
    """Decorator per route web (legge token dai cookie)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")
        if not token:
            return redirect(url_for("login"))
        try:
            decoded = jwt.decode(
                token, app.config["SECRET_KEY"], algorithms=["HS256"])
            kwargs["current_user"] = decoded["user"]
        except jwt.ExpiredSignatureError:
            return redirect(url_for("login"))
        except jwt.InvalidTokenError:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def api_token_required(f):
    """Decorator per API (legge token dall'header X-Token)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        token = request.headers.get("X-Token")
        
        # Verifica API key
        if api_key != "CHIAVE_SEGRETA_CLIENT":
            return jsonify({"error": "API Key non valida"}), 401
        
        # Verifica token JWT
        if not token:
            return jsonify({"error": "Token mancante"}), 401
        
        try:
            decoded = jwt.decode(
                token, app.config["SECRET_KEY"], algorithms=["HS256"])
            kwargs["current_user"] = decoded["user"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token scaduto"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token non valido"}), 401
        
        return f(*args, **kwargs)
    return decorated
################################################################################

########################### RESET PASSWORD #####################################
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    message = ""
    if request.method == "POST":
        email = request.form["email"]

        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT username FROM users WHERE email=%s", (email,))
            user = cursor.fetchone()

        if user:
            otp = str(random.randint(100000, 999999))  # codice a 6 cifre
            session["reset_otp"] = otp
            session["reset_user"] = user["username"]

            if send_reset_email(email, otp):
                return redirect(url_for("verify_code"))
            else:
                message = "Errore durante l'invio della mail."
        else:
            message = "Email non trovata."

    return render_template("forgot_password.html", message=message)

@app.route("/verify_code", methods=["GET", "POST"])
def verify_code():
    error = ""
    if request.method == "POST":
        code = request.form["otp"]
        if code == session.get("reset_otp"):
            return redirect(url_for("reset_password"))
        else:
            error = "Codice errato."

    return render_template("verify_code.html", error=error)

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    error = ""
    username = session.get("reset_user")
    if not username:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form["password"]
        confirm = request.form["confirm"]

        if password != confirm:
            error = "Le password non coincidono."
        else:
            psw_hashed = hash_password(password)
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET password_hash=%s WHERE username=%s",
                    (psw_hashed, username),
                )
                conn.commit()

            # pulizia sessione
            session.pop("reset_otp", None)
            session.pop("reset_user", None)

            return redirect(url_for("login"))

    return render_template("reset_password.html", error=error)

################################################################################

################# FUNZIONI BARRA SINISTRA ####################
# VERSIONE BASE
@app.route('/storici', methods=['GET', 'POST'])
@token_required
def storici(current_user):
    risultato = ""
    campo_selezionato = ""

    conn = get_db_connection()

    # preselezione da home
    campo_id = request.args.get('campo_id')
    if campo_id:
        campo_selezionato = campo_id

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM data WHERE id_t = %s AND id_u = %s",
                (session[f"campo{campo_selezionato}"], session["id"])
            )
            risultato = cursor.fetchall()

    if request.method == 'POST':
        if request.form.get('action-ricercaSt') == 'Ricerca':
            campo_selezionato = request.form["selezionato"][-1]

            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM data WHERE id_t = %s AND id_u = %s",
                    (session[f"campo{campo_selezionato}"], session["id"])
                )
                risultato = cursor.fetchall()

        elif request.form.get('action-dettagli') == 'dettagli':
            id_ricerca = request.form.get('id_ricerca')

            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM assoc_sens_data WHERE id_data = %s",
                    (id_ricerca,)
                )
                dettaglio = cursor.fetchall()

            return render_template(
                'dettagli_storico.html',
                dettagli=dettaglio
            )

    return render_template(
        'storici.html',
        info=risultato,
        campo=campo_selezionato
    )

@app.route('/dettagli_storici', methods=['GET', 'POST'])
@token_required
def dettagli_storici(current_user):
    pass

@app.route('/aggiungiCampo', methods=['GET', 'POST'])
@token_required
def aggiungiCampo(current_user):
    error = ""
    coordinate = session.get('coordinate', None)

    # Inizializza sempre le variabili
    provincia = ""
    comune = ""
    cap = ""

    # Se coordinate ci sono (dalla mappa), ricava automaticamente comune/provincia/CAP
    if coordinate:
        try:
            
            #import requests --> già fatto sopra
            res = requests.get(
                url_for('get_location_by_coords',
                        lat=coordinate['lat'], lon=coordinate['lon'], _external=True)
            )
            if res.status_code == 200:
                loc = res.json()
                provincia = loc.get('provincia', "")
                comune = loc.get('comune', "")
                cap = loc.get('cap', "")
        except Exception as e:
            print("Errore fetch location:", e)

    if request.method == 'POST':
        # Se l’utente modifica i campi, sovrascrivi
        provincia = request.form.get('provincia', provincia)
        comune = request.form.get('comune', comune)
        cap = request.form.get('cap', cap)

        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id_u FROM users WHERE username=%s", (current_user,))
                user_db = cursor.fetchone()
                if not user_db:
                    error = "Utente non trovato."
                    return render_template('aggiungi_campo.html', error=error)
                user_id = user_db["id_u"]

                # Salvataggio coordinate come stringa "raw" se esistono
                coord_str = coordinate['raw'] if coordinate and 'raw' in coordinate else None

                cursor.execute(
                    "INSERT INTO fields (id_user, provincia, comune, CAP, coordinate) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (user_id, provincia, comune, cap, coord_str)
                )
                connection.commit()
                # Pulisci sessione dopo salvataggio
                session.pop('coordinate', None)
                return redirect(url_for('home'))
        except Exception as e:
            error = f"Errore del database: {str(e)}"
            print("Errore durante l'inserimento:", e)
        finally:
            connection.close()

    print("Rendering aggiungiCampo con:",
          coordinate, provincia, comune, cap, error)

    return render_template(
        'aggiungi_campo.html',
        coordinate=coordinate,
        provincia=provincia,
        comune=comune,
        cap=cap,
        error=error
    )

@app.route('/salva-coordinate', methods=['POST'])
def salvaCoordinate():
    coordinate = request.form.get('coordinate')  # stringa dal frontend

    # Validazione base: almeno due coordinate e formato corretto
    matches = re.findall(
        r'\((-?\d+(?:\.\d+)?),\s*(-?\d+(?:\.\d+)?)\)', coordinate)
    if len(matches) < 2:
        print("Coordinate non valide o insufficienti")
        session['coordinate'] = None
        return redirect(url_for('aggiungiCampo'))

    # Salvataggio della stringa completa come è, con la virgola finale
    if not coordinate.endswith(','):
        coordinate += ','

    # Calcolo del centroide solo per uso interno
    lats = [float(lat) for lat, lon in matches]
    lons = [float(lon) for lat, lon in matches]
    centro_lat = sum(lats) / len(lats)
    centro_lon = sum(lons) / len(lons)

    # Salva in sessione sia il centroide che la stringa completa
    session['coordinate'] = {
        'lat': centro_lat,
        'lon': centro_lon,
        'raw': coordinate  # <-- questa è la stringa da salvare in DB
    }

    return redirect(url_for('aggiungiCampo'))

@app.route('/api/get_session_coordinate')
def get_session_coordinate():
    return jsonify(session.get('coordinate', {}))

@app.route('/mappa', methods=['GET', 'POST'])
@token_required
def mappa(current_user):
    return render_template('mappa.html')

#CORRETTO
@app.route('/insert_sensori', methods=['GET', 'POST'])
@token_required
def insert_sensori(current_user):
    if request.method == 'POST':
        campo_id   = request.form.get('campo_id')
        sensore_id = request.form.get('sensore_id')
        lat        = request.form.get('lat')
        lng        = request.form.get('lng')
        filare     = request.form.get('filare')
        #print("ciao")
        #print(lat, lng, filare, sensore_id)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE sensor
                SET filare=%s, latitude=%s, longitude=%s, accuracy=0
                WHERE id_sens=%s
                """,
                (filare, lat, lng, sensore_id)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("Errore DB:", e)
        finally:
            cursor.close()
            conn.close()
        return redirect(url_for('gestioneCampo', campo_id=campo_id))
        #return redirect(url_for('insert_sensori', campo_id=campo_id))

    campo_id = request.args.get('campo_id')
    user_id  = get_user_id(current_user)
    sensori  = get_sensor2(user_id)
    return render_template('insert_sensori.html', sensori=sensori, campo_id=campo_id,
                           coordinate_campo=get_coordinate(campo_id))

@app.route("/api/campi-utente")
@token_required
def api_campi_utente(current_user):
    """Restituisce tutti i campi dell'utente con i loro dettagli"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT f.id_t, f.provincia, f.comune, f.CAP, f.coordinate 
                FROM fields f 
                INNER JOIN users u ON f.id_user = u.id_u 
                WHERE u.username = %s 
                ORDER BY f.id_t
            """, (current_user,))
            campi = cursor.fetchall()
            return jsonify(campi)
    except Exception as e:
        print(f"Errore nel recupero campi utente: {e}")
        return jsonify({"error": "Errore interno del server"}), 500
    finally:
        conn.close()

@app.route("/api/campo/<int:campo_id>")
@token_required
def api_dettaglio_campo(current_user, campo_id):
    """Restituisce i dettagli di un campo specifico"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Verifica che il campo appartenga all'utente
            cursor.execute("""
                SELECT f.id_t, f.provincia, f.comune, f.CAP, f.coordinate,
                       u.username
                FROM fields f 
                INNER JOIN users u ON f.id_user = u.id_u 
                WHERE f.id_t = %s AND u.username = %s
            """, (campo_id, current_user))

            campo = cursor.fetchone()
            if not campo:
                return jsonify({"error": "Campo non trovato"}), 404

            return jsonify(campo)
    except Exception as e:
        print(f"Errore nel recupero dettaglio campo: {e}")
        return jsonify({"error": "Errore interno del server"}), 500
    finally:
        conn.close()

@app.route('/gestioneCampo', methods=['GET', 'POST'])
@token_required
def gestioneCampo(current_user):
    """Gestisce la modifica e cancellazione dei campi"""
    if request.method == 'GET':
        return render_template('gestione_campo.html')

    if request.method == 'POST':
        action = request.form.get('action')
        campo_id = request.form.get('campoSelezionato')

        if not campo_id:
            return redirect(url_for('gestioneCampo'))

        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                # Verifica che il campo appartenga all'utente
                cursor.execute("""
                    SELECT f.id_t FROM fields f 
                    INNER JOIN users u ON f.id_user = u.id_u 
                    WHERE f.id_t = %s AND u.username = %s
                """, (campo_id, current_user))

                if not cursor.fetchone():
                    return redirect(url_for('gestioneCampo'))

                if action == 'delete':
                    # Elimina il campo
                    cursor.execute(
                        "DELETE FROM fields WHERE id_t = %s", (campo_id,))
                    conn.commit()
                    return redirect(url_for('home'))

                elif action == 'save':
                    # Aggiorna il campo
                    provincia = request.form.get('provincia')
                    comune = request.form.get('comune')
                    cap = request.form.get('zip')

                    cursor.execute("""
                        UPDATE fields 
                        SET provincia = %s, comune = %s, CAP = %s
                        WHERE id_t = %s
                    """, (provincia, comune, cap, campo_id))
                    conn.commit()

                    return redirect(url_for('gestioneCampo'))
                
                elif action == 'insert_sensori':
                    return redirect(url_for('insert_sensori', campo_id=campo_id))

        except Exception as e:
            print(f"Errore nella gestione campo: {e}")
            return redirect(url_for('gestioneCampo'))
        finally:
            conn.close()

    return redirect(url_for('gestioneCampo'))

@app.route('/gestione_sensori', methods=['POST', 'GET'])
@token_required
def gestione_sensori(current_user):
    conn = get_db_connection()
    user = None
    sensori = []
    try:
        with conn.cursor() as cursor:
            user_id = get_user_id(current_user)

            if request.method == 'POST':
                action = request.form.get('action')

                # A) AGGIUNGI SENSORE
                if action == 'aggiungi':
                    node_id_input = request.form.get('id_sensore', '').strip()
                    nome_sens = request.form.get(
                        'nome_sensore', '').strip()

                    if not node_id_input:
                        sensori = get_sensor2(user_id)
                        return render_template('gestione_sensori.html',
                                               user=user,
                                               sensori=sensori,
                                               error='invalid')

                    cursor.execute(
                        "SELECT id_sens FROM sensor WHERE Node_id = %s", (node_id_input,))
                    sensor_row = cursor.fetchone()

                    id_sens_db = None

                    if sensor_row:
                        # Il sensore esiste già, prendiamo il suo ID numerico (PK)
                        id_sens_db = sensor_row['id_sens']
                    else:
                        # Il sensore non esiste, lo creiamo nella tabella 'sensor'
                        # Default: stato 'O' (Operativo) e posizione vuota
                        cursor.execute("""
                            INSERT INTO sensor (Node_id, stato_sens, nome_sens)
                            VALUES (%s, 'C', %s)
                        """, (node_id_input, nome_sens))
                        conn.commit()
                        id_sens_db = cursor.lastrowid

                    # 2. Verifica se è GIÀ associato a questo utente
                    cursor.execute("""
                        SELECT id FROM assoc_users_sens 
                        WHERE id_utente = %s AND id_sens = %s
                    """, (user_id, id_sens_db))
                    existing_assoc = cursor.fetchone()

                    if existing_assoc:
                        sensori = get_sensor2(user_id)
                        return render_template('gestione_sensori.html',
                                               user=user,
                                               sensori=sensori,
                                               error='duplicate')

                    cursor.execute("""
                        INSERT INTO assoc_users_sens (id_utente, id_sens)
                        VALUES (%s, %s)
                    """, (user_id, id_sens_db))

                    conn.commit()

                    sensori = get_sensor2(user_id)
                    return render_template('gestione_sensori.html',
                                           user=user,
                                           sensori=sensori,
                                           success='added')

                elif action == 'elimina':
                    id_sens_to_delete = request.form.get(
                        'id_sensore', '').strip()

                    if not id_sens_to_delete:
                        sensori = get_sensor2(user_id)
                        return render_template('gestione_sensori.html',
                                               user=user,
                                               sensori=sensori,
                                               error='invalid')

                    # Elimina l'associazione dalla tabella assoc_users_sens
                    cursor.execute("""
                        DELETE FROM assoc_users_sens 
                        WHERE Node_id = %s AND id_utente = %s
                    """, (id_sens_to_delete, user_id))

                    affected_rows = cursor.rowcount
                    conn.commit()

                    # Recupera lista aggiornata
                    sensori = get_sensor2(user_id)
                    if affected_rows > 0:
                        return render_template('gestione_sensori.html',
                                               user=user,
                                               sensori=sensori,
                                               success='deleted')
                    else:
                        return render_template('gestione_sensori.html',
                                               user=user,
                                               sensori=sensori,
                                               error='not_found')

                elif action == 'sospendi':
                    id_sens_to_suspend = request.form.get(
                        'id_sensore', '').strip()
                    set_state_sensor('S', id_sens_to_suspend)
                    # print("Prova")
                    # print(get_sensor(current_user))
                    sensori = get_sensor2(user_id)
                    return render_template('gestione_sensori.html',
                                           user=user,
                                           sensori=sensori,
                                           success='suspend')

                elif action == 'riattiva':
                    id_sens_to_activate = request.form.get(
                        'id_sensore', '').strip()
                    set_state_sensor('C', id_sens_to_activate)
                    sensori = get_sensor2(user_id)
                    return render_template('gestione_sensori.html',
                                           user=user,
                                           sensori=sensori,
                                           success='activate')
                
                elif action == 'modifica':
                    #DA FARE
                    id_sens = request.form.get('id_sensore', '').strip()
                    pass

            sensori = get_sensor2(user_id)
            # print("sensori corretti: " + str(sensori))
    except Exception as e:
        print(f"Errore nella gestione sensori: {e}")
        import traceback
        traceback.print_exc()

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM users WHERE username = %s", (current_user,))
                user = cursor.fetchone()
        except:
            pass

        return render_template('gestione_sensori.html',
                               user=user,
                               sensori=[],
                               error='generic')
    finally:
        conn.close()
    return render_template('gestione_sensori.html', user=user, sensori=sensori)


@app.route('/visualizzaCampi', methods=['GET', 'POST'])
@token_required
def visualizzaCampi(current_user):
    return render_template('visualizzaCampi.html')

################################################################

############################# STRIPE ROUTES #############################
@app.route('/pagamenti', methods=['GET', 'POST'])
@token_required
def pagamenti(current_user):
    """Pagina dei piani abbonamento con dati completamente dinamici"""
    subscription_info = get_user_subscription_info(current_user)

    # Recupera i piani da Stripe
    plans = get_all_plans_from_stripe()

    return render_template('pagamenti.html',
                           stripe_public_key=app.config['STRIPE_PUBLIC_KEY'],
                           subscription_info=subscription_info,
                           plans=plans)

@app.route("/api/plans", methods=["GET"])
@token_required
def api_get_plans(current_user):
    """
    Restituisce tutti i piani recuperati dinamicamente da Stripe
    """
    try:
        user_info = get_user_subscription_info(current_user)

        # Normalizza il piano corrente
        current_plan = "free"
        if user_info and user_info.get("subscription_plan"):
            try:
                current_plan = str(
                    user_info["subscription_plan"]).strip().lower()
            except Exception:
                pass

        # Recupera tutti i piani da Stripe
        plans = get_all_plans_from_stripe()

        return jsonify({
            "current_plan": current_plan,
            "plans": plans
        })

    except Exception as e:
        print(f"Errore in /api/plans: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Errore nel recupero dei piani"}), 500

@app.route('/create-checkout-session', methods=['POST'])
@token_required
def create_checkout_session(current_user):
    """Crea una sessione di checkout con validazione dinamica"""
    try:
        data = request.get_json()
        plan_key = data.get('plan')

        if not plan_key or plan_key == 'free':
            return jsonify({'error': 'Piano non valido'}), 400

        # Recupera il piano da Stripe
        plan = get_plan_by_key(plan_key)

        if not plan or not plan.get('stripe_price_id'):
            return jsonify({'error': 'Piano non trovato o non configurato'}), 404

        # Recupera o crea il customer Stripe
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT stripe_customer_id, email FROM users WHERE username = %s",
                (current_user,)
            )
            user = cursor.fetchone()
        conn.close()

        if not user:
            return jsonify({'error': 'Utente non trovato'}), 404

        # Crea o recupera il customer
        customer_id = user.get('stripe_customer_id')
        if not customer_id:
            customer = stripe.Customer.create(
                email=user['email'],
                metadata={'username': current_user}
            )
            customer_id = customer.id

            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET stripe_customer_id = %s WHERE username = %s",
                    (customer_id, current_user)
                )
                conn.commit()
            conn.close()

        # Crea la sessione di checkout
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': plan['stripe_price_id'],
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('payment_success', _external=True) +
            '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('payment_cancel', _external=True),
            metadata={
                'plan_key': plan_key,
                'username': current_user
            }
        )

        return jsonify({'sessionId': checkout_session.id})

    except Exception as e:
        print(f"Errore creazione checkout: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/admin/refresh-plans-cache', methods=['POST'])
@token_required
def admin_refresh_plans_cache(current_user):
    """
    Endpoint per svuotare e ricaricare la cache dei piani
    Utile dopo aver modificato i piani su Stripe
    """
    # TODO: Aggiungi controllo admin
    # if not is_admin(current_user):
    #     return jsonify({'error': 'Non autorizzato'}), 403

    try:
        clear_plans_cache()
        plans = get_all_plans_from_stripe(force_refresh=True)

        return jsonify({
            'message': 'Cache aggiornata con successo',
            'plans_count': len(plans),
            'plans': list(plans.keys())
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/payment-success')
@token_required
def payment_success(current_user):

    session_id = request.args.get('session_id')

    # Attendi che il webhook processi (max 5 secondi)
    import time
    max_attempts = 10
    attempt = 0

    info = None
    while attempt < max_attempts:
        info = get_user_subscription_info(current_user)

        # Se session_id è presente, verifica che il piano sia aggiornato
        if session_id:
            try:
                session = stripe.checkout.Session.retrieve(session_id)
                expected_plan = session.get(
                    'metadata', {}).get('plan_key', 'free')

                # Se il piano è aggiornato, esci dal loop
                if info and info['subscription_status'] == 'active':
                    break
            except Exception as e:
                print(f"Errore recupero session: {e}")

        time.sleep(0.5)
        attempt += 1

    # Fallback: se dopo 5 secondi non è aggiornato, mostra messaggio generico
    if not info or not info.get('subscription_plan'):
        return render_template(
            'payment_success.html',
            plan='Elaborazione in corso',
            status='processing',
            message="Il pagamento è stato ricevuto. L'abbonamento sarà attivato entro pochi secondi."
        )

    plan_name = info['subscription_plan'].capitalize()
    status = info['subscription_status']

    return render_template(
        'payment_success.html',
        plan=plan_name,
        status=status,
        message=f"Benvenuto nel piano {plan_name}! Il tuo abbonamento è ora attivo."
    )

@app.route('/payment-cancel')
@token_required
def payment_cancel(current_user):
    """
    Gestisce il caso in cui l'utente annulla il checkout 
    PRIMA di pagare (pulsante 'Indietro' su Stripe).
    """
    return render_template('payment_cancel.html')

@app.route('/subscribe-free', methods=['POST'])
@token_required
def subscribe_free(current_user):
    """
    Passaggio al piano Free = cancellazione subscription Stripe.
    Il DB viene aggiornato SOLO dai webhook.
    """
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT stripe_subscription_id
                FROM users
                WHERE username = %s
            """, (current_user,))
            user = cursor.fetchone()

        if not user or not user.get('stripe_subscription_id'):
            # Nessuna subscription → è già free
            return jsonify({
                'success': True,
                'message': 'Sei già sul piano Free'
            })

        sub_id = user['stripe_subscription_id']

        # Cancella a fine periodo pagato
        stripe.Subscription.modify(
            sub_id,
            cancel_at_period_end=True
        )

        return jsonify({
            'success': True,
            'message': 'Abbonamento annullato. Passerai al piano Free a fine periodo.'
        })

    except stripe.error.InvalidRequestError as e:
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        print(f"Errore subscribe-free: {e}")
        return jsonify({'error': 'Errore durante il passaggio al piano Free'}), 500

    finally:
        conn.close()

@app.route('/create-customer-portal-session', methods=['POST'])
@token_required
def create_customer_portal_session(current_user):
    """Crea una sessione per il portale clienti Stripe"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT stripe_customer_id 
                FROM users 
                WHERE username = %s AND stripe_customer_id IS NOT NULL
            """, (current_user,))
            user = cursor.fetchone()
        conn.close()

        if not user or not user['stripe_customer_id']:
            return jsonify({'error': 'Nessun abbonamento attivo'}), 400

        # Crea sessione portale clienti
        portal_session = stripe.billing_portal.Session.create(
            customer=user['stripe_customer_id'],
            return_url=url_for('pagamenti', _external=True)
        )

        return jsonify({'url': portal_session.url})

    except Exception as e:
        print(f"Errore creazione portale clienti: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            app.config['STRIPE_WEBHOOK_SECRET']
        )
    except Exception as e:
        print(f"❌ Webhook reject: {e}")
        return 'Invalid', 400

    event_type = event['type']
    obj = event['data']['object']
    print(f"📥 Stripe event: {event_type}")

    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:

            # ==================================================
            # CHECKOUT SESSION COMPLETED (BOOTSTRAP ONLY)
            # ==================================================
            if event_type == 'checkout.session.completed':

                if obj['mode'] != 'subscription':
                    return 'OK', 200

                cursor.execute("""
                    UPDATE users
                    SET stripe_customer_id = %s,
                        stripe_subscription_id = %s,
                        subscription_plan = %s
                    WHERE username = %s
                """, (
                    obj['customer'],
                    obj['subscription'],
                    obj['metadata']['plan_key'],
                    obj['metadata']['username']
                ))

                conn.commit()
                print("✅ Checkout bootstrap completato")

            # ==================================================
            # INVOICE PAID (SOURCE OF TRUTH)
            # ==================================================
            elif event_type == 'invoice.paid':
                invoice = obj
                subscription_id = invoice['subscription']
                plan_key = invoice['lines']['data'][0]['plan']['id']  # o 'nickname'

                subscription = stripe.Subscription.retrieve(subscription_id)

                cursor.execute("""
                    UPDATE users
                    SET subscription_plan = %s,
                        subscription_status = 'active',
                        subscription_start_date = FROM_UNIXTIME(%s),
                        subscription_end_date = FROM_UNIXTIME(%s),
                        stripe_subscription_id = %s,
                        stripe_customer_id = %s
                    WHERE stripe_subscription_id = %s
                """, (
                    plan_key,
                    subscription['current_period_start'],
                    subscription['current_period_end'],
                    subscription['id'],
                    invoice['customer'],
                    subscription_id
                ))

                cursor.execute("""
                    INSERT INTO payment_history
                        (user_id, stripe_payment_intent_id, amount, currency,
                        plan_type, payment_status, payment_date)
                    SELECT id_u, %s, %s, %s, %s, 'paid', NOW()
                    FROM users
                    WHERE stripe_subscription_id = %s
                    ON DUPLICATE KEY UPDATE payment_status = 'paid'
                """, (
                    invoice.get('payment_intent', invoice['id']),
                    invoice['amount_paid'] / 100,
                    invoice['currency'].upper(),
                    plan_key,
                    subscription_id
                ))

                conn.commit()
                print("💰 Invoice paid processata")

            # ==================================================
            # SUBSCRIPTION UPDATED
            # ==================================================
            elif event_type == 'customer.subscription.updated':
                cursor.execute("""
                    UPDATE users
                    SET subscription_status = %s,
                        subscription_end_date = FROM_UNIXTIME(%s)
                    WHERE stripe_subscription_id = %s
                """, (
                    obj['status'],
                    obj['current_period_end'],
                    obj['id']
                ))

                conn.commit()
                print("🔄 Subscription aggiornata")

            # ==================================================
            # SUBSCRIPTION DELETED
            # ==================================================
            elif event_type == 'customer.subscription.deleted':
                cursor.execute("""
                    UPDATE users
                    SET subscription_status = 'canceled',
                        subscription_plan = 'free',
                        stripe_subscription_id = NULL
                    WHERE stripe_subscription_id = %s
                """, (obj['id'],))

                conn.commit()
                print("❌ Subscription cancellata")

            # ==================================================
            # INVOICE PAYMENT FAILED
            # ==================================================
            elif event_type == 'invoice.payment_failed':
                cursor.execute("""
                    UPDATE users
                    SET subscription_status = 'past_due'
                    WHERE stripe_subscription_id = %s
                """, (obj['subscription'],))

                conn.commit()
                print("⚠️ Payment failed")

    except Exception as e:
        import traceback
        traceback.print_exc()
        return 'Error', 500

    finally:
        if conn and conn.open:
            conn.close()

    return 'OK', 200

@app.route('/api/subscription-status')
@token_required
def api_subscription_status(current_user):
    """API per ottenere lo stato dell'abbonamento dell'utente"""
    info = get_user_subscription_info(current_user)
    if not info:
        return jsonify({'error': 'Utente non trovato'}), 404

    return jsonify({
        'plan': info['subscription_plan'] or 'free',
        'status': info['subscription_status'] or 'inactive',
        'max_fields': info['max_fields'],
        'current_fields': info['current_fields'],
        'can_add_field': info['max_fields'] == -1 or info['current_fields'] < info['max_fields'],
        'has_ai_analysis': bool(info['has_ai_analysis']),
        'has_priority_support': bool(info['has_priority_support']),
        'has_custom_api': bool(info['has_custom_api']),
        'subscription_start': str(info['subscription_start_date']) if info['subscription_start_date'] else None,
        'subscription_end': str(info['subscription_end_date']) if info['subscription_end_date'] else None
    })

############################# FUNZIONALITÀ PREMIUM #############################

################### PROFILO #################################
def get_chat_id_by_username(username: str):
    BOT_TOKEN = "8303477409:AAEzEvqwd5-NZEG2WOlCJvA9J4DWRVBcaTA"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for update in data.get("result", []):
            message = update.get("message") or update.get("edited_message")
            if not message:
                continue
            user = message.get("from", {})
            chat = message.get("chat", {})
            if user.get("first_name") == username:
                return chat.get("id")
        return None
    except requests.RequestException as e:
        print("Errore richiesta Telegram:", e)
        return None
    
@app.route('/profilo', methods=['POST', 'GET'])
@token_required
def profilo(current_user):
    conn = get_db_connection()
    user = None
    with conn.cursor() as cursor:
        # Recupera i dati dell'utente
        cursor.execute(
            "SELECT * FROM users WHERE username = %s", (current_user,))
        user = cursor.fetchone()

    if request.method == 'POST':
        if request.form.get('action-salvataggio') == "Salva":
            # Prendi tutti i campi dal form
            nome = request.form['nome']
            cognome = request.form['cognome']
            email = request.form['email']
            telefono = request.form['telefono']
            cod_fiscale = request.form['cod_fiscale']
            dataDiNascita = request.form['DataDiNascita']
            telegram_user = request.form['username_telegram']
            telegram_chat_id = get_chat_id_by_username(telegram_user)

            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users
                    SET nome=%s,
                        cognome=%s,
                        email=%s,
                        telefono=%s,
                        cod_fiscale=%s,
                        DataDiNascita=%s
                    WHERE username=%s
                """, (nome, cognome, email, telefono, cod_fiscale, dataDiNascita, current_user))
                conn.commit()
            
            if telegram_chat_id is not None:
               with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users
                    SET telegram_chat_id=%s
                    WHERE username=%s
                """, (telegram_chat_id, current_user))
                conn.commit() 

            # Redirect con messaggio di successo
            return redirect(url_for('profilo') + '?saved=true')

    # Render del template con i dati aggiornati
    return render_template('profilo.html', user=user)

@app.route('/privacy', methods=['GET', 'POST'])
def privacy():
    return render_template('privacy.html')

@app.route('/terms', methods=['GET', 'POST'])
def terms():
    return render_template('terms.html')

@app.route('/contatti', methods=['GET', 'POST'])
def contatti():
    return render_template('contatti.html')

@app.route("/supporto")
def supporto():
    return render_template("supporto.html")
#############################################################

#################### GESTIONE DINAMICA DEI CAMPI e SENSORI - API ###############################

@app.route("/api/get_location_by_coords", methods=["GET"])
def get_location_by_coords():
    lat = float(request.args.get("lat"))
    lon = float(request.args.get("lon"))

    file_path = os.path.join(JSON_DIR, "gi_comuni_cap.json")
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    comuni = data.get("dati", [])
    if not comuni:
        return jsonify({"error": "Nessun comune trovato"}), 404

    nearest = min(
        comuni,
        key=lambda c: haversine(lat, lon, float(c["lat"]), float(c["lon"]))
    )

    result = {
        "comune": nearest["denominazione_ita"],
        "cap": nearest["cap"],
        "provincia": nearest["denominazione_provincia"],
        "sigla_provincia": nearest["sigla_provincia"]
    }
    return jsonify(result)


@app.route("/api/numCampi")
@token_required
def api_num_campi(current_user):
    campi = get_campi(current_user)
    return jsonify(campi)

@app.route("/api/infoCampi")
@token_required
def api_info_campi(current_user):
    info = get_info_campi(current_user)
    return jsonify(info)

@app.route("/api/get_provincia")
def get_provincia():
    file_path = os.path.join(JSON_DIR, "gi_province.json")
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return jsonify({"province": data.get("province", [])})

@app.route("/api/get_comune", methods=["GET"])
def get_comune():
    file_path = os.path.join(JSON_DIR, "gi_comuni_cap.json")
    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    comuni = data.get("dati", [])
    provincia = request.args.get("provincia")
    if provincia:
        comuni = [c for c in comuni if c['sigla_provincia'] == provincia]
    return jsonify({"comuni": comuni})

def get_sensor_selected(state):
    # ritorna i sensori selezionati in base allo stato
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT a.Node_id FROM assoc_sens_data a "
        "JOIN sensor s ON a.id_sens = s.id_sens AND a.Node_id = s.Node_id "
        "WHERE a.id_data = %s AND s.stato_sens = %s",
        (session['id_data'], state,)
    )
    row = cursor.fetchall()
    sens = [item['Node_id'] for item in row]
    cursor.close()
    conn.close()
    return sens

def get_state_data():
    # ritorna se è possbile continare o iniziare la sessione o meno
    # print("Sessione: " + str(session['id_data']))
    if 'id_data' in session:
        if session['id_data'] != 0:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT data_fine_irr FROM data WHERE id_ricerca = %s",
                (session['id_data'], )
            )
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            print("Fine irr: " + str(row['data_fine_irr']))
            if row['data_fine_irr'] is not None:        #row['data_fine_irr'] is not None
                return 'Stop'
            else:
                return 'Go'
        else:
            return 'Stop'
    else:
        return 'Stop' #Go

# FUNZIONANTE
def get_finish_session():
    # vado a stabilire la fine della sessione di irrigazione quando tutti i sensori coinvolti hanno la date_conc_sens diverso da NULL
    # se ritorna come conteggio 0, si salva la data di conclusione dell'ultimo sensore come data di fine
    # irrigazione sulla tabella "DATA"
    # (VERSIONE BASE) imposta tutti i sensori coinvolti a disponibili
    if 'id_data' not in session or session['id_data'] == 0:
        return False, "Continue"
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT count(*) FROM assoc_sens_data "
            "WHERE id_data = %s "
            "AND date_conc_sens IS NOT NULL "
            "GROUP BY id_data",
            (session['id_data'],)
        )
        null_count = cursor.fetchone()
        print("NULL COUNT: " + str(null_count))
        cursor.close()
        conn.close()

        if null_count == 0:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT TOP 1 date_conc_sens FROM assoc_sens_data WHERE id_data = %s"
                "order by date_conc_sens desc",
                (session['id_data'],)
            )
            data = cursor.fetchone()[0]

            cursor.execute(
                "UPDATE data SET data_fine_irr = %s"
                "WHERE id_ricerca = %s",
                (data, session['id_data'],)
            )
            conn.commit()
            cursor.close()
            conn.close()

            return True, "Concluded"
        else:
            return False, "Continue"

# API PER SENSORI NELL'INIZIALIZZAZIONE (possibile da rimuovere)
@app.route("/api/get_sensor")
@token_required
def api_get_sensor(current_user):
    info = get_sensor(current_user)
    return jsonify(info)

# API PER INFO SENSORI E CAMPO (PER NOTIFICA TELEGRAM)
@app.route("/api/get_user_info_data/<username>")
def api_get_user_info_data(username):
    user_id = get_user_id(username)
    if user_id is None:
        return jsonify({"error": "User not found"}), 404
    info = get_sensor2(user_id)
    id_ricerca, id_terreno, sensors = get_data_info(user_id)
    return jsonify({"sensors": info, "id_ricerca": id_ricerca, "id_terreno": id_terreno})

# API PER SENSORI SCELTI E PRONTI PER L'IRRIGAZIONE
@app.route("/api/get_sensor_selected")
def api_get_sensor_selected():
    info = get_sensor_selected('O')
    return jsonify(info)

# API PER SENSORI CONCLUSI NELL'IRRIGAZIONE
@app.route("/api/get_sensor/concluded")
def api_get_sensor_concluded():
    info = get_sensor_selected('C')
    return jsonify(info)

# API PER SENSORI SOSPESI NELL'IRRIGAZIONE
@app.route("/api/get_sensor/suspended")
def api_get_sensor_suspended():
    info = get_sensor_selected('S')
    return jsonify(info)

# API PER SESSIONE DI IRRIGAZIONE
@app.route("/api/get_session_data")
def api_get_session_data():
    info = get_state_data()
    print("INFO: " + str(info))
    return jsonify(info)

# API PER CHIUDERE LA SESSIONE DI IRRIGAZIONE -- DA CONTROLLARE
@app.route("/api/get_finish_session")
def api_get_finish_session():
    info = get_finish_session()[1]
    print("Finish session: " + str(info))
    return jsonify(info)

# API PER RICEVERE INFO SULLA CONNESSIONE DEL DISPOSITIVO -- DA TESTARE
@app.route('/api/init_receiver', methods=['POST'])
@api_token_required
def init_serial_receiver(current_user):
    data = request.get_json()
    all_sensor_wet = False
    
    if data.get('type') == 'Connection':
        print("=" * 50)
        print("STATO CONNESSIONE SERIALE (DAL CLIENT):")
        print(f"Connesso: {data.get('connected')}")
        print(f"Porta: {data.get('port')}")
        print(f"Errore: {data.get('error')}")
        print("=" * 50)
            
    elif data.get('type') == 'Failed':
        print("=" * 50)
        print("ERRORE:")
        print(f"Dati: {data}")
        print("=" * 50)
        set_error_state_data(data)

    elif data.get('type') == 'Authentication':
        print("=" * 50)
        print("UTENTE:")
        print(f"Dati: {data}")
        print("=" * 50)
        
    else:
        all_sensor_wet = get_finish_session()[0]
        print(f"Stato sensori: {all_sensor_wet}")
        if all_sensor_wet:
            print("Fine della sessione")
            
        print("=" * 50)
        print("DATI INVIATI DA SENSORE:")
        print(f"Dati: {data}")
        print("=" * 50)
        id_user = get_user_id(data.get('user'))
        id_ricerca, id_terreno, sensors = get_data_info(id_user)
        print(f"Info: {id_user} - {id_ricerca} - {id_terreno} - {sensors}")
        insert_sensor_data(data, sensors, id_ricerca)   #correggere sensors perchè non passa parametro come dizionario

    return jsonify({"status": "ok"})

# API PER INVIO TOKEN AL CLIENT
@app.route('/api/get_token/<username>')
def get_token_api(username):
    token = generate_token(username)   
    return jsonify({"token": token})

# PREMIUM -- invio id chat con telegram per notifiche
@app.route("/api/get_telegram_chat_id/<username>")
def api_get_telegram_chat_id(username):
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT telegram_chat_id FROM users WHERE username = %s", (username,))
        info = cursor.fetchone()
    return jsonify({"chat_id": info})
########################################################################################

############################ AZIONI IRRIGAZIONE #########################################
@app.route('/ini_irr', methods=['GET', 'POST'])
def inizializzaIrrigazione():
    # controllo per la prima volta che si entra nel sito
    if 'id_data' not in session:
        session['id_data'] = 0

    if request.method == 'POST':
        print("Prova sessione data: " + str(session['id_data']))
        # STOP --> si intende che non si può procedere con la visualizzazione dell'irrigazione avviata
        # usata la stessa funzione per vedere se è possibile vedeere il pulsante "Visualizza Irrigazione"
        if get_state_data() == 'Stop':      
            data = request.get_json()
            campo_id = data.get('campo_id')
            selected_sensors = data.get('selectedSensors', [])
            sensori_posizione = data.get('sensoriConPosizione', [])

            # Crea dizionario node_id → posizione per accesso rapido
            posizioni_map = {
                sp['node_id']: sp['posizione'] for sp in sensori_posizione
            }
            print(f"Mappa posizioni: {posizioni_map}")

            session['id_campo_selezionato'] = campo_id
            session['selected_sensors'] = selected_sensors

            # aggiorna lo stato dei sensori da disponibili a operativi
            conn = get_db_connection()
            cursor = conn.cursor()
            # utilizzo l'id univoco del sensore
            for i in selected_sensors:
                pos = posizioni_map.get(i)
                if pos is None:
                    cursor.execute(
                        "UPDATE sensor SET stato_sens = 'O' WHERE Node_ID = %s",
                        (i,)
                    )
                else:
                    lat      = pos.get('latitude')
                    lon      = pos.get('longitude')
                    accuracy = pos.get('accuracy')
                    cursor.execute(
                        "UPDATE sensor SET stato_sens='O', latitude=%s, longitude=%s, accuracy=%s WHERE Node_ID = %s",
                        (lat, lon, accuracy, i) 
                    )

            conn.commit()
            cursor.close()
            conn.close()

            # avvio della irrigazione
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO `data`(`id_u`, `id_t`, `data_inizio_irr`, `data_fine_irr`) "
                "VALUES (%s, %s, NOW(), NULL)",
                (session['id'], campo_id)
            )
            conn.commit()
            # estraggo l'id della registrazione dell'irrigazione appena inserita
            last_id = cursor.lastrowid
            session["id_data"] = last_id
            cursor.close()
            conn.close()

            # ricerco il l'ID "nostro" dei sensori confrontandolo con quello univoco del sensore
            result_ids = []
            conn = get_db_connection()
            cursor = conn.cursor()
            for k in selected_sensors:
                cursor.execute(
                    "SELECT id_sens FROM sensor WHERE Node_ID = %s",
                    (k,)
                )
                row = cursor.fetchone()
                if row:
                    result_ids.append(row['id_sens'])
            cursor.close()
            conn.close()
            print(f"ID sensori utilizzati: {result_ids}")

            # inserisco i dati dell' avvio alla registrazione all'interno della tabella assoc_sens_data per ogni sensore selezionato
            conn = get_db_connection()
            cursor = conn.cursor()
            with conn:
                for our_id, node_id in zip(result_ids, selected_sensors):
                    cursor.execute(
                        "INSERT INTO assoc_sens_data "
                        "(id_data, id_sens, date_att_sens, date_conc_sens, Node_id, idx, Bat, Humidity, Temperature, ADC) "
                        "VALUES (%s, %s, %s, NULL, %s, NULL, NULL, NULL, NULL, NULL)",
                        (last_id, our_id, datetime.now(), node_id)
                    )
                    conn.commit()
                cursor.close()

            # API per sensori selezionati
            return jsonify({"status": "ok", "selected_sensors": selected_sensors})
        else:
            # print("SESSIONE GIà AVVIATA")
            return jsonify({"status": "no", "selected_sensors": None})

    campo_id = request.args.get('campo_id')
    return render_template('inizializzazione_irr.html', campo_id=campo_id)


# FUNZIONANTE
def set_error_state_data(message):
    # setta ad errore la ricerca / ripristina i sensori / conclude la sessione di irrigazione
    state = 'ERR'
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE data SET error_data = %s, desc_error = %s, data_fine_irr = %s WHERE id_ricerca = %s",
        (state, message, datetime.now(), session['id_data'])
    )
    conn.commit()
    cursor.close()
    conn.close()
    for k in session['selected_sensors']:
        set_state_sensor('C', k)
    session['id_data'] = 0


@app.route('/avvia_irr', methods=['GET', 'POST'])
def avviaIrrigazione():
    print("AVVIA IRRIGAZIONE")
    # aggiungere la parte dello storico
    campo_id = request.args.get("campo_id")
    if campo_id is None:
        campo_id = session['id_campo_selezionato']

    if request.method == 'POST':
        azione = request.form.get("azione")
        sensor_id = request.form.get("sensor_id")

        if azione == "sospendi":
            set_state_sensor("S", sensor_id)
            # session.modified = True
            return redirect("/avvia_irr")
        elif azione == 'riattiva':
            set_state_sensor("O", sensor_id)
            return redirect("/avvia_irr")
        elif azione == 'concludi':
            print("Conclusione")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE data SET data_fine_irr = %s"
                "WHERE id_ricerca = %s",
                (datetime.now(), session['id_data'],)
            )
            conn.commit()
            cursor.close()
            conn.close()
            for k in session['selected_sensors']:
                set_state_sensor('C', k)
            return redirect(url_for('home'))
    
    return render_template('avvia_irrigazione.html', campo_id=campo_id, coordinate_campo=get_coordinate(campo_id))
####################################################################################

def associazioneSessionCampi(current_user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT f.id_t FROM users u, fields f WHERE u.username = %s AND u.id_u = f.id_user", (current_user,))
    risultato = cursor.fetchall()
    id_array = [row['id_t'] for row in risultato]
    cursor.execute("SELECT id_u FROM users WHERE username = %s",
                   (current_user,))
    user_id = cursor.fetchone()['id_u']
    session['id'] = user_id
    if get_campi(current_user) > 0:
        for i, e in enumerate(id_array):
            session[f"campo{i+1}"] = e

@app.route('/', methods=['GET'])
def index():
    token = request.cookies.get("token")
    if token:
        try:
            jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            return redirect(url_for('home'))
        except Exception:
            pass
    return render_template("index.html")  # pagina pubblica iniziale

@app.route('/home', methods=['GET', 'POST'])
@token_required
def home(current_user):
    associazioneSessionCampi(current_user)
    if request.method == 'POST':
        resp = None
        if request.form.get('action-storici') == "Storico Controlli":
            resp = make_response(redirect(url_for('storici')))
        if request.form.get('action-aggCampo') == "Aggiungi Campo":
            resp = make_response(redirect(url_for('aggiungiCampo')))
        if request.form.get('action-gesCampo') == "Gestione Campo":
            resp = make_response(redirect(url_for('gestioneCampo')))
        if request.form.get('action-visCampi') == "Visualizza i tuoi campi":
            resp = make_response(redirect(url_for('visualizzaCampi')))
        if request.form.get('action-profilo') == "Profilo":
            resp = make_response(redirect(url_for('profilo')))
        if request.form.get('action1') == "log-out":
            resp = make_response(redirect(url_for('index')))
            resp.delete_cookie('token')

        campo_value = request.form.get('action_ricerca_drone')
        if campo_value and campo_value.startswith("Campo "):
            numero_campo = campo_value.split(" ")[1]
            id_campo = session[f'campo{numero_campo}']
            """avvioDrone(id_campo)"""
            resp = make_response(redirect(url_for('home')))
        return resp

    campo_corrente = session.get('campo_corrente', None)
    return render_template('home.html', campo_corrente=campo_corrente)

@app.route('/logout', methods=['POST'])
def logout():
    response = make_response(redirect(url_for('index')))
    response.delete_cookie('token')
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
    # per pubblicare app.debug=False
