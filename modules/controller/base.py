from datetime import date, datetime
from functools import wraps
from inspect import iscoroutinefunction, signature
from typing import Any, Callable

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from modules.core.logging import get_logger

logger = get_logger(__name__)


routers: list[tuple[str, APIRouter]] = []


def to_json(obj: Any) -> list | dict | str | int | float | bool | None:
    """Convert object to JSON string."""
    if isinstance(obj, list):
        return [to_json(item) for item in obj]
    if isinstance(obj, tuple):
        return [to_json(item) for item in obj]
    if isinstance(obj, dict):
        return {key: to_json(value) for key, value in obj.items()}
    if isinstance(obj, (int, float, bool, str)):
        return obj
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    return obj


def wrap_response(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorate response with status code 200."""

    if iscoroutinefunction(func):

        @wraps(func)
        async def decorator(*args: Any, **kwargs: Any) -> JSONResponse:
            try:
                result = await func(*args, **kwargs)
                result = to_json(result)
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "code": 200,
                        "data": result,
                    },
                )
            except Exception as e:
                logger.exception("Error in %s: %s", func.__name__, e)
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "code": 500,
                        "msg": str(e),
                    },
                )

        decorator.__signature__ = signature(func).replace(
            return_annotation=JSONResponse
        )
        return decorator

    @wraps(func)
    def decorator(*args: Any, **kwargs: Any) -> JSONResponse:
        try:
            result = func(*args, **kwargs)
            result = to_json(result)
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "code": 200,
                    "data": result,
                },
            )
        except Exception as e:
            logger.exception("Error in %s: %s", func.__name__, e)
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "code": 500,
                    "msg": str(e),
                },
            )

    decorator.__signature__ = signature(func).replace(return_annotation=JSONResponse)
    return decorator


def rest_controller(path: str) -> Callable[[type[Any]], type[Any]]:
    """Rest controller decorator."""

    def decorator(cls: type[Any]) -> type[Any]:
        router = APIRouter()
        controller = cls()

        for attr_name in dir(controller):
            handler = getattr(controller, attr_name)
            route_path = getattr(handler, "__route_path__", None)
            route_method = getattr(handler, "__route_method__", None)

            if route_path is None or route_method is None:
                continue
            router.add_api_route(
                route_path, wrap_response(handler), methods=[route_method]
            )

        routers.append((path, router))
        return cls

    return decorator


def request_mapping(
    path: str, *, method: str
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Request mapping decorator."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "__route_path__", path)
        setattr(func, "__route_method__", method.upper())
        return func

    return decorator


def get_mapping(path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Get mapping decorator."""
    return request_mapping(path, method="GET")


def post_mapping(path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Post mapping decorator."""
    return request_mapping(path, method="POST")
