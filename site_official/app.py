from flask import Flask, render_template, redirect, url_for, request, make_response
from functools import wraps
import pymysql
import datetime
import jwt
import hashlib

############################# Flask-DB connection ##############################
app = Flask(__name__)
app.config["SECRET_KEY"] = "chiave_super_segreta"

# Configurazione della connessione manuale a MariaDB
def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',
        database='alpeggio',
        cursorclass=pymysql.cursors.DictCursor  # Restituisce i risultati come dizionario
    )
###############################################################################

########################### Login-Create account #########################
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = ""
    if request.method == 'POST':
        username = request.form['email']  # Usa il campo 'email' come login
        password = request.form['password']
        print(username)
        print(password)
        
        if validate(username, password):
            resp = make_response(redirect(url_for('prova')))
            return generate_and_set_token(resp, username)
        else:
            error = "Username o password non corretti"
    
    return render_template('login.html', error=error)

# Funzione per validare username e password
def validate(username, password):
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            sql = 'SELECT * FROM users WHERE email = %s AND password_hash = %s'
            cursor.execute(sql, (username, password))
            user = cursor.fetchone()  # Prende il primo risultato
            return user is not None  # Restituisce True se l'utente esiste
    finally:
        connection.close()

def hash(psw):
    return hashlib.sha256(psw.encode()).hexdigest()

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    error = ""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                    cursor.execute("SELECT * FROM users WHERE email = %s", (username, password))
                    user = cursor.fetchone()  # Prende il primo risultato
                    if user:
                        error = "Username già presente"
                    else:
                        cursor.execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)", (username, password))
                        connection.commit()
                        return redirect(url_for('login'))
        except Exception as e:
            error = "errore del database"
        finally:
            connection.close()
    return render_template('createAccount.html', error=error)
##################################################################################


################################ Cookie-Token ####################################
# Funzione per generare il token JWT
def generate_token(username):
    payload = {
        "user": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")
    return token

# Funzione per impostare il token nei cookie
def generate_and_set_token(response, username):
    token = generate_token(username)
    response.set_cookie("token", token, max_age=3600, httponly=True)
    return response

# Decoratore per richiedere il token JWT
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get("token")
        if not token:
            return redirect(url_for("login"))
        try:
            decoded = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            current_user = decoded["user"]
        except jwt.ExpiredSignatureError:
            return redirect(url_for("login"))
        except jwt.InvalidTokenError:
            return redirect(url_for("login"))
        return f(current_user, *args, **kwargs)
    return decorated
################################################################################

################# FUNZIONI BARRA SINISTRA ####################
@app.route('/storici', methods=['GET', 'POST'])
def storici():
    return render_template('storici.html')

@app.route('/aggiungiCampo', methods=['GET', 'POST'])
def aggiungiCampo():
    return render_template('aggiungi_campo.html')

@app.route('/gestioneCampo', methods=['GET', 'POST'])
def gestioneCampo():
    return render_template('gestione_campo.html')
################################################################

@app.route('/', methods=['GET', 'POST'])
@token_required
def prova(current_user): 
    if request.method == 'POST':
        resp = None
        if request.form.get('action-storici') == "Storico Controlli":
            resp = make_response(redirect(url_for('storici')))
        if request.form.get('action-aggCampo') == "Aggiungi Campo":
            resp = make_response(redirect(url_for('aggiungiCampo')))
        if request.form.get('action-gesCampo') == "Gestione Campo":
            resp = make_response(redirect(url_for('gestioneCampo')))
        if request.form.get('action1') == "log-out":
            resp = make_response(redirect(url_for('login')))
            resp.delete_cookie('token')
        return resp
    return render_template('prova.html', username=current_user)
   
if __name__ == '__main__':
    app.run(debug=True, host='localhost')
