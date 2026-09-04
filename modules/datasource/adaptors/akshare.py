from __future__ import annotations

import contextlib
import io
import time
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Iterable, TypeVar

import pandas as pd

from modules.datasource.adaptors.base import (
    StockFetcher,
    TradingCalendarFetcher,
    StockDailyQuoteFetcher,
)
from modules.datasource.shared import (
    ConfigurationError,
    compact_date,
    parse_date,
    now_shanghai,
)
from modules.repositories.models import StockRecord, DailyQuoteRecord


class AkshareClient:
    def __init__(self) -> None:
        import akshare as ak

        self._client = ak

    def tool_trade_date_hist_sina(self) -> Any:
        return self._client.tool_trade_date_hist_sina()

    def stock_info_sh_name_code(self, symbol: str = "主板A股") -> Any:
        return self._client.stock_info_sh_name_code(symbol=symbol)

    def stock_info_sz_name_code(self, symbol: str = "A股列表") -> Any:
        return self._client.stock_info_sz_name_code(symbol=symbol)

    def stock_info_sh_delist(self, symbol: str = "全部") -> Any:
        return self._client.stock_info_sh_delist(symbol=symbol)

    def stock_info_sz_delist(self, symbol: str = "终止上市公司") -> Any:
        return self._client.stock_info_sz_delist(symbol=symbol)

    def stock_zh_a_hist_tx(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> Any:
        return self._client.stock_zh_a_hist_tx(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )


T = TypeVar("T")


class BaseAkshareAdapterMixin[T](ABC):
    source_name = "akshare"

    def __init__(self) -> None:
        self._client = AkshareClient()

    @staticmethod
    def _sleep(seconds: float) -> None:
        time.sleep(seconds)

    def _call_frame(
        self, function: Callable[[], pd.DataFrame | None]
    ) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with (
                    contextlib.redirect_stdout(io.StringIO()),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    frame = function()
                if frame is None:
                    return []
                return list(frame.to_dict(orient="records"))
            except Exception as exc:  # pragma: no cover - depends on remote client
                last_error = exc
                if attempt == 2:
                    break
                self._sleep(0.5 * (2**attempt))
        assert last_error is not None
        raise last_error

    def _deduplicate_records(self, payloads: Iterable[dict[str, Any]]) -> list[T]:
        deduplicated_payloads: dict[str, dict[str, Any]] = {}
        for payload in payloads:
            deduplicated_payloads[self.build_source_record_key(payload)] = payload

        records = []
        for payload in deduplicated_payloads.values():
            record = self.convert_to_record(payload)
            if record is None:
                continue
            records.append(record)
        return records

    @abstractmethod
    def build_source_record_key(self, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    def convert_to_record(self, raw: dict[str, Any]) -> T | None:
        raise NotImplementedError


class AkshareStockAdapter(StockFetcher, BaseAkshareAdapterMixin[StockRecord]):
    def fetch(self) -> list[StockRecord]:
        raw_record_list = self._fetch_batch()
        return self._deduplicate_records(raw_record_list)

    def _fetch_batch(self):
        payloads: list[dict[str, Any]] = []
        payloads.extend(
            self._annotate_records(
                self._call_frame(
                    lambda: self._client.stock_info_sh_name_code(symbol="主板A股")
                ),
                exchange="SSE",
                status="active",
                dataset="stock_info_sh_name_code",
            )
        )
        payloads.extend(
            self._annotate_records(
                self._call_frame(
                    lambda: self._client.stock_info_sz_name_code(symbol="A股列表")
                ),
                exchange="SZSE",
                status="active",
                dataset="stock_info_sz_name_code",
            )
        )
        payloads.extend(
            self._annotate_records(
                self._call_frame(
                    lambda: self._client.stock_info_sh_delist(symbol="全部")
                ),
                exchange="SSE",
                status="delisted",
                dataset="stock_info_sh_delist",
            )
        )
        payloads.extend(
            self._annotate_records(
                self._call_frame(
                    lambda: self._client.stock_info_sz_delist(symbol="终止上市公司")
                ),
                exchange="SZSE",
                status="delisted",
                dataset="stock_info_sz_delist",
            )
        )
        return payloads

    def convert_to_record(self, raw: dict[str, Any]) -> T | None:
        exchange, symbol = self._extract_stock_identity(raw)
        list_status = self._extract_stock_status(raw)
        name = self._extract_stock_name(raw)
        if exchange not in {"SSE", "SZSE"}:
            raise ValueError("unsupported exchange")
        if list_status not in {"L", "D"}:
            raise ValueError("unsupported list_status")
        if not name:
            raise ValueError("name is required")
        now = now_shanghai()
        return StockRecord(
            id=None,
            market="CN",
            exchange=exchange,
            symbol=symbol,
            ticker=symbol,
            name=name,
            asset_type="stock",
            currency="CNY",
            lot_size=100,
            listed_at=parse_date(self._extract_stock_listed_at(raw)),
            delisted_at=parse_date(self._extract_stock_delisted_at(raw)),
            status="active" if list_status == "L" else "delisted",
            created_at=now,
            updated_at=now,
        )

    def build_source_record_key(self, payload: dict[str, Any]) -> str:
        return f"{payload['_exchange']}:{payload['_symbol']}"

    @classmethod
    def _extract_stock_identity(cls, row: dict[str, Any]) -> tuple[str, str]:
        return (
            str(row.get("_exchange", "")).strip(),
            str(row.get("_symbol", "")).strip(),
        )

    @classmethod
    def _extract_stock_status(cls, row: dict[str, Any]) -> str:
        return "L" if row.get("_status") == "active" else "D"

    @classmethod
    def _extract_stock_name(cls, row: dict[str, Any]) -> str:
        for field_name in ("证券简称", "A股简称", "公司简称", "名称"):
            value = row.get(field_name)
            if value:
                return str(value).strip()
        return ""

    @classmethod
    def _extract_stock_listed_at(cls, row: dict[str, Any]) -> str | None:
        for field_name in ("上市日期", "A股上市日期"):
            value = row.get(field_name)
            if value:
                return str(value).strip()
        return None

    @classmethod
    def _extract_stock_delisted_at(cls, row: dict[str, Any]) -> str | None:
        for field_name in ("终止上市日期", "暂停上市日期"):
            value = row.get(field_name)
            if value:
                return str(value).strip()
        return None

    @classmethod
    def _annotate_records(
        cls,
        records: list[dict[str, Any]],
        *,
        exchange: str,
        status: str,
        dataset: str,
    ) -> list[dict[str, Any]]:
        annotated: list[dict[str, Any]] = []
        for row in records:
            symbol = _extract_akshare_stock_symbol(row)
            if not symbol:
                continue
            annotated.append(
                {
                    **row,
                    "_exchange": exchange,
                    "_status": status,
                    "_symbol": symbol,
                    "_dataset": dataset,
                }
            )
        return annotated


class AkshareTradingCalendarAdapter(
    TradingCalendarFetcher, BaseAkshareAdapterMixin[str]
):
    def fetch(self, start_date: str, end_date: str) -> list[str]:
        raw_list = self._call_frame(lambda: self._client.tool_trade_date_hist_sina())
        return self._deduplicate_records(raw_list)

    def convert_to_record(self, raw: dict[str, Any]) -> str | None:
        trade_date: date | None = raw.get("trade_date")
        if trade_date is None:
            return None
        return trade_date.isoformat()

    def build_source_record_key(self, payload: dict[str, Any]) -> str:
        return f"CN:{payload['trade_date']}"


class AkshareDailyQuoteAdapter(
    StockDailyQuoteFetcher, BaseAkshareAdapterMixin[DailyQuoteRecord]
):
    resource_type = "daily_quote"

    def fetch(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        stock_id: int,
        batch_id: int,
    ) -> list[DailyQuoteRecord]:
        start_date = compact_date(start_date) or "20000101"
        end_date = compact_date(end_date) or "20500101"
        records = self._fetch_symbol_history(symbol, start_date, end_date)
        records = self._deduplicate_records(records)
        for record in records:
            record.ingestion_batch_id = batch_id
            record.stock_id = stock_id
        return records

    def convert_to_record(self, raw: dict[str, Any]) -> T | None:
        trade_date = parse_date(raw.get("trade_date"))
        exchange = raw.get("exchange")
        now = now_shanghai()
        if trade_date is None:
            raise ValueError("trade_date is required")
        if exchange not in {"SSE", "SZSE"}:
            raise ValueError("unsupported exchange")
        return DailyQuoteRecord(
            id=None,
            stock_id=0,
            trade_date=trade_date,
            open=_to_cents(raw.get("open")),
            high=_to_cents(raw.get("high")),
            low=_to_cents(raw.get("low")),
            close=_to_cents(raw.get("close")),
            volume=_to_shares(raw.get("volume_raw")),
            turnover=_to_turnover_cents(raw.get("turnover_raw")),
            ingestion_batch_id=0,
            ingested_at=now,
            updated_at=now,
        )

    @classmethod
    def _to_cents(cls, value: Any) -> int:
        if value in (None, ""):
            raise ValueError("price is required")
        decimal_value = Decimal(str(value)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return int((decimal_value * 100).to_integral_value(rounding=ROUND_HALF_UP))

    def build_source_record_key(self, payload: dict[str, Any]) -> str:
        return f"{payload['_market_symbol']}:{payload['date']}"

    def _fetch_symbol_history(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        market_symbol = infer_akshare_market_symbol(symbol)
        records = self._call_frame(
            lambda: self._client.stock_zh_a_hist_tx(
                symbol=market_symbol,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            ),
        )
        return [
            {
                **row,
                "_market_symbol": market_symbol,
                "_symbol": market_symbol[2:],
                "_exchange": "SSE" if market_symbol.startswith("sh") else "SZSE",
            }
            for row in records
        ]


def infer_akshare_market_symbol(symbol: str) -> str:
    normalized = symbol.strip().lower()
    if normalized.startswith(("sh", "sz")) and len(normalized) == 8:
        return normalized
    if normalized.isdigit():
        return f"sh{normalized}" if normalized.startswith("6") else f"sz{normalized}"
    raise ConfigurationError(f"unsupported stock symbol: {symbol}")


def _extract_akshare_stock_symbol(payload: dict[str, Any]) -> str | None:
    for field_name in ("证券代码", "公司代码", "A股代码", "代码"):
        value = payload.get(field_name)
        if value:
            return str(value).strip()
    return None


def _to_cents(value: Any) -> int:
    if value in (None, ""):
        raise ValueError("price is required")
    decimal_value = Decimal(str(value)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return int((decimal_value * 100).to_integral_value(rounding=ROUND_HALF_UP))


def _to_shares(value: Any) -> int:
    if value in (None, ""):
        raise ValueError("volume is required")
    decimal_value = Decimal(str(value))
    return int(decimal_value.to_integral_value(rounding=ROUND_HALF_UP))


def _to_turnover_cents(value: Any) -> int | None:
    if value in (None, ""):
        return None
    decimal_value = Decimal(str(value))
    return int((decimal_value * 100).to_integral_value(rounding=ROUND_HALF_UP))
