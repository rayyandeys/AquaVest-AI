import os
from pathlib import Path
from dotenv import load_dotenv
BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / '.env')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///' + str(BASE / 'aquavest.db'))
MARKET_MODE = os.getenv('MARKET_MODE', 'auto')
DISCLAIMER = 'AI-generated insights are for educational and analytical purposes only and are not financial advice.'
