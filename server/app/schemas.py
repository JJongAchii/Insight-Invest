from pydantic import BaseModel, validator
from datetime import datetime, date
from typing import Optional, List

class Meta(BaseModel):
    meta_id : int
    ticker : str
    name : Optional[str] = None
    isin : Optional[str] = None
    security_type : str
    asset_class : Optional[str] = None
    sector : Optional[str] = None
    iso_code : str
    marketcap : Optional[int] = None
    fee : Optional[float] = None
    remark : Optional[str] = None
    
    class Config:
        orm_mode = True
    

class Ticker(BaseModel):
    meta_id: int
    ticker: str
    name: Optional[str] = None
    iso_code: Optional[str] = None
    security_type: Optional[str] = None
    sector: Optional[str] = None

    class Config:
        orm_mode = True
        

class Price(BaseModel):
    meta_id : int
    trade_date : datetime
    close : Optional[float] = None
    adj_close : Optional[float] = None
    gross_return : Optional[float] = None
    
    @validator("trade_date", pre=True)
    def parse_trade_date(cls, value):
        if isinstance(value, date):  # Check if `value` is of type `date`
            return datetime(value.year, value.month, value.day)
        return value
    
    class Config:
        orm_mode = True
        
        
class BacktestRequest(BaseModel):
    meta_id: List[int]
    algorithm: Optional[str]
    startDate: date
    endDate: date