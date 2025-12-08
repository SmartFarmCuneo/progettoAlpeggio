# (aggiornato) flask_app.py
from flask import Flask, render_template, redirect, url_for, request, make_response
from flask import session, jsonify, render_template_string, current_app
from functools import wraps
import pymysql
import datetime
import jwt
import hashlib
import requests
import subprocess
import os
import json
import smtplib
import random
import math
import re
import stripe
import sys
from email.mime.text import MIMEText
from flask_mail import Message, Mail


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_DIR = os.path.join(BASE_DIR, "static", "json")

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

# Database connection
def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", 'localhost'),
        user=os.getenv("DB_USER", 'root'),
        password=os.getenv("DB_PASSWORD", ''),
        database=os.getenv("DB_NAME", 'irrigazione'),
        cursorclass=pymysql.cursors.DictCursor
    )

# se non hai il .env quella sopra funziona lo stesso
"""def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='irrigazione',
        cursorclass=pymysql.cursors.DictCursor
    )"""

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
        "timestamp": datetime.datetime.now().isoformat() + "Z"
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


# Definizione piani di abbonamento
SUBSCRIPTION_PLANS = {
    'free': {
        'name': 'Free',
        'price': 0,
        'currency': 'eur',
        'interval': 'month',
        'features': [
            'Aggiunta fino a 10 campi',
            'Dati meteorologici base',
            '3 tipi di sensori',
            'Supporto email',
            'Report mensili'
        ]
    },
    'basic': {
        'name': 'Basic',
        'price': 19,
        'currency': 'eur',
        'interval': 'month',
        'features': [
            'Monitoraggio fino a 5 ettari',
            'Dati meteorologici base',
            '3 tipi di sensori',
            'Supporto email',
            'Report mensili'
        ]
    },
    'professional': {
        'name': 'Professional',
        'price': 49,
        'currency': 'eur',
        'interval': 'month',
        'features': [
            'Monitoraggio fino a 25 ettari',
            'Dati meteorologici avanzati',
            '8 tipi di sensori',
            'Supporto email e telefono',
            'Report settimanali',
            'Analisi predittive AI',
            'Allerte automatiche'
        ]
    },
    'enterprise': {
        'name': 'Enterprise',
        'price': 99,
        'currency': 'eur',
        'interval': 'month',
        'features': [
            'Monitoraggio illimitato',
            'Dati meteorologici premium',
            'Tutti i tipi di sensori',
            'Supporto prioritario 24/7',
            'Report personalizzati',
            'Analisi predittive AI avanzate',
            'Allerte in tempo reale',
            'API personalizzate'
        ]
    }
}

############################# STRIPE HELPER FUNCTIONS #############################


def get_user_plan_limits(username):
    """Restituisce i limiti del piano dell'utente"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.* FROM plan_limits p 
                INNER JOIN users u ON p.plan_name = u.subscription_plan 
                WHERE u.username = %s
            """, (username,))
            return cursor.fetchone()
    except Exception as e:
        print(f"Errore nel recupero limiti piano: {e}")
        return None
    finally:
        conn.close()


def can_user_add_field(username):
    """Controlla se l'utente può aggiungere un nuovo campo"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.subscription_plan, p.max_fields,
                       (SELECT COUNT(*) FROM fields f WHERE f.id_user = u.id_u) as current_fields
                FROM users u 
                LEFT JOIN plan_limits p ON p.plan_name = u.subscription_plan 
                WHERE u.username = %s
            """, (username,))
            result = cursor.fetchone()

            if not result:
                return False

            max_fields = result['max_fields']
            current_fields = result['current_fields']

            # -1 significa illimitato
            return max_fields == -1 or current_fields < max_fields

    except Exception as e:
        print(f"Errore nel controllo limiti campi: {e}")
        return False
    finally:
        conn.close()


