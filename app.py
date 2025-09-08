# app.py — FinApp (modo ultraestável + fallback DEMO sem banco)
# Requisitos: streamlit, pandas, openpyxl
# Execução simples: python -m streamlit run app.py --server.port 8501 --server.fileWatcherType=none
# Dica: se a tela ficar preta, ative o "Modo DEMO (sem banco)" na barra lateral para abrir a UI imediatamente.

import os
import hashlib
import sqlite3
from io import StringIO, BytesIO
from datetime import date, datetime

import pandas as pd
import streamlit as st

# ---------------------- Constantes ----------------------
DB_PATH = "finapp.db"
ATTACH_DIR = "attachments"
SQLITE_TIMEOUT = 4.0
PAGE_TITLE = "FinApp | Pequenas Empresas"

# ---------------------- Config inicial ----------------------
st.set_page_config(page_title=PAGE_TITLE, layout="wide")

def do_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()  # compat c/ versões antigas
        except Exception:
            pass

# ---------------------- Helpers UI ----------------------
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
    if ext in (".png", ".jpg", ".jpeg"):
        st.image(data, caption=fname, use_column_width=True)
    else:
        st.info("Pré-visualização inline disponível apenas para imagens. Use o botão para baixar o arquivo.")
    st.download_button("⬇️ Baixar anexo", data=data, file_name=fname)

def header():
    st.title("FinApp — Controle Financeiro de Pequenas Empresas")
    st.caption("Lançamentos por setor, conciliação e relatórios, com guias amigáveis.")

def unauth_screen():
    st.title("FinApp — Acesse pela barra lateral")
    st.markdown(
        """
        **Você ainda não está logado.**
        1) Crie o **OWNER** na barra lateral (se a base estiver vazia).  
        2) Faça **login** com email e senha.  
        Depois de logar, o **Dashboard** aparece aqui.
        """
    )

# ---------------------- DB (conexões curtas, sem WAL) ----------------------
def _connect() -> sqlite3.Connection:
    """
    Conexão curta (abre/fecha a cada operação) em modo DELETE (sem -wal/-shm),
    ajuda a evitar travas no Windows/Antivírus.
    """
    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
        timeout=SQLITE_TIMEOUT,
    )
    try:
        conn.execute("PRAGMA journal_mode=DELETE;")
    except Exception:
        pass
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn

def db_ready() -> tuple[bool, str]:
    try:
        with _connect() as conn:
            conn.execute("SELECT 1;").fetchone()
        return True, "ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

def fetch_df(query: str, params: tuple = ()) -> pd.DataFrame:
    try:
        with _connect() as conn:
            return pd.read_sql_query(query, conn, params=params)
    except Exception as e:
        st.error(f"Erro ao consultar o banco: {e}")
        return pd.DataFrame()

def exec_sql(query: str, params: tuple = ()) -> int | None:
    try:
        with _connect() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()
            return cur.lastrowid
    except Exception as e:
        st.error(f"Erro ao gravar no banco: {e}")
        return None

def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def init_db():
    os.makedirs(ATTACH_DIR, exist_ok=True)
    with _connect() as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)

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
            CREATE TABLE IF NOT EXISTS cost_centers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                bank_account_id INTEGER,
                closing_day INTEGER,
                due_day INTEGER,
                credit_limit REAL,
                FOREIGN KEY(bank_account_id) REFERENCES accounts(id)
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
                attachment_path TEXT,
                FOREIGN KEY(cost_center_id) REFERENCES cost_centers(id),
                FOREIGN KEY(category_id) REFERENCES categories(id),
                FOREIGN KEY(account_id) REFERENCES accounts(id),
                FOREIGN KEY(card_id) REFERENCES cards(id)
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
                role TEXT CHECK(role IN ('owner','admin','user')) NOT NULL DEFAULT 'user',
                account_id INTEGER,
                sectors TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            );
        """)

        # Migração defensiva: garantir coluna sectors
        cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
        if "sectors" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN sectors TEXT")

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
    if fetch_df("SELECT COUNT(*) as n FROM cost_centers").iloc[0, 0] == 0:
        for n in ["Administrativo", "Produção", "Comercial", "Logística"]:
            exec_sql("INSERT INTO cost_centers (name) VALUES (?)", (n,))

# ---------------------- Login/escopo (DB) ----------------------
def login_widget_db() -> bool:
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
            do_rerun()
        else:
            st.sidebar.error("Credenciais inválidas")
    if "user" in st.session_state:
        u = st.session_state["user"]
        st.sidebar.success(f"Olá, {u['name']} ({u['role']})")
        if st.sidebar.button("Sair"):
            del st.session_state["user"]
            do_rerun()
        return True
    return False

def require_role(min_role: str) -> bool:
    ranking = {"user": 1, "admin": 2, "owner": 3}
    if "user" not in st.session_state:
        st.warning("Faça login para acessar esta seção.")
        return False
    return ranking.get(st.session_state["user"]["role"], 1) >= ranking.get(min_role, 1)

def scope_filters(base_query: str, params: list) -> tuple[str, list]:
    if "user" in st.session_state:
        role = st.session_state["user"].get("role")
        if role == "owner":
            return base_query, params  # OWNER vê tudo
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

# ---------------------- Páginas (DB) ----------------------
def kpis_overview_db():
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
               (SELECT name FROM cost_centers cc WHERE cc.id = t.cost_center_id) as Centro_de_Custos,
               t.sector as Setor,
               t.status as Status
        FROM transactions t WHERE 1=1
    """
    q, p = scope_filters(q, [])
    q += " ORDER BY t.id DESC LIMIT 10"
    st.dataframe(fetch_df(q, tuple(p)), use_container_width=True)

