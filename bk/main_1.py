from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

app = Flask(__name__)
DB_NAME = "database.db"

# Inizializza il database alla prima esecuzione
def init_db():
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # Tabella Distinte
        c.execute('''
            CREATE TABLE distinte (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice TEXT NOT NULL,
                descrizione TEXT
            )
        ''')

        # Tabella Componenti
        c.execute('''
            CREATE TABLE componenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_distinta INTEGER,
                macrozona TEXT,
                nome TEXT,
                codice TEXT,
                materiale TEXT,
                spessore TEXT,
                qty REAL,
                lavorazioni TEXT,
                costo REAL,
                tipo TEXT,
                FOREIGN KEY (id_distinta) REFERENCES distinte(id)
            )
        ''')

        # Tabella Fornitori
        c.execute('''
            CREATE TABLE fornitori (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT,
                telefono TEXT
            )
        ''')

        # Tabella Prezzi Fornitori
        c.execute('''
            CREATE TABLE prezzi_fornitori (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_componente INTEGER,
                id_fornitore INTEGER,
                prezzo REAL,
                FOREIGN KEY (id_componente) REFERENCES componenti(id),
                FOREIGN KEY (id_fornitore) REFERENCES fornitori(id)
            )
        ''')

        conn.commit()
        conn.close()

@app.route('/')
def home():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM distinte")
    distinte = c.fetchall()
    conn.close()
    return render_template("home.html", distinte=distinte)

@app.route('/nuova-distinta', methods=['GET', 'POST'])
def nuova_distinta():
    if request.method == 'POST':
        codice = request.form['codice']
        descrizione = request.form['descrizione']

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO distinte (codice, descrizione) VALUES (?, ?)", (codice, descrizione))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))

    return render_template("nuova_distinta.html")

@app.route('/distinta/<int:id_distinta>')
def dettaglio_distinta(id_distinta):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM distinte WHERE id = ?", (id_distinta,))
    distinta = c.fetchone()
    c.execute("SELECT * FROM componenti WHERE id_distinta = ?", (id_distinta,))
    componenti = c.fetchall()
    conn.close()
    return render_template("dettaglio_distinta.html", distinta=distinta, componenti=componenti)

@app.route('/distinta/<int:id_distinta>/aggiungi-componente', methods=['GET', 'POST'])
def aggiungi_componente(id_distinta):
    if request.method == 'POST':
        macrozona = request.form['macrozona']
        nome = request.form['nome']
        materiale = request.form['materiale']
        spessore = request.form['spessore']
        qty = request.form['qty']
        lavorazioni = request.form['lavorazioni']
        costo = request.form['costo']
        tipo = request.form['tipo']
        codice = f"{macrozona[:3].upper()}-{nome[:5].upper()}"

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO componenti (
                id_distinta, macrozona, nome, codice, materiale,
                spessore, qty, lavorazioni, costo, tipo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (id_distinta, macrozona, nome, codice, materiale, spessore, qty, lavorazioni, costo, tipo))
        conn.commit()
        conn.close()
        return redirect(url_for('dettaglio_distinta', id_distinta=id_distinta))

    return render_template("aggiungi_componente.html", id_distinta=id_distinta)

@app.route('/fornitori')
def elenco_fornitori():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM fornitori")
    fornitori = c.fetchall()
    conn.close()
    return render_template("fornitori.html", fornitori=fornitori)

# Nuovo Fornitore
@app.route('/nuovo-fornitore', methods=['GET', 'POST'])
def nuovo_fornitore():
    if request.method == 'POST':
        nome = request.form['nome'] 
        indirizzo = request.form['indirizzo']
        piva = request.form['piva']
        email = request.form['email']
        telefono = request.form['telefono']
        iban = request.form['iban']
        lavorazioni = request.form['lavorazioni']

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO fornitori (nome, indirizzo, piva, email, telefono, iban, lavorazioni)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (nome, indirizzo, piva, email, telefono, iban, lavorazioni))
        conn.commit()
        conn.close()
        return redirect(url_for('elenco_fornitori'))

    return render_template("nuovo_fornitore.html")


