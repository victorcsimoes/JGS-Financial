# app.py — FinApp Pequenas Empresas (guias completas + usuários por conta + escopo por conta/setor + anexos + exportação)
# Requisitos: streamlit, pandas, openpyxl
# Execução: streamlit run app.py

import os
import hashlib
import sqlite3
from io import StringIO, BytesIO
from datetime import date, datetime

import pandas as pd
import streamlit as st

DB_PATH = "finapp.db"
ATTACH_DIR = "attachments"

st.set_page_config(page_title="FinApp | Pequenas Empresas", layout="wide")

# ---------------------- Utils & DB ----------------------
@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def init_db():
    os.makedirs(ATTACH_DIR, exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT CHECK(type IN ('bank','cash','card')) NOT NULL,
            institution TEXT,
            number TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            kind TEXT CHECK(kind IN ('expense','income','tax','payroll')) NOT NULL DEFAULT 'expense'
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cost_centers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bank_account_id INTEGER,
            closing_day INTEGER,
            due_day INTEGER,
            credit_limit REAL,
            FOREIGN KEY(bank_account_id) REFERENCES accounts(id)
        );
        """
    )

    cur.execute(
        """
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
            attachment_path TEXT,
            FOREIGN KEY(cost_center_id) REFERENCES cost_centers(id),
            FOREIGN KEY(category_id) REFERENCES categories(id),
            FOREIGN KEY(account_id) REFERENCES accounts(id),
            FOREIGN KEY(card_id) REFERENCES cards(id)
        );
        """
    )

    cur.execute(
        """
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
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS taxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            jurisdiction TEXT,
            code TEXT,
            periodicity TEXT,
            due_day INTEGER
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT CHECK(role IN ('owner','admin','user')) NOT NULL DEFAULT 'user',
            account_id INTEGER,
            sectors TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(account_id) REFERENCES accounts(id)
        );
        """
    )

    # Garantir coluna sectors caso venha de versão anterior
    cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
    if "sectors" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN sectors TEXT")

    conn.commit()


def fetch_df(query: str, params: tuple = ()):  # SELECT helper
    conn = get_conn()
    return pd.read_sql_query(query, conn, params=params)


def exec_sql(query: str, params: tuple = ()):  # INSERT/UPDATE/DELETE helper
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    return cur.lastrowid

# ---------------------- Settings helpers ----------------------
def get_setting(key: str, default: str = "") -> str:
    df = fetch_df("SELECT value FROM settings WHERE key = ?", (key,))
    return df.iloc[0, 0] if not df.empty else default

def set_setting(key: str, value: str):
    exec_sql("REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))

# ---------------------- Seed mínimo ----------------------
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
    if fetch_df("SELECT COUNT(*) as n FROM cost_centers").iloc[0, 0] == 0:
        for n in ["Administrativo", "Produção", "Comercial", "Logística"]:
            exec_sql("INSERT INTO cost_centers (name) VALUES (?)", (n,))

# ---------------------- Login ----------------------
def login_widget() -> bool:
    auth_enabled = get_setting("auth_enabled", "0") == "1"
    if not auth_enabled:
        return True
    st.sidebar.markdown("### Entrar")
    email = st.sidebar.text_input("Email")
    pwd = st.sidebar.text_input("Senha", type="password")
    ok = st.sidebar.button("Login")
    if ok:
        u = fetch_df("SELECT * FROM users WHERE email = ? AND is_active = 1", (email.strip().lower(),))
        if not u.empty and u.iloc[0]["password_hash"] == hash_password(pwd):
            st.session_state["user"] = {
                "id": int(u.iloc[0]["id"]),
                "name": u.iloc[0]["name"],
                "email": u.iloc[0]["email"],
                "role": u.iloc[0]["role"],
                "account_id": int(u.iloc[0]["account_id"]) if pd.notna(u.iloc[0]["account_id"]) else None,
                "sectors": [s.strip() for s in str(u.iloc[0]["sectors"] or "").split(",") if s.strip()],
            }
            st.experimental_rerun()
        else:
            st.sidebar.error("Credenciais inválidas")
    if "user" in st.session_state:
        u = st.session_state["user"]
        st.sidebar.success(f"Olá, {u['name']}")
        if st.sidebar.button("Sair"):
            del st.session_state["user"]
            st.experimental_rerun()
        return True
    return False


def require_role(min_role: str) -> bool:
    ranking = {"user": 1, "admin": 2, "owner": 3}
    if get_setting("auth_enabled", "0") != "1":
        return True
    if "user" not in st.session_state:
        st.warning("Faça login para acessar esta seção.")
        return False
    return ranking.get(st.session_state["user"]["role"], 1) >= ranking.get(min_role, 1)

# ---------------------- Helpers de UI ----------------------
def money(v: float) -> str:
    return (f"R$ {v:,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")


def safe_label(x):
    try:
        if isinstance(x, tuple):
            lab = x[1]
        else:
            lab = x
        if lab is None or (isinstance(lab, float) and pd.isna(lab)):
            return "—"
        return str(lab)
    except Exception:
        return "—"


def export_excel(df: pd.DataFrame, filename: str = "relatorio.xlsx"):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    st.download_button(
        "⬇️ Exportar Excel",
        data=buf.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

def export_csv(df: pd.DataFrame, filename: str = "relatorio.csv"):
    st.download_button(
        "⬇️ Exportar CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
    )

# --- Anexos: preview e download ---
def _read_file_bytes(path: str) -> bytes | None:
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
    # Preview simples para imagens
    if ext in (".png", ".jpg", ".jpeg"):
        st.image(data, caption=fname, use_column_width=True)
    else:
        st.info("Pré-visualização inline disponível apenas para imagens. Use o botão para baixar o arquivo.")
    st.download_button("⬇️ Baixar anexo", data=data, file_name=fname)

# Aplica escopo por conta e setor
def scope_filters(base_query: str, params: list) -> tuple[str, list]:
    if get_setting("auth_enabled", "0") == "1" and "user" in st.session_state:
        acc = st.session_state["user"].get("account_id")
        sectors = st.session_state["user"].get("sectors", [])
        if acc:
            base_query += " AND (account_id IS NULL OR account_id = ?)"
            params.append(acc)
        if sectors:
            placeholders = ",".join(["?"] * len(sectors))
            base_query += f" AND (sector IS NULL OR sector IN ({placeholders}))"
            params.extend(sectors)
    return base_query, params

# ---------------------- Componentes de UI ----------------------
def header():
    st.title("FinApp — Controle Financeiro de Pequenas Empresas")
    st.caption("Lançamentos por setor, conciliação e relatórios, com guias amigáveis.")

def kpis_overview():
    query = "SELECT type, status, amount, account_id, sector FROM transactions WHERE 1=1"
    query, params = scope_filters(query, [])
    df = fetch_df(query, tuple(params))
    if df.empty:
        st.info("Sem lançamentos ainda. Use as guias para começar.")
        return
    total_desp = df.query("type in ['expense','tax','payroll','card']")["amount"].sum()
    total_rec = df.query("type == 'income'")["amount"].sum()
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
               (SELECT name FROM cost_centers cc WHERE cc.id = t.cost_center_id) as Centro_de_Custos,
               t.sector as Setor,
               t.status as Status
        FROM transactions t WHERE 1=1
    """
    q, p = scope_filters(q, [])
    q += " ORDER BY t.id DESC LIMIT 10"
    st.dataframe(fetch_df(q, tuple(p)), use_container_width=True)

