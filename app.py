from datetime import datetime
import os
import sqlite3
import pandas as pd
import streamlit as st

# Nome del database SQLite
DB_FILE = "cassa_caffe.db"

# Lista iniziale dei colleghi
UTENTI_INIZIALI = [
    "Catalyn",
    "Davide",
    "Dennis",
    "Giuseppe",
    "Leonardo",
    "Michael",
    "Renato",
    "Walter",
]


def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  # Tabella utenti
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS utenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL
        )
    """)
  # Tabella transazioni (versamenti o consumi)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS transazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            utente TEXT NOT NULL,
            tipo TEXT NOT NULL, -- 'Versamento' o 'Consumo'
            importo REAL NOT NULL,
            descrizione TEXT
        )
    """)

  # Inserimento predefinito dei nomi se la tabella è vuota
  cursor.execute("SELECT COUNT(*) FROM utenti")
  if cursor.fetchone()[0] == 0:
    for nome in UTENTI_INIZIALI:
      cursor.execute("INSERT INTO utenti (nome) VALUES (?)", (nome,))

  conn.commit()
  conn.close()


init_db()


# Funzioni di utilità per il DB
def get_utenti():
  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query("SELECT nome FROM utenti ORDER BY nome", conn)
  conn.close()
  return df["nome"].tolist()


def aggiungi_utente(nome):
  try:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO utenti (nome) VALUES (?)", (nome,))
    conn.commit()
    conn.close()
    return True
  except sqlite3.IntegrityError:
    return False


def elimina_utente(nome):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("DELETE FROM utenti WHERE nome = ?", (nome,))
  conn.commit()
  conn.close()


def registra_transazione(data, utente, tipo, importo, descrizione):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO transazioni (data, utente, tipo, importo, descrizione)"
      " VALUES (?, ?, ?, ?, ?)",
      (data, utente, tipo, importo, descrizione),
  )
  conn.commit()
  conn.close()


def get_transazioni():
  conn = sqlite3.connect(DB_FILE)
  df = pd.read_sql_query(
      "SELECT * FROM transazioni ORDER BY data DESC, id DESC", conn
  )
  conn.close()
  return df


def elimina_transazione(trans_id):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("DELETE FROM transazioni WHERE id = ?", (trans_id,))
  conn.commit()
  conn.close()


# --- CONFIGURAZIONE INTERFACCIA STREAMLIT ---
st.set_page_config(
    page_title="Cassa Comune Caffè", page_icon="☕", layout="wide"
)

st.title("☕ Gestione Cassa Comune Caffè")
st.markdown(
    "Avvicina lo smartphone all'adesivo NFC per registrare velocemente il tuo"
    " caffè o il versamento!"
)

# Menu laterale
st.sidebar.header("Menu")
scelta = st.sidebar.radio(
    "Vai a:",
    [
        "Dashboard & Saldi",
        "Nuova Operazione",
        "Gestione Utenti",
        "Storico Transazioni",
    ],
)

utenti = get_utenti()
df_trans = get_transazioni()

# Calcolo saldi per utente e cassa totale
if not df_trans.empty:
  riepilogo = []
  for u in utenti:
    df_u = df_trans[df_trans["utente"] == u]
    versamenti = df_u[df_u["tipo"] == "Versamento"]["importo"].sum()
    consumi = df_u[df_u["tipo"] == "Consumo"]["importo"].sum()
    saldo = versamenti - consumi
    riepilogo.append(
        {
            "Utente": u,
            "Totale Versato (€)": versamenti,
            "Totale Consumato (€)": consumi,
            "Saldo (€)": saldo,
        }
    )
  df_saldi = pd.DataFrame(riepilogo)
  cassa_totale = df_trans.apply(
      lambda row: (
          row["importo"] if row["tipo"] == "Versamento" else -row["importo"]
      ),
      axis=1,
  ).sum()
else:
  df_saldi = pd.DataFrame(
      columns=[
          "Utente",
          "Totale Versato (€)",
          "Totale Consumato (€)",
          "Saldo (€)",
      ]
  )
  for u in utenti:
    df_saldi.loc[len(df_saldi)] = [u, 0.0, 0.0, 0.0]
  cassa_totale = 0.0


