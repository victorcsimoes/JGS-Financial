# app.py — FinApp (UI clara + tabelas visíveis + botões corrigidos + avisos 3s + valor digitável + CONFIGURAÇÕES + AGENDA PÚBLICA/PRIVADA)
# Execução: streamlit run app.py
# Requisitos: streamlit, pandas, openpyxl
# Opcionais: yfinance (dólar) e plotly (gráficos)

import os
import time
import hashlib
import sqlite3
from io import BytesIO
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, List

import pandas as pd
import streamlit as st
import urllib.parse as urlparse
from calendar import monthrange

# ======== USD opcional ========
try:
    import yfinance as yf
except Exception:
    yf = None

# ======== Gráficos (opcional) ========
try:
    import plotly.express as px
    import plotly.graph_objects as go
except Exception:
    px = None
    go = None

# ---------------------- Constantes ----------------------
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "finapp.db")
ATTACH_DIR = os.path.join(BASE_DIR, "attachments")
SQLITE_TIMEOUT = 4.0
PAGE_TITLE = "FinApp | JVSeps® "

# ---------------------- Config inicial ----------------------
st.set_page_config(page_title=PAGE_TITLE, layout="wide")

# =============== Tema (somente CLARO) & estilos globais ===============
PRIMARY_DARK_BLUE = "#0E2A47"
PRIMARY_BLUE_2   = "#0F4C81"

def apply_global_styles():
    st.markdown(f"""
    <style>
      :root {{
        --finapp-bg:#F7FAFF;
        --finapp-bg-2:#FFFFFF;
        --finapp-primary:{PRIMARY_DARK_BLUE};
        --finapp-primary-2:{PRIMARY_BLUE_2};
        --finapp-text:#0f172a;
        --finapp-text-soft:#475569;
        --finapp-border:#e6ebf2;
        --finapp-shadow:0 6px 18px rgba(14,42,71,0.08);
        --finapp-radius:16px;
        --finapp-grad-1:var(--finapp-primary);
        --finapp-grad-2:var(--finapp-primary-2);
        --finapp-link:#0F4C81;
        --finapp-line-blue:{PRIMARY_DARK_BLUE};
        --finapp-contrast:#ffffff;

        --ticker-offset-top: 18px;
        --ticker-height: 46px;
      }}

      div[data-testid="stDecoration"] {{ display:none !important; }}
      header[data-testid="stHeader"] {{ background: transparent !important; box-shadow: none !important; }}

      html, body, .stApp {{ height: 100%; overflow-y: auto !important; }}
      .stApp {{ background: var(--finapp-bg); color: var(--finapp-text); }}
      .block-container {{ overflow: visible !important; padding-top: .6rem; max-width: 1240px; }}

      h1,h2,h3,h4,h5,h6 {{ color: var(--finapp-primary) !important; letter-spacing:.2px; }}
      .stMarkdown, .markdown-text-container, p, label, span, div {{ color: var(--finapp-text) !important; }}
      .finapp-muted {{ color: var(--finapp-text-soft) !important; }}
      a, .stMarkdown a {{ color: var(--finapp-link) !important; text-decoration: none; }}
      a:hover {{ text-decoration: underline; }}

      /* ===== Barra superior rolante ===== */
      .finapp-marquee-wrap {{ position: sticky; top: var(--ticker-offset-top); z-index: 1000; margin: 0 0 10px 0; }}
      .finapp-marquee {{
        width: 100%; height: var(--ticker-height); overflow: hidden; white-space: nowrap; box-sizing: border-box;
        background: {PRIMARY_DARK_BLUE}; border-radius: 12px; box-shadow: var(--finapp-shadow);
        display: flex; align-items: center; padding: 0 14px;
      }}
      .finapp-marquee, .finapp-marquee * {{ color:#fff !important; fill:#fff !important; }}
      .finapp-marquee span {{ display: inline-block; padding-left: 100%; line-height: var(--ticker-height); animation: finapp-scroll-left 22s linear infinite; }}
      @keyframes finapp-scroll-left {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-100%); }} }}

      /* ===== Tabs ===== */
      .stTabs [role="tablist"] {{
        position: sticky; top: calc(var(--ticker-offset-top) + var(--ticker-height) + 8px); z-index: 999;
        background: var(--finapp-bg); padding: 6px 0; margin-bottom: 8px; border-bottom: none;
      }}
      .stTabs [data-baseweb="tab-list"] {{ gap: 6px; background: transparent; flex-wrap: wrap; }}
      .stTabs [data-baseweb="tab"]{{
        height: 42px; border-radius: 12px; padding: 8px 14px;
        background: var(--finapp-bg-2); border: 1px solid var(--finapp-border);
        color: var(--finapp-primary); box-shadow: var(--finapp-shadow);
      }}
      .stTabs [role="tab"][aria-selected="true"] {{
        background: linear-gradient(90deg, var(--finapp-grad-1), var(--finapp-grad-2)) !important;
        border-color: transparent !important; font-weight: 700; color:#fff !important;
      }}
      .stTabs [role="tab"][aria-selected="true"] * {{ color:#fff !important; }}

      /* ===== Cards / BANNERS ===== */
      .finapp-card {{
        background: var(--finapp-bg-2); border: 1px solid var(--finapp-border);
        border-radius: var(--finapp-radius); padding: 16px 18px; box-shadow: var(--finapp-shadow);
        color: var(--finapp-text) !important;
      }}
      .finapp-card * {{ color: var(--finapp-text) !important; }}
      [data-testid="stAlert"] {{
        background:#FFFFFF !important; border:1px solid var(--finapp-border) !important;
        color: var(--finapp-text) !important; border-radius: 14px !important; box-shadow: var(--finapp-shadow);
      }}
      [data-testid="stAlert"] * {{ color: var(--finapp-text) !important; }}

      /* ===== BOTÕES ===== */
      .stButton > button[kind="primary"], .stForm button, .stDownloadButton > button {{
        background: var(--finapp-grad-2) !important;
        color: var(--finapp-contrast) !important;
        border: 1px solid var(--finapp-grad-2) !important;
        border-radius: 14px; padding: 8px 14px; font-weight: 700;
        transition: all .15s ease; box-shadow: var(--finapp-shadow);
      }}
      .stButton > button[kind="primary"]:hover, .stForm button:hover, .stDownloadButton > button:hover {{
        background: var(--finapp-grad-1) !important; border-color: var(--finapp-grad-1) !important;
        transform: translateY(-1px); color: var(--finapp-contrast) !important;
      }}
      .stDownloadButton > button *, .stButton > button[kind="primary"] *, .stForm button * {{
        color: var(--finapp-contrast) !important; fill: var(--finapp-contrast) !important;
      }}

      /* Secundário */
      .stButton > button[kind="secondary"], .stButton > button:not([kind]) {{
        background: transparent !important;
        color: var(--finapp-primary) !important;
        border: 1.5px solid var(--finapp-primary) !important;
        border-radius: 14px; padding: 8px 14px; font-weight: 700; box-shadow: none !important;
      }}
      .stButton > button[kind="secondary"]:hover, .stButton > button:not([kind]):hover {{
        background: #0E2A4714 !important;
      }}

      /* ===== INPUTS ===== */
      .stTextInput > div > div > input,
      .stNumberInput input,
      .stDateInput input,
      .stSelectbox > div > div {{
        background: var(--finapp-bg-2) !important; color: var(--finapp-text) !important;
        border-radius: 12px !important; border: 1px solid var(--finapp-border) !important; box-shadow: none !important;
      }}
      .stTextInput label, .stNumberInput label, .stDateInput label, .stSelectbox label {{ color: var(--finapp-text) !important; }}
      ::placeholder {{ color: var(--finapp-text-soft); opacity: 0.9; }}

      /* ===== SELECTS ===== */
      [data-baseweb="select"] * {{ background-color: #FFFFFF !important; color: var(--finapp-text) !important; }}
      div[role="combobox"] {{ background-color: #FFFFFF !important; color: var(--finapp-text) !important; border-radius: 12px !important; }}
      ul[role="listbox"], div[role="listbox"] {{ background-color: #FFFFFF !important; color: var(--finapp-text) !important; border: 1px solid #E5E7EB !important; }}
      li[role="option"] {{ background-color: #FFFFFF !important; color: var(--finapp-text) !important; }}
      li[role="option"][aria-selected="true"], li[role="option"]:hover {{ background-color: #EEF2FF !important; color: var(--finapp-text) !important; }}

      /* ===== TABELAS ===== */
      .stTable, .stDataFrame, .stDataFrame div, .stDataFrame table {{ background:#FFFFFF !important; color:#0f172a !important; }}
      [data-testid="stDataFrame"], [data-testid="stTable"] {{ color:#0f172a !important; }}
      [data-testid="stDataFrame"] *, [data-testid="stTable"] * {{ color:#0f172a !important; opacity:1 !important; }}
      .stDataFrame thead th, .stTable thead th {{ background:#FFFFFF !important; color:#0f172a !important; border-color:#E5E7EB !important; }}
      .stDataFrame tbody td, .stTable tbody td {{ background:#FFFFFF !important; color:#0f172a !important; border-color:#E5E7EB !important; }}
      .stDataFrame table tbody tr:nth-child(even) td {{ background:#FAFAFF !important; }}
      .stDataFrame table tbody tr:hover td {{ background:#F0F4FF !important; }}

      /* ===== MÉTRICAS ===== */
      [data-testid="stMetric"] {{
        background:#FFFFFF; border:1px solid var(--finapp-border);
        border-radius:14px; padding:10px 12px; box-shadow:var(--finapp-shadow);
      }}
      [data-testid="stMetricLabel"]{{ color:#64748b !important; font-weight:600 !important; }}
      [data-testid="stMetricValue"]{{ color:#0f172a !important; font-weight:800 !important; }}

      /* ===== File Uploader ===== */
      [data-testid="stFileUploaderDropzone"],
      [data-testid="stFileUploader"] section {{
        background:#FFFFFF !important; border:1px solid #E5E7EB !important; color:#0f172a !important;
        border-radius:14px !important;
      }}
      [data-testid="stFileUploaderDropzone"] * {{ color:#0f172a !important; opacity:1 !important; }}

      /* ===== Grids utilitários ===== */
      .finapp-grid {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); align-items: stretch; }}
      .finapp-grid-2 {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); align-items: stretch; }}

      hr, .stDivider hr, div[role="separator"], div[data-testid="stDivider"] hr {{
        border: none !important; border-top: 1px solid var(--finapp-line-blue) !important; height: 0 !important; margin: 8px 0 !important;
      }}

      section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, var(--finapp-grad-1) 0%, var(--finapp-grad-2) 100%) !important; }}
      section[data-testid="stSidebar"] * {{ color: #e6edf7 !important; }}
      section[data-testid="stSidebar"] .stButton>button {{ background: #ffffff22 !important; border-color: #ffffff33 !important; color:#fff !important; }}
      section[data-testid="stSidebar"] .stButton>button:hover {{ background: #ffffff33 !important; transform: none; color:#fff !important; }}

      @media (max-width: 640px){{ h1,h2 {{ font-size: 1.3rem; }} .finapp-marquee {{ font-size: 0.95rem; }} }}
    </style>
    """, unsafe_allow_html=True)

