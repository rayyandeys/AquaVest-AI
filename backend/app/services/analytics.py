import math
import statistics

def analyze(q):
    prices=[p['value'] for p in q['history']]
    returns=[math.log(b/a) for a,b in zip(prices,prices[1:])]
    vol=statistics.stdev(returns)*math.sqrt(252)*100 if len(returns)>1 else 0
    ma20=statistics.mean(prices[-20:]); ma50=statistics.mean(prices[-50:])
    momentum=(prices[-1]/prices[-min(21,len(prices))]-1)*100
    trend='Bullish' if momentum>2 else 'Bearish' if momentum< -2 else 'Neutral'
    return dict(ma20=ma20,ma50=ma50,momentum=momentum,volatility=vol,trend=trend,
        volatility_label='High' if vol>30 else 'Medium' if vol>15 else 'Low',
        risk_level='High' if vol>30 else 'Moderate' if vol>15 else 'Low',
        distance_high=(q['price']/q['high_52w']-1)*100,
        distance_low=(q['price']/q['low_52w']-1)*100,
        ma_position='Above 20D MA' if q['price']>=ma20 else 'Below 20D MA')