def form_lancamento_generico_db(default_type: str = 'expense', label: str = "Novo lançamento", force_account_id: int | None = None):
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

        allowed_sectors = st.session_state.get("user", {}).get("sectors", []) if "user" in st.session_state else []
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
                        method, doc, party, desc, float(amount), status, 'manual', attach_path
                    )
                )
                st.success("Lançamento salvo!")
                do_rerun()

def page_dashboard_db():
    header()
    kpis_overview_db()

def page_extratos_bancarios_db():
    st.header("Extratos Bancários")
    st.caption("Importe CSV simples (data, descrição, valor) e classifique rapidamente.")

    accounts_df = fetch_df("SELECT id, name FROM accounts WHERE type='bank'")
    if not accounts_df.empty:
        accounts_df["name"] = accounts_df["name"].fillna("—").astype(str)
    force_acc = st.session_state.get("user", {}).get("account_id") if "user" in st.session_state else None
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
        try:
            content = StringIO(up.getvalue().decode("utf-8"))
            df = pd.read_csv(content)
        except Exception as e:
            st.error(f"Erro ao ler CSV: {e}")
            return

        st.write("Pré-visualização:")
        st.dataframe(df.head(), use_container_width=True)

        cols = list(df.columns)
        if not cols:
            st.warning("CSV sem colunas detectadas.")
            return

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
            do_rerun()

    st.divider()
    st.subheader("Lançamentos recentes do banco")
    q = "SELECT trx_date as Data, description as Descrição, amount as Valor, status as Status, sector as Setor FROM transactions WHERE origin='bank'"
    q, p = scope_filters(q, [])
    q += " ORDER BY id DESC LIMIT 20"
    st.dataframe(fetch_df(q, tuple(p)), use_container_width=True)

