import json
import logging
import os
import httpx
from ..config import DISCLAIMER
from ..schemas import StockAnalysis, PortfolioAnalysis
from .analytics import analyze
logger=logging.getLogger(__name__)
class LocalInsightProvider:
    def stock(self,q):
        a=analyze(q)
        return dict(summary=f"{q['company_name']} has {a['trend'].lower()} recent momentum of {a['momentum']:.1f}% over approximately 20 sessions. Annualized historical volatility is {a['volatility']:.1f}%. These backward-looking measures do not predict returns.",
            trend=a['trend'],risk_level=a['risk_level'],confidence=70,
            strengths=[a['ma_position'],f"Latest price is {a['distance_low']:.1f}% above the observed 52-week low."],
            risks=[f"Historical annualized volatility: {a['volatility']:.1f}%.", 'Synthetic data is illustrative; verify all figures.' if q['source']=='demo' else 'Daily Yahoo quotes may be delayed; fundamentals may be unavailable.'],
            valuation_view=f"P/E of {q['pe']:.1f} is a descriptive multiple; sector peers and earnings quality are needed for context." if q['pe'] else 'P/E is unavailable. No valuation conclusion is inferred.',
            momentum_view=f"{a['ma_position']}; 20D average {a['ma20']:.2f}, 50D average {a['ma50']:.2f}.",
            investor_considerations=['How sensitive are earnings to the economic cycle?','How does this position affect total sector exposure?','Does the historical risk fit the intended investment horizon?'])
    def portfolio(self,s):
        return dict(summary=s['story'],healthy=[f"Portfolio spans {len(s['holdings'])} securities and {len(s['sector_allocation'])} sectors.",f"Unrealized return is {s['return_percent']:.2f}%."],
            weaknesses=s['alerts'] or ['No configured concentration or drawdown threshold was breached. This does not imply absence of risk.'],
            concentration_risks=[f"{x['name']}: {x['percent']:.1f}% of current value." for x in s['sector_allocation']],
            questions=['Is sector exposure consistent with the intended risk tolerance?','How might correlated holdings behave during a downturn?'],
            observations=[f"Weighted individual-stock volatility is {s['weighted_volatility']:.1f}% (not covariance-adjusted portfolio volatility).", 'Risk and diversification scores are transparent heuristics, not credit ratings.'])
class GeminiProvider:
    def generate(self,prompt):
        model=os.getenv('GEMINI_MODEL','gemini-2.5-flash')
        r=httpx.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',headers={'x-goog-api-key':os.environ['GEMINI_API_KEY']},json={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseMimeType':'application/json','temperature':0.2}},timeout=20)
        r.raise_for_status(); return json.loads(r.json()['candidates'][0]['content']['parts'][0]['text'])
class GroqProvider:
    def generate(self,prompt):
        r=httpx.post('https://api.groq.com/openai/v1/chat/completions',headers={'Authorization':'Bearer '+os.environ['GROQ_API_KEY']},json={'model':os.getenv('GROQ_MODEL','llama-3.3-70b-versatile'),'messages':[{'role':'user','content':prompt}],'response_format':{'type':'json_object'},'temperature':0.2},timeout=20)
        r.raise_for_status(); return json.loads(r.json()['choices'][0]['message']['content'])
class AIService:
    def generate(self,kind,data):
        local=LocalInsightProvider(); fallback=local.stock(data) if kind=='stock' else local.portfolio(data)
        schema=StockAnalysis if kind=='stock' else PortfolioAnalysis
        provider=os.getenv('AI_PROVIDER','gemini').lower(); result=fallback; source='local'
        key=os.getenv(provider.upper()+'_API_KEY')
        if key and provider in ('gemini','groq'):
            prompt='You are an educational financial data analyst, NOT a financial adviser. Never issue buy/sell instructions, promise returns, or invent missing facts. Distinguish synthetic demo data from observed data. Confidence means completeness of analysis, not probability of profit. Return only JSON matching this schema: '+json.dumps(schema.model_json_schema())+' Input data: '+json.dumps(data,default=str)
            try:
                raw=(GeminiProvider() if provider=='gemini' else GroqProvider()).generate(prompt)
                result=schema.model_validate(raw).model_dump(); source=provider
            except Exception as exc:
                logger.warning('AI provider failed (%s); local analysis used',type(exc).__name__)
        result.update(provider=source,disclaimer=DISCLAIMER,data_source=data.get('source','demo'))
        if kind=='portfolio': result.update(risk_score=data['risk_score'],diversification=data['diversification'],risk_level=data['risk_level'])
        return result