def get_user_subscription_info(username):
    """Restituisce informazioni complete sull'abbonamento dell'utente (approccio più robusto e debug)"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1) Leggiamo direttamente la riga utente
            cursor.execute(
                "SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if not user:
                # nessun utente trovato
                print(
                    f"[get_user_subscription_info] user='{username}' non trovato nel DB")
                return None

            # 2) Normalizziamo il valore del piano per evitare mismatch (trim + lower + fallback 'free')
            raw_plan = user.get("subscription_plan") or "free"
            try:
                normalized_plan = str(raw_plan).strip().lower()
            except Exception:
                normalized_plan = "free"

            # 3) Recuperiamo i limiti del piano in maniera case-insensitive / trim
            try:
                cursor.execute(
                    "SELECT max_fields, max_sensors, has_ai_analysis, has_priority_support, has_custom_api "
                    "FROM plan_limits WHERE LOWER(TRIM(plan_name)) = %s",
                    (normalized_plan,)
                )
                plan = cursor.fetchone()
            except Exception as e:
                print(
                    f"[get_user_subscription_info] errore recupero plan_limits per '{normalized_plan}': {e}")
                plan = None

            # 4) Calcoliamo il numero corrente di campi dell'utente
            try:
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM fields WHERE id_user = %s", (user['id_u'],))
                cnt_row = cursor.fetchone()
                current_fields = cnt_row['cnt'] if cnt_row else 0
            except Exception as e:
                print(
                    f"[get_user_subscription_info] errore conteggio fields per id_user={user.get('id_u')}: {e}")
                current_fields = 0

            # 5) Costruiamo il risultato coerente
            result = {
                'subscription_plan': normalized_plan,
                'subscription_status': user.get('subscription_status'),
                'subscription_start_date': user.get('subscription_start_date'),
                'subscription_end_date': user.get('subscription_end_date'),
                'stripe_customer_id': user.get('stripe_customer_id'),
                'max_fields': plan.get('max_fields') if plan else None,
                'max_sensors': plan.get('max_sensors') if plan else None,
                'has_ai_analysis': bool(plan.get('has_ai_analysis')) if plan else False,
                'has_priority_support': bool(plan.get('has_priority_support')) if plan else False,
                'has_custom_api': bool(plan.get('has_custom_api')) if plan else False,
                'current_fields': current_fields
            }

            # log utile per debug
            print(
                f"[get_user_subscription_info] user='{username}' raw_plan='{raw_plan}' normalized='{normalized_plan}' result_keys={list(result.keys())}")

            return result

    except Exception as e:
        import traceback
        print("[get_user_subscription_info] eccezione:", e)
        traceback.print_exc()
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


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


def save_payment_history(user_id, payment_intent_id, amount, currency, plan_type, status):
    """Salva la cronologia dei pagamenti nel database"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO payment_history 
                (user_id, stripe_payment_intent_id, amount, currency, plan_type, payment_status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, payment_intent_id, amount, currency, plan_type, status))
            conn.commit()
    except Exception as e:
        print(f"Errore nel salvataggio cronologia pagamenti: {e}")
    finally:
        conn.close()


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


def hash_password(psw):
    return hashlib.sha256(psw.encode()).hexdigest()


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
            #session['id_data'] = 0
            response = make_response(redirect(url_for("home")))
            if remember_me:
                return generate_and_set_token(response, username, durata=24*7)
            else:
                return generate_and_set_token(response, username)
        else:
            error = "Nome utente o password errati."

    return render_template("login.html", error=error)


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
                    return redirect(url_for('aggiungiCampo'))
        except Exception as e:
            error = "Errore del database"
        finally:
            connection.close()

    return render_template('registrati.html', error=error)

##################################################################################

################################ Cookie-Token ####################################


