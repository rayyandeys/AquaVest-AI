from decimal import Decimal
from sqlalchemy import select
from fastapi import HTTPException
from ..models import Holding, Transaction, User
from .market_data import quote, normalize
from .analytics import analyze

def trade(db, data, user_id):
    symbol=normalize(data.symbol)
    # Reserve SQLite write lock before reading quantities to avoid concurrent oversells.
    from sqlalchemy import text
    db.execute(text('BEGIN IMMEDIATE'))
    h=db.scalar(select(Holding).where(Holding.symbol==symbol, Holding.user_id==user_id))
    user=db.get(User,user_id)
    q=quote(symbol)
    latest=db.scalar(select(Transaction).where(Transaction.symbol==symbol, Transaction.user_id==user_id).order_by(Transaction.transaction_date.desc(),Transaction.id.desc()).limit(1))
    if latest and data.transaction_date < latest.transaction_date:
        raise HTTPException(400,'Date precedes the latest transaction for this stock. Enter trades chronologically.')
    realized=Decimal(0)
    total=data.quantity*data.price
    if data.transaction_type=='SELL':
        if not h or h.quantity<data.quantity: raise HTTPException(400,'Cannot sell more shares than currently owned')
        realized=(data.price-h.average_price)*data.quantity
        user.cash_balance=Decimal(user.cash_balance)+total
        h.quantity-=data.quantity
        if h.quantity==0: db.delete(h)
    else:
        if Decimal(user.cash_balance)<total: raise HTTPException(400,'Insufficient demo cash balance for this buy order')
        user.cash_balance=Decimal(user.cash_balance)-total
        if h:
            h.average_price=(h.quantity*h.average_price+data.quantity*data.price)/(h.quantity+data.quantity)
            h.quantity+=data.quantity
        else:
            db.add(Holding(user_id=user_id,symbol=symbol,company_name=q['company_name'],sector=q['sector'],quantity=data.quantity,average_price=data.price))
    t=Transaction(user_id=user_id,symbol=symbol,company_name=q['company_name'],transaction_type=data.transaction_type,
        quantity=data.quantity,price=data.price,transaction_date=data.transaction_date,realized_pnl=realized)
    db.add(t); db.commit(); db.refresh(t)
    return t

def holdings(db, user_id):
    result=[]
    for h in db.scalars(select(Holding).where(Holding.user_id==user_id).order_by(Holding.symbol)):
        q=quote(h.symbol); quantity=float(h.quantity); average=float(h.average_price)
        investment=quantity*average; value=quantity*q['price']; pnl=value-investment
        result.append(dict(id=h.id,symbol=h.symbol,company_name=h.company_name,sector=h.sector,
            quantity=quantity,average_price=average,current_price=q['price'],investment=investment,
            current_value=value,pnl=pnl,return_percent=pnl/investment*100 if investment else 0,
            day_pnl=quantity*q['change'],day_change=q['change_percent'],source=q['source'],
            as_of=q['as_of'],updated_at=q['updated_at'],is_stale=q.get('is_stale',False),
            volatility=analyze(q)['volatility']))
    return result

def snapshot(db, user_id):
    rows=holdings(db,user_id); value=sum(h['current_value'] for h in rows); invested=sum(h['investment'] for h in rows)
    day=sum(h['day_pnl'] for h in rows); pnl=value-invested
    sectors={}
    for h in rows: sectors[h['sector']]=sectors.get(h['sector'],0)+h['current_value']
    allocation=[dict(name=h['symbol'].replace('.NS',''),value=h['current_value'],percent=h['current_value']/value*100) for h in rows] if value else []
    sector_allocation=[dict(name=k,value=v,percent=v/value*100) for k,v in sectors.items()] if value else []
    max_stock=max((a['percent'] for a in allocation),default=0); max_sector=max((a['percent'] for a in sector_allocation),default=0)
    volatility=sum(h['volatility']*h['current_value']/value for h in rows) if value else 0
    risk=min(100,round(volatility*1.5+max_stock*.4+max_sector*.2)) if rows else 0
    alerts=[]
    if max_stock>30: alerts.append('High single-stock concentration: the largest position exceeds 30%.')
    if max_sector>40: alerts.append('Sector concentration detected: one sector exceeds 40%.')
    if len(rows)<4: alerts.append('Low diversification: fewer than four securities.')
    if any(h['volatility']>30 for h in rows): alerts.append('Elevated volatility in one or more holdings.')
    gains=sum(max(0,h['pnl']) for h in rows)
    if gains and any(h['pnl']>gains*.5 for h in rows): alerts.append('Returns heavily dependent on one holding: over 50% of positive unrealized gains.')
    if any(h['return_percent']< -15 for h in rows): alerts.append('Large unrealized drawdown: a holding is more than 15% below cost.')
    ordered=sorted(rows,key=lambda h:h['day_pnl'],reverse=True)
    story='Add an investment to begin your portfolio story.'
    if rows:
        strongest=', '.join(h['symbol'].replace('.NS','') for h in ordered[:2])
        largest=max(sector_allocation,key=lambda a:a['value'])
        drag=next((h for h in reversed(ordered) if h['day_pnl']<0),None)
        story=f"Your portfolio moved {day/(value-day)*100 if value-day else 0:+.2f}% across the latest daily closes. {strongest} led contributions. "
        if drag: story+=f"{drag['symbol'].replace('.NS','')} was the largest drag. "
        story+=f"{largest['name']} represents {largest['percent']:.1f}% of portfolio value."
    user=db.get(User,user_id)
    realized=sum(float(t.realized_pnl) for t in db.scalars(select(Transaction).where(Transaction.user_id==user_id)))
    return dict(holdings=rows,current_value=value,investment=invested,pnl=pnl,return_percent=pnl/invested*100 if invested else 0,
        cash_balance=float(user.cash_balance),account_value=value+float(user.cash_balance),
        day_pnl=day,day_percent=day/(value-day)*100 if value-day else 0,realized_pnl=realized,
        risk_score=risk,risk_level='High' if risk>=70 else 'Moderate' if risk>=35 else 'Low',
        diversification=round(100-max_stock) if rows else 0,weighted_volatility=volatility,
        stock_allocation=allocation,sector_allocation=sector_allocation,alerts=alerts,story=story,
        best_performer=max(rows,key=lambda h:h['return_percent'])['symbol'] if rows else '—',
        source='demo' if any(h['source']=='demo' for h in rows) or not rows else 'yahoo',
        quote_updated_at=min((h['updated_at'] for h in rows),default=None),
        quotes_stale=any(h['is_stale'] for h in rows))