def page_cartoes_credito_db():
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
        allowed_sectors = st.session_state.get("user", {}).get("sectors", []) if "user" in st.session_state else []
        sector_options = allowed_sectors if allowed_sectors else ["Administrativo", "Produção", "Comercial", "Logística", "Outros"]
        sector = st.selectbox("Setor", sector_options)
        attach = st.file_uploader("Comprovante (opcional)", type=["pdf", "png", "jpg", "jpeg"], key="card_attach")
        ok = st.form_submit_button("Salvar")
        if ok:
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
            exec_sql(
                """
                INSERT INTO transactions (trx_date, type, card_id, category_id, description, amount, status, method, origin, sector, attachment_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (dt_val.isoformat(), 'card', card[0], cat[0], desc, float(amount), 'planned', 'cartão', 'card', sector, attach_path)
            )
            st.success("Lançado na fatura do cartão.")
            do_rerun()

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

def page_impostos_db():
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
    force_acc = st.session_state.get("user", {}).get("account_id") if "user" in st.session_state else None
    form_lancamento_generico_db(default_type='tax', label="Novo pagamento de tributo", force_account_id=force_acc)

def page_folha_db():
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
            force_acc = st.session_state.get("user", {}).get("account_id") if "user" in st.session_state else None
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

def page_outras_despesas_db():
    st.header("Outras Despesas (Fornecedores & Compras)")
    st.caption("Lance despesas gerais por setor/centro de custos.")
    force_acc = st.session_state.get("user", {}).get("account_id") if "user" in st.session_state else None
    form_lancamento_generico_db(default_type='expense', label="Nova despesa", force_account_id=force_acc)

def page_receitas_db():
    st.header("Receitas")
    st.caption("Registre entradas de vendas e outras receitas.")
    force_acc = st.session_state.get("user", {}).get("account_id") if "user" in st.session_state else None
    form_lancamento_generico_db(default_type='income', label="Nova receita", force_account_id=force_acc)

def page_conciliacao_db():
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
        do_rerun()

def page_admin_users_db():
    st.header("Admin: Usuários")
    if not require_role("admin"):
        return

    df = fetch_df(
        """
        SELECT
            u.id as ID,
            u.name as Nome,
            u.email as Email,
            u.role as Papel,
            u.is_active as Ativo,
            u.account_id as Conta_ID,
            COALESCE(a.name,'—') as Conta_Nome,
            COALESCE(u.sectors,'') as Setores,
            u.created_at as Criado_em
        FROM users u
        LEFT JOIN accounts a ON a.id = u.account_id
        ORDER BY u.id DESC
        """
    )
    st.dataframe(df, use_container_width=True)
    st.caption("Observação: esta listagem não concede acesso aos lançamentos de outras contas. O escopo continua aplicado para user e admin. Apenas OWNER tem visão completa dos dados financeiros.")

# ---------------------- DEMO (sem banco) ----------------------
def demo_seed():
    # dados simples em memória
    st.session_state.setdefault("demo_user", {"name": "Demo Owner", "role": "owner"})
    st.session_state.setdefault("demo_accounts", pd.DataFrame([
        {"id": 1, "name": "Conta Corrente", "type": "bank"},
        {"id": 2, "name": "Caixa", "type": "cash"},
    ]))
    st.session_state.setdefault("demo_tx", pd.DataFrame([
        {"id": 1, "trx_date": str(date.today()), "type": "income", "sector": "Comercial", "description": "Venda #1001", "amount": 1500.00, "status": "paid"},
        {"id": 2, "trx_date": str(date.today()), "type": "expense", "sector": "Administrativo", "description": "Energia", "amount": 420.75, "status": "paid"},
        {"id": 3, "trx_date": str(date.today()), "type": "tax", "sector": "Administrativo", "description": "ICMS", "amount": 230.00, "status": "planned"},
    ]))

def header_demo():
    st.title("FinApp (DEMO) — Sem Banco de Dados")
    st.caption("Este modo ignora SQLite e usa dados fictícios em memória — útil se algo estiver bloqueando o banco de dados na sua máquina.")

def page_dashboard_demo():
    header_demo()
    df = st.session_state["demo_tx"]
    total_rec = float(df.query("type == 'income'")["amount"].sum())
    total_desp = float(df.query("type != 'income'")["amount"].sum())
    saldo = total_rec - total_desp
    c1, c2, c3 = st.columns(3)
    c1.metric("Receitas", money(total_rec))
    c2.metric("Despesas", money(total_desp))
    c3.metric("Saldo", money(saldo))
    st.divider()
    st.subheader("Lançamentos (amostra)")
    st.dataframe(df.rename(columns={
        "trx_date":"Data","type":"Tipo","description":"Descrição","amount":"Valor","sector":"Setor","status":"Status"
    }), use_container_width=True)
    st.info("Modo DEMO: cadastros/lançamentos não são persistidos.")

def router_demo():
    page = st.sidebar.selectbox("Navegação", [
        "Dashboard (DEMO)",
    ], index=0)
    if page == "Dashboard (DEMO)":
        page_dashboard_demo()

# ---------------------- Main ----------------------
def main():
    # Toggle DEMO (sem banco) — garante UI mesmo se SQLite travar
    with st.sidebar:
        st.markdown("## ⚙️ Opções")
        demo = st.checkbox("Modo DEMO (sem banco)", value=False, help="Se a tela ficar preta/sem resposta, ative este modo para abrir a UI imediatamente (usa dados em memória).")

    if demo:
        # Sem tocar no banco: UI imediata
        demo_seed()
        router_demo()
        return

    # ---- Modo normal com banco ----
    ok, msg = db_ready()
    if not ok:
        st.error(f"Banco de dados indisponível: {msg}")
        st.info("Ative o **Modo DEMO (sem banco)** na barra lateral para abrir a UI agora mesmo.")
        return

    try:
        init_db()
        seed_minimums()
    except Exception as e:
        st.error(f"Falha ao iniciar o banco de dados: {e}")
        st.info("Ative o **Modo DEMO (sem banco)** na barra lateral para abrir a UI agora mesmo.")
        return

    # Se não houver usuários, mostrar bootstrap na sidebar
    def _users_count() -> int:
        df = fetch_df("SELECT COUNT(*) as n FROM users")
        return int(df.iloc[0, 0]) if not df.empty else 0

    def create_initial_owner_ui() -> None:
        st.sidebar.warning("Configuração inicial: crie o usuário OWNER (acesso total).")
        with st.sidebar.form("form_first_owner"):
            name = st.text_input("Nome")
            email = st.text_input("Email (login)")
            pwd = st.text_input("Senha", type="password")
            acc_df = fetch_df("SELECT id, name FROM accounts ORDER BY name")
            acc_opts = [(None, "—")] + ([(int(r.id), r.name) for _, r in acc_df.iterrows()] if not acc_df.empty else [])
            acc_sel = st.selectbox("Conta padrão (opcional)", acc_opts, format_func=safe_label)
            sectors_csv = st.text_input("Setores (CSV, opcional)", placeholder="Administrativo,Produção")
            okbtn = st.form_submit_button("Criar OWNER")
            if okbtn:
                if not (name and email and pwd):
                    st.sidebar.error("Preencha nome, email e senha.")
                else:
                    exec_sql(
                        "INSERT INTO users (name,email,password_hash,role,account_id,sectors,is_active) VALUES (?,?,?,?,?,?,1)",
                        (
                            name.strip(),
                            email.strip().lower(),
                            hash_password(pwd),
                            "owner",
                            acc_sel[0] if isinstance(acc_sel, tuple) else None,
                            sectors_csv.strip(),
                        ),
                    )
                    st.sidebar.success("OWNER criado. Faça login com este usuário.")
                    do_rerun()

    if _users_count() == 0:
        create_initial_owner_ui()

    logged = login_widget_db()
    if not logged:
        unauth_screen()
        return

    role = st.session_state["user"]["role"]
    with st.sidebar:
        st.markdown("## FinApp")
        st.caption("Selecione uma área:")
        pages = [
            "Dashboard",
            "Extratos Bancários",
            "Cartões de Crédito",
            "Impostos & Tributos",
            "Folha & Encargos",
            "Outras Despesas",
            "Receitas",
            "Conciliação",
            "Relatórios",
        ]
        if role in ("admin", "owner"):
            pages.append("Admin: Usuários")
        page = st.selectbox("Navegação", pages, index=0)

    if page == "Dashboard":
        page_dashboard_db()
    elif page == "Extratos Bancários":
        page_extratos_bancarios_db()
    elif page == "Cartões de Crédito":
        page_cartoes_credito_db()
    elif page == "Impostos & Tributos":
        page_impostos_db()
    elif page == "Folha & Encargos":
        page_folha_db()
    elif page == "Outras Despesas":
        page_outras_despesas_db()
    elif page == "Receitas":
        page_receitas_db()
    elif page == "Conciliação":
        page_conciliacao_db()
    elif page == "Relatórios":
        # relatório rápido (mesma lógica anterior, reusada)
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
            query += " AND (sector = ?)"; params.append(setor)
        if tipo != "(Todos)":
            query += " AND (type = ?)"; params.append(tipo)
        query, params = scope_filters(query, params)
        query += " ORDER BY date(trx_date)"
        df = fetch_df(query, tuple(params))
        st.dataframe(df, use_container_width=True)
        if not df.empty:
            st.success(f"Total no período filtrado: {money(df['Valor'].sum())}")
            colx, coly = st.columns(2)
            with colx: export_excel(df)
            with coly: export_csv(df)
            st.divider()
            st.subheader("Anexos")
            att_df = df.dropna(subset=['Anexo']) if 'Anexo' in df.columns else pd.DataFrame()
            if att_df.empty:
                st.info("Nenhum lançamento com anexo no filtro atual.")
            else:
                sel_id = st.selectbox("Escolha o lançamento para visualizar o anexo", att_df['ID'].tolist())
                path = att_df.loc[att_df['ID'] == sel_id, 'Anexo'].values[0]
                show_attachment_ui(str(path))
    elif page == "Admin: Usuários":
        page_admin_users_db()
    else:
        page_dashboard_db()

if __name__ == "__main__":
    main()
