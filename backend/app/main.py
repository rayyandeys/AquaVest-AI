import os
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session
from .auth import current_user, hash_password, verify_password, issue_session, clear_session, public_user
from .database import Base, engine, SessionLocal, get_db, migrate_legacy_database
from .models import Holding, Transaction, WatchlistItem, User
from .schemas import TradeInput, WatchInput, Registration, Credentials
from .seed import seed
from .services.market_data import quote, history, normalize, UNIVERSE
from .services.analytics import analyze
from .services.portfolio_service import holdings, snapshot, trade
from .services.ai_service import AIService

DEMO_EMAIL = 'demo@aquavest.local'
DEFAULT_DEMO_PASSWORD = 'AquaVestDemo2026!'


@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        demo_user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if not demo_user:
            demo_user = User(name='Demo Investor', email=DEMO_EMAIL,
                             password_hash=hash_password(os.getenv('DEMO_PASSWORD', DEFAULT_DEMO_PASSWORD)),
                             cash_balance=1000000)
            db.add(demo_user); db.commit(); db.refresh(demo_user)
    migrate_legacy_database()
    with SessionLocal() as db:
        demo_user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        seed(db, demo_user)
    yield


app=FastAPI(title='AquaVest AI',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_credentials=True,allow_methods=['GET','POST','DELETE','OPTIONS'],allow_headers=['Content-Type'])


@app.get('/api/health')
def health(): return {'status':'healthy','app':'AquaVest AI'}


@app.post('/api/auth/register',status_code=201)
def register(data:Registration,response:Response,db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email==data.email)):
        raise HTTPException(409,'An account with this email already exists')
    user=User(name=data.name,email=data.email,password_hash=hash_password(data.password),cash_balance=1000000)
    db.add(user)
    try:
        db.commit(); db.refresh(user)
    except Exception:
        db.rollback(); raise HTTPException(409,'Unable to create this account. Please check the email and try again.')
    seed(db,user)
    issue_session(response,db,user)
    return public_user(user)


@app.post('/api/auth/login')
def login(data:Credentials,response:Response,db:Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==data.email))
    if not user or not verify_password(data.password,user.password_hash):
        raise HTTPException(401,'Email or password is incorrect')
    issue_session(response,db,user)
    return public_user(user)


@app.post('/api/auth/logout')
def logout(request:Request,response:Response,db:Session=Depends(get_db)):
    clear_session(response,request,db)
    return {'message':'Signed out'}


@app.get('/api/auth/me')
def me(user:User=Depends(current_user)):
    return public_user(user)


@app.get('/api/portfolio')
def portfolio(db:Session=Depends(get_db),user:User=Depends(current_user)): return holdings(db,user.id)
@app.get('/api/portfolio/summary')
def summary(db:Session=Depends(get_db),user:User=Depends(current_user)): return snapshot(db,user.id)
@app.get('/api/portfolio/allocation')
def allocation(db:Session=Depends(get_db),user:User=Depends(current_user)):
    s=snapshot(db,user.id); return {'stocks':s['stock_allocation'],'sectors':s['sector_allocation']}
@app.get('/api/portfolio/history')
def portfolio_history(period:Literal['1d','1w','1m','3m','1y']='1m',db:Session=Depends(get_db),user:User=Depends(current_user)):
    rows=holdings(db,user.id); series={h['symbol']:history(h['symbol'],period) for h in rows}
    dates=sorted(set.intersection(*(set(p['date'] for p in v['points']) for v in series.values()))) if series else []
    maps={s:{p['date']:p['value'] for p in v['points']} for s,v in series.items()}
    return {'points':[{'date':d,'value':sum(h['quantity']*maps[h['symbol']][d] for h in rows)} for d in dates], 'source':'demo' if any(v['source']=='demo' for v in series.values()) or not rows else 'yahoo','note':'Current-holdings price illustration; excludes historical cash flows and is not an actual portfolio return series.'}
@app.delete('/api/portfolio/{symbol}')
def remove_holding(symbol:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    symbol=normalize(symbol)
    h=db.scalar(select(Holding).where(Holding.symbol==symbol,Holding.user_id==user.id))
    if not h: raise HTTPException(404,'Holding not found')
    data=TradeInput(symbol=symbol,transaction_type='SELL',quantity=h.quantity,price=str(round(quote(symbol)['price'],6)))
    trade(db,data,user.id); return {'message':'Position closed; sale recorded'}
@app.get('/api/transactions')
def transactions(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return list(db.scalars(select(Transaction).where(Transaction.user_id==user.id).order_by(Transaction.transaction_date.desc(),Transaction.id.desc())))
@app.post('/api/transactions',status_code=201)
def add_transaction(data:TradeInput,db:Session=Depends(get_db),user:User=Depends(current_user)): return trade(db,data,user.id)
@app.get('/api/watchlist')
def watchlist(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [public_quote(w.symbol) for w in db.scalars(select(WatchlistItem).where(WatchlistItem.user_id==user.id))]
@app.post('/api/watchlist',status_code=201)
def add_watch(data:WatchInput,db:Session=Depends(get_db),user:User=Depends(current_user)):
    symbol=normalize(data.symbol)
    db.execute(insert(WatchlistItem).values(user_id=user.id,symbol=symbol).on_conflict_do_nothing(index_elements=['user_id','symbol'])); db.commit()
    return public_quote(symbol)
@app.delete('/api/watchlist/{symbol}')
def remove_watch(symbol:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    w=db.scalar(select(WatchlistItem).where(WatchlistItem.symbol==normalize(symbol),WatchlistItem.user_id==user.id))
    if w: db.delete(w); db.commit()
    return {'message':'Watchlist updated'}
def public_quote(symbol): return {k:v for k,v in quote(symbol).items() if k!='history'}
@app.get('/api/stocks/search')
def search(q:str='',user:User=Depends(current_user)):
    return [dict(symbol=r[0],company_name=r[1],sector=r[2]) for r in UNIVERSE if q.lower() in (r[0]+' '+r[1]).lower()]
@app.get('/api/stocks/{symbol}')
def stock(symbol:str,user:User=Depends(current_user)): return public_quote(symbol)
@app.get('/api/stocks/{symbol}/history')
def stock_history(symbol:str,period:Literal['1d','1w','1m','3m','1y']='1m',user:User=Depends(current_user)): return history(symbol,period)
@app.get('/api/stocks/{symbol}/analytics')
def analytics(symbol:str,user:User=Depends(current_user)): return analyze(quote(symbol))
@app.post('/api/ai/analyze-stock/{symbol}')
def ai_stock(symbol:str,user:User=Depends(current_user)):
    q=quote(symbol); q['analytics']=analyze(q); return AIService().generate('stock',q)
@app.post('/api/ai/analyze-portfolio')
def ai_portfolio(db:Session=Depends(get_db),user:User=Depends(current_user)): return AIService().generate('portfolio',snapshot(db,user.id))
@app.get('/api/insights')
def insights(db:Session=Depends(get_db),user:User=Depends(current_user)):
    s=snapshot(db,user.id); return {'alerts':s['alerts'],'story':s['story']}
@app.get('/api/markets')
def markets(user:User=Depends(current_user)):
    stocks=[public_quote(r[0]) for r in UNIVERSE]
    return {'indices':[{'name':'NIFTY 50','value':24835.4,'change':0.62},{'name':'SENSEX','value':81306.8,'change':0.57},{'name':'NIFTY BANK','value':51295.2,'change':0.84}], 'indices_source':'demo','stocks':stocks,'most_watched':stocks[:5]}
