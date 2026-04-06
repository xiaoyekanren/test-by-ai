from typing import Optional

from pydantic import BaseModel, Field


class MonitorSettings(BaseModel):
    refreshInterval: int = Field(default=10, ge=5, le=300)


class ObservabilitySettings(BaseModel):
    prometheusUrl: Optional[str] = Field(default=None, max_length=500)
    grafanaUrl: Optional[str] = Field(default=None, max_length=500)
    grafanaDashboardUid: Optional[str] = Field(default=None, max_length=200)
    grafanaDatasource: Optional[str] = Field(default=None, max_length=200)
    grafanaOrgId: Optional[str] = Field(default=None, max_length=50)
    grafanaTimeRange: str = Field(default="now-6h")
    grafanaEmbedEnabled: bool = False


class SettingsResponse(BaseModel):
    monitor: MonitorSettings = Field(default_factory=MonitorSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)


class SettingsUpdate(BaseModel):
    monitor: Optional[MonitorSettings] = None
    observability: Optional[ObservabilitySettings] = None


class ObservabilitySettingsUpdate(ObservabilitySettings):
    pass
