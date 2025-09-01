# app.py — Painel Financeiro | JVSeps (robusto: log da carteira + gráficos imunes a falhas)
import datetime as dt
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.graph_objects as go
import re
import os
from pathlib import Path

st.set_page_config(page_title="Painel Financeiro | JVSeps", layout="wide")

# =============== Utils básicos ===============
def do_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def fmt_br(d):
    if not d:
        return "—"
    return dt.datetime.strptime(str(d), "%Y-%m-%d").strftime("%d/%m/%y")

def brl(x):
    try:
        return f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"

def parse_brl_text(txt: str) -> float:
    """Converte 'R$ 1.234,56' / '1234,56' / '1234.56' em float."""
    if txt is None:
        return 0.0
    s = str(txt).strip()
    if not s:
        return 0.0
    s = s.replace("R$", "").replace("r$", "").strip()
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    s = re.sub(r"[^0-9\.\-]", "", s)
    try:
        return float(s)
    except Exception:
        return 0.0

# =============== Login simples ===============
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False

def login_ui():
    st.title("🔐 Acesso restrito")
    with st.form("login_form", clear_on_submit=False):
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type="password")
        ok = st.form_submit_button("Entrar", use_container_width=True)
    if ok:
        if u.strip() == "jvseps" and p == "162023":
            st.session_state.auth_ok = True
            st.success("Autenticado!")
            do_rerun()
        else:
            st.error("Usuário ou senha inválidos.")

if not st.session_state.auth_ok:
    login_ui()
    st.stop()

# =============== Faixa de índices ===============
ECON_TICKERS = {
    "DXY": "^DXY",
    "USD/BRL": "BRL=X",
    "IBOV": "^BVSP",
    "S&P 500": "^GSPC",
    "Nasdaq": "^IXIC",
    "Dow": "^DJI",
    "VIX": "^VIX",
    "Ouro": "GC=F",
    "Brent": "BZ=F",
}

def _fmt_change(last: float, prev: float) -> str:
    if np.isnan(last) or np.isnan(prev) or prev == 0:
        return "—"
    pct = (last / prev - 1.0) * 100
    sign = "▲" if pct >= 0 else "▼"
    color = "#16a34a" if pct >= 0 else "#dc2626"
    return f'<span style="color:{color};">{sign} {pct:+.2f}%</span>'

@st.cache_data(ttl=300, show_spinner=False)
def load_econ_batch():
    tickers = list(ECON_TICKERS.values())
    end = dt.date.today()
    start = end - dt.timedelta(days=10)
    try:
        df = yf.download(
            tickers=" ".join(tickers),
            start=start, end=end + dt.timedelta(days=1),
            interval="1d", auto_adjust=True, progress=False,
            group_by="ticker", threads=False,
        )
    except Exception:
        return {}
    out = {}
    for name, t in ECON_TICKERS.items():
        try:
            s = df[t]["Close"].dropna()
            last = float(s.iloc[-1]) if len(s) >= 1 else np.nan
            prev = float(s.iloc[-2]) if len(s) >= 2 else np.nan
            out[name] = (last, prev)
        except Exception:
            out[name] = (np.nan, np.nan)
    return out

def build_marquee_html():
    data = load_econ_batch()
    items = []
    for name, (last, prev) in data.items():
        if str(last) == "nan":
            text = f"<b>{name}</b>: n/d"
        else:
            val = f"{last:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            delta = _fmt_change(last, prev)
            text = f"<b>{name}</b>: {val} {delta}"
        items.append(text)
    content = " &nbsp;&nbsp;•&nbsp;&nbsp; ".join(items)
    html = f"""
    <style>
      .ticker-wrap {{ position:relative; overflow:hidden; background:#0b1220; border-bottom:1px solid #1f2a44; }}
      .ticker {{ display:inline-block; white-space:nowrap; padding:8px 0; animation:ticker-scroll 35s linear infinite;
                 font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; font-size:14px; color:#e5e7eb; }}
      .ticker:hover {{ animation-play-state: paused; }}
      @keyframes ticker-scroll {{ 0% {{ transform: translateX(100%); }} 100% {{ transform: translateX(-100%); }} }}
      .ticker b {{ color:#93c5fd; }}
    </style>
    <div class="ticker-wrap"><div class="ticker">{content}</div></div>
    """
    return html

