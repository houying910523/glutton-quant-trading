from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FactorDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor_id: str
    version: str = "v1"
    factor_name: str
    category: Literal[
        "trend",
        "momentum",
        "volatility",
        "volume",
        "custom",
    ]
    compute_ref: str
    params: dict[str, Any] = Field(default_factory=dict)
    output_columns: list[str]
    storage_key: str
    description: str | None = None
    status: Literal["active", "deprecated", "disabled"] = "active"
    last_materialized_date: str | None = None


class FactorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_columns: list[str] = Field(default_factory=list)
    required_history_bars: int = 0
    output_columns: list[str] = Field(default_factory=list)
