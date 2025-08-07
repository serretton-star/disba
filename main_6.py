from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
import os
from flask import render_template, send_file, render_template_string
import pandas as pd
import io
from werkzeug.utils import secure_filename
from xhtml2pdf import pisa

UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
        # Aggiungi queste righe alla funzione init_db() se non esistono già
        c.execute('''
            CREATE TABLE IF NOT EXISTS magazzino (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_componente INTEGER NOT NULL,
                giacenza REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (id_componente) REFERENCES componenti(id)
            )
        ''')

        c.execute('''
            CREATE TABLE IF NOT EXISTS produzioni (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_distinta INTEGER NOT NULL,
                qty_prodotta INTEGER NOT NULL,
                data_produzione TEXT NOT NULL,
                numero_produzione TEXT,
                FOREIGN KEY (id_distinta) REFERENCES distinte(id)
            )
        ''')
        
        # Testata ordini
        c.execute('''
            CREATE TABLE IF NOT EXISTS ordini_fornitore (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_ordine TEXT NOT NULL,
                id_fornitore INTEGER NOT NULL,
                data_ordine TEXT NOT NULL,
                riferimento_oc TEXT,
                FOREIGN KEY (id_fornitore) REFERENCES fornitori(id)
            )
        ''')

        # Righe ordini
        c.execute('''
            CREATE TABLE IF NOT EXISTS righe_ordine_fornitore (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_ordine INTEGER NOT NULL,
                id_componente INTEGER NOT NULL,
                qty INTEGER NOT NULL,
                data_richiesta TEXT NOT NULL,
                data_confermata TEXT,
                data_consegna TEXT,
                FOREIGN KEY (id_ordine) REFERENCES ordini_fornitore(id),
                FOREIGN KEY (id_componente) REFERENCES componenti(id)
            )
        ''')
        
        # Tabella Clienti
        c.execute('''
            CREATE TABLE IF NOT EXISTS clienti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice TEXT UNIQUE,  -- verrà generato automaticamente
                ragione_sociale TEXT NOT NULL,
                indirizzo TEXT,
                email TEXT,
                telefono TEXT,
                iban TEXT,
                persona_riferimento TEXT,
                note TEXT
            )
        ''')

        conn.commit()
        conn.close()
        
@app.route('/')
def dashboard():
    return render_template("dashboard.html")


@app.route('/distinte')
def distinte():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Recupera distinte
    c.execute("SELECT * FROM distinte")
    distinte_raw = c.fetchall()

    distinte = []
    for d in distinte_raw:
        id_distinta = d[0]
        codice = d[1]
        descrizione = d[2]

        # Calcola costo totale
        c.execute("SELECT SUM(qty * costo) FROM componenti WHERE id_distinta = ?", (id_distinta,))
        totale = c.fetchone()[0]
        if totale is None:
            totale = 0.0

        # Conta i componenti
        c.execute("SELECT COUNT(*) FROM componenti WHERE id_distinta = ?", (id_distinta,))
        n_componenti = c.fetchone()[0]

        distinte.append((id_distinta, codice, descrizione, round(totale, 2), n_componenti))

    conn.close()
    return render_template("lista_distinte.html", distinte=distinte)


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

    # Recupera info distinta
    c.execute("SELECT * FROM distinte WHERE id = ?", (id_distinta,))
    distinta = c.fetchone()

    # Recupera componenti
    c.execute("SELECT * FROM componenti WHERE id_distinta = ?", (id_distinta,))
    componenti = c.fetchall()

    # Calcola costi per macrozona
    c.execute('''
        SELECT macrozona, SUM(costo * qty)
        FROM componenti
        WHERE id_distinta = ?
        GROUP BY macrozona
    ''', (id_distinta,))
    costi_macrozona = c.fetchall()

    # Calcola costo totale
    c.execute("SELECT SUM(costo * qty) FROM componenti WHERE id_distinta = ?", (id_distinta,))
    costo_totale = c.fetchone()[0] or 0

    # Calcola incidenza %
    riassunto = []
    for macrozona, costo in costi_macrozona:
        incidenza = round((costo / costo_totale) * 100, 1) if costo_totale else 0
        riassunto.append((macrozona, round(costo, 2), incidenza))

    conn.close()
    return render_template(
        "dettaglio_distinta.html",
        distinta=distinta,
        componenti=componenti,
        riassunto=riassunto,
        costo_totale=round(costo_totale, 2)
    )

