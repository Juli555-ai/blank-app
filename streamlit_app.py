import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timezone

st.set_page_config(page_title='Crypto Pilot 2.0', page_icon='🚀', layout='wide')
st.title('🚀 Crypto Pilot 2.0')
st.caption('Binance Spot-Marktdaten · Analyse · KI-Chat · Paper-Trading')
st.warning('Nur Lern- und Simulationszwecke. Kein echtes Trading. Futures-Kurse und Liquidationen werden nicht exakt modelliert.')

API = 'https://data-api.binance.vision/api/v3/klines'
COINS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT']

@st.cache_data(ttl=60, show_spinner=False)
def market_data(symbol, interval):
    resp = requests.get(API, params={'symbol': symbol, 'interval': interval, 'limit': 250}, timeout=15)
    resp.raise_for_status()
    values = resp.json()
    if not isinstance(values, list) or len(values) < 60:
        raise ValueError('Keine ausreichenden Marktdaten')
    d = pd.DataFrame(values)
    return pd.DataFrame({'time': pd.to_datetime(d[0], unit='ms', utc=True),
                         'close': pd.to_numeric(d[4]), 'high': pd.to_numeric(d[2]),
                         'low': pd.to_numeric(d[3]), 'volume': pd.to_numeric(d[5])})

def indicators(df):
    d = df.copy()
    d['EMA20'] = d.close.ewm(span=20, adjust=False).mean()
    d['EMA50'] = d.close.ewm(span=50, adjust=False).mean()
    delta = d.close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, float('nan'))
    d['RSI'] = (100 - 100/(1+rs)).fillna(100)
    ema12 = d.close.ewm(span=12, adjust=False).mean()
    ema26 = d.close.ewm(span=26, adjust=False).mean()
    d['MACD'] = ema12 - ema26
    d['MACD_signal'] = d.MACD.ewm(span=9, adjust=False).mean()
    true_range = pd.concat([(d.high-d.low), (d.high-d.close.shift()).abs(),
                            (d.low-d.close.shift()).abs()], axis=1).max(axis=1)
    d['ATR'] = true_range.ewm(alpha=1/14, adjust=False).mean()
    d['volume_avg'] = d.volume.rolling(20).mean()
    return d

def signal_for(row):
    bull = row.EMA20 > row.EMA50 and row.MACD > row.MACD_signal and 45 <= row.RSI < 70
    bear = row.EMA20 < row.EMA50 and row.MACD < row.MACD_signal and 30 < row.RSI <= 55
    return '🟢 Bullisches Setup' if bull else ('🔴 Bärisches Setup' if bear else '🟡 Kein klares Setup')

if 'cash' not in st.session_state:
    st.session_state.cash = 10000.0
if 'position' not in st.session_state:
    st.session_state.position = None
if 'trades' not in st.session_state:
    st.session_state.trades = []
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'auto' not in st.session_state:
    st.session_state.auto = False

with st.sidebar:
    st.header('⚙️ Einstellungen')
    coin = st.selectbox('Kryptowährung', COINS)
    interval = st.selectbox('Zeitrahmen', ['15m', '1h', '4h', '1d'], index=1)
    st.caption('Die Marktdaten stammen von der Binance Spot-API. Futures werden nur vereinfacht simuliert.')
    if st.button('🔄 Daten aktualisieren'):
        market_data.clear()
        st.rerun()

try:
    df = indicators(market_data(coin, interval))
except Exception as exc:
    st.error('Binance-Kurse konnten nicht geladen werden.')
    st.code(str(exc))
    st.stop()

r = df.iloc[-1]
price = float(r.close)
atr = float(r.ATR)
sig = signal_for(r)
volume_ratio = float(r.volume/r.volume_avg) if pd.notna(r.volume_avg) and r.volume_avg else 0.0

# Paper stop / target updates only when the app reruns. Not a background trading service.
p = st.session_state.position
if p and p['symbol'] == coin:
    pnl_raw = (price / p['entry'] - 1) * (1 if p['direction']=='Long' else -1)
    pnl = max(-p['margin'], p['margin'] * p['leverage'] * pnl_raw)
    stop_hit = (price <= p['stop'] if p['direction']=='Long' else price >= p['stop'])
    target_hit = (price >= p['target'] if p['direction']=='Long' else price <= p['target'])
    if stop_hit or target_hit:
        st.session_state.cash += max(0, p['margin'] + pnl)
        st.session_state.trades.append({'Zeit (UTC)': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),
            'Coin': coin, 'Richtung': p['direction'], 'Ergebnis USDT': round(pnl,2),
            'Grund': 'Stop-Loss (Prüfung)' if stop_hit else 'Take-Profit (Prüfung)'})
        st.session_state.position = None
        st.toast('Virtueller Trade beim Aktualisieren geschlossen.')