def generate_token(username):
    payload = {
        "user": username,
        "exp": datetime.datetime.now() + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")


def generate_and_set_token(response, username, durata=1):
    token = generate_token(username)
    response.set_cookie("token", token, max_age=3600, httponly=True)
    return response


def token_required(f):
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
@app.route('/storici', methods=['GET', 'POST'])
@token_required
def storici(current_user):
    risultato = ""
    campo_selezionato = ""
    conn = get_db_connection()
    if request.method == 'POST':
        if request.form.get('action-ricercaSt') == 'Ricerca':
            campo_selezionato = request.form["selezionato"]
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM data d WHERE id_t = %s AND id_u = %s",
                    (session[f"{campo_selezionato}"], session["id"])
                )
                risultato = cursor.fetchall()
    return render_template('storici.html', info=risultato, campo=campo_selezionato)


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
            import requests
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
            # Recupera i dati dell'utente
            cursor.execute(
                "SELECT * FROM users WHERE username = %s", (current_user,))
            user = cursor.fetchone()

            if not user:
                return redirect(url_for('login'))

            user_id = user['id_u']  # FIX: era user['id'], ora è user['id_u']

            if request.method == 'POST':
                action = request.form.get('action')

                # AGGIUNGI SENSORE
                if action == 'aggiungi':
                    id_sensore = request.form.get('id_sensore', '').strip()
                    nome_sensore = request.form.get('nome_sensore', '').strip()

                    # Validazione input
                    if not id_sensore or not nome_sensore:
                        return render_template('gestione_sensori.html',
                                               user=user,
                                               sensori=sensori,
                                               error='invalid')

                    # Verifica se l'ID sensore esiste già per questo utente
                    cursor.execute("""
                        SELECT id_sensore FROM sensori 
                        WHERE id_sensore = %s AND id_utente = %s
                    """, (id_sensore, user_id))
                    existing_sensor = cursor.fetchone()

                    if existing_sensor:
                        # Recupera i sensori prima di ritornare
                        cursor.execute("""
                            SELECT id_sensore, nome_sensore, data_registrazione
                            FROM sensori
                            WHERE id_utente = %s
                            ORDER BY data_registrazione DESC
                        """, (user_id,))
                        sensori = cursor.fetchall()

                        return render_template('gestione_sensori.html',
                                               user=user,
                                               sensori=sensori,
                                               error='duplicate')

                    # Inserisci il nuovo sensore
                    cursor.execute("""
                        INSERT INTO sensori (id_sensore, nome_sensore, id_utente, data_registrazione)
                        VALUES (%s, %s, %s, NOW())
                    """, (id_sensore, nome_sensore, user_id))

                    conn.commit()

                    # Recupera la lista aggiornata dei sensori
                    cursor.execute("""
                        SELECT id_sensore, nome_sensore, data_registrazione
                        FROM sensori
                        WHERE id_utente = %s
                        ORDER BY data_registrazione DESC
                    """, (user_id,))
                    sensori = cursor.fetchall()

                    return render_template('gestione_sensori.html',
                                           user=user,
                                           sensori=sensori,
                                           success='added')

                # ELIMINA SENSORE
                elif action == 'elimina':
                    id_sensore = request.form.get('id_sensore', '').strip()

                    if not id_sensore:
                        return render_template('gestione_sensori.html',
                                               user=user,
                                               sensori=sensori,
                                               error='invalid')

                    # Elimina solo se il sensore appartiene all'utente
                    cursor.execute("""
                        DELETE FROM sensori 
                        WHERE id_sensore = %s AND id_utente = %s
                    """, (id_sensore, user_id))

                    affected_rows = cursor.rowcount
                    conn.commit()

                    # Recupera la lista aggiornata dei sensori
                    cursor.execute("""
                        SELECT id_sensore, nome_sensore, data_registrazione
                        FROM sensori
                        WHERE id_utente = %s
                        ORDER BY data_registrazione DESC
                    """, (user_id,))
                    sensori = cursor.fetchall()

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

            # GET request - Recupera tutti i sensori dell'utente
            cursor.execute("""
                SELECT id_sensore, nome_sensore, data_registrazione
                FROM sensori
                WHERE id_utente = %s
                ORDER BY data_registrazione DESC
            """, (user_id,))

            sensori = cursor.fetchall()

    except Exception as e:
        print(f"Errore nella gestione sensori: {e}")
        import traceback
        traceback.print_exc()

        # In caso di errore, prova comunque a recuperare i dati dell'utente
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

    # Render del template con i dati
    return render_template('gestione_sensori.html', user=user, sensori=sensori)


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