apply_global_styles()

# ====================== Faixa rolante (data + USD + direitos) ======================
def get_usd_brl() -> Optional[float]:
    try:
        if yf is None:
            return None
        t = yf.Ticker("USDBRL=X")
        p = None
        try:
            p = float(getattr(t, "fast_info", {}).get("last_price", None))
        except Exception:
            p = None
        if p is None:
            hist = t.history(period="1d", auto_adjust=False)
            if not hist.empty:
                p = float(hist["Close"].iloc[-1])
        return p
    except Exception:
        return None

def top_ticker():
    hoje = datetime.now().strftime("%d/%m/%y")
    usd = get_usd_brl()
    usd_txt = f"Dólar: R$ {usd:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if usd else "Dólar: n/d"
    msg = f"{hoje}  •  {usd_txt}  •  Finapp® | todos os direitos reservados."
    st.markdown(
        f'<div class="finapp-marquee-wrap"><div class="finapp-marquee"><span>{msg} &nbsp; • &nbsp; {msg}</span></div></div>',
        unsafe_allow_html=True
    )

# ====================== Utilitários ======================
def do_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def flash(msg: str, kind: str = "success", seconds: float = 3.0):
    if   kind == "success": st.success(msg)
    elif kind == "info":    st.info(msg)
    elif kind == "warning": st.warning(msg)
    elif kind == "error":   st.error(msg)
    else:                   st.write(msg)
    time.sleep(max(0.1, seconds))

def current_theme_base() -> str:
    return "light"

# ====================== DB helpers ======================
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=SQLITE_TIMEOUT)
    try:
        conn.execute("PRAGMA journal_mode=DELETE;")
    except Exception:
        pass
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn

def fetch_df(query: str, params: Tuple = ()) -> pd.DataFrame:
    try:
        with _connect() as conn:
            return pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        st.error(f"Erro ao consultar o banco: {e}")
        return pd.DataFrame()

def exec_sql(query: str, params: Tuple = ()) -> Optional[int]:
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        st.error(f"Erro ao gravar no banco: {e}")
        return None

# ===== Migrações seguras (evitam "duplicate column name") =====
def _table_columns(table: str) -> List[str]:
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({table});")
            cols = [str(r[1]).lower() for r in cur.fetchall()]
            return cols
    except Exception:
        return []

def add_column_if_not_exists(table: str, column_name: str, column_sql_def: str):
    """Adiciona coluna (ALTER TABLE) somente se não existir. Silencioso em caso de corrida."""
    column_name = column_name.lower().strip()
    if column_name in _table_columns(table):
        return
    try:
        with _connect() as conn:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_sql_def};")
            conn.commit()
    except Exception:
        # Silenciar para evitar banner vermelho; se falhar aqui, a coluna provavelmente já existe.
        pass

# ====================== Bootstrap DB ======================
def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def init_db():
    os.makedirs(ATTACH_DIR, exist_ok=True)
    with _connect() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT CHECK(type IN ('bank','cash','card')) NOT NULL,
                institution TEXT,
                number TEXT
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                parent_id INTEGER,
                kind TEXT CHECK(kind IN ('expense','income','tax','payroll')) NOT NULL DEFAULT 'expense'
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trx_date TEXT NOT NULL,
                due_date TEXT,
                paid_date TEXT,
                type TEXT CHECK(type IN ('expense','income','transfer','tax','payroll','card')) NOT NULL,
                sector TEXT,
                cost_center_id INTEGER,
                category_id INTEGER,
                account_id INTEGER,
                card_id INTEGER,
                method TEXT,
                doc_number TEXT,
                counterparty TEXT,
                description TEXT,
                amount REAL NOT NULL,
                status TEXT CHECK(status IN ('planned','paid','overdue','reconciled','canceled')) NOT NULL DEFAULT 'planned',
                tags TEXT,
                origin TEXT CHECK(origin IN ('manual','bank','card','import')) DEFAULT 'manual',
                external_id TEXT UNIQUE,
                attachment_path TEXT
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS payroll (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period TEXT NOT NULL,
                employee TEXT NOT NULL,
                gross REAL NOT NULL,
                charges REAL NOT NULL,
                benefits REAL NOT NULL,
                total REAL NOT NULL,
                paid INTEGER NOT NULL DEFAULT 0
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS taxes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                jurisdiction TEXT,
                code TEXT,
                periodicity TEXT,
                due_day INTEGER
            );
        """)

        # --- Tabela de compromissos da Agenda ---
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                date TEXT,                 -- data base (único) ou início (recorrente)
                is_recurring INTEGER NOT NULL DEFAULT 0,
                recur_rule TEXT,           -- 'daily'|'weekly'|'monthly'|'yearly' ou NULL
                recur_until TEXT,          -- última data (opcional)
                src_transaction_id INTEGER,
                is_public INTEGER NOT NULL DEFAULT 0,
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()

    # === Migrações seguras (só cria se faltar) ===
    # transactions
    add_column_if_not_exists("transactions", "show_on_calendar", "show_on_calendar INTEGER NOT NULL DEFAULT 0")
    add_column_if_not_exists("transactions", "cal_is_recurring", "cal_is_recurring INTEGER NOT NULL DEFAULT 0")
    add_column_if_not_exists("transactions", "cal_recur_rule", "cal_recur_rule TEXT")

    # calendar_events: alguns bancos podem ter usado 'event_date' ao invés de 'date'
    add_column_if_not_exists("calendar_events", "event_date", "event_date TEXT")
    add_column_if_not_exists("calendar_events", "is_public", "is_public INTEGER NOT NULL DEFAULT 0")
    add_column_if_not_exists("calendar_events", "created_by", "created_by INTEGER")

def seed_minimums():
    if fetch_df("SELECT COUNT(*) as n FROM accounts").iloc[0, 0] == 0:
        exec_sql("INSERT INTO accounts (name, type, institution, number) VALUES (?,?,?,?)",
                 ("Conta Corrente Principal", 'bank', 'Banco Exemplo', '0001-1'))
        exec_sql("INSERT INTO accounts (name, type, institution, number) VALUES (?,?,?,?)",
                 ("Caixa", 'cash', '', ''))
    if fetch_df("SELECT COUNT(*) as n FROM categories").iloc[0, 0] == 0:
        base = [
            ("Energia Elétrica", None, 'expense'),
            ("Água", None, 'expense'),
            ("Frete", None, 'expense'),
            ("Vendas", None, 'income'),
            ("ICMS", None, 'tax'),
            ("Folha - Salários", None, 'payroll'),
        ]
        for n, p, k in base:
            exec_sql("INSERT INTO categories (name,parent_id,kind) VALUES (?,?,?)", (n, p, k))
    if fetch_df("SELECT COUNT(*) as n FROM sectors").iloc[0, 0] == 0:
        for s in ["Administrativo", "Produção", "Comercial", "Logística", "Outros"]:
            exec_sql("INSERT INTO sectors (name) VALUES (?)", (s,))

# ===== Helper: coluna de data na tabela calendar_events pode variar =====
_CAL_DATE_COL = None
def _detect_calendar_date_col() -> str:
    """Detecta se calendar_events usa 'date' ou 'event_date'. Se nenhuma existir, cria 'date'."""
    try:
        info = fetch_df("PRAGMA table_info(calendar_events)")
        cols = [str(n).lower() for n in info.get("name", [])]
        if "date" in cols:
            return "date"
        if "event_date" in cols:
            return "event_date"
    except Exception:
        pass
    try:
        add_column_if_not_exists("calendar_events", "date", "date TEXT")
        return "date"
    except Exception:
        return "date"

def cal_date_col() -> str:
    global _CAL_DATE_COL
    if _CAL_DATE_COL is None:
        _CAL_DATE_COL = _detect_calendar_date_col()
    return _CAL_DATE_COL

# ====================== Escopo (placeholder para multi-empresa) ======================
def scope_filters(base_query: str, params: List) -> Tuple[str, List]:
    return base_query, params

# ====================== Helpers UI/Export ======================
def money(v: float) -> str:
    try:
        return (f"R$ {float(v):,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def safe_label(x):
    try:
        lab = x[1] if isinstance(x, tuple) else x
        if lab is None or (isinstance(lab, float) and pd.isna(lab)):
            return "—"
        return str(lab)
    except Exception:
        return "—"

def export_excel(df: pd.DataFrame, filename: str = "relatorio.xlsx"):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    st.download_button("⬇️ Exportar Excel", data=buf.getvalue(),
                       file_name=filename,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def export_csv(df: pd.DataFrame, filename: str = "relatorio.csv"):
    st.download_button("⬇️ Exportar CSV",
                       data=df.to_csv(index=False).encode("utf-8"),
                       file_name=filename,
                       mime="text/csv")

def _read_file_bytes(path: str) -> Optional[bytes]:
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None

def show_attachment_ui(path: str):
    if not path or not os.path.exists(path):
        st.warning("Anexo não encontrado no disco.")
        return
    fname = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    data = _read_file_bytes(path)
    if data is None:
        st.error("Falha ao abrir o anexo.")
        return
    if ext in (".png", ".jpg", ".jpeg"):
        st.image(data, caption=fname, use_column_width=True)
    else:
        st.info("Pré-visualização inline disponível apenas para imagens. Use o botão para baixar o arquivo.")
    st.download_button("⬇️ Baixar anexo", data=data, file_name=fname)

# ====================== Agenda: helpers ======================
def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")

def add_calendar_event(
    title: str,
    dt: date,
    description: str = "",
    is_recurring: bool = False,
    recur_rule: Optional[str] = None,
    recur_until: Optional[date] = None,
    src_transaction_id: Optional[int] = None,
    is_public: bool = False,
    created_by: Optional[int] = None,
):
    col = cal_date_col()
    exec_sql(
        f"""
        INSERT INTO calendar_events (title, description, {col}, is_recurring, recur_rule, recur_until,
                                     src_transaction_id, is_public, created_by)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            title.strip(),
            (description or "").strip(),
            dt.isoformat(),
            1 if is_recurring else 0,
            (recur_rule or None),
            (recur_until.isoformat() if recur_until else None),
            src_transaction_id,
            1 if is_public else 0,
            created_by,
        ),
    )

