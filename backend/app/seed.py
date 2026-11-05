from datetime import date, timedelta
from sqlalchemy import select
from .models import Holding, Transaction, WatchlistItem, Metadata, User
from .services.market_data import UNIVERSE

def seed(db, user: User):
    marker = f'seeded:{user.id}'
    if db.get(Metadata, marker): return
    if not db.scalar(select(Holding).where(Holding.user_id == user.id)) and not db.scalar(select(Transaction).where(Transaction.user_id == user.id)):
        quantities=[100,35,60,100,85,180,55,25]
        for i,(symbol,name,sector,price,pe) in enumerate(UNIVERSE[:8]):
            average=round(price * [0.89,0.92,1.04,0.87,0.90,0.95,0.83,0.94][i],2)
            db.add(Holding(user_id=user.id,symbol=symbol,company_name=name,sector=sector,quantity=quantities[i],average_price=average))
            db.add(Transaction(user_id=user.id,symbol=symbol,company_name=name,transaction_type='BUY',quantity=quantities[i],price=average,transaction_date=date.today()-timedelta(days=90)))
    if not db.scalar(select(WatchlistItem).where(WatchlistItem.user_id == user.id)):
        for row in UNIVERSE[8:]: db.add(WatchlistItem(user_id=user.id,symbol=row[0]))
    db.add(Metadata(key=marker,value='1'))
    cash_marker = f'cash-initialized:{user.id}'
    if not db.get(Metadata, cash_marker):
        db.flush()
        txns = list(db.scalars(select(Transaction).where(Transaction.user_id == user.id)))
        net_outflow = sum(float(t.quantity * t.price) * (1 if t.transaction_type == 'BUY' else -1) for t in txns)
        user.cash_balance = max(0, 1000000 - net_outflow)
        db.add(Metadata(key=cash_marker,value='1'))
    db.commit()
