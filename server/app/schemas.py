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
        from_attributes  = True
    

class Ticker(BaseModel):
    meta_id: int
    ticker: str
    name: Optional[str] = None
    iso_code: Optional[str] = None
    security_type: Optional[str] = None
    sector: Optional[str] = None

    class Config:
        from_attributes  = True


class Strategy(BaseModel):
    strategy_id: int
    strategy: str
    strategy_name: str
    
    class Config:
        from_attributes  = True
        

class Portfolio(BaseModel):
    port_id: int
    port_name: str
    strategy_name: str
    ann_ret: float
    ann_vol: float
    sharpe: float
    
    class Config:
        from_attributes = True
        

class PortNav(BaseModel):
    port_id: int
    trade_date: datetime
    value: float


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
        from_attributes  = True
        
        
class BacktestRequest(BaseModel):
    strategy_name: str
    meta_id: List[int]
    algorithm: Optional[str]
    startDate: date
    endDate: date
    
    
class PortIdInfo(BaseModel):
    port_id: int
    port_name: str
    strategy_name: str
    ann_retr: float
    ann_vol: float
    sharpe: float
    mdd: float
    skew: float
    kurt: float
    var: float
    cvar: float
    
    class Config:
        from_attributes  = True