from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models.database import SystemSetting
from app.schemas.settings import (
    MonitorSettings,
    ObservabilitySettings,
    ObservabilitySettingsUpdate,
    SettingsResponse,
    SettingsUpdate,
)

router = APIRouter()

MONITOR_KEY = "monitor"
OBSERVABILITY_KEY = "observability"


def _default_monitor() -> dict:
    return MonitorSettings().model_dump()


def _default_observability() -> dict:
    return ObservabilitySettings().model_dump()


def _load_setting(db: Session, key: str, default: dict) -> dict:
    record = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not record or not isinstance(record.value, dict):
        return default
    return {**default, **record.value}


def _save_setting(db: Session, key: str, value: dict) -> dict:
    record = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if record:
        record.value = value
    else:
        record = SystemSetting(key=key, value=value)
        db.add(record)
    db.commit()
    return value


@router.get("", response_model=SettingsResponse)
def get_settings(db: Session = Depends(get_db)):
    return SettingsResponse(
        monitor=_load_setting(db, MONITOR_KEY, _default_monitor()),
        observability=_load_setting(db, OBSERVABILITY_KEY, _default_observability()),
    )


@router.put("", response_model=SettingsResponse)
def update_settings(payload: SettingsUpdate, db: Session = Depends(get_db)):
    monitor = _load_setting(db, MONITOR_KEY, _default_monitor())
    observability = _load_setting(db, OBSERVABILITY_KEY, _default_observability())

    if payload.monitor is not None:
        monitor = _save_setting(db, MONITOR_KEY, payload.monitor.model_dump())
    if payload.observability is not None:
        observability = _save_setting(db, OBSERVABILITY_KEY, payload.observability.model_dump())

    return SettingsResponse(monitor=monitor, observability=observability)


@router.get("/observability", response_model=ObservabilitySettings)
def get_observability_settings(db: Session = Depends(get_db)):
    return _load_setting(db, OBSERVABILITY_KEY, _default_observability())


@router.put("/observability", response_model=ObservabilitySettings)
def update_observability_settings(payload: ObservabilitySettingsUpdate, db: Session = Depends(get_db)):
    return _save_setting(db, OBSERVABILITY_KEY, payload.model_dump())
