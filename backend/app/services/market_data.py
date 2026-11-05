"""Cached Yahoo snapshots with bounded background refresh and deterministic offline data."""
import hashlib
import math
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta, datetime, timezone
from fastapi import HTTPException
from ..config import MARKET_MODE
UNIVERSE = [
 ('RELIANCE.NS','Reliance Industries','Energy',1482,24.6),
 ('TCS.NS','Tata Consultancy Services','Technology',3860,29.1),
 ('INFY.NS','Infosys','Technology',1825,26.2),
 ('HDFCBANK.NS','HDFC Bank','Financial Services',1740,19.5),
 ('ICICIBANK.NS','ICICI Bank','Financial Services',1280,20.3),
 ('ITC.NS','ITC Limited','Consumer',465,28.4),
 ('BHARTIARTL.NS','Bharti Airtel','Telecommunications',1680,65.2),
 ('LT.NS','Larsen & Toubro','Industrials',3520,32.1),
 ('TATASTEEL.NS','Tata Steel','Materials',156,22.8),
 ('SBIN.NS','State Bank of India','Financial Services',810,10.2),
 ('MARUTI.NS','Maruti Suzuki','Consumer',12450,27.8),
 ('SUNPHARMA.NS','Sun Pharmaceutical','Healthcare',1780,34.2),
 ('TITAN.NS','Titan Company','Consumer',3420,78.5)]
CATALOG = {r[0]: r for r in UNIVERSE}
_cache = {}
_pending = set()
_retry = {}
_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=3)
def normalize(symbol):
    symbol = symbol.upper().strip()
    if not symbol.endswith('.NS'): symbol += '.NS'
    if symbol not in CATALOG: raise HTTPException(404, 'Stock is not in the supported local universe')
    return symbol

def demo(symbol):
    symbol = normalize(symbol)
    _, name, sector, price, pe = CATALOG[symbol]
    seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8],16)
    rng = random.Random(seed)
    prices = [price * 0.86]
    for i in range(260): prices.append(prices[-1] * (1 + rng.gauss(.0005,.012)))
    prices = [v * price / prices[-1] for v in prices]
    days = []
    d = date.today()
    while len(days) < len(prices):
        if d.weekday() < 5: days.append(d)
        d -= timedelta(days=1)
    history = [{'date':str(d),'value':v} for d,v in zip(reversed(days),prices)]
    previous = prices[-2]
    return dict(symbol=symbol, company_name=name, sector=sector, price=price,
        previous_close=previous, change=price-previous, change_percent=(price/previous-1)*100,
        open=previous*1.002, day_high=max(price,previous)*1.008, day_low=min(price,previous)*.994,
        high_52w=max(prices)*1.02, low_52w=min(prices)*.98, pe=pe,
        market_cap=price*2_500_000_000, dividend_yield=1.4, volume=2_450_000+seed%1000000,
        source='demo', as_of='Synthetic educational snapshot', updated_at=datetime.now(timezone.utc).isoformat(), is_stale=False, history=history)

def refresh(symbol):
    try:
        import yfinance as yf
        frame = yf.Ticker(symbol).history(period='1y', auto_adjust=True, timeout=5)
        if len(frame) < 50: return
        hist = [{'date':str(i.date()), 'value':float(r['Close'])} for i,r in frame.iterrows()]
        if not all(math.isfinite(p['value']) and p['value'] > 0 for p in hist): return
        row = frame.iloc[-1]; previous = hist[-2]['value']; price=hist[-1]['value']
        data = demo(symbol)
        data.update(price=price, previous_close=previous, change=price-previous,
            change_percent=(price/previous-1)*100, open=float(row['Open']), day_high=float(row['High']),
            day_low=float(row['Low']), high_52w=float(frame['High'].max()), low_52w=float(frame['Low'].min()),
            volume=int(row['Volume']), pe=None, market_cap=None, dividend_yield=None,
            history=hist, source='yahoo', as_of=hist[-1]['date'], updated_at=datetime.now(timezone.utc).isoformat(), is_stale=False)
        with _lock: _cache[symbol] = (time.monotonic(),data)
    except Exception:
        pass
    finally:
        with _lock:
            _pending.discard(symbol)
            _retry[symbol]=time.monotonic()+300

def quote(symbol):
    symbol=normalize(symbol)
    with _lock:
        cached=_cache.get(symbol)
        if MARKET_MODE != 'demo' and (not cached or time.monotonic()-cached[0]>300) and symbol not in _pending and time.monotonic()>_retry.get(symbol,0):
            _pending.add(symbol); _pool.submit(refresh,symbol)
    if cached:
        data=dict(cached[1]); data['is_stale']=time.monotonic()-cached[0]>300
        return data
    return demo(symbol)

def history(symbol, period='1m'):
    q=quote(symbol)
    if period=='1d':
        # Daily provider cannot supply intraday bars; explicitly return the two closes.
        points=q['history'][-2:]
    else: points=q['history'][-{'1w':5,'1m':22,'3m':66,'1y':261}.get(period,22):]
    return dict(points=points,source=q['source'],as_of=q['as_of'],interval='daily',note='1D compares the previous and latest daily close.' if period=='1d' else '')
