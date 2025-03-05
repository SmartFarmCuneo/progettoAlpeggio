from flask import Flask, render_template, redirect, url_for, request, make_response
from functools import wraps
import pymysql
import datetime
import jwt
import hashlib

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
            print("ciao")
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
    conn = get_db_connection()
    if request.method == 'POST':
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users s JOIN data d on s.id = d.id_u WHERE s.username = ?", (current_user,))
            storici = cursor.fetchall()
    return render_template('storici.html', username=current_user)

@app.route('/aggiungiCampo', methods=['GET', 'POST'])
@token_required
def aggiungiCampo(current_user):
    primaVolta = True

    if request.method == 'POST':
        coordinate = getCoordinate()
        provincia = request.form['provincia']
        comune = request.form['comune']
        cap = request.form['cap']
        num_bestiame = request.form['num_bestiame']
        print(coordinate)

        try:
            connection = get_db_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT id_u FROM users WHERE username = %s", (current_user,))
                id_u = cursor.fetchone()
                cursor.execute(
                    "INSERT INTO users (`id_user`, `provincia`, `comune`, `CAP`, `num_bestiame`, `cordinate`) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (id_u, provincia, comune, cap, num_bestiame, coordinate)
                )
                connection.commit()
                return redirect(url_for('login'))
        except Exception as e:
            error = "Errore del database"
        finally:
            connection.close()
    """if primaVolta == False: 
        primaVolta = False
        return render_template('login.html')"""
    return render_template('aggiungi_campo.html')

@app.route('/salva-coordinate', methods=['POST'])
def getCoordinate():
    coordinate = request.form.get('coordinate')
    print(f'Coordinate ricevute: {coordinate}')
    return render_template("aggiungi_campo.html")

@app.route('/gestioneCampo', methods=['GET', 'POST'])
def gestioneCampo():
    conn = get_db_connection()
    return render_template('gestione_campo.html')

@app.route('/mappa', methods=['GET', 'POST'])
def mappa():
    conn = get_db_connection()
    return render_template('mappaOff.html')

@app.route('/mappaManuale', methods=['GET', 'POST'])
def mappaManuale():
    conn = get_db_connection()
    return render_template('mappaManuale.html')
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
