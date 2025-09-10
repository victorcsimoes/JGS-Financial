# app.py — FinApp (DEV) | UI air (azul/white), tema claro/escuro automático, Home com pizza + Links Úteis
# Execução: python -m streamlit run app.py --server.port 8501 --server.fileWatcherType=none
# Requisitos: streamlit, pandas, openpyxl
# Opcionais: yfinance (dólar na faixa) e plotly (gráficos)

import os
import hashlib
import sqlite3
from io import BytesIO
from datetime import date, datetime
from typing import Optional, Tuple, List

import pandas as pd
import streamlit as st

# --- USD opcional (yfinance) ---
try:
    import yfinance as yf  # pip install yfinance
except Exception:
    yf = None

# --- Gráficos (plotly) ---
try:
    import plotly.express as px  # pip install plotly
except Exception:
    px = None

# ---------------------- Constantes ----------------------
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "finapp.db")
ATTACH_DIR = os.path.join(BASE_DIR, "attachments")
SQLITE_TIMEOUT = 4.0
PAGE_TITLE = "FinApp | JVSeps® "

# ---------------------- Config inicial ----------------------
st.set_page_config(page_title=PAGE_TITLE, layout="wide")

# ====================== Estilos (claro/escuro) ======================
# Usamos variáveis CSS + overrides para [data-base-theme="dark"]
st.markdown(
    """
    <style>
    /* ---------- Variáveis padrão (modo CLARO) ---------- */
    :root{
        --finapp-bg:#F7FAFF;                 /* fundo claro */
        --finapp-bg-2:#FFFFFF;               /* cartões */
        --finapp-primary:#0E2A47;            /* azul escuro */
        --finapp-primary-2:#0F4C81;          /* azul secundário */
        --finapp-text:#0d1b2a;               /* texto principal escuro */
        --finapp-text-soft:#334155;          /* texto secundário */
        --finapp-border:#e6ebf2;
        --finapp-shadow:0 6px 18px rgba(14,42,71,0.08);
        --finapp-radius:16px;
        --finapp-grad-1:var(--finapp-primary);
        --finapp-grad-2:var(--finapp-primary-2);
        --finapp-link:#0F4C81;
    }

    /* ---------- Overrides (modo ESCURO) ---------- */
    [data-base-theme="dark"] :root{
        --finapp-bg:linear-gradient(180deg, #0E2A47 0%, #0F4C81 100%); /* fundo com leve degradê */
        --finapp-bg-2:rgba(255,255,255,0.06);   /* cartões translúcidos */
        --finapp-primary:#EAF2FF;               /* texto/realce claro */
        --finapp-primary-2:#D2E6FF;
        --finapp-text:#F3F7FF;
        --finapp-text-soft:#D8E6FF;
        --finapp-border:rgba(255,255,255,0.15);
        --finapp-shadow:0 8px 28px rgba(0,0,0,0.35);
        --finapp-grad-1:#10355E;
        --finapp-grad-2:#0F4C81;
        --finapp-link:#D6E8FF;
    }

    /* ---------- Base ---------- */
    .stApp {
        background: var(--finapp-bg);
    }
    .block-container { padding-top: 0.6rem; max-width: 1240px; }

    h1,h2,h3,h4,h5,h6 { color: var(--finapp-primary); letter-spacing:.2px; }
    .markdown-text-container, .stMarkdown, p, label, span, div {
        color: var(--finapp-text);
    }
    .finapp-muted { color: var(--finapp-text-soft); }

    a, .stMarkdown a { color: var(--finapp-link) !important; text-decoration: none; }
    a:hover { text-decoration: underline; }

    /* ---------- Marquee/top bar ---------- */
    .finapp-marquee {
        width: 100%;
        overflow: hidden;
        white-space: nowrap;
        box-sizing: border-box;
        color: #ffffff;
        font-weight: 700;
        padding: 10px 0;
        border-radius: 0 0 14px 14px;
        background: linear-gradient(90deg, var(--finapp-grad-1), var(--finapp-grad-2));
        box-shadow: var(--finapp-shadow);
        margin-bottom: 14px;
    }
    .finapp-marquee span {
        display: inline-block;
        padding-left: 100%;
        animation: finapp-scroll-left 22s linear infinite;
    }
    @keyframes finapp-scroll-left {
        0%   { transform: translateX(0); }
        100% { transform: translateX(-100%); }
    }

    /* ---------- Cards ---------- */
    .finapp-card {
        background: var(--finapp-bg-2);
        border: 1px solid var(--finapp-border);
        border-radius: var(--finapp-radius);
        padding: 16px 18px;
        box-shadow: var(--finapp-shadow);
    }
    .finapp-card h3 { margin: 0 0 8px 0; }

    /* ---------- Botões ---------- */
    .stButton > button {
        background: var(--finapp-grad-2);
        color: #fff;
        border: 1px solid var(--finapp-grad-2);
        border-radius: 14px;
        padding: 8px 14px;
        font-weight: 700;
        transition: all .15s ease;
        box-shadow: var(--finapp-shadow);
    }
    .stButton > button:hover {
        background: var(--finapp-grad-1);
        border-color: var(--finapp-grad-1);
        transform: translateY(-1px);
    }

    /* Botão + */
    .finapp-plus {
        display:inline-flex; align-items:center; justify-content:center;
        width: 40px; height: 40px; border-radius: 12px;
        background: var(--finapp-bg-2);
        color: var(--finapp-primary);
        border:1px solid var(--finapp-border); box-shadow: var(--finapp-shadow);
        font-size: 22px; font-weight: 800; line-height: 1;
    }
    .finapp-plus:hover { filter: brightness(1.06); }

    /* ---------- Inputs ---------- */
    .stTextInput > div > div > input,
    .stNumberInput input,
    .stDateInput input,
    .stSelectbox > div > div {
        background: var(--finapp-bg-2);
        color: var(--finapp-text) !important;
        border-radius: 12px !important;
        border: 1px solid var(--finapp-border);
        box-shadow: none;
    }
    .stTextInput label, .stNumberInput label, .stDateInput label, .stSelectbox label { color: var(--finapp-text); }

    /* Placeholder visível no escuro */
    ::placeholder { color: var(--finapp-text-soft); opacity: 0.9; }

    /* ---------- Métricas ---------- */
    [data-testid="stMetric"] {
        background: var(--finapp-bg-2);
        border: 1px solid var(--finapp-border);
        border-radius: 14px;
        padding: 10px 12px;
        box-shadow: var(--finapp-shadow);
        color: var(--finapp-primary);
    }

    /* ---------- Tabs ---------- */
    .stTabs [data-baseweb="tab-list"] { gap: 6px; background: transparent; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"]{
        height: 42px;
        border-radius: 12px;
        padding: 8px 14px;
        background: var(--finapp-bg-2);
        border: 1px solid var(--finapp-border);
        color: var(--finapp-primary);
        box-shadow: var(--finapp-shadow);
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, var(--finapp-grad-1), var(--finapp-grad-2));
        color: #fff !important;
        border-color: transparent;
    }

    /* ---------- Dataframe ---------- */
    .stDataFrame { border: 1px solid var(--finapp-border); border-radius: 12px; box-shadow: var(--finapp-shadow); }

    /* ---------- Sidebar ---------- */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, var(--finapp-grad-1) 0%, var(--finapp-grad-2) 100%) !important;
    }
    section[data-testid="stSidebar"] * { color: #e6edf7 !important; }
    section[data-testid="stSidebar"] .stButton>button {
        background: #ffffff22; border-color: #ffffff33;
    }
    section[data-testid="stSidebar"] .stButton>button:hover {
        background: #ffffff33; transform: none;
    }

    /* ---------- Grids responsivos ---------- */
    .finapp-grid {
        display: grid;
        gap: 14px;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        align-items: stretch;
    }
    .finapp-grid-2 {
        display: grid;
        gap: 14px;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        align-items: stretch;
    }

    /* Títulos reduzidos em telas menores */
    @media (max-width: 640px){
        h1,h2 { font-size: 1.3rem; }
        .finapp-marquee { font-size: 0.95rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def do_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

# Detecta tema para ajustar gráficos (plotly)
def current_theme_base() -> str:
    try:
        base = st.get_option("theme.base")
        return base if base in ("light", "dark") else "light"
    except Exception:
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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                account_id INTEGER,
                sectors TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()

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

# ====================== Escopo (DEV: sem restrição) ======================
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
    st.markdown(f'<div class="finapp-marquee"><span>{msg} &nbsp; • &nbsp; {msg}</span></div>', unsafe_allow_html=True)

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
                        (name.strip(), email.strip().lower(), hash_password(pwd), "user", None, "",)
                    )
                    user_id = int(fetch_df("SELECT id FROM users WHERE email=?", (email.strip().lower(),)).iloc[0]["id"])
                    st.session_state["user"] = {
                        "id": user_id,
                        "name": name.strip(),
                        "email": email.strip().lower(),
                        "role": "user",
                        "account_id": None,
                        "sectors": [],
                    }
                    st.sidebar.success("Conta criada e login efetuado.")
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
                    "role": "user",
                    "account_id": int(u.iloc[0]["account_id"]) if pd.notna(u.iloc[0]["account_id"]) else None,
                    "sectors": [s.strip() for s in str(u.iloc[0]["sectors"] or "").split(",") if s.strip()],
                }
                do_rerun()
            else:
                st.sidebar.error("Credenciais inválidas.")
        return False

    u = st.session_state["user"]
    with st.sidebar.container():
        st.markdown(f"**{u['name']}**\n\n`{u['email']}`")
        if st.sidebar.button("Sair"):
            del st.session_state["user"]
            do_rerun()
    return True

# ====================== KPIs (sem tabela) ======================
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

# ====================== Formulário genérico ======================
def form_lancamento_generico(default_type: str = 'expense', label: str = "Novo lançamento", force_account_id: Optional[int] = None):
    st.markdown(f"### {label}")
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    with st.form(f"form_{label}_{default_type}"):
        c1, c2, c3 = st.columns(3)
        dt_val = c1.date_input("Data", value=date.today())
        amount = c2.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
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
        else:
            acc_options = [(None, "—")] + [(int(r.id), r.name) for _, r in accounts_df.iterrows()]
            acc = c4.selectbox("Conta", options=acc_options, format_func=safe_label)

        if default_type != 'income':
            categories_df = fetch_df("SELECT id, name FROM categories WHERE kind IN ('expense','tax','payroll')")
        else:
            categories_df = fetch_df("SELECT id, name FROM categories WHERE kind = 'income'")
        cat_options = [(None, "—")] + [(int(r.id), r.name) for _, r in categories_df.iterrows()]
        cat = c5.selectbox("Categoria", options=cat_options, format_func=safe_label)

        sector_options = ["Administrativo", "Produção", "Comercial", "Logística", "Outros"]
        sector = c6.selectbox("Setor", sector_options)

        c7, c8 = st.columns([2, 1])
        desc = c7.text_input("Descrição")
        doc = c8.text_input("Documento/Nota")

        c9, c10, c11 = st.columns(3)
        party = c9.text_input("Contraparte (fornecedor/cliente)")
        status_index = 1 if default_type != "income" else 0
        status = c10.selectbox("Status", ["planned", "paid", "overdue", "reconciled", "canceled"], index=status_index)
        attach = c11.file_uploader("Comprovante (opcional)", type=["pdf", "png", "jpg", "jpeg"])

        submitted = st.form_submit_button("Salvar lançamento")
        if submitted:
            if amount <= 0:
                st.error("Informe um valor maior que zero.")
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
                        st.error(f"Falha ao salvar anexo: {e}")

                account_id_final = force_account_id if force_account_id else (acc[0] if isinstance(acc, tuple) else None)
                exec_sql(
                    """
                    INSERT INTO transactions (
                        trx_date, type, sector, cost_center_id, category_id, account_id,
                        method, doc_number, counterparty, description, amount, status, origin, attachment_path
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        dt_val.isoformat(), default_type, sector,
                        None,
                        (cat[0] if isinstance(cat, tuple) else None),
                        account_id_final,
                        method, doc, party, desc, float(amount), status, "manual", attach_path
                    ),
                )
                st.success("Lançamento salvo com sucesso.")
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
    st.dataframe(df, use_container_width=True)
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

