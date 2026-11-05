import os
os.environ['MARKET_MODE']='demo'
os.environ['GEMINI_API_KEY']=''
os.environ['GROQ_API_KEY']=''
import pytest
from decimal import Decimal
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from app.seed import seed
from app.models import Holding, WatchlistItem, Transaction, Metadata, User
from app.auth import hash_password

@pytest.fixture
def client(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'test.db'),connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    Session=sessionmaker(bind=engine)
    with Session() as db:
        user=User(name='Demo Investor',email='demo@aquavest.local',password_hash=hash_password('AquaVestDemo2026!'),cash_balance=1000000)
        db.add(user);db.commit();db.refresh(user);seed(db,user)
    def override():
        with Session() as db: yield db
    import app.main as main_module
    monkeypatch.setattr(main_module,"engine",engine)
    monkeypatch.setattr(main_module,"SessionLocal",Session)
    monkeypatch.setattr(main_module,"migrate_legacy_database",lambda:None)
    app.dependency_overrides[get_db]=override
    # No lifespan needed: this fixture creates and seeds its isolated database.
    with TestClient(app,raise_server_exceptions=True) as c:
        c.post('/api/auth/login',json={'email':'demo@aquavest.local','password':'AquaVestDemo2026!'})
        yield c,Session
    app.dependency_overrides.clear()
    engine.dispose()

def test_health(client):
    c,_=client
    assert c.get('/api/health').json()=={'status':'healthy','app':'AquaVest AI'}

def test_summary_and_allocation(client):
    c,_=client
    rows=c.get('/api/portfolio').json();s=c.get('/api/portfolio/summary').json()
    assert len(rows)==8
    assert s['current_value']==pytest.approx(sum(h['quantity']*h['current_price'] for h in rows))
    assert s['pnl']==pytest.approx(s['current_value']-s['investment'])
    assert sum(a['percent'] for a in s['stock_allocation'])==pytest.approx(100)
    assert c.get('/api/portfolio/history').json()['points'][-1]['value']==pytest.approx(s['current_value'])

def test_buy_sell_accounting(client):
    c,_=client
    before=next(h for h in c.get('/api/portfolio').json() if h['symbol']=='TCS.NS')
    payload={'symbol':'TCS.NS','quantity':'5','price':'4000','transaction_type':'BUY'}
    assert c.post('/api/transactions',json=payload).status_code==201
    h=next(h for h in c.get('/api/portfolio').json() if h['symbol']=='TCS.NS')
    expected=(before['quantity']*before['average_price']+20000)/(before['quantity']+5)
    assert h['average_price']==pytest.approx(expected)
    payload.update(transaction_type='SELL',quantity='2',price='4200')
    t=c.post('/api/transactions',json=payload)
    assert t.status_code==201
    assert float(t.json()['realized_pnl'])==pytest.approx((4200-expected)*2)
    after=next(h for h in c.get('/api/portfolio').json() if h['symbol']=='TCS.NS')
    assert after['average_price']==pytest.approx(expected)
    assert after['quantity']==h['quantity']-2

def test_reject_oversell_and_invalid(client):
    c,_=client
    count=len(c.get('/api/transactions').json())
    assert c.post('/api/transactions',json={'symbol':'TCS','transaction_type':'SELL','quantity':999999,'price':100}).status_code==400
    assert c.post('/api/transactions',json={'symbol':'TCS','transaction_type':'BUY','quantity':-1,'price':100}).status_code==422
    assert c.post('/api/transactions',json={'symbol':'TCS','transaction_type':'BUY','quantity':1,'price':'NaN'}).status_code==422
    assert len(c.get('/api/transactions').json())==count

def test_watchlist(client):
    c,_=client
    for _ in range(2): assert c.post('/api/watchlist',json={'symbol':'TCS'}).status_code==201
    assert sum(x['symbol']=='TCS.NS' for x in c.get('/api/watchlist').json())==1
    assert c.delete('/api/watchlist/TCS.NS').status_code==200
    assert not any(x['symbol']=='TCS.NS' for x in c.get('/api/watchlist').json())

def test_local_ai_analytics(client):
    c,_=client
    a=c.get('/api/stocks/TCS.NS/analytics').json()
    assert a['ma20']>0 and a['volatility']>=0
    s=c.post('/api/ai/analyze-stock/TCS.NS').json()
    assert s['provider']=='local' and s['strengths'] and 'not financial advice' in s['disclaimer']
    p=c.post('/api/ai/analyze-portfolio').json()
    assert p['provider']=='local' and p['observations']

