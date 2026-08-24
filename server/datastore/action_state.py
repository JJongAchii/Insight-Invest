"""Action Center 사용자 상태 저장소.

시장 이벤트 자체는 가격·수급·포트폴리오 원천에서 매 요청 시 재구성한다. 여기에는
사용자가 만든 상태(read/snoozed/dismissed)만 저장해 원천 사실과 UI 상태를 섞지 않는다.
"""

from datetime import datetime, timezone

import pandas as pd

from datastore import storage

FILE = "action_states.parquet"
COLUMNS = ["event_id", "state", "snoozed_until", "updated_at"]


def list_states() -> pd.DataFrame:
    if not storage.exists(FILE):
        return pd.DataFrame(columns=COLUMNS)
    frame = storage.read_parquet(FILE)
    for column in COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame[COLUMNS]


def set_state(event_id: str, state: str, snoozed_until=None) -> None:
    frame = list_states()
    frame = frame[frame["event_id"] != event_id]
    if state != "new":
        row = pd.DataFrame(
            [
                {
                    "event_id": event_id,
                    "state": state,
                    "snoozed_until": snoozed_until,
                    "updated_at": datetime.now(timezone.utc),
                }
            ]
        )
        frame = pd.concat([frame, row], ignore_index=True) if not frame.empty else row
    storage.write_parquet(frame.reindex(columns=COLUMNS), FILE)
