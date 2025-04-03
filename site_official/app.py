from flask import Flask, render_template, redirect, url_for, request, make_response, session, jsonify
from functools import wraps
import pymysql
import datetime
import jwt
import hashlib
import requests
import subprocess
import os
import json

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

########################### Login-Create account #########################

def hash_password(psw):
    return hashlib.sha256(psw.encode()).hexdigest()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ""
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        psw = hash_password(password)
        
        conn = get_db_connection()
        with conn.cursor() as cursor:
            try:
                cursor.execute("SELECT password_hash FROM users WHERE username = %s", (username,))
                p_user = cursor.fetchone()
            finally:
                conn.close()
        
        if p_user and p_user["password_hash"] == psw:
            response = make_response(redirect(url_for("prova")))
            return generate_and_set_token(response, username)
        else:
            error = "Nome utente o password errati."
    
    return render_template("login.html", error=error)

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
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
                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                if user:
                    error = "Username già presente"
                else:
                    cursor.execute(
                        "INSERT INTO users (username, password_hash, email, telefono, nome, cognome, cod_fiscale, DataDiNascita) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (username, psw, email, telefono, nome, cognome, cod_fiscale, data_nascita)
                    )
                    connection.commit()
                    return redirect(url_for('aggiungiCampo'))
        except Exception as e:
            error = "Errore del database"
        finally:
            connection.close()
    
    return render_template('createAccount.html', error=error)

##################################################################################