def test_seed_once_and_empty_portfolio(client):
    c,Session=client
    with Session() as db:
        seed(db,db.scalar(select(User).where(User.email=='demo@aquavest.local'))); assert len(list(db.scalars(select(Holding))))==8
    for h in c.get('/api/portfolio').json(): assert c.delete('/api/portfolio/'+h['symbol']).status_code==200
    with Session() as db: seed(db)
    assert c.get('/api/portfolio').json()==[]
    assert c.get('/api/portfolio/summary').json()['current_value']==0
    assert c.get('/api/portfolio/history').json()['points']==[]
    assert c.post('/api/ai/analyze-portfolio').status_code==200

def test_search_history_and_errors(client):
    c,_=client
    assert c.get('/api/stocks/search?q=HDFC').json()[0]['symbol']=='HDFCBANK.NS'
    assert c.get('/api/stocks/UNKNOWN').status_code==404
    assert c.get('/api/stocks/TCS/history?period=invalid').status_code==422
    a=c.get('/api/stocks/TCS/history?period=1y').json()
    assert a==c.get('/api/stocks/TCS/history?period=1y').json()
    assert len(a['points'])>200 and a['source']=='demo'
    assert c.get('/api/markets').status_code==200

def test_external_ai_failure_falls_back(client,monkeypatch):
    import app.services.ai_service as ai
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setenv('AI_PROVIDER','gemini')
    def fail(*args,**kwargs): raise RuntimeError('offline')
    monkeypatch.setattr(ai.GeminiProvider,'generate',fail)
    assert client[0].post('/api/ai/analyze-stock/TCS').json()['provider']=='local'

def test_backdated_and_full_sell(client):
    c,_=client
    payload={'symbol':'TITAN','transaction_type':'BUY','quantity':'1.5','price':'3000','transaction_date':str(date.today())}
    assert c.post('/api/transactions',json=payload).status_code==201
    payload['transaction_date']='2000-01-01'
    assert c.post('/api/transactions',json=payload).status_code==400
    payload.update(transaction_date=str(date.today()),transaction_type='SELL',price='3200')
    assert c.post('/api/transactions',json=payload).status_code==201
    assert not any(h['symbol']=='TITAN.NS' for h in c.get('/api/portfolio').json())

def test_cors(client):
    r=client[0].options('/api/transactions',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST'})
    assert r.headers['access-control-allow-origin']=='http://localhost:5173'


def test_malformed_ai_falls_back(client,monkeypatch):
    import app.services.ai_service as ai
    monkeypatch.setenv('GROQ_API_KEY','test-only')
    monkeypatch.setenv('AI_PROVIDER','groq')
    monkeypatch.setattr(ai.GroqProvider,'generate',lambda self,prompt: {'summary':'Incomplete'})
    assert client[0].post('/api/ai/analyze-portfolio').json()['provider']=='local'

def test_auth_isolation_and_cash_accounting(client):
    c,_=client
    assert c.get('/api/portfolio').status_code==200
    c.post('/api/auth/logout')
    assert c.get('/api/portfolio').status_code==401
    r=c.post('/api/auth/register',json={'name':'New Investor','email':'new@example.com','password':'CorrectHorse2026!'})
    assert r.status_code==201
    before=c.get('/api/portfolio/summary').json()
    assert len(before['holdings'])==8
    cash_before=before['cash_balance']
    trade=c.post('/api/transactions',json={'symbol':'TCS','transaction_type':'BUY','quantity':'1','price':'1000'})
    assert trade.status_code==201
    after=c.get('/api/portfolio/summary').json()
    assert after['cash_balance']==pytest.approx(cash_before-1000)
    c.post('/api/auth/logout')
    c.post('/api/auth/login',json={'email':'demo@aquavest.local','password':'AquaVestDemo2026!'})
    assert c.get('/api/portfolio/summary').json()['cash_balance']==pytest.approx(before['cash_balance'])

def test_market_provider_failure_keeps_demo(monkeypatch):
    import app.services.market_data as market
    import yfinance
    class OfflineTicker:
        def history(self,**kwargs): raise ConnectionError('offline')
    monkeypatch.setattr(yfinance,'Ticker',lambda symbol:OfflineTicker())
    before=market.quote('TCS.NS')
    market.refresh('TCS.NS')
    after=market.quote('TCS.NS')
    assert after==before and after['source']=='demo'
