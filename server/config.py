import os
import argparse
from datetime import date


PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))
LOGDB_FOLDER = os.path.join(PROJECT_FOLDER, "log")



####################################################################################################
# def get_args():
#     # parse arguments
#     parse = argparse.ArgumentParser(description="Running Script.")
#     parse.add_argument("-s", "--script")
#     parse.add_argument("-d", "--date", default=date.today().strftime("%Y-%m-%d"))
#     parse.add_argument("-u", "--user")
#     parse.add_argument("-r", "--regime", default = 'lei')
#     parse.add_argument("-db", "--database")
#     args = parse.parse_args()
    
#     return args