def update_calendar_event(eid: int, title: str, description: str, dt: date,
                          is_recurring: bool, recur_rule: Optional[str], recur_until: Optional[date],
                          is_public: bool):
    col = cal_date_col()
    exec_sql(
        f"""
        UPDATE calendar_events
           SET title=?, description=?, {col}=?, is_recurring=?, recur_rule=?, recur_until=?, is_public=?
         WHERE id=?
        """,
        (
            title.strip(), (description or "").strip(), dt.isoformat(),
            1 if is_recurring else 0, (recur_rule or None),
            (recur_until.isoformat() if recur_until else None),
            1 if is_public else 0,
            int(eid),
        ),
    )

def delete_calendar_event(eid: int):
    exec_sql("DELETE FROM calendar_events WHERE id=?", (int(eid),))

def duplicate_calendar_event(eid: int, new_owner_id: Optional[int] = None):
    col = cal_date_col()
    df = fetch_df(f"SELECT *, {col} AS ev_date FROM calendar_events WHERE id=?", (int(eid),))
    if df.empty:
        return
    r = df.iloc[0]
    base_dt = _parse_date(str(r["ev_date"])).date()

    add_calendar_event(
        title=f"{r['title']} (cópia)",
        dt=base_dt,
        description=(r.get("description") or ""),
        is_recurring=bool(r.get("is_recurring", 0)),
        recur_rule=(r.get("recur_rule") if pd.notna(r.get("recur_rule")) else None),
        recur_until=(
            _parse_date(str(r["recur_until"])).date()
            if pd.notna(r.get("recur_until")) and r.get("recur_until")
            else None
        ),
        src_transaction_id=(
            int(r["src_transaction_id"]) if pd.notna(r.get("src_transaction_id")) else None
        ),
        is_public=bool(r.get("is_public", 0)),
        created_by=(
            new_owner_id
            if new_owner_id is not None
            else (int(r["created_by"]) if pd.notna(r.get("created_by"])) else None)
        ),
    )

def _expand_event_occurrences(row: pd.Series, month_start: date, month_end: date) -> List[Tuple[date, int, str]]:
    base = _parse_date(str(row["ev_date"])).date()
    eid = int(row["id"])
    title = str(row["title"])
    is_rec = bool(row.get("is_recurring", 0))
    rule = (row.get("recur_rule") if pd.notna(row.get("recur_rule")) else None)
    until = (_parse_date(str(row["recur_until"])).date() if pd.notna(row.get("recur_until")) and row.get("recur_until") else None)

    if not is_rec or not rule:
        if month_start <= base <= month_end:
            return [(base, eid, title)]
        return []

    cur = base
    out = []
    hard_limit = 400
    steps = 0
    while cur <= month_end and steps < hard_limit:
        if cur >= month_start:
            out.append((cur, eid, title))
        if rule == "daily":
            cur = cur + pd.Timedelta(days=1).to_pytimedelta()
        elif rule == "weekly":
            cur = cur + pd.Timedelta(weeks=1).to_pytimedelta()
        elif rule == "monthly":
            y, m = cur.year, cur.month
            if m == 12:
                y, m = y+1, 1
            else:
                m += 1
            last = monthrange(y, m)[1]
            d = min(cur.day, last)
            cur = date(y, m, d)
        elif rule == "yearly":
            try:
                cur = date(cur.year+1, cur.month, cur.day)
            except ValueError:
                cur = date(cur.year+1, cur.month, monthrange(cur.year+1, cur.month)[1])
        else:
            break
        steps += 1
        if until and cur > until:
            break
    return out

def _get_user_id() -> Optional[int]:
    u = st.session_state.get("user")
    return int(u["id"]) if u and "id" in u else None

def get_month_events(year: int, month: int, scope: str = "mine") -> List[Tuple[date, int, str]]:
    """
    scope: 'mine'  -> eventos públicos + privados do usuário logado
           'public'-> apenas eventos públicos
    """
    uid = _get_user_id()
    col = cal_date_col()
    if scope == "public":
        df = fetch_df(f"SELECT *, {col} AS ev_date FROM calendar_events WHERE is_public=1")
    else:
        if uid is not None:
            df = fetch_df(
                f"SELECT *, {col} AS ev_date FROM calendar_events WHERE (is_public=1) OR (is_public=0 AND created_by=?)",
                (uid,),
            )
        else:
            df = fetch_df(f"SELECT *, {col} AS ev_date FROM calendar_events WHERE is_public=1")

    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    all_occ = []
    for _, row in df.iterrows():
        if pd.isna(row.get("ev_date")) or not str(row["ev_date"]).strip():
            continue
        all_occ.extend(_expand_event_occurrences(row, month_start, month_end))
    return sorted(all_occ, key=lambda x: (x[0], x[1]))

# ====================== Tabelas estáticas legíveis ======================
def show_df(df: pd.DataFrame, empty_msg: str = "Sem dados para exibir."):
    if df is None or df.empty:
        st.info(empty_msg)
        return
    try:
        styler = (
            df.style
              .set_properties(**{"color":"#0f172a", "border-color":"#E5E7EB"})
              .set_table_styles([
                  {"selector":"th", "props":[("color","#0f172a"),("border","1px solid #E5E7EB"),("background","#FFFFFF")]},
                  {"selector":"td", "props":[("color","#0f172a"),("border","1px solid #E5E7EB"),("background","#FFFFFF")]},
                  {"selector":"tbody tr:nth-child(even) td", "props":[("background","#FAFAFF")]},
              ])
        )
        st.table(styler)
    except Exception:
        st.table(df)

