import os
import logging
from logging import Handler
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from config import LOGDB_FOLDER


if not os.path.exists(LOGDB_FOLDER):
    os.makedirs(LOGDB_FOLDER)


Base = declarative_base()
engine = create_engine(
    url=f"sqlite:///{LOGDB_FOLDER}/log.db", connect_args=dict(check_same_thread=False)
)
session = scoped_session(session_factory=sessionmaker(bind=engine))()


class DBhandler(Handler):

    """db logging handler"""

    def emit(self, record) -> None:

        category = getattr(record, "category", "monitoring")

        if category == "script":
            table = TbScriptLog
        else:
            table = TbMonitoringLog

        table(
            user=getattr(record, "user", None),
            activity=getattr(record, "activity", None),
            module=record.module,
            thread_name=record.threadName,
            file_name=record.filename,
            func_name=record.funcName,
            level_name=record.levelname,
            line_no=record.lineno,
            process_name=record.processName,
            message=record.msg,
        ).commit()


class TbLog(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True)
    user = Column(String(50), nullable=True)
    activity = Column(String(100), nullable=True)
    time = Column(DateTime, nullable=False, default=datetime.now)
    level_name = Column(String(10), nullable=True)
    module = Column(String(200), nullable=True)
    thread_name = Column(String(200), nullable=True)
    file_name = Column(String(200), nullable=True)
    func_name = Column(String(200), nullable=True)
    line_no = Column(Integer, nullable=True)
    process_name = Column(String(200), nullable=True)
    message = Column(Text)

    def commit(self) -> None:
        """record instance"""
        session.add(self)
        try:
            session.commit()
        except Exception as exception:
            session.rollback()
            raise exception


class TbScriptLog(TbLog):
    """log records table"""

    __tablename__ = "tb_script_log"


class TbMonitoringLog(TbLog):
    __tablename__ = "tb_monitoring_log"


Base.metadata.create_all(bind=engine)
logging.captureWarnings(capture=True)
logger = logging.getLogger("sqlite")
logger.setLevel(logging.DEBUG)
dbhandler = DBhandler()
dbhandler.setLevel(level=logging.DEBUG)
logger.addHandler(dbhandler)
streamhandler = logging.StreamHandler()
dbhandler.setLevel(level=logging.DEBUG)
logger.propagate = False
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
streamhandler.setFormatter(formatter)
logger.addHandler(streamhandler)