t1, t2, t3, t4 = st.tabs(['📊 Dashboard', '🎯 Signale', '💰 Paper-Trading', '🧠 KI-Chat'])
with t1:
    a,b,c = st.columns(3)
    a.metric(f'{coin} (USDT)', f'{price:,.2f}')
    b.metric('RSI (14)', f'{float(r.RSI):.1f}')
    c.metric('Volumen / Durchschnitt', f'{volume_ratio:.2f}×')
    st.subheader(sig)
    st.line_chart(df.set_index('time')[['close','EMA20','EMA50']])
    st.caption('Kurs und EMA 20/50. Intraday-Kurse können von Börsen-Ausführungen abweichen.')
    st.write(f'MACD: **{r.MACD:.2f}** · MACD-Signallinie: **{r.MACD_signal:.2f}** · ATR(14): **{atr:.2f}**')

with t2:
    st.subheader('🎯 Regelbasiertes Setup')
    st.write(sig)
    st.write('Diese Regeln kombinieren EMA20/50, MACD und RSI; sie sind keine Kursvorhersage.')
    if 'Bullisch' in sig:
        direction = 'Long'
    elif 'Bärisch' in sig:
        direction = 'Short'
    else:
        direction = None
    if direction:
        stop = price - 1.5*atr if direction=='Long' else price + 1.5*atr
        target = price + 3*atr if direction=='Long' else price - 3*atr
        st.write(f'**Beispielrichtung:** {direction}')
        st.write(f'**Möglicher Einstieg (aktueller Spot-Kurs):** {price:,.3f} USDT')
        st.write(f'**Beispiel-Stop-Loss (1,5 ATR):** {stop:,.3f} USDT')
        st.write(f'**Beispiel-Take-Profit (3 ATR):** {target:,.3f} USDT')
        st.write('**Rechnerisches Chance-Risiko-Verhältnis:** 2:1 vor Gebühren')
    else:
        st.info('Derzeit kein regelbasiertes Setup. Kein Trade ist ebenfalls eine Entscheidung.')
    st.caption('ATR-Distanzen sind Beispiele, keine garantierten Ausführungsniveaus.')

with t3:
    st.subheader('💰 Virtuelles Handelskonto')
    st.metric('Freies virtuelles Guthaben', f'{st.session_state.cash:,.2f} USDT')
    mode = st.selectbox('Simulationsart', ['Spot', 'Futures (vereinfacht)'])
    direction = st.selectbox('Richtung', ['Long'] if mode=='Spot' else ['Long','Short'])
    margin = st.number_input('Einsatz / Margin (USDT)', min_value=10.0, value=100.0, step=10.0)
    lev = st.slider('Hebel', 1, 3, 1) if mode != 'Spot' else 1
    stop_distance = max(0.001, 1.5*atr)
    tp_distance = max(0.002, 3*atr)
    suggested_stop = price-stop_distance if direction=='Long' else price+stop_distance
    suggested_target = price+tp_distance if direction=='Long' else price-tp_distance
    st.write(f'Beispiel SL **{suggested_stop:,.3f}** · TP **{suggested_target:,.3f}** USDT')
    p = st.session_state.position
    if p:
        st.info(f'Offene Position: {p["direction"]} {p["symbol"]} bei {p["entry"]:,.3f} USDT')
        if p['symbol'] == coin:
            result = max(-p['margin'], p['margin']*p['leverage']*(price/p['entry']-1)*(1 if p['direction']=='Long' else -1))
            st.metric('Unrealisierter P/L (vereinfachter Wert)', f'{result:+.2f} USDT')
            if st.button('Position zum aktuellen Spot-Kurs schliessen'):
                st.session_state.cash += max(0, p['margin']+result)
                st.session_state.trades.append({'Zeit (UTC)': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'), 'Coin':coin,
                    'Richtung':p['direction'],'Ergebnis USDT':round(result,2),'Grund':'Manuell'})
                st.session_state.position=None
                st.rerun()
        else:
            st.info(f'Wähle {p["symbol"]}, um diese Position zu bewerten oder zu schliessen.')
    else:
        if st.button('Virtuellen Trade eröffnen', type='primary'):
            if margin > st.session_state.cash:
                st.error('Zu wenig virtuelles Guthaben.')
            elif suggested_stop <= 0:
                st.error('Ungültiger Stop-Loss.')
            else:
                st.session_state.cash -= margin
                st.session_state.position = {'symbol':coin,'direction':direction,'mode':mode,
                    'entry':price,'margin':margin,'leverage':lev,
                    'stop':suggested_stop,'target':suggested_target}
                st.rerun()
    st.divider()
    st.subheader('🤖 Regelbasiertes Paper-Auto-Trading')
    st.caption('Nur beim Tippen auf „Einmal prüfen“ wird ein virtueller Trade erwogen. Keine Hintergrundüberwachung.')
    if st.button('Strategie jetzt einmal prüfen'):
        if st.session_state.position:
            st.info('Bereits eine Position offen.')
        elif 'Bullisch' in sig or 'Bärisch' in sig:
            auto_dir = 'Long' if 'Bullisch' in sig else 'Short'
            if auto_dir == 'Short':
                st.info('Short-Setup erkannt, aber Spot erlaubt nur Long. Nutze Futures-Simulation manuell.')
            else:
                auto_margin = min(100., st.session_state.cash)
                if auto_margin >= 10 and price-1.5*atr > 0:
                    st.session_state.cash -= auto_margin
                    st.session_state.position={'symbol':coin,'direction':'Long','mode':'Spot',
                        'entry':price,'margin':auto_margin,'leverage':1,
                        'stop':price-1.5*atr,'target':price+3*atr}
                    st.rerun()
                else:
                    st.info('Nicht genügend Guthaben oder Stop-Loss ungültig.')
        else:
            st.info('Kein Setup – es wurde kein Trade eröffnet.')
    if st.session_state.trades:
        st.dataframe(pd.DataFrame(st.session_state.trades), hide_index=True, use_container_width=True)
    if st.button('Paper-Konto zurücksetzen'):
        st.session_state.cash=10000.0
        st.session_state.position=None
        st.session_state.trades=[]
        st.rerun()
    st.caption('Kein persistentes Konto. Zustand kann bei neuer Sitzung verloren gehen. Keine Gebühren, Slippage, Funding oder vollständige Futures-Liquidation.')