@app.route('/distinta/<int:id_distinta>/export_excel')
def export_distinta_excel(id_distinta):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT * FROM componenti WHERE id_distinta = ?", (id_distinta,))
    componenti = c.fetchall()
    conn.close()

    colonne = ['ID', 'ID Distinta', 'Macrozona', 'Nome', 'Codice', 'Materiale', 'Spessore', 'QTY', 'Lavorazioni', 'Costo', 'Tipo', 'File']
    df = pd.DataFrame(componenti, columns=colonne)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Componenti')
    output.seek(0)

    return send_file(output, download_name=f"distinta_{id_distinta}.xlsx", as_attachment=True)

@app.route('/distinta/<int:id_distinta>/export_pdf')
def export_distinta_pdf(id_distinta):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT * FROM componenti WHERE id_distinta = ?", (id_distinta,))
    componenti = c.fetchall()
    conn.close()

    html = render_template_string("""
        <h2>Distinta {{ id }}</h2>
        <table border="1" cellspacing="0" cellpadding="4">
            <thead>
                <tr>
                    <th>Macrozona</th>
                    <th>Nome</th>
                    <th>Materiale</th>
                    <th>Spessore</th>
                    <th>QTY</th>
                    <th>Lavorazioni</th>
                    <th>Costo</th>
                </tr>
            </thead>
            <tbody>
                {% for c in componenti %}
                <tr>
                    <td>{{ c[2] }}</td>
                    <td>{{ c[3] }}</td>
                    <td>{{ c[5] }}</td>
                    <td>{{ c[6] }}</td>
                    <td>{{ c[7] }}</td>
                    <td>{{ c[8] }}</td>
                    <td>{{ '%.2f'|format(c[9]) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    """, id=id_distinta, componenti=componenti)

    pdf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=pdf)
    pdf.seek(0)

    return send_file(pdf, download_name=f"distinta_{id_distinta}.pdf", as_attachment=True)
    

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
    c.execute("SELECT codice FROM distinte WHERE id=?", (id_distinta,))
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
    
@app.route('/componente/<int:id_componente>/carica-file/<int:id_distinta>', methods=['POST'])
def carica_file_componente(id_componente, id_distinta):
    if 'file' not in request.files:
        return "Nessun file inviato", 400

    file = request.files['file']
    if file.filename == '':
        return "Nome file vuoto", 400

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)

        # Aggiorna la riga del componente con il nome del file
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE componenti SET file = ? WHERE id = ?", (filename, id_componente))
        conn.commit()
        conn.close()

    return redirect(url_for('dettaglio_distinta', id_distinta=id_distinta))

@app.route('/ordini-fornitore')
def elenco_ordini_fornitore():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('''
        SELECT o.id, o.numero_ordine, f.nome, o.data_ordine, o.riferimento_oc
        FROM ordini_fornitore o
        JOIN fornitori f ON o.id_fornitore = f.id
        ORDER BY o.data_ordine DESC
    ''')
    ordini_base = c.fetchall()

    ordini = []
    for o in ordini_base:
        id_ordine = o[0]

        c.execute('''
            SELECT data_confermata, data_consegna
            FROM righe_ordine_fornitore
            WHERE id_ordine = ? AND qty > 0
        ''', (id_ordine,))
        righe = c.fetchall()

        semaforo = "🔴"
        if all(r[1] for r in righe if r):  # tutte le data_consegna sono compilate
            semaforo = "🟢"
        elif all(r[0] for r in righe if r):  # tutte le data_confermata sono compilate
            semaforo = "🟡"

        ordini.append(o + (semaforo,))  # aggiunge lo stato al record

    conn.close()
    return render_template("ordini_fornitore.html", ordini=ordini)


@app.route('/ordine-fornitore/<int:id_ordine>')
def dettaglio_ordine_fornitore(id_ordine):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Testata ordine (aggiungo anche id_fornitore per la query dei prezzi)
    c.execute('''
        SELECT o.numero_ordine, f.nome, f.email, f.telefono, o.data_ordine, o.riferimento_oc, f.id
        FROM ordini_fornitore o
        JOIN fornitori f ON o.id_fornitore = f.id
        WHERE o.id = ?
    ''', (id_ordine,))
    ordine = c.fetchone()

    id_fornitore = ordine[6]  # serve per ottenere i prezzi corretti

    
    c.execute('''
        SELECT 
            c.nome, 
            r.qty, 
            r.data_richiesta, 
            r.data_confermata, 
            r.data_consegna, 
            c.file,
            COALESCE(pf.prezzo, 0) AS prezzo_unitario,
            COALESCE(pf.prezzo, 0) * r.qty AS costo_totale
        FROM righe_ordine_fornitore r
        JOIN componenti c ON r.id_componente = c.id
        LEFT JOIN prezzi_fornitori pf ON pf.id_componente = c.id AND pf.id_fornitore = ?
        WHERE r.id_ordine = ? AND r.qty > 0
    ''', (id_fornitore, id_ordine))

    righe = c.fetchall()

    # Calcolo il totale ordine
    totale_ordine = sum([r[7] for r in righe])

    conn.close()
    return render_template("dettaglio_ordine_fornitore.html",
                           ordine=ordine,
                           righe=righe,
                           id_ordine=id_ordine,
                           totale_ordine=totale_ordine)
        
    
