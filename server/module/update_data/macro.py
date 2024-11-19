import os
import sys
from fredapi import Fred

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../..")))
import db

fred = Fred(api_key="052594dd220d531c37205d1819b573f5")


def update_macro():
    last_macro = db.get_last_updated_macro()
    
    for macro_id in last_macro.macro_id:
        macro = last_macro[last_macro.macro_id == macro_id]
        
        if macro.max_dt.values:
            data = fred.get_series(series_id=macro.fred.values[0], observation_start=macro.max_dt.values[0])[1:]
        else:
            data = fred.get_series(series_id=macro.fred.values[0])
        
        data_df = data.dropna().reset_index()
        data_df.columns = ["base_date", "value"]
        data_df["macro_id"] = macro_id
        
        if not data_df.empty:
            db.TbMacroData.insert(data_df)