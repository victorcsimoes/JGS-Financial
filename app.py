# app.py — Painel Financeiro | JVSeps (fix: proporção auto pelos valores + Ativa robusta)
import datetime as dt
import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.graph_objects as go
import re

st.set_page_config(page_title="Painel Financeiro | JVSeps", layout="wide")

# -------------------- Util: rerun compat --------------------
def do_rerun():
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

# ===================== LOGIN SIMPLES =====================
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

# ===================== FAIXA DE ÍNDICES =====================
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
            val = f"{last:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
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

# ===================== HELPERS =====================
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

def _extract_close(df: pd.DataFrame) -> pd.Series:
    if df is None or df.empty:
        return pd.Series(dtype=float)
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
    # 3) fallback '1d'
    if interval != "1d":
        try:
            t = yf.Ticker(ticker)
            df = t.history(start=start_date, end=end_date + dt.timedelta(days=1), interval="1d", auto_adjust=True)
            s = _extract_close(df); s = _make_index_naive(s)
            s = s[(s.index >= pd.to_datetime(start_date)) & (s.index <= pd.to_datetime(end_date))]
            if not s.empty:
                return s
        except Exception:
            pass
        try:
            df = yf.download(
                tickers=ticker, start=start_date, end=end_date + dt.timedelta(days=1),
                interval="1d", auto_adjust=True, progress=False, threads=False,
            )
            s = _extract_close(df); s = _make_index_naive(s)
            s = s[(s.index >= pd.to_datetime(start_date)) & (s.index <= pd.to_datetime(end_date))]
            if not s.empty:
                return s
        except Exception:
            pass
    return pd.Series(dtype=float)

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
        return pd.Series(dtype=float), "Sem dados históricos."

def pct_change(s: pd.Series):
    if s.size < 2: return np.nan
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

# ===================== Sidebar (controles) =====================
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

# Campos LIVRES de moeda (texto)
valor_vcs_str = st.sidebar.text_input("Valor VCS (R$)", value="0,00", help="Ex.: 50.000,50")
valor_whs_str = st.sidebar.text_input("Valor WHS (R$)", value="0,00", help="Ex.: 1.000,00")

valor_vcs = parse_brl_text(valor_vcs_str)
valor_whs = parse_brl_text(valor_whs_str)
valor_total = float(valor_vcs) + float(valor_whs)

# ---- cálculo da proporção (auto ou manual) ----
if auto_pct:
    if valor_total > 0:
        vcs_pct = round((valor_vcs / valor_total) * 100.0, 2)
    else:
        vcs_pct = 0.0
    whs_pct = round(100.0 - vcs_pct, 2)
    st.sidebar.markdown(f"**VCS (%)**: {vcs_pct:.2f}%  \n**WHS (%)**: {whs_pct:.2f}%")
else:
    vcs_pct = st.sidebar.number_input("Proporção VCS (%)", min_value=0.0, max_value=100.0, value=18.91, step=0.01)
    whs_pct = round(100.0 - float(vcs_pct), 2)
    st.sidebar.markdown(f"**WHS (%)**: {whs_pct:.2f}%")

# ===================== TOPO =====================
if show_marquee:
    st.markdown(build_marquee_html(), unsafe_allow_html=True)

# ===================== Carregamento (sempre) =====================
end = dt.date.today()

# ---- Criptos ----
assets = {}
for sym in ["BTC-USD", "ETH-USD", "SOL-USD"]:
    if st.session_state.assets_on.get(sym, False) and sym in date_since_crypto:
        start = date_since_crypto[sym]
        s = fetch_series_resilient(sym, start, end, interval)
        note = None
        if s.empty:
            s, note = preserve_last_when_empty(sym, end)
        assets[sym] = (s, start, note)

# ---- IBOV (tenta ^BVSP -> ^IBOV -> BOVA11.SA) ----
ibov_used = None
ibov_note = None
ibov = pd.Series(dtype=float)
for candidate in ["^BVSP", "^IBOV", "BOVA11.SA"]:
    s_try = fetch_series_resilient(candidate, since_ibov, end, interval)
    note_try = None
    if s_try.empty:
        s_try, note_try = preserve_last_when_empty(candidate, end)
    if not s_try.empty:
        ibov = s_try
        ibov_used = candidate
        ibov_note = note_try
        break
if ibov_used and ibov_used != "^BVSP":
    extra = "IBOV (alt)" if ibov_used == "^IBOV" else "BOVA11 (proxy)"
    ibov_note = (ibov_note + " • " if ibov_note else "") + f"Fonte: {extra}"

# ===================== UI =====================
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

# --------- Aba: Criptos ---------
with tab_criptos:
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

# --------- Aba: Ativa (Carteira + IBOV) ---------
with tab_ativa:
    try:
        st.markdown("### 💼 Carteira (Ativa)")
        col_left, col_right = st.columns([1, 1], gap="small")

        # normaliza e garante soma 100
        vcs_pct = float(np.clip(vcs_pct, 0.0, 100.0))
        whs_pct = float(np.clip(100.0 - vcs_pct, 0.0, 100.0))
        total_pct = vcs_pct + whs_pct
        if total_pct > 0 and abs(total_pct - 100.0) > 0.01:
            vcs_pct = round(vcs_pct * 100.0 / total_pct, 2)
            whs_pct = round(100.0 - vcs_pct, 2)

        with col_left:
            proporcoes = {"VCS": vcs_pct, "WHS": whs_pct}
            mini_prop_card(proporcoes, title="Proporção de Ativos (VCS/WHS)")

        with col_right:
            with _container_border():
                st.markdown("#### Valores da Carteira")
                c1, c2 = st.columns(2, gap="small")
                with c1:
                    st.metric("VCS", brl(valor_vcs))
                    st.metric("WHS", brl(valor_whs))
                with c2:
                    st.metric("Total", brl(valor_total))
                    st.metric("VCS (%)", f"{vcs_pct:.2f}%")

        st.markdown("---")

        if ibov.empty:
            st.info("Sem dados do IBOV/Proxy para o período.")
        else:
            mini_card("Índice Bovespa", ibov, y_label="Pts", start_date=since_ibov, note=ibov_note)
    except Exception as e:
        st.error(f"Erro ao renderizar a aba Ativa: {e}")

# fim