def form_lancamento_generico(default_type: str = 'expense', label: str = "Novo lançamento", force_account_id: int | None = None):
    st.markdown(f"**{label}**")
    with st.form(f"form_{label}_{default_type}"):
        c1, c2, c3 = st.columns(3)
        dt_val = c1.date_input("Data", value=date.today())
        amount = c2.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
        method = c3.selectbox("Meio de Pagamento", ["pix", "ted", "boleto", "dinheiro", "cartão", "outro"]) if default_type != 'card' else "cartão"

        c4, c5, c6 = st.columns(3)
        accounts_df = fetch_df("SELECT id, name FROM accounts WHERE type <> 'card'")
        # Se login ativo e usuario tem account_id, pré-selecionar/forçar
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

        # Limitar setores conforme escopo do usuário
        allowed_sectors = st.session_state.get("user", {}).get("sectors", []) if get_setting("auth_enabled", "0") == "1" else []
        sector_options = allowed_sectors if allowed_sectors else ["Administrativo", "Produção", "Comercial", "Logística", "Outros"]
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
                    with open(fpath, "wb") as f:
                        f.write(attach.getbuffer())
                    attach_path = fpath

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
                        None,  # cost center opcional
                        (cat[0] if isinstance(cat, tuple) else None),
                        account_id_final,
                        method, doc, party, desc, float(amount), status, 'manual', attach_path
                    )
                )
                st.success("Lançamento salvo!")
                st.experimental_rerun()