# ====================== Login & Cadastro (compacto) ======================
def signup_widget():
    if "user" in st.session_state:
        return
    with st.sidebar.expander("🆕 Cadastro rápido", expanded=False):
        name = st.text_input("Nome completo", key="su_name")
        email = st.text_input("Email", key="su_email")
        pwd = st.text_input("Senha", type="password", key="su_pwd")
        pwd2 = st.text_input("Confirmar senha", type="password", key="su_pwd2")
        if st.button("Criar conta e entrar", key="su_btn"):
            if not (name and email and pwd and pwd2):
                st.sidebar.error("Preencha todos os campos.")
            elif pwd != pwd2:
                st.sidebar.error("As senhas não coincidem.")
            else:
                exists = fetch_df("SELECT id FROM users WHERE email=?", (email.strip().lower(),))
                if not exists.empty:
                    st.sidebar.error("Email já cadastrado.")
                else:
                    exec_sql(
                        "INSERT INTO users (name,email,password_hash,role,account_id,sectors,is_active) VALUES (?,?,?,?,?,?,1)",
                        (name.strip(), email.strip().lower(), hash_password(pwd), "launcher", None, "",)
                    )
                    user_id = int(fetch_df("SELECT id FROM users WHERE email=?", (email.strip().lower(),)).iloc[0]["id"])
                    st.session_state["user"] = {
                        "id": user_id,
                        "name": name.strip(),
                        "email": email.strip().lower(),
                        "role": "launcher",
                        "account_id": None,
                        "sectors": [],
                    }
                    flash("Conta criada e login efetuado.", "success", 3)
                    do_rerun()

