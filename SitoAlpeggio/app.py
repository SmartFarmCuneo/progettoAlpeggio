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
from email.mime.text import MIMEText
from flask_mail import Message, Mail


############################# Flask-DB connection ##############################
app = Flask(__name__)
app.config["SECRET_KEY"] = "chiave_super_segreta"


def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='alpeggio',
        cursorclass=pymysql.cursors.DictCursor
    )
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
        max_age=60 * 60 * 24 * 365,  # 1 anno
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

############################## FUNZIONE INVIO MAIL #############################
############################## CONFIG MAIL #############################
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = "tuoaccount@gmail.com"      # <-- cambia qui
app.config['MAIL_PASSWORD'] = "TUA_APP_PASSWORD"          # <-- cambia qui
app.config['MAIL_DEFAULT_SENDER'] = ("Agritech", "tuoaccount@gmail.com")

mail = Mail(app)


def send_reset_email(user_email, code):
    msg = Message("🌱 Agritech - Reset Password", recipients=[user_email])

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
          <img src="https://i.ibb.co/3sWD5Vj/Farm-Logo.png" alt="Agritech Logo">
        </div>
        <div class="content">
          <h1>Richiesta reset password</h1>
          <p>Ciao, abbiamo ricevuto la tua richiesta di reimpostare la password.</p>
          <p>Usa questo codice per procedere:</p>
          <div class="code">{{ code }}</div>
          <p>Se non hai richiesto tu il reset, ignora questa email.</p>
        </div>
        <div class="footer">
          &copy; 2024 Agritech - Innovazione per l'agricoltura del futuro
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
    session['aggiungiCampo'] = False
    coordinate = session.get('coordinate', None)
    if coordinate is None:
        error = "Le coordinate non sono disponibili."
        return render_template('aggiungi_campo.html', error=error)

    if request.method == 'POST':
        provincia = request.form['provincia']
        comune = request.form['comune']
        cap = request.form['cap']
        num_bestiame = request.form['num_bestiame']

        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id_u FROM users WHERE username = %s", (current_user,))
                user_db = cursor.fetchone()

                if user_db is None:
                    error = "Utente non trovato."
                    return render_template('aggiungi_campo.html', error=error)
                user_id = user_db["id_u"]

                cursor.execute(
                    "INSERT INTO fields (id_user, provincia, comune, CAP, num_bestiame, coordinate) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, provincia, comune, cap, num_bestiame, coordinate)
                )
                connection.commit()
                return redirect(url_for('home'))
        except Exception as e:
            error = f"Errore del database: {str(e)}"
            print("Errore durante l'inserimento:", e)
        finally:
            connection.close()

    return render_template('aggiungi_campo.html', error=error)


@app.route('/salva-coordinate', methods=['POST'])
def getCoordinate():
    coordinate = request.form.get('coordinate')
    print(f'Coordinate ricevute: {coordinate}')
    session['coordinate'] = coordinate
    if session['gestioneCampo'] == True:
        session['gestioneCampo'] = False
        return render_template("gestione_campo.html")
    else:
        session['aggiungiCampo'] = False
        return render_template("aggiungi_campo.html")


@app.route('/mappa', methods=['GET', 'POST'])
@token_required
def mappa(current_user):
    return render_template('mappaOff.html')


@app.route('/mappaManuale', methods=['GET', 'POST'])
@token_required
def mappaManuale(current_user):
    return render_template('mappaManuale.html')


@app.route('/gestioneCampo', methods=['GET', 'POST'])
@token_required
def gestioneCampo(current_user):
    session["gestioneCampo"] = True
    if request.method == 'POST':
        if 'action-save' in request.form:
            coordinate = session.get('coordinate')
            campo_selezionato = request.form.get('campoSelezionato')
            state = request.form.get('state')
            zip_code = request.form.get('zip')
            print(coordinate, campo_selezionato, state, zip_code)
    return render_template('gestione_campo.html')


@app.route('/visualizzaCampi', methods=['GET', 'POST'])
@token_required
def visualizzaCampi(current_user):
    return render_template('visualizzaCampi.html')

################################################################

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

@app.route('/pagamenti', methods=['GET', 'POST'])
@token_required
def pagamenti(current_user):
    return render_template('pagamenti.html')

@app.route('/privacy', methods=['GET', 'POST'])
@token_required
def privacy(current_user):
    return render_template('privacy.html')


@app.route('/terms', methods=['GET', 'POST'])
@token_required
def terms(current_user):
    return render_template('terms.html')


#############################################################

#################### GESTIONE DINAMICA DEI CAMPI E API###############################
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
            "SELECT coordinate, comune, num_bestiame FROM users u, fields f WHERE u.username = %s AND u.id_u = f.id_user ", (current_user,))
        risultato = cursor.fetchall()
        info = ""
        for i in range(0, len(risultato)):
            info += str(risultato[i]["coordinate"]) + "/" + str(risultato[i]
                                                                ["comune"]) + "/" + str(risultato[i]["num_bestiame"]) + "|"
        return info


@app.route("/api/infoCampi")
@token_required
def api_info_campi(current_user):
    info = get_info_campi(current_user)
    return jsonify(info)


@app.route("/api/get_provincia")
def get_provincia():
    with open("./static/json/gi_province.json", "r", encoding="utf-8") as file:
        data = json.load(file)
    province = data.get("province", [])
    return jsonify({"province": province})


@app.route("/api/get_comune", methods=["GET"])
def get_comune():
    with open("./static/json/gi_comuni_cap.json", "r", encoding="utf-8") as file:
        data = json.load(file)
    comuni = data.get("dati", [])
    if 'provincia' in request.args:
        provincia = str(request.args['provincia'])
        comuniP = [
            comune for comune in comuni if comune['sigla_provincia'] == provincia]
    return jsonify({"comuni": comuniP})
########################################################################################

############################# Avvio del drone#######################################


def avvioDrone(campo):
    home1_path = os.path.join(os.getcwd(), 'home1.py')
    try:
        result = subprocess.run(['python', home1_path, str(
            campo)], capture_output=True, text=True, check=True)
        output = result.stdout.strip() if result.stdout else "(Nessun output ricevuto)"
        print("Output ricevuto:", output)
        if output == "sono connesso":
            print("Messaggio ricevuto correttamente!")
    except subprocess.CalledProcessError as e:
        print("Errore durante l'esecuzione di home1.py:", e)
        print("Stdout:", e.stdout)
        print("Stderr:", e.stderr)
###################################################################################


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
            pass  # se il token non è valido, resta sulla pagina index
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
            avvioDrone(id_campo)
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
    app.run(debug=True, host='localhost')
    # per pubblicare app.debug=False