from datetime import datetime
from flask import request

@app.route('/genera-ordine/<int:id_distinta>', methods=['GET', 'POST'])
def genera_ordine_fornitore(id_distinta):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == 'GET':
        # Mostra il form per inserire la quantità da produrre
        c.execute("SELECT codice FROM distinte WHERE id = ?", (id_distinta,))
        nome_distinta = c.fetchone()
        conn.close()
        return render_template("genera_ordine_fornitore.html", id_distinta=id_distinta, nome_distinta=nome_distinta[0] if nome_distinta else "")

    # POST: Riceve la quantità da produrre
    qty_produzione = int(request.form['qty_produzione'])
    data_ordine = datetime.now().strftime('%Y-%m-%d')

    # Recupera componenti della distinta
    c.execute("SELECT id, qty FROM componenti WHERE id_distinta = ?", (id_distinta,))
    componenti = c.fetchall()

    # Raggruppa per fornitore
    fornitori_componenti = {}
    for id_comp, qty_singola in componenti:
        qty_totale = qty_singola * qty_produzione
        c.execute('''
            SELECT id_fornitore, prezzo FROM prezzi_fornitori
            WHERE id_componente = ?
            ORDER BY prezzo ASC
            LIMIT 1
        ''', (id_comp,))
        fornitore = c.fetchone()
        if fornitore:
            id_fornitore, _ = fornitore
            fornitori_componenti.setdefault(id_fornitore, []).append((id_comp, qty_totale))

    # Crea un ordine per ogni fornitore
    for id_fornitore, comp_list in fornitori_componenti.items():
        numero_ordine = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{id_fornitore}"
        riferimento_oc = f"OC-{id_distinta}"

        # Testata ordine
        c.execute('''
            INSERT INTO ordini_fornitore (numero_ordine, id_fornitore, data_ordine, riferimento_oc)
            VALUES (?, ?, ?, ?)
        ''', (numero_ordine, id_fornitore, data_ordine, riferimento_oc))
        id_ordine = c.lastrowid

        # Righe ordine
        for id_comp, qty in comp_list:
            c.execute('''
                INSERT INTO righe_ordine_fornitore (id_ordine, id_componente, qty, data_richiesta)
                VALUES (?, ?, ?, ?)
            ''', (id_ordine, id_comp, qty, data_ordine))

    conn.commit()
    conn.close()
    return redirect(url_for('elenco_ordini_fornitore'))


@app.route('/ordine-fornitore/<int:id_ordine>/modifica', methods=['GET', 'POST'])
def modifica_ordine_fornitore(id_ordine):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == 'POST':
        numero_ordine = request.form['numero_ordine']
        riferimento_oc = request.form['riferimento_oc']
        data_ordine = request.form['data_ordine']

        # Aggiorna testata ordine
        c.execute('''
            UPDATE ordini_fornitore
            SET numero_ordine = ?, riferimento_oc = ?, data_ordine = ?
            WHERE id = ?
        ''', (numero_ordine, riferimento_oc, data_ordine, id_ordine))

        # Aggiorna righe ordine
        righe = request.form.getlist('riga_id')
        qtys = request.form.getlist('qty')
        date_richiesta = request.form.getlist('data_richiesta')
        date_confermata = request.form.getlist('data_confermata')
        date_consegna = request.form.getlist('data_consegna')

        for i in range(len(righe)):
            c.execute('''
                UPDATE righe_ordine_fornitore
                SET qty = ?, data_richiesta = ?, data_confermata = ?, data_consegna = ?
                WHERE id = ?
            ''', (qtys[i], date_richiesta[i], date_confermata[i], date_consegna[i], righe[i]))

        conn.commit()
        conn.close()
        return redirect(url_for('dettaglio_ordine_fornitore', id_ordine=id_ordine))

    # GET: carica dati ordine e righe
    c.execute('''
        SELECT numero_ordine, data_ordine, riferimento_oc
        FROM ordini_fornitore WHERE id = ?
    ''', (id_ordine,))
    testata = c.fetchone()

    c.execute('''
        SELECT r.id, c.nome, r.qty, r.data_richiesta, r.data_confermata, r.data_consegna
        FROM righe_ordine_fornitore r
        JOIN componenti c ON r.id_componente = c.id
        WHERE r.id_ordine = ?
    ''', (id_ordine,))
    righe = c.fetchall()

    conn.close()
    return render_template("modifica_ordine_fornitore.html", id_ordine=id_ordine, testata=testata, righe=righe)

