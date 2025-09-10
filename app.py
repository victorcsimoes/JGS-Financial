# app.py — FinApp (DEV) com guias, login compacto, botão "+" e faixa rolante com data e USD
# Execução: python -m streamlit run app.py --server.port 8501 --server.fileWatcherType=none
# Requisitos: streamlit, pandas, openpyxl
# Opcional p/ dólar: yfinance

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

# ---------------------- Constantes ----------------------
BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "finapp.db")
ATTACH_DIR = os.path.join(BASE_DIR, "attachments")
SQLITE_TIMEOUT = 4.0
PAGE_TITLE = "FinApp | Pequenas Empresas (DEV)"

# ---------------------- Config inicial ----------------------
st.set_page_config(page_title=PAGE_TITLE, layout="wide")

def do_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

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

    st.markdown(
        """
        <style>
        .marquee {
            width: 100%;
            overflow: hidden;
            white-space: nowrap;
            box-sizing: border-box;
            border-bottom: 1px solid #e5e7eb;
            color: #111827;
            font-weight: 600;
            padding: 6px 0;
        }
        .marquee span {
            display: inline-block;
            padding-left: 100%;
            animation: scroll-left 18s linear infinite;
        }
        @keyframes scroll-left {
            0%   { transform: translateX(0); }
            100% { transform: translateX(-100%); }
        }
        .plus-box { display:flex; align-items:center; gap:8px; }
        .plus-icon { font-size: 22px; color: #16a34a; line-height:1; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="marquee"><span>{msg} &nbsp; • &nbsp; {msg}</span></div>', unsafe_allow_html=True)

# ====================== Login & Cadastro (compacto) ======================
def signup_widget():
    if "user" in st.session_state:
        return
    with st.sidebar.expander("🆕 Cadastro rápido"):
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
                    # Auto-login
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

    # Compacto após login
    u = st.session_state["user"]
    with st.sidebar.container():
        st.markdown(f"**{u['name']}**\n\n`{u['email']}`")
        if st.sidebar.button("Sair"):
            del st.session_state["user"]
            do_rerun()
    return True

# ====================== Componentes de conteúdo ======================
def kpis_overview():
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

    c1, c2, c3 = st.columns(3)
    c1.metric("Receitas", money(total_rec))
    c2.metric("Despesas", money(total_desp))
    c3.metric("Saldo", money(saldo))

    st.divider()
    st.subheader("Últimos lançamentos")
    q = """
        SELECT t.id, t.trx_date as Data, t.type as Tipo, t.description as Descrição, t.amount as Valor,
               (SELECT name FROM categories c WHERE c.id = t.category_id) as Categoria,
               t.sector as Setor, t.status as Status
        FROM transactions t WHERE 1=1
    """
    q, p = scope_filters(q, [])
    q += " ORDER BY t.id DESC LIMIT 10"
    st.dataframe(fetch_df(q, tuple(p)), use_container_width=True)

def form_lancamento_generico(default_type: str = 'expense', label: str = "Novo lançamento", force_account_id: Optional[int] = None):
    st.markdown(f"**{label}**")
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

def tabela_lancamentos_filtro():
    st.markdown("### Filtro de lançamentos")
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

# ====================== Páginas ======================
def page_receitas_despesas():
    st.markdown("## Receitas e Despesas")

    ctop1, ctop2 = st.columns([1, 3])
    with ctop1:
        if st.button("➕ Novo lançamento", help="Atalho para incluir um lançamento"):
            st.session_state["tab_index"] = 0  # permanece na mesma aba e rola até os formulários
    with ctop2:
        pass

    st.divider()
    st.markdown("### Lançar")
    c1, c2 = st.columns(2)
    with c1:
        form_lancamento_generico(default_type="expense", label="Despesa")
        form_lancamento_generico(default_type="tax", label="Imposto/Taxa")
        form_lancamento_generico(default_type="payroll", label="Folha")
    with c2:
        form_lancamento_generico(default_type="income", label="Receita")
        form_lancamento_generico(default_type="card", label="Lançamento de Cartão")

    st.divider()
    tabela_lancamentos_filtro()

def page_extratos():
    st.markdown("## Extratos")
    accs = fetch_df("SELECT id, name, type FROM accounts ORDER BY name")
    if accs.empty:
        st.info("Cadastre ao menos uma conta em 'accounts' (seed já inclui duas).")
        return

    nomes = [(int(r.id), f"{r.name} ({r.type})") for _, r in accs.iterrows()]
    acc_id, acc_label = st.selectbox("Conta", options=nomes, format_func=lambda x: x[1] if isinstance(x, tuple) else x)
    acc_id = acc_id if isinstance(acc_id, int) else acc_id[0]

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

def page_conciliacao():
    st.markdown("## Conciliação")
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

def page_relatorios():
    st.markdown("## Relatórios e Dashboard")
    kpis_overview()

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

# ====================== Layout principal ======================
def main():
    init_db()
    seed_minimums()
    top_ticker()

    # Barra superior com botão "+"
    ctop1, ctop2 = st.columns([0.1, 0.9])
    with ctop1:
        if st.button("➕", help="Adicionar lançamento (vai para 'Receitas e Despesas')"):
            st.session_state["tab_index"] = 0
    with ctop2:
        st.markdown(f"### {PAGE_TITLE}")

    # Login / Cadastro
    signup_widget()
    logged = login_widget()
    if not logged:
        st.stop()

    # Controle de guia ativa
    if "tab_index" not in st.session_state:
        st.session_state["tab_index"] = 0

    tabs = st.tabs(["Receitas e Despesas", "Extratos", "Conciliação", "Relatórios e Dashboard"])
    with tabs[0]:
        page_receitas_despesas()
    with tabs[1]:
        page_extratos()
    with tabs[2]:
        page_conciliacao()
    with tabs[3]:
        page_relatorios()

if __name__ == "__main__":
    main()
