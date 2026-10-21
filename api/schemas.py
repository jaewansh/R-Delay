"""Bounded requests for the local synthetic prototype; no personal data input."""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

BASE_TIME = datetime.fromisoformat("2026-10-21T08:00:00+09:00")
DECISION_TIME = BASE_TIME + timedelta(hours=2)

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class Observation(StrictModel):
    kind: Literal["snapshot", "incident"] = "snapshot"
    node: Literal["sea", "land"] = "land"
    value: int = Field(default=8, ge=0, le=500)
    sample_size: int = Field(default=20, ge=1, le=500)
    concentration: float = Field(default=25, gt=0, le=200)
    dispersion: float = Field(default=12, gt=0, le=200)
    event_time: datetime = DECISION_TIME
    available_at: datetime = DECISION_TIME
    source_id: Literal["synthetic-observation"] = "synthetic-observation"

    @model_validator(mode="after")
    def validate_observation(self):
        if self.event_time.tzinfo is None or self.available_at.tzinfo is None:
            raise ValueError("timezone-aware event_time and available_at are required")
        if self.event_time != DECISION_TIME or self.available_at != DECISION_TIME:
            raise ValueError("v0.2 accepts one observation available at 10:00; late/future replay not implemented")
        if self.kind == "snapshot" and self.value > self.sample_size:
            raise ValueError("delayed count exceeds observed sample size")
        return self

class Action(StrictModel):
    id: str = Field(min_length=1, max_length=24, pattern=r"^[a-zA-Z0-9_-]+$")
    label: str = Field(min_length=1, max_length=48)
    vehicle_at_h: float = Field(ge=2, le=12)
    change_fee_krw: int = Field(ge=0, le=1000000)
    is_change: bool = True
    change_cutoff_h: float | None = Field(default=3, ge=0, le=12)
    vehicle: Literal["confirmed", "unavailable", "unknown"] = "confirmed"
    reservation: Literal["confirmed", "unavailable", "unknown"] = "confirmed"
    approval: Literal["confirmed", "unavailable", "unknown"] = "confirmed"

    @model_validator(mode="after")
    def action_validity(self):
        if self.is_change and self.change_cutoff_h is None:
            raise ValueError("a changed dispatch requires a cutoff")
        if not self.is_change and self.change_fee_krw != 0:
            raise ValueError("the unchanged plan must have zero change fee")
        return self


def default_actions():
    return [Action(id="keep",label="11:30 유지",vehicle_at_h=3.5,change_fee_krw=0,is_change=False,change_cutoff_h=None),
            Action(id="a1230",label="12:30 변경",vehicle_at_h=4.5,change_fee_krw=10000,change_cutoff_h=2.5),
            Action(id="a1330",label="13:30 변경",vehicle_at_h=5.5,change_fee_krw=15000,change_cutoff_h=3)]

class RunRequest(StrictModel):
    data_type: Literal["synthetic"] = "synthetic"
    seed: int = Field(default=20261021, ge=0, le=2**32-1)
    particles: Literal[64,128,256,512] = 256
    kappa: float = Field(default=1.0, ge=0, le=3)
    ou_sigma: float = Field(default=.25, ge=0, le=.8)
    calibration: Literal["clean", "noise_a", "noise_b"] = "clean"
    observation: Observation | None = Field(default_factory=Observation)
    berth_closed_hours: float = Field(default=0, ge=0, le=14)
    queue_cap: int = Field(default=40, ge=8, le=80)
    initial_ships_at_decision: int = Field(default=2, ge=0, le=8)
    risk_limit: float = Field(default=.2, ge=0, le=1)
    actions: list[Action] = Field(default_factory=default_actions, min_length=1, max_length=8)

    @model_validator(mode="after")
    def run_validity(self):
        if self.initial_ships_at_decision > self.queue_cap:
            raise ValueError("initial ships exceed queue cap")
        if len({a.id for a in self.actions}) != len(self.actions):
            raise ValueError("action ids must be unique")
        return self

class CalibrationPoint(StrictModel):
    time_h: float = Field(ge=0, le=100)
    sea_fraction: float = Field(ge=0, le=1)
    land_fraction: float = Field(ge=0, le=1)

class CalibrationRequest(StrictModel):
    data_type: Literal["synthetic"] = "synthetic"
    observations: list[CalibrationPoint] = Field(min_length=3, max_length=101)
    known_beta_land: float = Field(default=.6, gt=0, le=5)
    known_coupling_lp: float = Field(default=.5, ge=0, le=3)
