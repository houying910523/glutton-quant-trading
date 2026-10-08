from pydantic import BaseModel, Field

from modules.core.context import ParamsProperty


class FilterMeta(BaseModel):
    label: str
    name: str
    description: str = ""
    params_schema: list[ParamsProperty] = Field(default_factory=list)