def login_widget() -> bool:
    if "user" not in st.session_state:
        st.sidebar.markdown("### Entrar")
        email = st.sidebar.text_input("Email")
        pwd = st.sidebar.text_input("Senha", type="password")
        ok = st.sidebar.button("Login")
        if ok:
            u = fetch_df("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
            if not u.empty and u.iloc[0]["password_hash"] == hash_password(pwd):
                st.session_state["user"] = {
                    "id": int(u.iloc[0]["id"]),
                    "name": u.iloc[0]["name"],
                    "email": u.iloc[0]["email"],
                    "role": u.iloc[0]["role"],
                    "account_id": int(u.iloc[0]["account_id"]) if pd.notna(u.iloc[0]["account_id"]) else None,
                    "sectors": [s.strip() for s in str(u.iloc[0]["sectors"] or "").split(",") if s.strip()],
                }
                do_rerun()
            else:
                st.sidebar.error("Credenciais inválidas.")
        return False

    u = st.session_state["user"]
    with st.sidebar.container():
        st.markdown(f"**{u['name']}**\n\n`{u['email']}`\n\n• Permissão: **{('Gerencial' if u['role']=='manager' else 'Lançador')}**")
        if st.sidebar.button("Sair"):
            del st.session_state["user"]
            do_rerun()
    return True

# ====================== KPIs ======================
def kpis_cards():
    base = (
        "SELECT "
        "SUM(CASE WHEN type IN ('expense','tax','payroll','card') THEN amount ELSE 0 END) AS total_desp, "
        "SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS total_rec "
        "FROM transactions WHERE 1=1"
    )
    base, params = scope_filters(base, [])
    df_kpi = fetch_df(base, tuple(params))
    total_desp = float(df_kpi.iloc[0]["total_desp"] or 0) if not df_kpi.empty else 0.0
    total_rec  = float(df_kpi.iloc[0]["total_rec"]  or 0) if not df_kpi.empty else 0.0
    saldo = total_rec - total_desp

    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Receitas", money(total_rec))
    c2.metric("Despesas", money(total_desp))
    c3.metric("Saldo", money(saldo))
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== Entrada livre de dinheiro ======================
def money_input(label: str, key: Optional[str] = None, value: str = "", help: Optional[str] = None) -> float:
    raw = st.text_input(label, value=value, key=key, help=help, placeholder="0,00")
    raw = (raw or "").strip().replace(" ", "")
    if raw == "":
        return 0.0
    cleaned = raw
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        val = float(cleaned)
    except Exception:
        val = 0.0
    return val

# ====================== Formulário genérico ======================
def form_lancamento_generico(default_type: str = 'expense', label: str = "Novo lançamento", force_account_id: Optional[int] = None):
    st.markdown(f"### {label}")
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    with st.form(f"form_{label}_{default_type}"):
        c1, c2, c3 = st.columns(3)
        dt_val = c1.date_input("Data", value=date.today())
        amount = money_input("Valor (R$)", key=f"money_{label}_{default_type}")
        method = c3.selectbox("Meio de Pagamento", ["pix", "ted", "boleto", "dinheiro", "cartão", "outro"]) if default_type != 'card' else "cartão"

        c4, c5, c6 = st.columns(3)
        accounts_df = fetch_df("SELECT id, name FROM accounts WHERE type <> 'card'")
        if force_account_id:
            acc = (
                (force_account_id, accounts_df.loc[accounts_df.id == force_account_id, "name"].values[0])
                if (not accounts_df.empty and (accounts_df.id == force_account_id).any())
                else (None, "—")
            )
            c4.caption(f"Conta vinculada: {acc[1]}")
            acc_value = acc
        else:
            acc_options = [(None, "—")] + [(int(r.id), r.name) for _, r in accounts_df.iterrows()]
            acc_value = c4.selectbox("Conta", options=acc_options, format_func=safe_label)

        if default_type != 'income':
            categories_df = fetch_df("SELECT id, name FROM categories WHERE kind IN ('expense','tax','payroll')")
        else:
            categories_df = fetch_df("SELECT id, name FROM categories WHERE kind = 'income'")
        cat_options = [(None, "—")] + [(int(r.id), r.name) for _, r in categories_df.iterrows()]
        cat = c5.selectbox("Categoria", options=cat_options, format_func=safe_label)

        sectors_df = fetch_df("SELECT name FROM sectors ORDER BY name")
        sector_options = [s for s in sectors_df["name"].tolist()] if not sectors_df.empty else ["Administrativo","Produção","Comercial","Logística","Outros"]
        sector = c6.selectbox("Setor", sector_options)

        c7, c8 = st.columns([2, 1])
        desc = c7.text_input("Descrição")
        doc = c8.text_input("Documento/Nota")

        c9, c10, c11 = st.columns(3)
        party = c9.text_input("Contraparte (fornecedor/cliente)")
        status_index = 1 if default_type != "income" else 0
        status = c10.selectbox("Status", ["planned", "paid", "overdue", "reconciled", "canceled"], index=status_index)
        attach = c11.file_uploader("Comprovante (opcional)", type=["pdf", "png", "jpg", "jpeg"])

        st.markdown("---")
        c12, c13, c14 = st.columns([1,1,1])
        show_on_cal = c12.toggle("Agendar?", value=False, help="Exibir este lançamento na Agenda")
        recur_kind = "único"
        recur_rule = None
        recur_until = None
        is_public = False
        if show_on_cal:
            vis = c13.selectbox("Visibilidade", ["Privado", "Público"], index=0)
            is_public = (vis == "Público")
            recur_kind = c14.selectbox("Recorrência", ["único", "recorrente"], index=0)
            if recur_kind == "recorrente":
                c15, c16 = st.columns(2)
                recur_rule = c15.selectbox(
                    "Periodicidade",
                    ["daily","weekly","monthly","yearly"], index=2,
                    format_func=lambda x: {"daily":"Diária","weekly":"Semanal","monthly":"Mensal","yearly":"Anual"}[x]
                )
                default_until = dt_val + timedelta(days=30)
                recur_until = c16.date_input("Repetir até (opcional)", value=default_until, key=f"until_{label}_{default_type}")

        submitted = st.form_submit_button("Salvar lançamento")
        if submitted:
            if amount <= 0:
                flash("Informe um valor maior que zero.", "warning", 3)
            else:
                attach_path = None
                if attach is not None:
                    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{attach.name}"
                    fpath = os.path.join(ATTACH_DIR, fname)
                    try:
                        with open(fpath, "wb") as f:
                            f.write(attach.getbuffer())
                        attach_path = fpath
                    except Exception as e:
                        flash(f"Falha ao salvar anexo: {e}", "error", 3)

                account_id_final = force_account_id if force_account_id else (acc_value[0] if isinstance(acc_value, tuple) else None)
                trx_id = exec_sql(
                    """
                    INSERT INTO transactions (
                        trx_date, type, sector, cost_center_id, category_id, account_id,
                        method, doc_number, counterparty, description, amount, status, origin, attachment_path,
                        show_on_calendar, cal_is_recurring, cal_recur_rule
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, ?, ?, ?)
                    """,
                    (
                        dt_val.isoformat(), default_type, sector,
                        None,
                        (cat[0] if isinstance(cat, tuple) else None),
                        account_id_final,
                        method, doc, party, desc, float(amount), status, "manual", attach_path,
                        (1 if show_on_cal else 0),
                        (1 if (show_on_cal and recur_kind=="recorrente") else 0),
                        (recur_rule if (show_on_cal and recur_kind=="recorrente") else None)
                    ),
                )
                if show_on_cal:
                    title = (desc.strip() or f"{'Receita' if default_type=='income' else 'Despesa'} - {money(amount)}").strip()
                    add_calendar_event(
                        title=title,
                        dt=dt_val,
                        description=f"Vinculado ao lançamento #{trx_id}",
                        is_recurring=(recur_kind=="recorrente"),
                        recur_rule=recur_rule,
                        recur_until=recur_until,
                        src_transaction_id=int(trx_id) if trx_id else None,
                        is_public=is_public,
                        created_by=_get_user_id()
                    )
                flash("Lançamento salvo com sucesso.", "success", 3)
                do_rerun()
    st.markdown('</div>', unsafe_allow_html=True)

def tabela_lancamentos_filtro():
    st.markdown("### Filtro de lançamentos")
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    dt_ini = c1.date_input("De", value=date(date.today().year, 1, 1))
    dt_fim = c2.date_input("Até", value=date.today())
    tipo = c3.selectbox("Tipo", ["Todos", "income", "expense", "tax", "payroll", "card", "transfer"])
    status = c4.selectbox("Status", ["Todos", "planned", "paid", "overdue", "reconciled", "canceled"])

    q = """
        SELECT t.id, t.trx_date as Data, t.type as Tipo, t.description as Descrição, t.amount as Valor,
               (SELECT name FROM categories c WHERE c.id = t.category_id) as Categoria,
               (SELECT name FROM accounts a WHERE a.id = t.account_id) as Conta,
               t.sector as Setor, t.status as Status, t.attachment_path as Anexo
        FROM transactions t
        WHERE date(t.trx_date) BETWEEN ? AND ?
    """
    params: List = [dt_ini.isoformat(), dt_fim.isoformat()]
    if tipo != "Todos":
        q += " AND t.type = ?"
        params.append(tipo)
    if status != "Todos":
        q += " AND t.status = ?"
        params.append(status)

    q, params = scope_filters(q, params)
    q += " ORDER BY date(t.trx_date) DESC, t.id DESC"

    df = fetch_df(q, tuple(params))
    show_df(df, empty_msg="Sem lançamentos no período.")
    col1, col2 = st.columns(2)
    with col1:
        export_excel(df, "lancamentos.xlsx")
    with col2:
        export_csv(df, "lancamentos.csv")

    st.caption("Clique em um ID abaixo para visualizar o anexo, se houver.")
    ids = df["id"].tolist() if not df.empty else []
    if ids:
        id_sel = st.selectbox("ID do lançamento", options=ids)
        if id_sel:
            path = fetch_df("SELECT attachment_path FROM transactions WHERE id=?", (id_sel,))
            if not path.empty and pd.notna(path.iloc[0, 0]) and str(path.iloc[0, 0]).strip():
                show_attachment_ui(str(path.iloc[0, 0]))
            else:
                st.info("Este lançamento não possui anexo salvo.")
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== Páginas principais ======================
def _fluxo_caixa_df():
    q = """
        SELECT
            strftime('%Y-%m', date(trx_date)) as ym,
            SUM(CASE WHEN type='income' THEN amount ELSE 0 END) -
            SUM(CASE WHEN type IN ('expense','tax','payroll','card') THEN amount ELSE 0 END) AS saldo
        FROM transactions
        GROUP BY ym
        ORDER BY ym ASC
    """
    df = fetch_df(q)
    if df.empty:
        return pd.DataFrame({"mes_label": ["Jan","Fev","Mar","Abr","Mai","Jun"], "saldo": [0,0,0,0,0,0]})
    df["ym_dt"] = pd.to_datetime(df["ym"] + "-01")
    df["mes_label"] = df["ym_dt"].dt.strftime("%b/%y").str.title()
    df = df[["mes_label","saldo"]].tail(6).reset_index(drop=True)
    return df

def page_home():
    st.markdown("## Home")
    kpis_cards()

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.subheader("Fluxo de Caixa (Mensal)")
    df_fluxo = _fluxo_caixa_df()
    tpl = "plotly_white"; paper_bg = "rgba(0,0,0,0)"
    if go and not df_fluxo.empty:
        fig_fluxo = go.Figure(data=[go.Bar(x=df_fluxo["mes_label"], y=df_fluxo["saldo"])])
        fig_fluxo.update_layout(template=tpl, paper_bgcolor=paper_bg, plot_bgcolor=paper_bg,
                                margin=dict(t=20,b=12,l=12,r=12), height=300,
                                yaxis_title="Saldo (R$)", xaxis_title="Mês")
        st.plotly_chart(fig_fluxo, use_container_width=True)
    else:
        st.bar_chart(df_fluxo.set_index("mes_label"))

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.subheader("Dashboards")
    palette = ["#0F4C81","#1E88E5","#90CAF9","#1565C0","#64B5F6","#1976D2","#42A5F5","#5E81AC","#81A1C1"]
    tpl = "plotly_white"

    q_desp = """
        SELECT
            COALESCE((SELECT name FROM categories c WHERE c.id = t.category_id),'(sem categoria)') as Categoria,
            SUM(t.amount) as Total
        FROM transactions t
        WHERE t.type IN ('expense','tax','payroll','card')
        GROUP BY Categoria
        ORDER BY Total DESC
    """
    q_desp, p_desp = scope_filters(q_desp, [])
    df_desp = fetch_df(q_desp, tuple(p_desp))

    q_rec = """
        SELECT
            COALESCE((SELECT name FROM categories c WHERE c.id = t.category_id),'(sem categoria)') as Categoria,
            SUM(t.amount) as Total
        FROM transactions t
        WHERE t.type = 'income'
        GROUP BY Categoria
        ORDER BY Total DESC
    """
    q_rec, p_rec = scope_filters(q_rec, [])
    df_rec = fetch_df(q_rec, tuple(p_rec))

    st.markdown('<div class="finapp-grid">', unsafe_allow_html=True)

    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    st.markdown("**Despesas por Categoria**")
    if px and not df_desp.empty and df_desp["Total"].sum() > 0:
        fig1 = px.pie(df_desp, names="Categoria", values="Total", hole=0.35, color_discrete_sequence=palette)
        fig1.update_traces(textposition='inside', textinfo='percent+label')
        fig1.update_layout(template=tpl, paper_bgcolor=paper_bg, plot_bgcolor=paper_bg, margin=dict(t=20,b=12,l=12,r=12))
        st.plotly_chart(fig1, use_container_width=True)
    elif df_desp.empty:
        st.info("Sem dados de despesas para exibir.")
    else:
        show_df(df_desp)
        st.caption("Instale o plotly para ver o gráfico: pip install plotly")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    st.markdown("**Receitas por Categoria**")
    if px and not df_rec.empty and df_rec["Total"].sum() > 0:
        fig2 = px.pie(df_rec, names="Categoria", values="Total", hole=0.35, color_discrete_sequence=palette)
        fig2.update_traces(textposition='inside', textinfo='percent+label')
        fig2.update_layout(template=tpl, paper_bgcolor=paper_bg, plot_bgcolor=paper_bg, margin=dict(t=20,b=12,l=12,r=12))
        st.plotly_chart(fig2, use_container_width=True)
    elif df_rec.empty:
        st.info("Sem dados de receitas para exibir.")
    else:
        show_df(df_rec)
        st.caption("Instale o plotly para ver o gráfico: pip install plotly")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.subheader("Links úteis")
    st.markdown('<div class="finapp-grid-2">', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="finapp-card">
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="width:40px;height:40px;border-radius:10px;background:#25D366;display:flex;align-items:center;justify-content:center;color:white;font-weight:900;">
              W
            </div>
            <div>
              <div style="font-weight:700;">WhatsApp</div>
              <div class="finapp-muted" style="font-size:0.95rem;">Abrir WhatsApp Web</div>
            </div>
          </div>
          <div style="margin-top:10px;">
            <a href="https://web.whatsapp.com" target="_blank" rel="noopener">Abrir no navegador</a>
          </div>
        </div>
        """, unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="finapp-card">
          <div style="display:flex;align-items:center;gap:12px;">
            <div style="width:40px;height:40px;border-radius:10px;background:linear-gradient(90deg,#0E2A47,#0F4C81);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:900;">
              RF
            </div>
            <div>
              <div style="font-weight:700;">Receita Federal</div>
              <div class="finapp-muted" style="font-size:0.95rem;">Portal oficial do Governo</div>
            </div>
          </div>
          <div style="margin-top:10px;">
            <a href="https://www.gov.br/receitafederal/pt-br" target="_blank" rel="noopener">Acessar Receita Federal</a>
          </div>
        </div>
        """, unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="finapp-card">
          <div style="font-weight:700;">Outro Link Útil</div>
          <div class="finapp-muted" style="margin-top:4px;">Adicionaremos aqui quando você enviar.</div>
        </div>
        """, unsafe_allow_html=True,
    )
    st.markdown('</div>', unsafe_allow_html=True)

def page_receitas_despesas():
    st.markdown("## Receitas e Despesas")
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

    tipo_lcto = st.selectbox(
        "Selecione o tipo de lançamento",
        options=["— selecione —", "Receita", "Despesa", "Imposto/Taxa", "Folha", "Cartão"],
        index=0
    )

    if tipo_lcto == "Receita":
        form_lancamento_generico(default_type="income", label="Receita")
    elif tipo_lcto == "Despesa":
        form_lancamento_generico(default_type="expense", label="Despesa")
    elif tipo_lcto == "Imposto/Taxa":
        form_lancamento_generico(default_type="tax", label="Imposto/Taxa")
    elif tipo_lcto == "Folha":
        form_lancamento_generico(default_type="payroll", label="Folha")
    elif tipo_lcto == "Cartão":
        form_lancamento_generico(default_type="card", label="Lançamento de Cartão")
    else:
        st.info("Escolha um tipo para mostrar os campos de lançamento.")

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    tabela_lancamentos_filtro()

def page_extratos():
    st.markdown("## Extratos")
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    accs = fetch_df("SELECT id, name, type FROM accounts ORDER BY name")
    if accs.empty:
        st.info("Cadastre ao menos uma conta em 'Configurações > Campos do formulário > Contas'.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    nomes = [(int(r.id), f"{r.name} ({r.type})") for _, r in accs.iterrows()]
    acc_sel = st.selectbox("Conta", options=nomes, index=0, format_func=lambda x: x[1] if isinstance(x, tuple) else x)
    acc_id = acc_sel if isinstance(acc_sel, int) else acc_sel[0]

    q = """
        SELECT t.id, t.trx_date as Data, t.type as Tipo, t.description as Descrição, t.amount as Valor,
               t.status as Status
        FROM transactions t
        WHERE t.account_id = ?
        ORDER BY date(t.trx_date) DESC, t.id DESC
    """
    df = fetch_df(q, (acc_id,))
    show_df(df, empty_msg="Sem movimentações para esta conta.")
    saldo = 0.0
    if not df.empty:
        entradas = df.loc[df["Tipo"] == "income", "Valor"].sum()
        saidas = df.loc[df["Tipo"] != "income", "Valor"].sum()
        saldo = float(entradas - saidas)
    st.metric("Saldo estimado da conta", money(saldo))
    st.markdown('</div>', unsafe_allow_html=True)

def page_conciliacao():
    st.markdown("## Conciliação")
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    st.info("Marque lançamentos como conciliados. Os itens conciliados descem para a lista **Conciliados**.")

    pendentes = fetch_df("""
        SELECT id, trx_date as Data, description as Descrição, amount as Valor, status as Status
        FROM transactions
        WHERE status IN ('planned','paid','overdue')
        ORDER BY date(trx_date) DESC, id DESC
        LIMIT 300
    """)
    st.subheader("A conciliar")
    if pendentes.empty:
        st.success("Não há lançamentos pendentes para conciliar.")
    else:
        show_df(pendentes, empty_msg="Sem pendências.")
        c1, c2 = st.columns([1,3])
        with c1:
            id_sel = st.number_input("ID para conciliar", min_value=0, step=1)
        with c2:
            if st.button("Marcar como conciliado", type="secondary", key="btn_conciliar"):
                if id_sel in pendentes["id"].values:
                    exec_sql("UPDATE transactions SET status='reconciled', paid_date=? WHERE id=?",
                             (date.today().isoformat(), int(id_sel)))
                    flash(f"Lançamento {int(id_sel)} conciliado.", "success", 3)
                    do_rerun()
                else:
                    flash("ID não encontrado na lista acima.", "error", 3)

    st.markdown("---")

    reconc = fetch_df("""
        SELECT id, trx_date as Data, description as Descrição, amount as Valor, paid_date as 'Conciliado em'
        FROM transactions
        WHERE status='reconciled'
        ORDER BY date(paid_date) DESC, id DESC
        LIMIT 300
    """)
    st.subheader("Conciliados")
    if reconc.empty:
        st.info("Ainda não há itens conciliados.")
    else:
        show_df(reconc, empty_msg="(vazio)")

    st.markdown('</div>', unsafe_allow_html=True)

def page_relatorios():
    st.markdown("## Relatórios e Dashboard")
    kpis_cards()

    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    st.subheader("Resumo por Categoria")
    q = """
        SELECT
            (SELECT name FROM categories c WHERE c.id = t.category_id) as Categoria,
            t.type as Tipo,
            SUM(CASE WHEN t.type='income' THEN t.amount ELSE 0 END) as Total_Receitas,
            SUM(CASE WHEN t.type!='income' THEN t.amount ELSE 0 END) as Total_Despesas
        FROM transactions t
        GROUP BY Categoria, Tipo
        ORDER BY COALESCE(Categoria,'(sem)') ASC
    """
    q, p = scope_filters(q, [])
    dfc = fetch_df(q, tuple(p))
    show_df(dfc, empty_msg="Sem dados para o período.")
    col1, col2 = st.columns(2)
    with col1:
        export_excel(dfc, "resumo_categoria.xlsx")
    with col2:
        export_csv(dfc, "resumo_categoria.csv")
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== Página Configurações ======================
def section_campos_formulario():
    st.markdown("### Campos do formulário")
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    sub_tabs = st.tabs(["Contas", "Categorias", "Setores"])

    with sub_tabs[0]:
        st.markdown("#### Contas")
        c1, c2, c3, c4 = st.columns(4)
        nm = c1.text_input("Nome da conta")
        tipo = c2.selectbox("Tipo", ["bank","cash","card"], index=0)
        inst = c3.text_input("Instituição")
        num = c4.text_input("Número")
        if st.button("Adicionar conta"):
            if nm.strip():
                exec_sql("INSERT INTO accounts (name,type,institution,number) VALUES (?,?,?,?)", (nm.strip(), tipo, inst.strip(), num.strip()))
                flash("Conta adicionada.", "success", 3)
                do_rerun()
            else:
                flash("Informe o nome da conta.", "warning", 3)

        df = fetch_df("SELECT id, name AS Nome, type AS Tipo, institution AS Instituição, number AS Número FROM accounts ORDER BY name")
        show_df(df, "Nenhuma conta cadastrada.")
        del_id = st.number_input("ID da conta para excluir", min_value=0, step=1, key="acc_del_id")
        if st.button("Excluir conta", key="btn_del_acc", type="secondary"):
            if del_id and del_id in (df["id"].tolist() if not df.empty else []):
                exec_sql("DELETE FROM accounts WHERE id=?", (int(del_id),))
                flash("Conta excluída.", "success", 3)
                do_rerun()
            else:
                flash("ID não encontrado.", "error", 3)

    with sub_tabs[1]:
        st.markdown("#### Categorias")
        c1, c2 = st.columns(2)
        nm = c1.text_input("Nome da categoria")
        kind = c2.selectbox("Tipo", ["expense","income","tax","payroll"], index=0)
        if st.button("Adicionar categoria"):
            if nm.strip():
                exec_sql("INSERT INTO categories (name, parent_id, kind) VALUES (?,?,?)", (nm.strip(), None, kind))
                flash("Categoria adicionada.", "success", 3)
                do_rerun()
            else:
                flash("Informe o nome da categoria.", "warning", 3)

        df = fetch_df("SELECT id, name AS Nome, kind AS Tipo FROM categories ORDER BY kind, name")
        show_df(df, "Nenhuma categoria cadastrada.")
        del_id = st.number_input("ID da categoria para excluir", min_value=0, step=1, key="cat_del_id")
        if st.button("Excluir categoria", key="btn_del_cat", type="secondary"):
            if del_id and del_id in (df["id"].tolist() if not df.empty else []):
                exec_sql("DELETE FROM categories WHERE id=?", (int(del_id),))
                flash("Categoria excluída.", "success", 3)
                do_rerun()
            else:
                flash("ID não encontrado.", "error", 3)

    with sub_tabs[2]:
        st.markdown("#### Setores")
        nm = st.text_input("Nome do setor")
        if st.button("Adicionar setor"):
            if nm.strip():
                ok = exec_sql("INSERT OR IGNORE INTO sectors (name) VALUES (?)", (nm.strip(),))
                if ok is None:
                    flash("Falha ao adicionar setor (talvez duplicado).", "error", 3)
                else:
                    flash("Setor adicionado.", "success", 3)
                do_rerun()
            else:
                flash("Informe o nome do setor.", "warning", 3)

        df = fetch_df("SELECT id, name AS Setor FROM sectors ORDER BY name")
        show_df(df, "Nenhum setor cadastrado.")
        del_id = st.number_input("ID do setor para excluir", min_value=0, step=1, key="sec_del_id")
        if st.button("Excluir setor", key="btn_del_sec", type="secondary"):
            if del_id and del_id in (df["id"].tolist() if not df.empty else []):
                exec_sql("DELETE FROM sectors WHERE id=?", (int(del_id),))
                flash("Setor excluído.", "success", 3)
                do_rerun()
            else:
                flash("ID não encontrado.", "error", 3)

    st.markdown('</div>', unsafe_allow_html=True)

def section_usuarios_permissoes():
    st.markdown("### Usuários & Permissões")
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)

    have_manager = fetch_df("SELECT COUNT(*) as n FROM users WHERE role='manager'")
    if not have_manager.empty and have_manager.iloc[0,0] == 0:
        st.warning("Não há nenhum usuário com permissão **Gerencial**. Você pode tornar-se gerente agora.")
        if st.button("🔓 Tornar-me gerente"):
            u = st.session_state.get("user", None)
            if u:
                exec_sql("UPDATE users SET role='manager' WHERE id=?", (int(u["id"]),))
                st.session_state["user"]["role"] = "manager"
                flash("Permissão elevada para Gerencial.", "success", 3)
                do_rerun()

    is_mgr = (st.session_state.get("user", {}).get("role") == "manager")

    df = fetch_df("SELECT id, name as Nome, email as Email, role as Permissão, is_active as Ativo FROM users ORDER BY created_at DESC")
    show_df(df, "Nenhum usuário cadastrado.")

    if is_mgr and not df.empty:
        st.markdown("---")
        st.subheader("Editar usuário")
        c1, c2, c3 = st.columns(3)
        uid = c1.number_input("ID do usuário", min_value=0, step=1)
        role = c2.selectbox("Permissão", ["launcher","manager"], index=0)
        ativo = c3.selectbox("Status", ["Ativo","Inativo"], index=0)
        if st.button("Salvar alterações no usuário"):
            ids = df["id"].tolist()
            if uid and uid in ids:
                exec_sql("UPDATE users SET role=?, is_active=? WHERE id=?", (role, 1 if ativo=="Ativo" else 0, int(uid)))
                flash("Usuário atualizado.", "success", 3)
                do_rerun()
            else:
                flash("ID não encontrado.", "error", 3)

    st.markdown('</div>', unsafe_allow_html=True)

def section_cadastros():
    st.markdown("### Cadastros (Clientes & Fornecedores)")
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    tabs = st.tabs(["Clientes", "Fornecedores"])

    with tabs[0]:
        st.markdown("#### Novo cliente")
        c1, c2 = st.columns(2)
        name = c1.text_input("Nome/Razão social", key="cli_name")
        doc  = c2.text_input("Documento (CPF/CNPJ)", key="cli_doc")
        c3, c4, c5 = st.columns(3)
        contact = c3.text_input("Contato", key="cli_contact")
        phone   = c4.text_input("Telefone", key="cli_phone")
        email   = c5.text_input("E-mail", key="cli_email")
        notes = st.text_area("Observações", key="cli_notes", placeholder="Informações adicionais...")

        if st.button("Adicionar cliente", key="cli_add_btn"):
            if name.strip():
                exec_sql("INSERT INTO clients (name, doc, contact, phone, email, notes, is_active) VALUES (?,?,?,?,?,?,1)",
                         (name.strip(), doc.strip(), contact.strip(), phone.strip(), email.strip(), notes.strip()))
                flash("Cliente adicionado.", "success", 3)
                do_rerun()
            else:
                flash("Informe o nome do cliente.", "warning", 3)

        st.markdown("---")
        df = fetch_df("SELECT id, name AS Nome, doc AS Documento, contact AS Contato, phone AS Telefone, email AS Email, is_active AS Ativo FROM clients ORDER BY created_at DESC")
        show_df(df, "Nenhum cliente cadastrado.")

        c6, c7, c8 = st.columns(3)
        cid = c6.number_input("ID para (des)ativar/apagar", min_value=0, step=1, key="cli_id_edit")
        ac  = c7.selectbox("Ação", ["Ativar","Inativar","Apagar"], key="cli_action")
        if st.button("Executar ação", key="cli_exec", type="secondary"):
            ids = df["id"].tolist() if not df.empty else []
            if cid and cid in ids:
                if ac == "Apagar":
                    exec_sql("DELETE FROM clients WHERE id=?", (int(cid),))
                    flash("Cliente apagado.", "success", 3)
                else:
                    exec_sql("UPDATE clients SET is_active=? WHERE id=?", (1 if ac=="Ativar" else 0, int(cid)))
                    flash("Cliente atualizado.", "success", 3)
                do_rerun()
            else:
                flash("ID não encontrado.", "error", 3)

    with tabs[1]:
        st.markdown("#### Novo fornecedor")
        c1, c2 = st.columns(2)
        name = c1.text_input("Nome/Razão social", key="for_name")
        doc  = c2.text_input("Documento (CPF/CNPJ)", key="for_doc")
        c3, c4, c5 = st.columns(3)
        contact = c3.text_input("Contato", key="for_contact")
        phone   = c4.text_input("Telefone", key="for_phone")
        email   = c5.text_input("E-mail", key="for_email")
        notes = st.text_area("Observações", key="for_notes", placeholder="Informações adicionais...")

        if st.button("Adicionar fornecedor", key="for_add_btn"):
            if name.strip():
                exec_sql("INSERT INTO suppliers (name, doc, contact, phone, email, notes, is_active) VALUES (?,?,?,?,?,?,1)",
                         (name.strip(), doc.strip(), contact.strip(), phone.strip(), email.strip(), notes.strip()))
                flash("Fornecedor adicionado.", "success", 3)
                do_rerun()
            else:
                flash("Informe o nome do fornecedor.", "warning", 3)

        st.markdown("---")
        df = fetch_df("SELECT id, name AS Nome, doc AS Documento, contact AS Contato, phone AS Telefone, email AS Email, is_active AS Ativo FROM suppliers ORDER BY created_at DESC")
        show_df(df, "Nenhum fornecedor cadastrado.")

        c6, c7, c8 = st.columns(3)
        sid = c6.number_input("ID para (des)ativar/apagar", min_value=0, step=1, key="for_id_edit")
        ac  = c7.selectbox("Ação", ["Ativar","Inativar","Apagar"], key="for_action")
        if st.button("Executar ação", key="for_exec", type="secondary"):
            ids = df["id"].tolist() if not df.empty else []
            if sid and sid in ids:
                if ac == "Apagar":
                    exec_sql("DELETE FROM suppliers WHERE id=?", (int(sid),))
                    flash("Fornecedor apagado.", "success", 3)
                else:
                    exec_sql("UPDATE suppliers SET is_active=? WHERE id=?", (1 if ac=="Ativar" else 0, int(sid)))
                    flash("Fornecedor atualizado.", "success", 3)
                do_rerun()
            else:
                flash("ID não encontrado.", "error", 3)

    st.markdown('</div>', unsafe_allow_html=True)

def page_configuracoes():
    st.markdown("## Configurações")
    tabs = st.tabs(["Campos do formulário", "Usuários & Permissões", "Cadastros"])
    with tabs[0]:
        section_campos_formulario()
    with tabs[1]:
        section_usuarios_permissoes()
    with tabs[2]:
        section_cadastros()

# ====================== Página Agenda (Minha & Pública) ======================
def _render_big_calendar(year: int, month: int, scope: str):
    first_wday, days_in_month = monthrange(year, month)
    weeks = [[]]
    for _ in range(first_wday):
        weeks[0].append({"day": "", "events": []})

    occ = get_month_events(year, month, scope=scope)  # [(date, id, title)]
    events_by_day = {}
    for d, eid, title in occ:
        events_by_day.setdefault(d.day, []).append((eid, title))

    day = 1
    while day <= days_in_month:
        if len(weeks[-1]) == 7:
            weeks.append([])
        evs = events_by_day.get(day, [])
        weeks[-1].append({"day": day, "events": evs})
        day += 1
    while len(weeks[-1]) < 7:
        weeks[-1].append({"day": "", "events": []})

    html = ['<div class="finapp-card"><div style="overflow-x:auto;">']
    html.append("""
    <table style="width:100%; border-collapse:separate; border-spacing:8px;">
      <thead>
        <tr>
          <th>Dom</th><th>Seg</th><th>Ter</th><th>Qua</th><th>Qui</th><th>Sex</th><th>Sáb</th>
        </tr>
      </thead>
      <tbody>
    """)
    for w in weeks:
        html.append("<tr>")
        for cell in w:
            day_label = f"<div style='font-weight:700'>{cell['day']}</div>" if cell["day"] != "" else "&nbsp;"
            ev_html = ""
            for eid, title in cell["events"][:4]:
                safe = str(title).replace("<","&lt;").replace(">","&gt;")
                ev_html += f"<div style='margin-top:6px; padding:6px 8px; border:1px solid var(--finapp-border); border-radius:10px; background:var(--finapp-bg-2); box-shadow:var(--finapp-shadow); font-size:0.9rem;'>#{eid} — {safe}</div>"
            html.append(f"<td style='vertical-align:top; min-width:140px; height:120px; background:#fff; border:1px solid var(--finapp-border); border-radius:12px; padding:8px;'>{day_label}{ev_html}</td>")
        html.append("</tr>")
    html.append("</tbody></table></div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)

def _event_share_links(title: str, dt_ev: date, is_rec: bool, recur_rule: Optional[str], desc: str) -> Tuple[str, str]:
    subj = f"Compromisso: {title}"
    body = f"Título: {title}\\nData: {dt_ev.strftime('%d/%m/%Y')}\\nRecorrente: {'Sim' if is_rec else 'Não'}\\n"
    if is_rec and recur_rule:
        body += f"Periodicidade: {{'daily':'Diária','weekly':'Semanal','monthly':'Mensal','yearly':'Anual'}}[{repr(recur_rule)}]\\n"
    if desc:
        body += f"Notas: {desc}\\n"
    mailto = f"mailto:?subject={urlparse.quote(subj)}&body={urlparse.quote(body)}"
    wa = f"https://wa.me/?text={urlparse.quote(subj + '\\n' + body)}"
    return mailto, wa

def _event_detail_form(eid: int):
    col = cal_date_col()
    df = fetch_df(f"SELECT *, {col} AS ev_date FROM calendar_events WHERE id=?", (int(eid),))
    if df.empty:
        st.warning("Compromisso não encontrado.")
        return
    r = df.iloc[0]
    owner = int(r["created_by"]) if pd.notna(r.get("created_by")) else None
    uid = _get_user_id()
    can_edit = (uid is not None) and (uid == owner or st.session_state.get("user",{}).get("role")=="manager")

    with st.form(f"event_edit_{eid}"):
        c1, c2 = st.columns([2,1])
        title = c1.text_input("Título", value=str(r["title"]), disabled=not can_edit)
        dt_ev = c2.date_input("Data base", value=_parse_date(str(r["ev_date"])).date(), disabled=not can_edit)
        desc = st.text_area("Descrição/Notas", value=(r["description"] or ""), disabled=not can_edit)

        c3, c4, c5 = st.columns(3)
        is_rec = c3.toggle("Recorrente?", value=bool(r["is_recurring"]), disabled=not can_edit)
        recur_rule = (r["recur_rule"] if pd.notna(r["recur_rule"]) else None)
        recur_until_val = (_parse_date(str(r["recur_until"])).date() if pd.notna(r["recur_until"]) and r["recur_until"] else None)

        c6 = st.columns(1)[0]
        vis_label = "Público" if int(r.get("is_public",0))==1 else "Privado"
        vis_new = c6.selectbox("Visibilidade", ["Privado","Público"], index=(1 if vis_label=="Público" else 0), disabled=not can_edit)

        if is_rec and can_edit:
            recur_rule = c4.selectbox("Periodicidade", ["daily","weekly","monthly","yearly"],
                                      index=(["daily","weekly","monthly","yearly"].index(recur_rule) if recur_rule in ["daily","weekly","monthly","yearly"] else 2),
                                      format_func=lambda x: {"daily":"Diária","weekly":"Semanal","monthly":"Mensal","yearly":"Anual"}[x])
            recur_until_val = c5.date_input("Repetir até (opcional)", value=(recur_until_val or (dt_ev + timedelta(days=30))))
        elif not is_rec:
            recur_rule = None
            recur_until_val = None

        if owner:
            st.caption(f"Criado por usuário #{owner}")

        c7, c8, c9, c10 = st.columns(4)
        save = c7.form_submit_button("💾 Salvar alterações", disabled=not can_edit)
        dup  = c8.form_submit_button("📄 Duplicar")
        delete = c9.form_submit_button("🗑️ Excluir", type="secondary", disabled=not can_edit)
        share = c10.form_submit_button("📤 Enviar (e-mail/WhatsApp)")

    if delete:
        delete_calendar_event(int(eid))
        flash("Compromisso excluído.", "success", 3)
        do_rerun()
    elif dup:
        duplicate_calendar_event(int(eid), new_owner_id=_get_user_id())
        flash("Compromisso duplicado.", "success", 3)
        do_rerun()
    elif save and can_edit:
        update_calendar_event(
            int(eid), title, desc, dt_ev, is_rec, recur_rule, recur_until_val,
            is_public=(vis_new=="Público")
        )
        flash("Compromisso atualizado.", "success", 3)
        do_rerun()
    elif share:
        mailto, wa = _event_share_links(title, dt_ev, is_rec, recur_rule, desc)
        st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
        st.markdown("**Compartilhar compromisso:**")
        st.markdown(f"- 📧 [Abrir e-mail preparado]({mailto})")
        st.markdown(f"- 💬 [Enviar no WhatsApp]({wa})")
        st.markdown('</div>', unsafe_allow_html=True)

def page_agenda():
    st.markdown("## Agenda")
    tabs = st.tabs(["Minha Agenda", "Calendário Público"])

    # ===== Minha Agenda: públicos + meus privados =====
    with tabs[0]:
        c1, c2, _ = st.columns([1,1,2])
        today = date.today()
        year = c1.number_input("Ano", min_value=2000, max_value=2100, value=today.year, step=1, key="ag_my_year")
        month = c2.number_input("Mês", min_value=1, max_value=12, value=today.month, step=1, key="ag_my_month")
        _render_big_calendar(int(year), int(month), scope="mine")

        st.markdown("### Novo compromisso")
        with st.form("form_new_event_mine"):
            c4, c5 = st.columns([2,1])
            title = c4.text_input("Título", placeholder="Ex.: Reunião com fornecedor")
            dt_ev  = c5.date_input("Data", value=today)
            desc = st.text_area("Descrição/Notas", placeholder="Detalhes do compromisso")

            c6, c7, c8 = st.columns(3)
            is_rec = c6.toggle("Recorrente?", value=False)
            vis = c7.selectbox("Visibilidade", ["Privado","Público"], index=0)
            recur_rule = None
            recur_until = None
            if is_rec:
                recur_rule = c8.selectbox("Periodicidade", ["daily","weekly","monthly","yearly"], index=2,
                                          format_func=lambda x: {"daily":"Diária","weekly":"Semanal","monthly":"Mensal","yearly":"Anual"}[x])
                recur_until = st.date_input("Repetir até (opcional)", value=today + timedelta(days=30), key="my_until")
            ok = st.form_submit_button("Adicionar compromisso")
            if ok:
                if not title.strip():
                    flash("Informe o título do compromisso.", "warning", 3)
                else:
                    add_calendar_event(
                        title=title, dt=dt_ev, description=desc,
                        is_recurring=is_rec, recur_rule=recur_rule, recur_until=recur_until,
                        is_public=(vis=="Público"), created_by=_get_user_id()
                    )
                    flash("Compromisso adicionado.", "success", 3)
                    do_rerun()

        st.markdown("---")
        st.markdown("### Compromissos do mês (abrir/editar)")
        occ = get_month_events(int(year), int(month), scope="mine")
        if not occ:
            st.info("Sem compromissos no mês selecionado.")
        else:
            ids = [eid for _, eid, _ in occ]
            labels = [f"{d.strftime('%d/%m')} · #{eid} · {title}" for d, eid, title in occ]
            options = list(zip(ids, labels))
            sel = st.selectbox("Escolha um compromisso", options=options, format_func=lambda x: x[1])
            if sel:
                _event_detail_form(int(sel[0]))

    # ===== Calendário Público =====
    with tabs[1]:
        c1, c2, _ = st.columns([1,1,2])
        today = date.today()
        year = c1.number_input("Ano", min_value=2000, max_value=2100, value=today.year, step=1, key="ag_pub_year")
        month = c2.number_input("Mês", min_value=1, max_value=12, value=today.month, step=1, key="ag_pub_month")
        _render_big_calendar(int(year), int(month), scope="public")

        st.markdown("---")
        st.markdown("### Compromissos públicos do mês (abrir)")
        occ = get_month_events(int(year), int(month), scope="public")
        if not occ:
            st.info("Sem compromissos públicos no mês selecionado.")
        else:
            ids = [eid for _, eid, _ in occ]
            labels = [f"{d.strftime('%d/%m')} · #{eid} · {title}" for d, eid, title in occ]
            options = list(zip(ids, labels))
            sel = st.selectbox("Escolha um compromisso público", options=options, format_func=lambda x: x[1], key="pub_sel")
            if sel:
                _event_detail_form(int(sel[0]))

# ====================== Layout principal ======================
def main():
    init_db()
    seed_minimums()
    top_ticker()

    st.markdown(f"### {PAGE_TITLE}")

    signup_widget()
    logged = login_widget()
    if not logged:
        st.stop()

    tabs = st.tabs(["Home", "Receitas e Despesas", "Extratos", "Conciliação", "Relatórios e Dashboard", "Agenda", "Configurações"])
    with tabs[0]:
        page_home()
    with tabs[1]:
        page_receitas_despesas()
    with tabs[2]:
        page_extratos()
    with tabs[3]:
        page_conciliacao()
    with tabs[4]:
        page_relatorios()
    with tabs[5]:
        page_agenda()
    with tabs[6]:
        page_configuracoes()

if __name__ == "__main__":
    main()

# (Opcional) esconder header/footer padrão do Streamlit
HIDE_DEFAULT_FORMATTING = """
<style>
#MainMenu {visibility:hidden;}
header {visibility:hidden;}
footer {visibility:hidden;}
</style>
"""
st.markdown(HIDE_DEFAULT_FORMATTING, unsafe_allow_html=True)