# ---------------------------------------------------------
# 1. DASHBOARD & SALDI
# ---------------------------------------------------------
if scelta == "Dashboard & Saldi":
  st.header("📊 Stato della Cassa")

  col1, col2 = st.columns(2)
  with col1:
    st.metric(
        label="Totale Cassa Attuale",
        value=f"€ {cassa_totale:.2f}",
        delta=(
            "In attivo" if cassa_totale >= 0 else "In rosso (Attenzione!)"
        ),
    )
  with col2:
    st.metric(label="Utenti Registrati", value=len(utenti))

  st.subheader("👥 Saldo per Partecipante")
  if not utenti:
    st.info("Nessun utente presente.")
  else:
    st.dataframe(
        df_saldi.style.format({
            "Totale Versato (€)": "€ {:.2f}",
            "Totale Consumato (€)": "€ {:.2f}",
            "Saldo (€)": "€ {:.2f}",
        }),
        width="stretch",
    )


# ---------------------------------------------------------
# 2. NUOVA OPERAZIONE
# ---------------------------------------------------------
elif scelta == "Nuova Operazione":
  st.header("➕ Registra Movimento")

  with st.form("form_operazione"):
    tipo_op = st.selectbox(
        "Tipo di operazione",
        [
            "Consumo (Caffè / Altro)",
            "Versamento (Ricarica cassa)",
        ],
    )
    utente_scelto = st.selectbox("Utente", utenti)

    if "Consumo" in tipo_op:
      importo_default = 0.50
      descrizione_default = "Caffè"
    else:
      importo_default = (
          50.00  # Valore predefinito impostato a 50€ per le ricariche
      )
      descrizione_default = "Ricarica cassa"

    importo = st.number_input(
        "Importo (€)", min_value=0.01, step=0.50, value=importo_default
    )
    descrizione = st.text_input("Descrizione / Note", value=descrizione_default)
    data_op = st.date_input("Data", value=datetime.now())

    submitted = st.form_submit_button("Registra Operazione")

    if submitted:
      tipo_db = "Versamento" if "Versamento" in tipo_op else "Consumo"
      registra_transazione(
          str(data_op), utente_scelto, tipo_db, importo, descrizione
      )
      st.success(
          f"Registrato {tipo_db.lower()} di €{importo:.2f} per {utente_scelto}!"
      )
      st.rerun()


# ---------------------------------------------------------
# 3. GESTIONE UTENTI
# ---------------------------------------------------------
elif scelta == "Gestione Utenti":
  st.header("👤 Gestione Utenti")

  with st.form("form_utente"):
    nuovo_nome = st.text_input("Aggiungi un nuovo collega")
    aggiungi = st.form_submit_button("Aggiungi Utente")

    if aggiungi:
      if nuovo_nome.strip() == "":
        st.error("Inserisci un nome valido.")
      else:
        successo = aggiungi_utente(nuovo_nome.strip())
        if successo:
          st.success(f"Utente '{nuovo_nome.strip()}' aggiunto!")
          st.rerun()
        else:
          st.error("Questo utente esiste già!")

  st.subheader("Elenco Utenti Attuali")
  if utenti:
    cols = st.columns(3)
    for idx, u in enumerate(utenti):
      cols[idx % 3].markdown(f"👤 **{u}**")
  else:
    st.info("Nessun utente presente.")


# ---------------------------------------------------------
# 4. STORICO TRANSAZIONI
# ---------------------------------------------------------
elif scelta == "Storico Transazioni":
  st.header("📜 Storico e Gestione Movimenti")

  if df_trans.empty:
    st.info("Nessuna transazione registrata finora.")
  else:
    filtro_utente = st.selectbox(
        "Filtra per utente", ["Tutti"] + list(utenti)
    )
    df_mostra = (
        df_trans
        if filtro_utente == "Tutti"
        else df_trans[df_trans["utente"] == filtro_utente]
    )

    st.dataframe(df_mostra, width="stretch")

    st.subheader("Annulla / Elimina Transazione Errata")
    id_da_eliminare = st.selectbox(
        "Seleziona l'ID della transazione da eliminare",
        df_mostra["id"].tolist() if not df_mostra.empty else [],
    )

    if st.button("Elimina Transazione Selezionata", type="primary"):
      if id_da_eliminare:
        elimina_transazione(id_da_eliminare)
        st.warning(f"Transazione ID {id_da_eliminare} eliminata.")
        st.rerun()