with t4:
    st.subheader('🧠 KI-Trading-Chat')
    st.write('Mit einem Groq-API-Schlüssel antwortet ein Sprachmodell. Ohne Schlüssel funktioniert ein einfacher Info-Chat.')
    try:
        api_key = st.secrets.get('GROQ_API_KEY', '')
    except (FileNotFoundError, KeyError):
        api_key = ''
    if not api_key:
        st.info('Für echte KI: kostenlosen Groq-API-Schlüssel erstellen und in Streamlit → App settings → Secrets als GROQ_API_KEY speichern. Kosten und Limits beim Anbieter prüfen.')
    for m in st.session_state.messages[-12:]:
        with st.chat_message(m['role']):
            st.write(m['content'])
    question = st.chat_input('Frag z. B.: Was bedeutet das aktuelle Signal?')
    if question:
        st.session_state.messages.append({'role':'user','content':question})
        with st.chat_message('user'):
            st.write(question)
        context = (f'Coin {coin}, Spotpreis {price:.3f} USDT, Zeitrahmen {interval}, RSI {r.RSI:.1f}, '
                   f'EMA20 {r.EMA20:.3f}, EMA50 {r.EMA50:.3f}, MACD {r.MACD:.3f}, '
                   f'MACD Signal {r.MACD_signal:.3f}, Volumenverhältnis {volume_ratio:.2f}, Setup {sig}.')
        if api_key:
            try:
                messages = [{'role':'system','content':
                    'Du bist Crypto Pilot, ein vorsichtiger deutschsprachiger Trading-Lernassistent. '
                    'Erkläre die Daten, Unsicherheit, Kosten und Verlustrisiken. Keine Gewinnversprechen. '
                    'Keine Behauptung über aktuelle Nachrichten oder echte Futures-Marktdaten. '+context}]
                messages += st.session_state.messages[-10:]
                resp = requests.post('https://api.groq.com/openai/v1/chat/completions',
                    headers={'Authorization':f'Bearer {api_key}','Content-Type':'application/json'},
                    json={'model':'llama-3.1-8b-instant','messages':messages,'temperature':0.3,
                          'max_completion_tokens':450}, timeout=35)
                resp.raise_for_status()
                answer = resp.json()['choices'][0]['message']['content']
            except Exception as exc:
                answer = 'KI-Dienst derzeit nicht verfügbar. Prüfe API-Schlüssel, Kontingent und App-Logs. '+str(exc)[:160]
        else:
            answer = (f'Aktuelle technische Daten: {context} '
                      'Ein RSI über 70 kann auf Überkauftheit hinweisen, unter 30 auf Überverkauftheit. '
                      'EMA/MACD-Signale sind keine sicheren Vorhersagen. Für freie Fragen den KI-Schlüssel einrichten.')
        st.session_state.messages.append({'role':'assistant','content':answer})
        with st.chat_message('assistant'):
            st.write(answer)