@app.route('/componente/<int:id_componente>/fornitori', methods=['GET', 'POST'])
def fornitori_componente(id_componente):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT nome FROM componenti WHERE id = ?", (id_componente,))
    componente = c.fetchone()
    c.execute("SELECT * FROM fornitori")
    fornitori = c.fetchall()
    c.execute('''
        SELECT pf.id, f.nome, pf.prezzo
        FROM prezzi_fornitori pf
        JOIN fornitori f ON pf.id_fornitore = f.id
        WHERE pf.id_componente = ?
    ''', (id_componente,))
    fornitori_assoc = c.fetchall()
    conn.close()
    return render_template("fornitori_componente.html",
                           componente_nome=componente[0],
                           id_componente=id_componente,
                           fornitori=fornitori,
                           fornitori_assoc=fornitori_assoc)

@app.route('/componente/<int:id_componente>/aggiungi-prezzo', methods=['POST'])
def aggiungi_prezzo_fornitore(id_componente):
    id_fornitore = request.form['id_fornitore']
    prezzo = request.form['prezzo']

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO prezzi_fornitori (id_componente, id_fornitore, prezzo)
        VALUES (?, ?, ?)
    ''', (id_componente, id_fornitore, prezzo))
    conn.commit()
    conn.close()
    return redirect(url_for('fornitori_componente', id_componente=id_componente))
    
# Modifica Componenti    
    
@app.route('/componente/<int:id_componente>/modifica', methods=['GET', 'POST'])
def modifica_componente(id_componente):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if request.method == 'POST':
        macrozona = request.form['macrozona']
        nome = request.form['nome']
        materiale = request.form['materiale']
        spessore = request.form['spessore']
        qty = request.form['qty']
        lavorazioni = request.form['lavorazioni']
        costo = request.form['costo']
        tipo = request.form['tipo']
        codice = f"{macrozona[:3].upper()}-{nome[:5].upper()}"

        c.execute('''
            UPDATE componenti
            SET macrozona=?, nome=?, codice=?, materiale=?, spessore=?,
                qty=?, lavorazioni=?, costo=?, tipo=?
            WHERE id=?
        ''', (macrozona, nome, codice, materiale, spessore, qty, lavorazioni, costo, tipo, id_componente))
        conn.commit()
        # Recupera id_distinta per redirect
        c.execute("SELECT id_distinta FROM componenti WHERE id = ?", (id_componente,))
        id_distinta = c.fetchone()[0]
        conn.close()
        return redirect(url_for('dettaglio_distinta', id_distinta=id_distinta))

    # GET: recupera i dati del componente
    c.execute("SELECT * FROM componenti WHERE id = ?", (id_componente,))
    comp = c.fetchone()
    conn.close()
    return render_template("modifica_componente.html", comp=comp)
    
# AGGIUNTA IN main.py

from flask import Flask, render_template, request, redirect, url_for
import sqlite3

# Simulazione
@app.route("/simula/<int:id_distinta>", methods=['GET', 'POST'])

def simula_distinta(id_distinta):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Recupera info sulla distinta
    c.execute("SELECT nome FROM distinte WHERE id=?", (id_distinta,))
    nome_distinta = c.fetchone()
    if not nome_distinta:
        return "Distinta non trovata", 404

    # Default: quantità 1
    qty = 1
    risultati = []
    costo_totale = 0

    if request.method == 'POST':
        try:
            qty = int(request.form['qty'])
        except:
            qty = 1

        # Recupera componenti
        c.execute("""
            SELECT nome, qty, costo
            FROM componenti
            WHERE id_distinta = ?
        """, (id_distinta,))
        componenti = c.fetchall()

        for nome, qty_singola, costo_unitario in componenti:
            qty_tot = qty_singola * qty
            costo_tot = round(costo_unitario * qty_tot, 2)
            costo_totale += costo_tot
            risultati.append((nome, qty_singola, qty_tot, costo_unitario, costo_tot))

    conn.close()
    return render_template("simulazione.html", nome=nome_distinta[0], id_distinta=id_distinta, qty=qty, risultati=risultati, costo_totale=costo_totale)



if __name__ == '__main__':
    init_db()
    app.run(debug=True)