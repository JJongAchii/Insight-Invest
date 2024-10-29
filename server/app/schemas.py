from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TbMeta(BaseModel):
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
    

class TbPrice(BaseModel):
    meta_id : int
    trade_date : datetime
    close : float
    adj_close : float
    gross_return : float
    
    class Config:
        orm_mode = True