# =============== Dados de preços (resiliente) ===============
def _extract_close(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype="float64")
    if isinstance(df.columns, pd.MultiIndex):
        for c in df.columns:
            if (isinstance(c, tuple) and len(c) > 0 and str(c[0]).lower() == "close") or (
                isinstance(c, str) and c.lower() == "close"
            ):
                return df[c].dropna()
        return df["Close"].dropna()
    return df["Close"].dropna()

def _make_index_naive(s: pd.Series) -> pd.Series:
    try:
        if getattr(s.index, "tz", None) is not None:
            s.index = s.index.tz_localize(None)
    except Exception:
        try:
            s.index = s.index.tz_convert(None)
        except Exception:
            pass
    return s

def _clamp_start_for_interval(start: dt.date, end: dt.date, interval: str) -> dt.date:
    if interval == "1h":
        max_days = 730
        min_start = end - dt.timedelta(days=max_days)
        if start < min_start:
            return min_start
    return start

def fetch_series_resilient(ticker: str, start_date: dt.date, end_date: dt.date, interval: str) -> pd.Series:
    start_date = _clamp_start_for_interval(start_date, end_date, interval)
    # 1) history()
    try:
        t = yf.Ticker(ticker)
        df = t.history(start=start_date, end=end_date + dt.timedelta(days=1), interval=interval, auto_adjust=True)
        s = _extract_close(df); s = _make_index_naive(s)
        s = s[(s.index >= pd.to_datetime(start_date)) & (s.index <= pd.to_datetime(end_date))]
        if not s.empty:
            return s
    except Exception:
        pass
    # 2) download()
    try:
        df = yf.download(
            tickers=ticker, start=start_date, end=end_date + dt.timedelta(days=1),
            interval=interval, auto_adjust=True, progress=False, threads=False,
        )
        s = _extract_close(df); s = _make_index_naive(s)
        s = s[(s.index >= pd.to_datetime(start_date)) & (s.index <= pd.to_datetime(end_date))]
        if not s.empty:
            return s
    except Exception:
        pass
    # 3) fallback diário
    if interval != "1d":
        for _int in ["1d"]:
            try:
                t = yf.Ticker(ticker)
                df = t.history(start=start_date, end=end_date + dt.timedelta(days=1), interval=_int, auto_adjust=True)
                s = _extract_close(df); s = _make_index_naive(s)
                s = s[(s.index >= pd.to_datetime(start_date)) & (s.index <= pd.to_datetime(end_date))]
                if not s.empty:
                    return s
            except Exception:
                pass
            try:
                df = yf.download(
                    tickers=ticker, start=start_date, end=end_date + dt.timedelta(days=1),
                    interval=_int, auto_adjust=True, progress=False, threads=False,
                )
                s = _extract_close(df); s = _make_index_naive(s)
                s = s[(s.index >= pd.to_datetime(start_date)) & (s.index <= pd.to_datetime(end_date))]
                if not s.empty:
                    return s
            except Exception:
                pass
    return pd.Series(dtype="float64")

def preserve_last_when_empty(ticker: str, end_date: dt.date, lookback_days: int = 365):
    start_lb = end_date - dt.timedelta(days=lookback_days)
    try:
        t = yf.Ticker(ticker)
        df = t.history(start=start_lb, end=end_date + dt.timedelta(days=1), interval="1d", auto_adjust=True)
        s = _extract_close(df); s = _make_index_naive(s)
        if s.empty:
            raise ValueError("history vazio")
        last_date = s.index.max(); last_val = float(s.loc[last_date])
        idx = pd.to_datetime([last_date, end_date])
        vals = pd.Series([last_val, last_val], index=idx)
        note = f"Último dado em {fmt_br(last_date.date())}; mantido até hoje."
        return vals, note
    except Exception:
        return pd.Series(dtype="float64"), "Sem dados históricos."

def pct_change(s: pd.Series):
    if s.size < 2:
        return np.nan
    return (s.iloc[-1] / s.iloc[0] - 1.0) * 100

def _container_border():
    try:
        return st.container(border=True)
    except TypeError:
        return st.container()

def mini_card(title, series, y_label="Preço", start_date=None, note=None,
              width_px=280, height_px=180):
    with _container_border():
        sub = f"<div style='margin-top:-6px;color:#94a3b8;font-size:12px;'>desde {fmt_br(start_date)}</div>" if start_date else ""
        st.markdown(f"#### {title}" + sub, unsafe_allow_html=True)
        if series.empty:
            st.warning("Sem dados para o período selecionado."); return
        last = float(series.iloc[-1]); delta = pct_change(series)
        c1, c2 = st.columns(2, gap="small")
        with c1: st.metric("Último", f"{last:,.2f}")
        with c2: st.metric("Período", f"{delta:+.2f}%")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=series.index, y=series.values, mode="lines"))
        fig.update_layout(width=width_px, height=height_px, margin=dict(l=16, r=10, t=6, b=6),
                          xaxis_title=None, yaxis_title=y_label, showlegend=False, font=dict(size=10))
        st.plotly_chart(fig, config={"displayModeBar": False})
        if note: st.markdown(f"<div style='color:#94a3b8;font-size:12px'>{note}</div>", unsafe_allow_html=True)