# ---------------------- Páginas ----------------------
def page_dashboard():
    header()
    kpis_overview()

def page_extratos_bancarios():
    st.header("Extratos Bancários")
    st.caption("Importe CSV simples (data, descrição, valor) e classifique rapidamente.")

    accounts_df = fetch_df("SELECT id, name FROM accounts WHERE type='bank'")
    if not accounts_df.empty:
        accounts_df["name"] = accounts_df["name"].fillna("—").astype(str)
    force_acc = st.session_state.get("user", {}).get("account_id") if get_setting("auth_enabled", "0") == "1" else None
    if accounts_df.empty and not force_acc:
        st.warning("Nenhuma conta bancária cadastrada em Configurações > Contas.")
        return

    if force_acc:
        st.info("Importando para a conta vinculada ao seu usuário.")
        if not accounts_df.empty and (accounts_df.id == force_acc).any():
            acc_name = accounts_df.loc[accounts_df.id == force_acc, "name"].iloc[0]
        else:
            acc_name = "Conta do Usuário"
        acc = (force_acc, acc_name)
    else:
        acc_options = [(int(r.id), r.name) for _, r in accounts_df.iterrows()]
        acc = st.selectbox("Conta de destino", acc_options, format_func=safe_label)

    up = st.file_uploader("Arraste o CSV do banco", type=["csv"])
    if up:
        content = StringIO(up.getvalue().decode("utf-8"))
        df = pd.read_csv(content)
        st.write("Pré-visualização:")
        st.dataframe(df.head(), use_container_width=True)

        cols = list(df.columns)
        col_date = st.selectbox("Coluna de Data", cols)
        col_desc = st.selectbox("Coluna de Descrição", cols, index=min(1, len(cols) - 1))
        col_val = st.selectbox("Coluna de Valor", cols, index=min(2, len(cols) - 1))

        if st.button("Importar lançamentos"):
            imp = df[[col_date, col_desc, col_val]].copy()
            imp.columns = ["date", "desc", "amount"]
            n_ok = 0
            for _, r in imp.iterrows():
                try:
                    d = pd.to_datetime(r["date"]).date().isoformat()
                    v = float(r["amount"])
                    exec_sql(
                        """
                        INSERT INTO transactions (trx_date, type, sector, category_id, account_id,
                                                  method, doc_number, counterparty, description, amount, status, origin)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            d, 'expense' if v < 0 else 'income', 'Administrativo', None,
                            acc[0] if isinstance(acc, tuple) else acc,
                            'extrato', '', '', str(r["desc"]).strip(), abs(v), 'paid', 'bank'
                        )
                    )
                    n_ok += 1
                except Exception as e:
                    st.error(f"Falha ao importar uma linha: {e}")
            st.success(f"Importação concluída: {n_ok} lançamentos")
            st.experimental_rerun()

    st.divider()
    st.subheader("Lançamentos recentes do banco")
    q = "SELECT trx_date as Data, description as Descrição, amount as Valor, status as Status, sector as Setor FROM transactions WHERE origin='bank'"
    q, p = scope_filters(q, [])
    q += " ORDER BY id DESC LIMIT 20"
    st.dataframe(fetch_df(q, tuple(p)), use_container_width=True)

def page_cartoes_credito():
    st.header("Cartões de Crédito")
    st.caption("Controle de faturas, despesas por cartão e conciliação com conta bancária.")

    cards = fetch_df("SELECT id, name FROM cards")
    if cards.empty:
        st.info("Nenhum cartão cadastrado. Vá em Configurações > Cartões.")
        return

    card_options = [(int(r.id), r.name) for _, r in cards.iterrows()]
    card = st.selectbox("Cartão", card_options, format_func=safe_label)

    st.markdown("**Lançar despesa do cartão**")
    with st.form("form_card"):
        dt_val = st.date_input("Data", value=date.today())
        amount = st.number_input("Valor (R$)", min_value=0.0, step=0.01)
        desc = st.text_input("Descrição")
        cat_df = fetch_df("SELECT id, name FROM categories WHERE kind='expense'")
        cat_options = [(int(r.id), r.name) for _, r in cat_df.iterrows()]
        cat = st.selectbox("Categoria", cat_options, format_func=safe_label)
        # setor conforme escopo
        allowed_sectors = st.session_state.get("user", {}).get("sectors", []) if get_setting("auth_enabled", "0") == "1" else []
        sector_options = allowed_sectors if allowed_sectors else ["Administrativo", "Produção", "Comercial", "Logística", "Outros"]
        sector = st.selectbox("Setor", sector_options)
        attach = st.file_uploader("Comprovante (opcional)", type=["pdf", "png", "jpg", "jpeg"], key="card_attach")
        ok = st.form_submit_button("Salvar")
        if ok:
            attach_path = None
            if attach is not None:
                fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{attach.name}"
                fpath = os.path.join(ATTACH_DIR, fname)
                with open(fpath, "wb") as f:
                    f.write(attach.getbuffer())
                attach_path = fpath
            exec_sql(
                """
                INSERT INTO transactions (trx_date, type, card_id, category_id, description, amount, status, method, origin, sector, attachment_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (dt_val.isoformat(), 'card', card[0], cat[0], desc, float(amount), 'planned', 'cartão', 'card', sector, attach_path)
            )
            st.success("Lançado na fatura do cartão.")
            st.experimental_rerun()

    st.divider()
    st.subheader("Lançamentos do cartão (recentes)")
    df = fetch_df(
        """
        SELECT trx_date as Data, description as Descrição, amount as Valor, status as Status, sector as Setor
        FROM transactions WHERE type='card' AND card_id = ?
        ORDER BY id DESC LIMIT 20
        """,
        (card[0],)
    )
    st.dataframe(df, use_container_width=True)

def page_impostos():
    st.header("Impostos & Tributos")
    st.caption("Controle de obrigações (ICMS, ISS, INSS, IRPJ/CSLL etc.) e seus vencimentos.")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("**Cadastrar tributo**")
        with st.form("form_tax"):
            name = st.text_input("Nome do tributo", placeholder="ICMS, ISS, INSS, IRPJ/CSLL…")
            jur = st.selectbox("Esfera", ["Federal", "Estadual", "Municipal"])
            code = st.text_input("Código/Referência (opcional)")
            per = st.selectbox("Periodicidade", ["mensal", "trimestral", "anual"])
            due = st.number_input("Dia de vencimento", min_value=1, max_value=31, value=20)
            ok = st.form_submit_button("Salvar")
            if ok and name:
                exec_sql(
                    "INSERT INTO taxes (name,jurisdiction,code,periodicity,due_day) VALUES (?,?,?,?,?)",
                    (name, jur, code, per, int(due)),
                )
                st.success("Tributo salvo")
    with col2:
        st.markdown("**Tributos cadastrados**")
        st.dataframe(
            fetch_df("SELECT id, name as Tributo, jurisdiction as Esfera, periodicity as Periodicidade, due_day as Vencimento FROM taxes ORDER BY name"),
            use_container_width=True,
        )

    st.divider()
    st.subheader("Lançar pagamento/guia")
    # força conta do usuário se houver
    force_acc = st.session_state.get("user", {}).get("account_id") if get_setting("auth_enabled", "0") == "1" else None
    form_lancamento_generico(default_type='tax', label="Novo pagamento de tributo", force_account_id=force_acc)

def page_folha():
    st.header("Folha & Encargos")
    st.caption("Registre folha, encargos e gere lançamentos financeiros automaticamente.")

    with st.form("form_payroll"):
        period = st.text_input("Período (AAAA-MM)", value=datetime.now().strftime("%Y-%m"))
        emp = st.text_input("Colaborador")
        gross = st.number_input("Salário Bruto (R$)", min_value=0.0, step=0.01)
        charges = st.number_input("Encargos (R$)", min_value=0.0, step=0.01, help="INSS patronal, FGTS etc.")
        benefits = st.number_input("Benefícios (R$)", min_value=0.0, step=0.01)
        total = gross + charges + benefits
        st.info(f"Total calculado: {money(total)}")
        add = st.form_submit_button("Salvar folha deste colaborador")
        if add and emp:
            exec_sql(
                "INSERT INTO payroll (period, employee, gross, charges, benefits, total, paid) VALUES (?,?,?,?,?,?,0)",
                (period, emp, float(gross), float(charges), float(benefits), float(total)),
            )
            # gera lançamento (escopo por conta se houver)
            force_acc = st.session_state.get("user", {}).get("account_id") if get_setting("auth_enabled", "0") == "1" else None
            exec_sql(
                """
                INSERT INTO transactions (trx_date, type, sector, description, amount, status, origin, account_id)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (date.today().isoformat(), 'payroll', 'Administrativo', f"Folha {period} - {emp}", float(total), 'planned', 'manual', force_acc),
            )
            st.success("Folha salva e lançamento financeiro criado.")

    st.divider()
    st.subheader("Folhas recentes")
    st.dataframe(
        fetch_df("SELECT period as Período, employee as Colaborador, total as Total, paid as Pago FROM payroll ORDER BY id DESC LIMIT 20"),
        use_container_width=True,
    )

def page_outras_despesas():
    st.header("Outras Despesas (Fornecedores & Compras)")
    st.caption("Lance despesas gerais por setor/centro de custos.")
    force_acc = st.session_state.get("user", {}).get("account_id") if get_setting("auth_enabled", "0") == "1" else None
    form_lancamento_generico(default_type='expense', label="Nova despesa", force_account_id=force_acc)

def page_receitas():
    st.header("Receitas")
    st.caption("Registre entradas de vendas e outras receitas.")
    force_acc = st.session_state.get("user", {}).get("account_id") if get_setting("auth_enabled", "0") == "1" else None
    form_lancamento_generico(default_type='income', label="Nova receita", force_account_id=force_acc)

def page_conciliacao():
    st.header("Conciliação")
    st.caption("Marque como conciliado o que já entrou/saiu conforme extrato/fatura.")
    q = "SELECT id, trx_date as Data, description as Descrição, amount as Valor, status as Status, sector as Setor FROM transactions WHERE 1=1"
    q, p = scope_filters(q, [])
    q += " ORDER BY id DESC LIMIT 200"
    df = fetch_df(q, tuple(p))
    if df.empty:
        st.info("Nada para conciliar.")
        return

    st.dataframe(df, use_container_width=True)
    ids = st.multiselect("Selecione IDs para marcar como conciliado", df["id"].tolist())
    if st.button("Marcar selecionados como conciliado") and ids:
        qmarks = ",".join(["?"] * len(ids))
        exec_sql(f"UPDATE transactions SET status='reconciled' WHERE id IN ({qmarks})", tuple(ids))
        st.success("Atualizado!")
        st.experimental_rerun()

def page_relatorios():
    st.header("Relatórios")
    c1, c2, c3, c4 = st.columns(4)
    dt_ini = c1.date_input("De", value=date(date.today().year, 1, 1))
    dt_fim = c2.date_input("Até", value=date.today())
    setor = c3.selectbox("Setor", ["(Todos)", "Administrativo", "Produção", "Comercial", "Logística", "Outros"])
    tipo = c4.selectbox("Tipo", ["(Todos)", "expense", "income", "tax", "payroll", "card"])

    query = (
        "SELECT id as ID, trx_date as Data, type as Tipo, sector as Setor, "
        "description as Descrição, amount as Valor, account_id as Conta, "
        "attachment_path as Anexo FROM transactions WHERE date(trx_date) BETWEEN ? AND ?"
    )
    params = [dt_ini.isoformat(), dt_fim.isoformat()]
    if setor != "(Todos)":
        query += " AND (sector = ?)"
        params.append(setor)
    if tipo != "(Todos)":
        query += " AND (type = ?)"
        params.append(tipo)

    query, params = scope_filters(query, params)
    query += " ORDER BY date(trx_date)"

    df = fetch_df(query, tuple(params))
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        st.success(f"Total no período filtrado: {money(df['Valor'].sum())}")
        colx, coly = st.columns(2)
        with colx:
            export_excel(df)
        with coly:
            export_csv(df)

        # ----- Visualização/Download de Anexos -----
        st.divider()
        st.subheader("Anexos")
        att_df = df.dropna(subset=['Anexo']) if 'Anexo' in df.columns else pd.DataFrame()
        if att_df.empty:
            st.info("Nenhum lançamento com anexo no filtro atual.")
        else:
            sel_id = st.selectbox("Escolha o lançamento para visualizar o anexo", att_df['ID'].tolist())
            path = att_df.loc[att_df['ID'] == sel_id, 'Anexo'].values[0]
            show_attachment_ui(str(path))

# ---------------------- Main / Navegação ----------------------
def main():
    init_db()
    seed_minimums()

    with st.sidebar:
        st.markdown("## FinApp")
        st.caption("Selecione uma área:")
        page = st.selectbox(
            "Navegação",
            [
                "Dashboard",
                "Extratos Bancários",
                "Cartões de Crédito",
                "Impostos & Tributos",
                "Folha & Encargos",
                "Outras Despesas",
                "Receitas",
                "Conciliação",
                "Relatórios",
            ],
            index=0,
        )

        st.divider()
        st.markdown("**Autenticação (opcional)**")
        auth_flag = get_setting("auth_enabled", "0")
        new_flag = st.checkbox("Exigir login", value=(auth_flag == "1"))
        if new_flag != (auth_flag == "1"):
            set_setting("auth_enabled", "1" if new_flag else "0")
            st.experimental_rerun()

    # Se login estiver habilitado, exigir autenticação antes das páginas
    if get_setting("auth_enabled", "0") == "1":
        if not login_widget():
            return

    if page == "Dashboard":
        page_dashboard()
    elif page == "Extratos Bancários":
        page_extratos_bancarios()
    elif page == "Cartões de Crédito":
        page_cartoes_credito()
    elif page == "Impostos & Tributos":
        page_impostos()
    elif page == "Folha & Encargos":
        page_folha()
    elif page == "Outras Despesas":
        page_outras_despesas()
    elif page == "Receitas":
        page_receitas()
    elif page == "Conciliação":
        page_conciliacao()
    elif page == "Relatórios":
        page_relatorios()
    else:
        page_dashboard()

if __name__ == "__main__":
    main()
