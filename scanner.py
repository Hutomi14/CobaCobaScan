import yfinance as yf
import pandas as pd
import numpy as np
import os
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 1. KONFIGURASI & BOT SETTINGS
# ==========================================
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    if TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": f"<pre>{message}</pre>", "parse_mode": "HTML"}
        requests.post(url, json=payload)

# ==========================================
# 2. MASTER TICKERS (Cleaned)
# ==========================================
def get_tickers():
    # Daftar saham likuid & potensial (Bisa ditambah hingga 800+)
    return [
        'ADRO.JK', 'ANTM.JK', 'ASII.JK', 'BBCA.JK', 'BBNI.JK', 'BBRI.JK', 'BBTN.JK', 
        'BMRI.JK', 'BRIS.JK', 'BRMS.JK', 'BREN.JK', 'CPIN.JK', 'GOTO.JK', 'INKP.JK', 
        'ITMG.JK', 'KLBF.JK', 'MDKA.JK', 'MEDC.JK', 'PGAS.JK', 'PTBA.JK', 'TINS.JK', 
        'TLKM.JK', 'UNTR.JK', 'UNVR.JK', 'PSAB.JK', 'SGER.JK', 'ACES.JK', 'AMMN.JK'
        # Tambahkan ticker lainnya di sini...
    ]

# ==========================================
# 3. CORE ANALYSIS LOGIC (VCP + PROBABILITY)
# ==========================================
def analyze_stock(ticker, df):
    try:
        if len(df) < 40: return None
        
        # Kalkulasi Data Dasar
        last_close = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        vol_ma20 = df['Volume'].rolling(20).mean().iloc[-1]
        last_vol = df['Volume'].iloc[-1]
        
        # A. FILTER LIKUIDITAS Dasar
        if last_close < 100 or last_vol < 100000: return None

        # B. LOGIKA VCP (Tightness Kontraksi)
        # Mengukur rentang High-Low 5 hari terakhir (VCP Tightness)
        recent_range = (df['High'].rolling(5).max() - df['Low'].rolling(5).min()) / df['Close'].rolling(5).mean()
        tightness = recent_range.iloc[-1]

        # C. PROBABILITY SELL PAGI (Gap Up History)
        # Menghitung % frekuensi Open > Prev Close dalam 30 hari terakhir
        df['Gap_Up'] = df['Open'] > df['Close'].shift(1)
        prob_gap = (df['Gap_Up'].tail(30).sum() / 30) * 100

        # D. ENTRY CONFIDENCE (Skor Akumulasi)
        # Poin diberikan jika Harga naik & Volume meledak
        entry_score = 0
        if last_close > prev_close: entry_score += 40
        if last_vol > vol_ma20: entry_score += 30
        if last_vol > vol_ma20 * 2: entry_score += 30 # Bonus volume masif
        
        # E. SELEKSI KETAT (VCP Standard)
        # Tightness < 6% dianggap area konsolidasi matang
        if tightness < 0.06 and entry_score >= 70:
            return {
                "Ticker": ticker.replace(".JK", ""),
                "Price": int(last_close),
                "Tight": f"{round(tightness*100,1)}%",
                "Entry": f"{entry_score}%",
                "GP_Prob": f"{round(prob_gap,0)}%",
                "Status": "VCP_READY" if tightness < 0.04 else "ACCUM"
            }
    except:
        return None

# ==========================================
# 4. EXECUTION ENGINE (FAST SCAN)
# ==========================================
def main():
    tickers = get_tickers()
    print(f"Memulai Scan {len(tickers)} saham...")
    
    # Download Massal (Optimasi Waktu)
    data = yf.download(tickers, period="3mo", interval="1d", group_by='ticker', progress=False)
    
    final_results = []
    # Multithreading (20 Jalur sekaligus)
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(analyze_stock, t, data[t]) for t in tickers if t in data]
        for f in futures:
            res = f.result()
            if res: final_results.append(res)
            
    # Reporting
    if final_results:
        df_final = pd.DataFrame(final_results).sort_values(by="Entry", ascending=False)
        report = f"🚀 BSJP SCANNER (VCP + ACCUM)\n"
        report += f"📅 {datetime.now().strftime('%d %b %Y | %H:%M')}\n\n"
        report += df_final.to_string(index=False)
        
        print(report)
        send_telegram(report)
    else:
        msg = "Tidak ada saham yang memenuhi kriteria VCP sore ini."
        print(msg)
        send_telegram(msg)

if __name__ == "__main__":
    main()