@app.route('/ordine-fornitore/<int:id_ordine>/riga/<int:id_riga>/elimina', methods=['POST'])
def elimina_riga_ordine(id_ordine, id_riga):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM righe_ordine_fornitore WHERE id = ?", (id_riga,))
    conn.commit()
    conn.close()
    return redirect(url_for('modifica_ordine_fornitore', id_ordine=id_ordine))

@app.route('/ordine-fornitore/<int:id_ordine>/elimina', methods=['POST'])
def elimina_ordine_fornitore(id_ordine):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Elimina righe ordine collegate
    c.execute("DELETE FROM righe_ordine_fornitore WHERE id_ordine = ?", (id_ordine,))
    # Elimina la testata dell'ordine
    c.execute("DELETE FROM ordini_fornitore WHERE id = ?", (id_ordine,))

    conn.commit()
    conn.close()
    return redirect(url_for('elenco_ordini_fornitore'))

@app.route('/ordine-fornitore/manuale', methods=['GET', 'POST'])
def crea_ordine_manuale():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == 'POST':
        # Nuovo fornitore o esistente
        id_fornitore = request.form.get('fornitore_esistente')
        if id_fornitore == 'nuovo':
            nome = request.form['nome_nuovo']
            email = request.form['email_nuovo']
            telefono = request.form['telefono_nuovo']
            c.execute('INSERT INTO fornitori (nome, email, telefono) VALUES (?, ?, ?)', (nome, email, telefono))
            id_fornitore = c.lastrowid
        else:
            id_fornitore = int(id_fornitore)

        numero_ordine = f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        data_ordine = datetime.now().strftime('%Y-%m-%d')
        riferimento_oc = request.form['riferimento_oc']

        # Crea ordine
        c.execute('''
            INSERT INTO ordini_fornitore (numero_ordine, id_fornitore, data_ordine, riferimento_oc)
            VALUES (?, ?, ?, ?)
        ''', (numero_ordine, id_fornitore, data_ordine, riferimento_oc))
        id_ordine = c.lastrowid

        # Righe ordine
        componenti = request.form.getlist('componente[]')
        qtys = request.form.getlist('qty[]')
        prezzi = request.form.getlist('prezzo[]')
        data_richiesta = data_ordine

        for comp_id, qty, prezzo in zip(componenti, qtys, prezzi):
            if not comp_id or int(qty) <= 0:
                continue
            c.execute('''
                INSERT INTO righe_ordine_fornitore (id_ordine, id_componente, qty, data_richiesta)
                VALUES (?, ?, ?, ?)
            ''', (id_ordine, int(comp_id), int(qty), data_richiesta))
            # salva anche il prezzo
            c.execute('''
                INSERT OR REPLACE INTO prezzi_fornitori (id_componente, id_fornitore, prezzo)
                VALUES (?, ?, ?)
            ''', (int(comp_id), int(id_fornitore), float(prezzo)))

        conn.commit()
        conn.close()
        return redirect(url_for('elenco_ordini_fornitore'))

    # GET: carica fornitori esistenti e componenti
    c.execute("SELECT id, nome FROM fornitori")
    fornitori = c.fetchall()
    c.execute("SELECT id, nome FROM componenti")
    componenti = c.fetchall()
    conn.close()
    return render_template("ordine_fornitore_manuale.html", fornitori=fornitori, componenti=componenti)
    
@app.route('/nuovo-cliente', methods=['GET', 'POST'])
def nuovo_cliente():
    if request.method == 'POST':
        ragione_sociale = request.form['ragione_sociale']
        indirizzo = request.form['indirizzo']
        email = request.form['email']
        telefono = request.form['telefono']
        iban = request.form['iban']
        persona_rif = request.form['persona_riferimento']
        note = request.form['note']

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO clienti (ragione_sociale, indirizzo, email, telefono, iban, persona_riferimento, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (ragione_sociale, indirizzo, email, telefono, iban, persona_rif, note))
        conn.commit()
        conn.close()
        return redirect(url_for('lista_clienti'))  # oppure altra pagina di conferma

    return render_template('nuovo_cliente.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