@app.route('/visualizzaCampi', methods=['GET', 'POST'])
@token_required
def visualizzaCampi(current_user):
    return render_template('visualizzaCampi.html')

################################################################

############################# STRIPE ROUTES #############################


@app.route('/pagamenti', methods=['GET', 'POST'])
@token_required
def pagamenti(current_user):
    """Pagina dei piani abbonamento"""
    subscription_info = get_user_subscription_info(current_user)

    return render_template('pagamenti.html',
                           stripe_public_key=app.config['STRIPE_PUBLIC_KEY'],
                           subscription_info=subscription_info)


@app.route("/api/plans", methods=["GET"])
@token_required
def api_get_plans(current_user):
    user_info = get_user_subscription_info(current_user)
    # Normalizza il piano (rimuovi spazi e rendilo lowercase) per evitare mismatch di case
    raw_plan = None
    if user_info:
        raw_plan = user_info.get("subscription_plan")
    # safety: se None -> 'free'
    if not raw_plan:
        current_plan = "free"
    else:
        try:
            current_plan = str(raw_plan).strip().lower()
        except Exception:
            current_plan = "free"

    # debug log (puoi togliere in produzione)
    print(
        f"[DEBUG] /api/plans user={current_user} raw_plan={raw_plan} normalized={current_plan}")

    # ritorna tutto, incluso free
    return jsonify({
        "current_plan": current_plan,
        "plans": SUBSCRIPTION_PLANS
    })


