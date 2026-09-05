from datetime import datetime

from pydantic import BaseModel


class HeartbeatResponse(BaseModel):
    status: str
    server_time: datetime


class DeviceStatusResponse(BaseModel):
    online: bool
    current_state: str
    last_heartbeat: datetime | None
    version: str
