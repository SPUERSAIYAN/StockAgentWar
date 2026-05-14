from __future__ import annotations

from dataclasses import dataclass

from ..http import HttpClientError, JsonHttpClient, UrllibJsonClient
from ._coerce import _coerce_float
from .base import ProviderParseError, SignalProvider

_URL = "https://www.cmegroup.com/services/fed-funds-target/fed-funds-target.json"


def _parse_target_range(raw: str) -> tuple[float, float] | None:
    """Parse '425-450' into (4.25, 4.50)."""
    parts = raw.split("-")
    if len(parts) != 2:
        return None
    low = _coerce_float(parts[0])
    high = _coerce_float(parts[1])
    if low is None or high is None:
        return None
    return low / 100.0, high / 100.0


@dataclass(frozen=True)
class FedRateProb:
    target_low: float
    target_high: float
    probability: float


@dataclass(frozen=True)
class FedMeetingProbability:
    meeting_date: str
    current_target_low: float
    current_target_high: float
    probabilities: tuple[FedRateProb, ...]


@dataclass(frozen=True)
class FedWatchUnavailable:
    available: bool
    provider_id: str
    reason: str
    source_url: str


class CMEFedWatchProvider(SignalProvider):
    provider_id = "cme_fedwatch"
    display_name = "CME FedWatch (implied from futures)"
    capabilities = ("rate_probabilities",)

    def __init__(self, http_client: JsonHttpClient | None = None) -> None:
        self.http_client = http_client or UrllibJsonClient()

    def get_probabilities(self) -> list[FedMeetingProbability] | FedWatchUnavailable:
        try:
            data = self.http_client.get_json(_URL)
        except HttpClientError as exc:
            if _is_cme_access_blocked(exc) or _is_cme_endpoint_unavailable(exc):
                return FedWatchUnavailable(
                    available=False,
                    provider_id=self.provider_id,
                    reason=_cme_unavailable_reason(exc),
                    source_url=_URL,
                )
            raise

        meetings_raw = self._extract_meetings(data)
        if meetings_raw is None:
            raise ProviderParseError(
                "cannot locate meetings data in CME FedWatch response"
            )

        results: list[FedMeetingProbability] = []
        for m in meetings_raw:
            parsed = self._parse_meeting(m)
            if parsed is not None:
                results.append(parsed)
        return results

    @staticmethod
    def _extract_meetings(data: object) -> list[object] | None:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("meetings", "Meetings", "data"):
                val = data.get(key)
                if isinstance(val, list):
                    return val
            if "meetingDate" in data or "meeting_date" in data:
                return [data]
        return None

    @staticmethod
    def _parse_meeting(m: object) -> FedMeetingProbability | None:
        if not isinstance(m, dict):
            return None

        meeting_date = m.get("meetingDate") or m.get("meeting_date") or ""
        if not meeting_date:
            return None

        current_raw = m.get("currentTarget") or m.get("current_target") or ""
        current_range = _parse_target_range(str(current_raw))
        if current_range is None:
            return None
        current_low, current_high = current_range

        probs_raw = m.get("probabilities") or m.get("Probabilities") or {}
        probs: list[FedRateProb] = []

        if isinstance(probs_raw, dict):
            for range_key, prob_val in probs_raw.items():
                rng = _parse_target_range(str(range_key))
                p = _coerce_float(prob_val)
                if rng is None or p is None or p == 0.0:
                    continue
                probs.append(
                    FedRateProb(
                        target_low=rng[0],
                        target_high=rng[1],
                        probability=p / 100.0,
                    )
                )
        elif isinstance(probs_raw, list):
            for item in probs_raw:
                if not isinstance(item, dict):
                    continue
                range_key = item.get("range") or item.get("target") or ""
                rng = _parse_target_range(str(range_key))
                p = _coerce_float(item.get("probability") or item.get("prob"))
                if rng is None or p is None or p == 0.0:
                    continue
                probs.append(
                    FedRateProb(
                        target_low=rng[0],
                        target_high=rng[1],
                        probability=p / 100.0,
                    )
                )

        return FedMeetingProbability(
            meeting_date=str(meeting_date),
            current_target_low=current_low,
            current_target_high=current_high,
            probabilities=tuple(probs),
        )


def _is_cme_access_blocked(exc: Exception) -> bool:
    text = str(exc).lower()
    return "http 403" in text and (
        "blocked" in text
        or "suspected web scraping" in text
        or "automated" in text
        or "cmegroup.com" in text
    )


def _is_cme_endpoint_unavailable(exc: Exception) -> bool:
    text = str(exc).lower()
    return "http 404" in text and "cmegroup.com" in text


def _cme_unavailable_reason(exc: Exception) -> str:
    if _is_cme_access_blocked(exc):
        return (
            "CME blocked automated access from this IP. "
            "Use an authorized CME FedWatch API subscription for live data."
        )
    return (
        "The CME FedWatch public JSON endpoint is unavailable. "
        "Use an authorized CME FedWatch API subscription for live data."
    )
