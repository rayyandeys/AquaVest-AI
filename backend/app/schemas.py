from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_validator

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=128)
    @field_validator('email')
    @classmethod
    def valid_email(cls, value):
        value = value.strip().lower()
        if value.count('@') != 1 or '.' not in value.rsplit('@', 1)[-1]:
            raise ValueError('Enter a valid email address')
        return value

class Registration(Credentials):
    name: str = Field(min_length=1, max_length=80)
    @field_validator('name')
    @classmethod
    def name_not_blank(cls, value):
        value = value.strip()
        if not value: raise ValueError('Name is required')
        return value
class TradeInput(BaseModel):
    symbol: str = Field(min_length=1, max_length=30)
    transaction_type: Literal['BUY', 'SELL']
    quantity: Decimal = Field(gt=0, le=10000000, max_digits=20, decimal_places=6)
    price: Decimal = Field(gt=0, le=100000000, max_digits=20, decimal_places=8)
    transaction_date: date = Field(default_factory=date.today)
    @field_validator('transaction_date')
    @classmethod
    def valid_date(cls, v):
        if v > date.today():
            raise ValueError('Transaction date cannot be in the future')
        return v
class WatchInput(BaseModel):
    symbol: str
class StockAnalysis(BaseModel):
    summary: str
    trend: Literal['Bullish', 'Neutral', 'Bearish']
    risk_level: Literal['Low', 'Moderate', 'High']
    confidence: int = Field(ge=0, le=100)
    strengths: list[str]
    risks: list[str]
    valuation_view: str
    momentum_view: str
    investor_considerations: list[str]
class PortfolioAnalysis(BaseModel):
    summary: str
    healthy: list[str]
    weaknesses: list[str]
    concentration_risks: list[str]
    questions: list[str]
    observations: list[str]