def mini_prop_card(proporcoes: dict, width_px=280, height_px=180, title="Proporção de Ativos"):
    with _container_border():
        st.markdown(f"#### {title}")
        labels = list(proporcoes.keys()); values = list(proporcoes.values())
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.5)])
        fig.update_layout(width=width_px, height=height_px, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
        st.plotly_chart(fig, config={"displayModeBar": False})

# =============== LOG da Carteira ===============
DATA_DIR = Path(".")
LOG_FILE = str(DATA_DIR / "carteira_log.csv")
LOG_COLS = ["data", "vcs_valor", "whs_valor", "vcs_pct", "whs_pct", "auto", "descricao", "ts"]

def _load_log() -> pd.DataFrame:
    # Prioriza sessão (caso escrita em disco falhe)
    if "log_df" in st.session_state and isinstance(st.session_state.log_df, pd.DataFrame):
        df = st.session_state.log_df.copy()
    elif os.path.exists(LOG_FILE):
        try:
            df = pd.read_csv(LOG_FILE, sep=",", encoding="utf-8")
        except Exception:
            df = pd.DataFrame(columns=LOG_COLS)
    else:
        df = pd.DataFrame(columns=LOG_COLS)

    # normaliza colunas
    for c in LOG_COLS:
        if c not in df.columns:
            df[c] = np.nan
    df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
    df["ts"]   = pd.to_datetime(df["ts"], errors="coerce")
    return df[LOG_COLS].copy()

def _save_log(df: pd.DataFrame):
    # guarda em sessão sempre
    st.session_state.log_df = df.copy()
    try:
        out = df.copy()
        out["data"] = pd.to_datetime(out["data"], errors="coerce").dt.strftime("%Y-%m-%d")
        out["ts"]   = pd.to_datetime(out["ts"],   errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        out.to_csv(LOG_FILE, index=False, encoding="utf-8")
        return True
    except Exception as e:
        # sem crash — apenas avisa
        st.sidebar.warning(f"Não foi possível salvar no arquivo (mantido em memória). Detalhe: {e}")
        return False

# =============== Sidebar (controles) ===============
show_marquee = st.sidebar.checkbox("Mostrar faixa de índices no topo", value=True)
interval = st.sidebar.selectbox("Intervalo", ["1d", "1h", "1wk"], index=0)

st.sidebar.markdown("### Criptos")
if "assets_on" not in st.session_state:
    st.session_state.assets_on = {"BTC-USD": True, "ETH-USD": True, "SOL-USD": True}
for sym in ["BTC-USD", "ETH-USD", "SOL-USD"]:
    st.session_state.assets_on[sym] = st.sidebar.checkbox(sym, value=st.session_state.assets_on[sym])

today = dt.date.today()
default_since = today - dt.timedelta(days=365)

st.sidebar.markdown("**Datas de entrada (Criptos)**")
date_since_crypto = {}
if st.session_state.assets_on.get("BTC-USD", False):
    date_since_crypto["BTC-USD"] = st.sidebar.date_input("BTC desde", value=default_since, max_value=today, key="btc_since")
if st.session_state.assets_on.get("ETH-USD", False):
    date_since_crypto["ETH-USD"] = st.sidebar.date_input("ETH desde", value=default_since, max_value=today, key="eth_since")
if st.session_state.assets_on.get("SOL-USD", False):
    date_since_crypto["SOL-USD"] = st.sidebar.date_input("SOL desde", value=default_since, max_value=today, key="sol_since")

st.sidebar.markdown("---")
st.sidebar.markdown("### Ativa (IBOV)")
since_ibov = st.sidebar.date_input("IBOV desde", value=default_since, max_value=today, key="ibov_since")

st.sidebar.markdown("---")
st.sidebar.markdown("### Carteira (Ativa)")
auto_pct = st.sidebar.checkbox("Calcular proporção automaticamente pelos valores", value=True)

valor_vcs_str = st.sidebar.text_input("Valor VCS (R$)", value="0,00", help="Ex.: 50.000,50")
valor_whs_str = st.sidebar.text_input("Valor WHS (R$)", value="0,00", help="Ex.: 1.000,00")
valor_vcs = parse_brl_text(valor_vcs_str)
valor_whs = parse_brl_text(valor_whs_str)
valor_total = float(valor_vcs) + float(valor_whs)

if auto_pct:
    vcs_pct = round((valor_vcs / valor_total) * 100.0, 2) if valor_total > 0 else 0.0
    whs_pct = round(100.0 - vcs_pct, 2)
    st.sidebar.markdown(f"**VCS (%)**: {vcs_pct:.2f}%  \n**WHS (%)**: {whs_pct:.2f}%")
else:
    vcs_pct = st.sidebar.number_input("Proporção VCS (%)", min_value=0.0, max_value=100.0, value=18.91, step=0.01)
    whs_pct = round(100.0 - float(vcs_pct), 2)
    st.sidebar.markdown(f"**WHS (%)**: {whs_pct:.2f}%")

# ---- Log (salvar/selecionar) ----
st.sidebar.markdown("#### Registro da carteira")
log_date = st.sidebar.date_input("Data do registro", value=today, max_value=today, key="carteira_data")
log_desc = st.sidebar.text_input("Descrição/nota (opcional)", value="")

if st.sidebar.button("💾 Salvar registro", use_container_width=True):
    try:
        df_log = _load_log()
        new_row = {
            "data": log_date,
            "vcs_valor": round(float(valor_vcs), 2),
            "whs_valor": round(float(valor_whs), 2),
            "vcs_pct": round(float(vcs_pct), 2),
            "whs_pct": round(float(whs_pct), 2),
            "auto": bool(auto_pct),
            "descricao": log_desc,
            "ts": dt.datetime.now(),
        }
        df_log = pd.concat([df_log, pd.DataFrame([new_row])], ignore_index=True)
        _save_log(df_log)
        st.sidebar.success("Registro salvo!")
    except Exception as e:
        st.sidebar.error(f"Falha ao salvar registro (mas o app segue): {e}")

df_log = _load_log()
if not df_log.empty:
    df_log = df_log.sort_values(["data", "ts"], ascending=[False, False]).reset_index(drop=True)
    def _fmt_row(i):
        r = df_log.iloc[i]
        tot = (float(r.get("vcs_valor", 0)) + float(r.get("whs_valor", 0)))
        dstr = fmt_br(r["data"])
        desc = str(r["descricao"]) if isinstance(r["descricao"], str) else ""
        return f"{dstr} — VCS {float(r['vcs_pct']):.2f}% | Total {brl(tot)}" + (f" — {desc}" if desc else "")
    sel_idx = st.sidebar.selectbox("Selecionar registro salvo", list(range(len(df_log))), index=0, format_func=_fmt_row)
    use_saved = st.sidebar.checkbox("Usar registro salvo no gráfico", value=False)
else:
    sel_idx = None
    use_saved = False
    st.sidebar.info("Nenhum registro salvo ainda.")

# =============== Topo ===============
if show_marquee:
    st.markdown(build_marquee_html(), unsafe_allow_html=True)

# =============== Carregamento de séries ===============
end = dt.date.today()

# Criptos
assets = {}
for sym in ["BTC-USD", "ETH-USD", "SOL-USD"]:
    if st.session_state.assets_on.get(sym, False) and sym in date_since_crypto:
        start = date_since_crypto[sym]
        try:
            s = fetch_series_resilient(sym, start, end, interval)
            note = None
            if s.empty:
                s, note = preserve_last_when_empty(sym, end)
            assets[sym] = (s, start, note)
        except Exception as e:
            # não travar a página
            st.warning(f"Falha ao carregar {sym}: {e}")

# IBOV (com fallbacks)
ibov_used = None
ibov_note = None
ibov = pd.Series(dtype="float64")
for candidate in ["^BVSP", "^IBOV", "BOVA11.SA"]:
    try:
        s_try = fetch_series_resilient(candidate, since_ibov, end, interval)
        note_try = None
        if s_try.empty:
            s_try, note_try = preserve_last_when_empty(candidate, end)
        if not s_try.empty:
            ibov = s_try
            ibov_used = candidate
            ibov_note = note_try
            break
    except Exception as e:
        continue
if ibov_used and ibov_used != "^BVSP":
    extra = "IBOV (alt)" if ibov_used == "^IBOV" else "BOVA11 (proxy)"
    ibov_note = (ibov_note + " • " if ibov_note else "") + f"Fonte: {extra}"

# =============== UI principal ===============
st.title("Painel Financeiro | JVSeps")

br_btc = fmt_br(date_since_crypto.get("BTC-USD")) if "BTC-USD" in date_since_crypto else "—"
br_eth = fmt_br(date_since_crypto.get("ETH-USD")) if "ETH-USD" in date_since_crypto else "—"
br_sol = fmt_br(date_since_crypto.get("SOL-USD")) if "SOL-USD" in date_since_crypto else "—"
br_ibv = fmt_br(since_ibov)
src_note = f" • Ticker IBOV usado: {ibov_used}" if ibov_used else ""
st.caption(
    f"Intervalo: {interval} • "
    f"Criptos: BTC {br_btc} | ETH {br_eth} | SOL {br_sol} • "
    f"Ativa: IBOV {br_ibv}{src_note}"
)

tab_criptos, tab_ativa = st.tabs(["📈 Criptos", "📊 Ativa"])

# ----- Criptos -----
with tab_criptos:
    try:
        if not assets:
            st.info("Nenhuma cripto selecionada ou sem dados para o período.")
        else:
            cards = []
            for sym in ["BTC-USD", "ETH-USD", "SOL-USD"]:
                if sym in assets:
                    s, sdate, note = assets[sym]
                    cards.append((sym, s, "USD", sdate, note))
            for i in range(0, len(cards), 4):
                cols = st.columns(4, gap="small")
                for c in range(4):
                    if i + c >= len(cards): break
                    sym, serie, ylab, sdate, note = cards[i + c]
                    with cols[c]:
                        mini_card(sym, serie, y_label=ylab, start_date=sdate, note=note)
    except Exception as e:
        st.error(f"Erro ao renderizar Criptos: {e}")

# ----- Ativa (Carteira + IBOV) -----
with tab_ativa:
    try:
        # usa valores atuais, ou o registro salvo (se marcado)
        use_vals = {
            "vcs_pct": float(vcs_pct), "whs_pct": float(100.0 - float(vcs_pct)),
            "vcs_valor": float(valor_vcs), "whs_valor": float(valor_whs),
            "origem": "atual"
        }
        registro_info = ""
        if use_saved and sel_idx is not None and not _load_log().empty:
            r = _load_log().iloc[int(sel_idx)]
            use_vals = {
                "vcs_pct": float(r["vcs_pct"] or 0.0),
                "whs_pct": float(r["whs_pct"] or 0.0),
                "vcs_valor": float(r["vcs_valor"] or 0.0),
                "whs_valor": float(r["whs_valor"] or 0.0),
                "origem": "registro"
            }
            registro_info = f"Usando registro de {fmt_br(r['data'])}" + (f" — {r['descricao']}" if isinstance(r['descricao'], str) and r['descricao'] else "")

        st.markdown("### 💼 Carteira (Ativa)")
        if registro_info:
            st.caption(registro_info)

        # normaliza soma 100
        total_pct = use_vals["vcs_pct"] + use_vals["whs_pct"]
        if total_pct > 0 and abs(total_pct - 100.0) > 0.01:
            p = use_vals["vcs_pct"] * 100.0 / total_pct
            use_vals["vcs_pct"] = round(p, 2)
            use_vals["whs_pct"] = round(100.0 - p, 2)

        col_left, col_right = st.columns([1, 1], gap="small")

        with col_left:
            mini_prop_card({"VCS": use_vals["vcs_pct"], "WHS": use_vals["whs_pct"]},
                           title="Proporção de Ativos (VCS/WHS)")

        with col_right:
            with _container_border():
                st.markdown("#### Valores da Carteira")
                c1, c2 = st.columns(2, gap="small")
                tot = float(use_vals["vcs_valor"]) + float(use_vals["whs_valor"])
                with c1:
                    st.metric("VCS", brl(use_vals["vcs_valor"]))
                    st.metric("WHS", brl(use_vals["whs_valor"]))
                with c2:
                    st.metric("Total", brl(tot))
                    st.metric("VCS (%)", f"{use_vals['vcs_pct']:.2f}%")

        st.markdown("---")

        # IBOV
        if ibov.empty:
            st.info("Sem dados do IBOV/Proxy para o período.")
        else:
            mini_card("Índice Bovespa", ibov, y_label="Pts", start_date=since_ibov, note=ibov_note)

    except Exception as e:
        st.error(f"Erro ao renderizar a aba Ativa: {e}")