@app.route('/create-checkout-session', methods=['POST'])
@token_required
def create_checkout_session(current_user):
    """Crea una sessione di checkout Stripe"""
    try:
        data = request.get_json()
        plan_id = data.get('plan_id')

        if plan_id not in SUBSCRIPTION_PLANS:
            return jsonify({'error': 'Piano non valido'}), 400

        plan = SUBSCRIPTION_PLANS[plan_id]

        # Recupera l'utente dal database
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM users WHERE username = %s", (current_user,))
            user = cursor.fetchone()
        conn.close()

        if not user:
            return jsonify({'error': 'Utente non trovato'}), 404

        # Crea la sessione di checkout
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': plan['currency'],
                    'product_data': {
                        'name': f'Abbonamento {plan["name"]} - Agrinnov',
                        'description': f'Piano {plan["name"]} - Monitoraggio agricolo avanzato'
                    },
                    # Stripe usa i centesimi
                    'unit_amount': plan['price'] * 100,
                    'recurring': {
                        'interval': plan['interval']
                    }
                },
                'quantity': 1,
            }],
            mode='subscription',
            success_url=url_for('payment_success', _external=True) +
            '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('payment_cancel', _external=True),
            customer_email=user['email'],
            metadata={
                'user_id': user['id_u'],
                'username': current_user,
                'plan': plan_id
            },
            # automatic_tax={'enabled': True}
        )

        return jsonify({'checkout_url': checkout_session.url})

    except Exception as e:
        print(f"Errore creazione sessione checkout: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/payment-success')
@token_required
def payment_success(current_user):
    """Pagina di conferma pagamento riuscito"""
    session_id = request.args.get('session_id')

    if not session_id:
        return redirect(url_for('pagamenti'))

    try:
        # Recupera la sessione da Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)

        if checkout_session.payment_status == 'paid':

            # Recupera la subscription
            if not checkout_session.subscription:
                return redirect(url_for('pagamenti'))

            subscription = stripe.Subscription.retrieve(
                checkout_session.subscription)

            # Accedi correttamente a current_period_end
            period_end = subscription.get('current_period_end')
            if not period_end:
                # Fallback: usa la data della sessione
                period_end = checkout_session.get('expires_at')

            # Aggiorna il database
            conn = get_db_connection()
            try:
                with conn.cursor() as cursor:
                    plan_name = checkout_session.metadata.get('plan')
                    customer_id = checkout_session.customer

                    cursor.execute("""
                        UPDATE users 
                        SET subscription_plan = %s, 
                            subscription_status = 'active',
                            stripe_customer_id = %s,
                            subscription_start_date = NOW(),
                            subscription_end_date = FROM_UNIXTIME(%s)
                        WHERE username = %s
                    """, (plan_name, customer_id, period_end, current_user))

                    rows_affected = cursor.rowcount

                    conn.commit()

                    # Salva nella cronologia pagamenti
                    cursor.execute(
                        "SELECT id_u FROM users WHERE username = %s", (current_user,))
                    user = cursor.fetchone()

                    if user:
                        user_id = user['id_u']

                        save_payment_history(
                            user_id,
                            checkout_session.payment_intent,
                            checkout_session.amount_total / 100,
                            checkout_session.currency.upper(),
                            plan_name,
                            'paid'
                        )

            except Exception as db_error:
                import traceback
                traceback.print_exc()
            finally:
                conn.close()

            plan = checkout_session.metadata.get('plan', 'unknown')
            return render_template('payment_success.html', plan=plan)

        else:
            return redirect(url_for('pagamenti'))

    except stripe.StripeError as e:
        import traceback
        traceback.print_exc()
        return redirect(url_for('pagamenti'))

    except Exception as e:
        import traceback
        print("Stack trace completo:")
        traceback.print_exc()
        return redirect(url_for('pagamenti'))


@app.route('/payment-cancel')
@token_required
def payment_cancel(current_user):
    """Pagina di annullamento pagamento"""
    return render_template('payment_cancel.html')


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
    """Gestisce i webhook di Stripe"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, app.config['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError:
        print("Invalid payload")
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        print("Invalid signature")
        return 'Invalid signature', 400

    # Gestisci gli eventi
    conn = get_db_connection()

    try:
        if event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            customer_id = subscription['customer']
            status = subscription['status']

            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET subscription_status = %s,
                        subscription_end_date = FROM_UNIXTIME(%s)
                    WHERE stripe_customer_id = %s
                """, (status, subscription['current_period_end'], customer_id))
                conn.commit()
                print(f"Abbonamento aggiornato per customer {customer_id}")

        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            customer_id = subscription['customer']

            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET subscription_status = 'cancelled',
                        subscription_plan = 'free'
                    WHERE stripe_customer_id = %s
                """, (customer_id,))
                conn.commit()
                print(f"Abbonamento cancellato per customer {customer_id}")

        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            customer_id = invoice['customer']

            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET subscription_status = 'active'
                    WHERE stripe_customer_id = %s
                """, (customer_id,))
                conn.commit()
                print(f"Pagamento riuscito per customer {customer_id}")

        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            customer_id = invoice['customer']

            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users 
                    SET subscription_status = 'past_due'
                    WHERE stripe_customer_id = %s
                """, (customer_id,))
                conn.commit()
                print(f"Pagamento fallito per customer {customer_id}")

    except Exception as e:
        print(f"Errore gestione webhook: {e}")
    finally:
        conn.close()

    return 'Success', 200


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


@app.route('/cancel-subscription', methods=['POST'])
@token_required
def cancel_subscription(current_user):
    """Cancella l'abbonamento dell'utente"""
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

        # Recupera tutte le subscription del cliente
        subscriptions = stripe.Subscription.list(
            customer=user['stripe_customer_id'])

        # Cancella tutte le subscription attive
        for subscription in subscriptions.data:
            if subscription.status == 'active':
                stripe.Subscription.delete(subscription.id)

        return jsonify({'success': True, 'message': 'Abbonamento cancellato'})

    except Exception as e:
        print(f"Errore cancellazione abbonamento: {e}")
        return jsonify({'error': str(e)}), 500

############################# FUNZIONALITÀ PREMIUM #############################


@app.route('/ai-analysis')
@token_required
@plan_feature_required('has_ai_analysis')
def ai_analysis(current_user):
    """Funzionalità di analisi AI (Professional ed Enterprise)"""
    return render_template('ai_analysis.html')


@app.route('/priority-support')
@token_required
@plan_feature_required('has_priority_support')
def priority_support(current_user):
    """Supporto prioritario (solo Enterprise)"""
    return render_template('priority_support.html')


@app.route('/custom-api')
@token_required
@plan_feature_required('has_custom_api')
def custom_api(current_user):
    """API personalizzate (solo Enterprise)"""
    return render_template('custom_api.html')


################### PROFILO #################################


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
            # deve corrispondere al nome del campo nel DB
            dataDiNascita = request.form['DataDiNascita']

            # Aggiorna il database
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


def haversine(lat1, lon1, lat2, lon2):
    # distanza in km tra due coordinate
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1) * \
        math.cos(phi2) * math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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

    # Trova il comune più vicino
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


def get_campi(current_user):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM fields f, users u WHERE f.id_user = u.id_u AND u.username = %s", (current_user,))
    num_campi = cursor.fetchone()['COUNT(*)']
    conn.close()
    return num_campi


@app.route("/api/numCampi")
@token_required
def api_num_campi(current_user):
    campi = get_campi(current_user)
    return jsonify(campi)


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


def get_sensor(current_user):
    print("inizio")
    conn = get_db_connection()

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id_u FROM users WHERE username = %s", (current_user,))
        result = cursor.fetchone()
        id_user = result['id_u']

    print(f"User ID: {id_user}")

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT s.posizione, s.Node_Id, s.stato_sens FROM sensor s, assoc_users_sens aus WHERE aus.id_utente = %s AND s.id_sens = aus.id_sens",
            (id_user,))
        risultato = cursor.fetchall()
        info = ""
        for i in range(len(risultato)):
            info += str(risultato[i]["posizione"]) + "/" + str(risultato[i]
                                                               ["Node_Id"]) + "/" + str(risultato[i]["stato_sens"]) + "|"
        print(f"Info: {info}")
        if info == '':
            return "nessuna info"
        else:
            return info

# API PER SENSORI NELL'INIZIALIZZAZIONE
@app.route("/api/get_sensor")
@token_required
def api_get_sensor(current_user):
    info = get_sensor(current_user)
    return jsonify(info)

def get_sensor_selected(state): 
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT a.Node_id FROM assoc_sens_data a "
        "JOIN sensor s ON a.id_sens = s.id_sens AND a.Node_id = s.Node_id "
        "WHERE a.id_data = %s AND s.stato_sens = %s", 
        (session['id_data'], state) 
    )
    row = cursor.fetchall() 
    sens = [item['Node_id'] for item in row]
    cursor.close()
    conn.close()
    return sens 

def get_state_data(): 
    #print("Sessione: " + str(session['id_data']))
    if session['id_data'] != 0 and 'id_data' in session:
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
        if str(row['data_fine_irr']) == 'None': return 'Stop' 
        else: return 'Go' 
    else:
        return 'Go'
    
# vado a stabilire la fine della sessione di irrigazione
# quando tutti i sensori coinvolti hanno la date_conc_sens
# diverso da NULL
# DA PROVARE
def get_finish_session():
    if 'id_data' not in session or session['id_data'] == 0:
        return "Continue" 
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM assoc_sens_data WHERE id_data = %s AND date_conc_sens IS NULL", 
            (session['id_data'], )
        )
        null_count = cursor.fetchone()[0]
        print("NULL COUNT: " + str(null_count))
        cursor.close()
        conn.close()
        
        return "Continue" if null_count > 0 else "Concluded"
    
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
    info = get_finish_session()
    print("Finish session: " + str(info))
    return jsonify(info)

########################################################################################

############################ GESTIONE SENSORI #####################################

@app.route('/sensori', methods=['GET', 'POST'])
def sensori():
    return render_template('assoc_gestione_sensori.html')

############################ AZIONI IRRIGAZIONE #########################################
@app.route('/assoc_gestione_sensori', methods=['GET', 'POST'])
def associaSensori():
    return render_template('assoc_gest_sens.html')

@app.route('/ini_irr', methods=['GET', 'POST'])
def inizializzaIrrigazione():
    #controllo per la prima volta che si entra nel sito
    if 'id_data' not in session:
        session['id_data'] = 0

    if request.method == 'POST':
        if get_state_data() == 'Go':
            data = request.get_json()
            campo_id = data.get('campo_id')
            selected_sensors = data.get('selectedSensors', [])
            session['id_campo_selezionato'] = campo_id
            #print("Sensori selezionati:", selected_sensors)

            # aggiorna lo stato dei sensori da disponibili a operativi
            conn = get_db_connection()
            cursor = conn.cursor()
            #utilizzo l'id univoco del sensore
            for i in selected_sensors:
                cursor.execute(
                    "UPDATE sensor SET stato_sens = 'O' WHERE Node_ID = %s",
                    (i)
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
            last_id = cursor.lastrowid #estraggo l'id della registrazione dell'irrigazione appena inserita
            session["id_data"] = last_id
            print("Sess1: "+ str(session['id_data']))
            cursor.close()
            conn.close()

            #ricerco il l'ID "nostro" dei sensori confrontandolo con quello univoco del sensore
            result_ids = []
            conn = get_db_connection()
            cursor = conn.cursor()
            for k in selected_sensors:
                cursor.execute(
                    "SELECT id_sens FROM sensor WHERE Node_ID = %s",
                    (k,) 
                )
                row = cursor.fetchone() 
                print(f"Riga: {row}")
                if row:
                    result_ids.append(row['id_sens'])  
            cursor.close()
            conn.close()
            print(f"ID sensori utilizzati: {result_ids}")

            #inserisco i dati dell' avvio alla registrazione all'interno della tabella assoc_sens_data per ogni sensore selezionato
            conn = get_db_connection()
            cursor = conn.cursor()
            with conn:
                for our_id, node_id in zip(result_ids, selected_sensors):
                    print("MIO ID:" + str(our_id))
                    print("NODE ID: " + str(node_id))
                    cursor.execute(
                        "INSERT INTO assoc_sens_data "
                        "(id_data, id_sens, date_att_sens, date_conc_sens, Node_id, idx, Bat, Humidity, Temperature, ADC) "
                        "VALUES (%s, %s, %s, NULL, %s, NULL, NULL, NULL, NULL, NULL)",
                        (last_id, our_id, datetime.datetime.now(), node_id)
                    )
                    conn.commit()
                cursor.close()

            #API per sensori selezionati
            return jsonify({"status": "ok", "selected_sensors": selected_sensors})
        else:
            #print("SESSIONE GIà AVVIATA")
            return jsonify({"status": "no", "selected_sensors": None})
        
    campo_id = request.args.get('campo_id')
    #init_exe() --> inizializzaione dell'exe
    return render_template('inizializzazione_irr.html', campo_id=campo_id)

def set_state_sensor(state, sensor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE sensor SET stato_sens = %s WHERE Node_ID = %s",
        (state, sensor_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

@app.route('/avvia_irr', methods=['GET', 'POST'])
@token_required
def avviaIrrigazione(current_user):
    if request.method == 'POST':
        azione = request.form.get("azione")
        sensor_id = request.form.get("sensor_id")

        if azione == "sospendi":
            print(f"Sospensione richiesta per sensore {sensor_id}")
            set_state_sensor("S", sensor_id)
            #session.modified = True
            return redirect("/avvia_irr")
            
        elif azione == 'riattiva':
            set_state_sensor("O", sensor_id)
            return redirect("/avvia_irr")

    try:
        response = requests.get('http://localhost:8000/api/connection_status', timeout=5)
        if response.status_code == 200:
            connection_status = response.json()
            print("=" * 50)
            print("STATO CONNESSIONE SERIALE:")
            print(f"Connesso: {connection_status.get('connected')}")
            print(f"Porta: {connection_status.get('port')}")
            print(f"Errore: {connection_status.get('error')}")
            print(f"Ultimo controllo: {connection_status.get('last_check')}")
            print("=" * 50)
    except requests.exceptions.RequestException as e:
        print(f"Errore nella chiamata API: {e}")

    return render_template('avvia_irrigazione.html', campo_id=session['id_campo_selezionato'])

@app.route('/reg_irr', methods=['GET', 'POST'])
def registroIrrigazione():
    campo_id = request.args.get('campo_id')
    return render_template('storici.html', campo_id=campo_id)

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