# ====================== Páginas ======================
def page_home():
    st.markdown("## Home")

    # KPIs (sem tabela)
    kpis_cards()

    # ----- Parte inferior: dashboards (gráficos pizza) -----
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.subheader("Dashboards")
    ctheme = current_theme_base()
    palette_light = ["#0F4C81","#1E88E5","#90CAF9","#1565C0","#64B5F6","#1976D2","#42A5F5","#5E81AC","#81A1C1"]
    palette_dark  = ["#D6E8FF","#9CC3FF","#7FB2FF","#B9D6FF","#EAF2FF","#A9C8FF","#C9DEFF","#E1EEFF","#F6FAFF"]
    palette = palette_dark if ctheme == "dark" else palette_light
    tpl = "plotly_dark" if ctheme == "dark" else "plotly_white"
    paper_bg = "rgba(0,0,0,0)"  # deixa o fundo do gráfico integrar com o card

    # Despesas por Categoria
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

    # Receitas por Categoria
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

    # Grid responsivo dos gráficos
    st.markdown('<div class="finapp-grid">', unsafe_allow_html=True)
    # Card 1: Despesas
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    st.markdown("**Despesas por Categoria**")
    if px and not df_desp.empty and df_desp["Total"].sum() > 0:
        fig1 = px.pie(df_desp, names="Categoria", values="Total", hole=0.35,
                      color_discrete_sequence=palette)
        fig1.update_traces(textposition='inside', textinfo='percent+label')
        fig1.update_layout(template=tpl, paper_bgcolor=paper_bg, plot_bgcolor=paper_bg,
                           margin=dict(t=20,b=12,l=12,r=12))
        st.plotly_chart(fig1, use_container_width=True)
    elif df_desp.empty:
        st.info("Sem dados de despesas para exibir.")
    else:
        st.dataframe(df_desp, use_container_width=True)
        st.caption("Instale o plotly para ver o gráfico: pip install plotly")
    st.markdown('</div>', unsafe_allow_html=True)

    # Card 2: Receitas
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    st.markdown("**Receitas por Categoria**")
    if px and not df_rec.empty and df_rec["Total"].sum() > 0:
        fig2 = px.pie(df_rec, names="Categoria", values="Total", hole=0.35,
                      color_discrete_sequence=palette)
        fig2.update_traces(textposition='inside', textinfo='percent+label')
        fig2.update_layout(template=tpl, paper_bgcolor=paper_bg, plot_bgcolor=paper_bg,
                           margin=dict(t=20,b=12,l=12,r=12))
        st.plotly_chart(fig2, use_container_width=True)
    elif df_rec.empty:
        st.info("Sem dados de receitas para exibir.")
    else:
        st.dataframe(df_rec, use_container_width=True)
        st.caption("Instale o plotly para ver o gráfico: pip install plotly")
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)  # fim grid dashboards

    # ----- Links Úteis (responsivo) -----
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    st.subheader("Links úteis")
    st.markdown('<div class="finapp-grid-2">', unsafe_allow_html=True)

    # WhatsApp (link genérico; depois você envia o que preferir)
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
        """,
        unsafe_allow_html=True,
    )

    # Receita Federal
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
        """,
        unsafe_allow_html=True,
    )

    # Placeholder para futuros links
    st.markdown(
        """
        <div class="finapp-card">
          <div style="font-weight:700;">Outro Link Útil</div>
          <div class="finapp-muted" style="margin-top:4px;">Adicionaremos aqui quando você enviar.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('</div>', unsafe_allow_html=True)

def page_receitas_despesas():
    st.markdown("## Receitas e Despesas")
    top_left, top_right = st.columns([0.15, 0.85])
    with top_left:
        if st.button("➕ Novo", help="Atalho para incluir um lançamento"):
            st.session_state["tab_index"] = 1  # guia 'Receitas e Despesas'
    with top_right:
        st.markdown('<span class="finapp-muted">Inclua receitas, despesas, impostos, folha e cartão.</span>', unsafe_allow_html=True)

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        form_lancamento_generico(default_type="expense", label="Despesa")
        form_lancamento_generico(default_type="tax", label="Imposto/Taxa")
        form_lancamento_generico(default_type="payroll", label="Folha")
    with c2:
        form_lancamento_generico(default_type="income", label="Receita")
        form_lancamento_generico(default_type="card", label="Lançamento de Cartão")

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    tabela_lancamentos_filtro()

def page_extratos():
    st.markdown("## Extratos")
    st.markdown('<div class="finapp-card">', unsafe_allow_html=True)
    accs = fetch_df("SELECT id, name, type FROM accounts ORDER BY name")
    if accs.empty:
        st.info("Cadastre ao menos uma conta em 'accounts' (seed já inclui duas).")
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
    st.dataframe(df, use_container_width=True)

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
    st.info("Módulo simples para marcar lançamentos como conciliados.")
    ids_df = fetch_df("""
        SELECT id, trx_date as Data, description as Descrição, amount as Valor, status as Status
        FROM transactions
        WHERE status IN ('planned','paid')
        ORDER BY date(trx_date) DESC, id DESC
        LIMIT 200
    """)
    if ids_df.empty:
        st.success("Não há lançamentos pendentes para conciliar.")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    st.dataframe(ids_df, use_container_width=True)
    id_sel = st.number_input("ID para conciliar", min_value=0, step=1)
    if st.button("Marcar como conciliado"):
        if id_sel in ids_df["id"].values:
            exec_sql("UPDATE transactions SET status='reconciled', paid_date=? WHERE id=?",
                     (date.today().isoformat(), int(id_sel)))
            st.success(f"Lançamento {int(id_sel)} conciliado.")
            do_rerun()
        else:
            st.error("ID não encontrado na lista acima.")
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
    st.dataframe(dfc, use_container_width=True)
    col1, col2 = st.columns(2)
    with col1:
        export_excel(dfc, "resumo_categoria.xlsx")
    with col2:
        export_csv(dfc, "resumo_categoria.csv")
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== Layout principal ======================
def main():
    init_db()
    seed_minimums()
    top_ticker()  # Faixa no topo (todas as páginas)

    # Barra superior com título e botão "+"
    ctop1, ctop2 = st.columns([0.08, 0.92])
    with ctop1:
        if st.button("➕", help="Adicionar lançamento (vai para 'Receitas e Despesas')"):
            st.session_state["tab_index"] = 1  # Home=0, Receitas=1
    with ctop2:
        st.markdown(f"### {PAGE_TITLE}")

    # Login / Cadastro
    signup_widget()
    logged = login_widget()
    if not logged:
        st.stop()

    if "tab_index" not in st.session_state:
        st.session_state["tab_index"] = 0  # Home

    tabs = st.tabs(["Home", "Receitas e Despesas", "Extratos", "Conciliação", "Relatórios e Dashboard"])
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

# === FINAPP-SIDEBAR-PATCH-2025-09-10 (começo) ===
st.markdown(
    """
    <style>
    /* Alvos compatíveis com versões diferentes do Streamlit (section/aside) */
    /* MODO CLARO — fundo azul claro (mesmo tom usado no "app/admin") */
    section[data-testid="stSidebar"] input[type="text"],
    section[data-testid="stSidebar"] input[type="password"],
    aside[aria-label="sidebar"] input[type="text"],
    aside[aria-label="sidebar"] input[type="password"] {
      background: #EAF2FF !important;      /* troque por #9CC3FF se quiser mais saturado */
      color: #0E2A47 !important;
      border: 1px solid #D2E6FF !important;
      border-radius: 12px !important;
    }
    /* Selectbox do "app/admin" com a mesma cor */
    section[data-testid="stSidebar"] .stSelectbox > div > div,
    aside[aria-label="sidebar"] .stSelectbox > div > div {
      background: #EAF2FF !important;
      color: #0E2A47 !important;
      border: 1px solid #D2E6FF !important;
      border-radius: 12px !important;
    }
    /* Foco sutil no claro */
    section[data-testid="stSidebar"] input[type="text"]:focus,
    section[data-testid="stSidebar"] input[type="password"]:focus,
    section[data-testid="stSidebar"] .stSelectbox > div > div:focus-within,
    aside[aria-label="sidebar"] input[type="text"]:focus,
    aside[aria-label="sidebar"] input[type="password"]:focus,
    aside[aria-label="sidebar"] .stSelectbox > div > div:focus-within {
      outline: 2px solid #9CC3FF !important;
      outline-offset: 0;
    }

    /* MODO ESCURO — azul mais escuro e texto claro */
    [data-base-theme="dark"] section[data-testid="stSidebar"] input[type="text"],
    [data-base-theme="dark"] section[data-testid="stSidebar"] input[type="password"],
    [data-base-theme="dark"] aside[aria-label="sidebar"] input[type="text"],
    [data-base-theme="dark"] aside[aria-label="sidebar"] input[type="password"] {
      background: #10355E !important;
      color: #EAF2FF !important;
      border: 1px solid #275B8F !important;
    }
    [data-base-theme="dark"] section[data-testid="stSidebar"] .stSelectbox > div > div,
    [data-base-theme="dark"] aside[aria-label="sidebar"] .stSelectbox > div > div {
      background: #10355E !important;
      color: #EAF2FF !important;
      border: 1px solid #275B8F !important;
      border-radius: 12px !important;
    }
    [data-base-theme="dark"] section[data-testid="stSidebar"] input[type="text"]:focus,
    [data-base-theme="dark"] section[data-testid="stSidebar"] input[type="password"]:focus,
    [data-base-theme="dark"] section[data-testid="stSidebar"] .stSelectbox > div > div:focus-within,
    [data-base-theme="dark"] aside[aria-label="sidebar"] input[type="text"]:focus,
    [data-base-theme="dark"] aside[aria-label="sidebar"] input[type="password"]:focus,
    [data-base-theme="dark"] aside[aria-label="sidebar"] .stSelectbox > div > div:focus-within {
      outline: 2px solid #9CC3FF !important;
      outline-offset: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
# === FINAPP-SIDEBAR-PATCH-2025-09-10 (fim) ===

if __name__ == "__main__":
    main()