################################ Cookie-Token ####################################
def generate_token(username):
    payload = {
        "user": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    return jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

def generate_and_set_token(response, username):
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
            decoded = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            kwargs["current_user"] = decoded["user"]
        except jwt.ExpiredSignatureError:
            return redirect(url_for("login"))
        except jwt.InvalidTokenError:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated
################################################################################


################# FUNZIONI BARRA SINISTRA ####################
@app.route('/storici', methods=['GET', 'POST'])
@token_required
def storici(current_user):
    risultato=""
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
                print(risultato)

    return render_template('storici.html', username=current_user, info=risultato, campo = campo_selezionato)

@app.route('/aggiungiCampo', methods=['GET', 'POST'])
@token_required
def aggiungiCampo(current_user):
    error = ""
    session['aggiungiCampo'] = False #usato per il reindirizzamento dopo aver messo le coordinate
    
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
                cursor.execute("SELECT id_u FROM users WHERE username = %s", (current_user,))
                user = cursor.fetchone()
                
                if user is None:
                    error = "Utente non trovato."
                    return render_template('aggiungi_campo.html', error=error)
                user_id = user["id_u"]
                
                cursor.execute(
                    "INSERT INTO fields (id_user, provincia, comune, CAP, num_bestiame, coordinate) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, provincia, comune, cap, num_bestiame, coordinate)
                )
                connection.commit()
                return redirect(url_for('prova'))
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
    # Salvataggio delle coordinate nella sessione
    session['coordinate'] = coordinate
    if session['gestioneCampo'] == True:
        session['gestioneCampo'] = False
        return render_template("gestione_campo.html")
    else:
        session['aggiungiCampo'] = False
        return render_template("aggiungi_campo.html")

@app.route('/mappa', methods=['GET', 'POST'])
def mappa():
    return render_template('mappaOff.html')

@app.route('/mappaManuale', methods=['GET', 'POST'])
def mappaManuale():
    conn = get_db_connection()
    return render_template('mappaManuale.html')

@app.route('/gestioneCampo', methods=['GET', 'POST'])
@token_required
def gestioneCampo(current_user):
    session["gestioneCampo"] = True #usato per il reindirizzamento dopo aver messo le coordinate
    if request.method == 'POST':            
        # Controllo sul tasto di salvataggios
        if 'action-save' in request.form:
            coordinate = session['coordinate', None]
            campo_selezionato = request.form.get('campoSelezionato')
            """ivestock_count = request.form.get('livestockCount')
            country = request.form.get('country')"""
            state = request.form.get('state')
            zip_code = request.form.get('zip')
            
            """print(f"Dati ricevuti dal form nascosto:")
            print(f"Campo selezionato: {campo_selezionato}")
            print(f"Numero bestiame: {livestock_count}")
            print(f"Stato: {country}")"""
            print(coordinate)
            print(f"Campo selezionato: {campo_selezionato}")
            print(session[f"{campo_selezionato}"])
            print(f"Provincia: {state}")
            print(f"CAP: {zip_code}")
            
            # Qui puoi salvare i dati nel database
            # ...
    return render_template('gestione_campo.html')

@app.route('/visualizzaCampi', methods=['GET', 'POST'])
@token_required
def visualizzaCampi(current_user):
    return render_template('visualizzaCampi.html')

"""@app.route('/guidaComandata', methods=['GET', 'POST'])
def guidaComandata():
    return render_template('guida_comandata.html')"""
################################################################

################### PROFILO #################################
@app.route('/profilo', methods=['POST', 'GET'])
@token_required
def profilo(current_user):
    conn = get_db_connection()
    
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM users WHERE username = %s", (current_user,))
        user = cursor.fetchone()
            
    if request.method == 'POST':
        print("ciao")
        if request.form.get('action-salvataggio') == "Salva":
            print("ei")
            nome = request.form['nome']
            print(nome)
    return render_template('profilo.html', user=user)

#############################################################

####################GESTIONE DINAMICA DEI CAMPI E API###############################
def get_campi(current_user):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ottieni tutti i campi dell'utente
    cursor.execute("SELECT COUNT(*) FROM fields f, users u WHERE f.id_user = u.id_u AND u.username = %s", (current_user,))
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
        cursor.execute("SELECT coordinate, comune, num_bestiame FROM users u, fields f WHERE u.username = %s AND u.id_u = f.id_user ", (current_user,))
        risultato = cursor.fetchall()
        info = ""
        for i in range(0, len(risultato)):
            info += str(risultato[i]["coordinate"]) + "/" + str(risultato[i]["comune"]) + "/" + str(risultato[i]["num_bestiame"]) + "|"
        print(info)
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
        comuniP = [comune for comune in comuni if comune['sigla_provincia'] == provincia]
    return jsonify({"comuni": comuniP})
########################################################################################

#############################Avvio del drone#######################################

def avvioDrone(campo):
    prova1_path = os.path.join(os.getcwd(), 'prova1.py')  # Percorso assoluto
    try:
        # Passa il parametro 'campo' come argomento alla riga di comando
        result = subprocess.run(['python', prova1_path, str(campo)], capture_output=True, text=True, check=True)
        output = result.stdout.strip() if result.stdout else "(Nessun output ricevuto)"
        print("Output ricevuto:", output)
        if output == "sono connesso":
            print("Messaggio ricevuto correttamente!")
    except subprocess.CalledProcessError as e:
        print("Errore durante l'esecuzione di prova1.py:", e)
        print("Stdout:", e.stdout)
        print("Stderr:", e.stderr)

###################################################################################

def associazioneSessionCampi(current_user):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT f.id_t FROM users u, fields f WHERE u.username = %s AND u.id_u = f.id_user", (current_user,))
    risultato = cursor.fetchall()
    id_array = [row['id_t'] for row in risultato] 

    cursor.execute("SELECT id_u FROM users WHERE username = %s", (current_user,))
    user_id = cursor.fetchone()['id_u'] 
    session['id'] = user_id

    #assocciazione del id del campo al numero crescente partendo da 1
    if get_campi(current_user) > 0:
        for i, e in enumerate(id_array):
            session[f"campo{i+1}"] = e

@app.route('/', methods=['GET', 'POST'])
@token_required
def prova(current_user): 
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
        #if request.form.get('action-guidaComandata') == "Guida Comandata":
            #resp = make_response(redirect(url_for('guidaComandata')))
        if request.form.get('action-profilo') == "Profilo":
            resp = make_response(redirect(url_for('profilo')))
        if request.form.get('action1') == "log-out":
            resp = make_response(redirect(url_for('login')))
            resp.delete_cookie('token')
        
        #Avvio del drone con acquisizione del campo selezionato
        campo_value = request.form.get('action_ricerca_drone')
        if campo_value and campo_value.startswith("Campo "):
            numero_campo = campo_value.split(" ")[1]  # Estrae il numero del campo
            id_campo = session[f'campo{numero_campo}']
            # Avvia il drone passando il numero del campo
            avvioDrone(id_campo)
            # Reindirizza alla stessa funzione prova
            resp = make_response(redirect(url_for('prova')))
            
        return resp
    
    # Se c'è un campo corrente nella sessione, puoi utilizzarlo per mostrare informazioni specifiche
    campo_corrente = session.get('campo_corrente', None)
    return render_template('prova.html', username=current_user, campo_corrente=campo_corrente)

if __name__ == '__main__':
    app.run(debug=True, host='localhost')
