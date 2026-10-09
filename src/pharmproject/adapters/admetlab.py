"""Адаптер ADMETlab 2.0 (веб-сервис).

Обращается к admetmesh.scbdd.com: получает CSRF-токен, отправляет SMILES батчем
(до 500) и парсит результат из CSV.
"""

from __future__ import annotations

import csv
import io
import re

import httpx
import tenacity

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_SMILES_PER_REQUEST = 500


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return False


def _normalize_value(v: str):
    """Превращает CSV-значение в float, если возможно, иначе оставляет строкой."""
    v = (v or "").strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return v


class AdmetlabAdapter:
    """Предсказывает финальные ADMET-свойства через ADMETlab 2.0."""

    def __init__(
        self,
        base_url: str = "https://admetmesh.scbdd.com",
        timeout: float = 60.0,
        max_retries: int = 5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=timeout, follow_redirects=True, trust_env=False)
        self._cache: dict[str, dict | None] = {}

    def predict(self, smiles_list: list[str]) -> list[dict | None]:
        """Предсказывает ADMET для списка SMILES (выровнено по входу), с кэшем."""
        to_fetch = [s for s in smiles_list if s not in self._cache]
        if to_fetch:
            for chunk in _chunks(to_fetch, MAX_SMILES_PER_REQUEST):
                for s, r in zip(chunk, self._predict_chunk(chunk)):
                    if r is not None:
                        self._cache[s] = r
        return [self._cache.get(s) for s in smiles_list]

    def _predict_chunk(self, smiles_list: list[str]) -> list[dict | None]:
        retrying = tenacity.Retrying(
            retry=tenacity.retry_if_exception(_retryable),
            wait=tenacity.wait_exponential_jitter(multiplier=1.0, max=30.0),
            stop=tenacity.stop_after_attempt(self.max_retries),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                return self._predict_chunk_once(smiles_list)

    def _predict_chunk_once(self, smiles_list: list[str]) -> list[dict | None]:
        # 1) CSRF-токен
        r = self._client.get(self.base_url + "/service/screening/index")
        r.raise_for_status()
        m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
        if not m:
            raise RuntimeError("Не удалось получить CSRF-токен ADMETlab")

        # 2) POST со SMILES
        data = {
            "smiles-list": "\n".join(smiles_list),
            "method": "2",
            "csrfmiddlewaretoken": m.group(1),
        }
        r2 = self._client.post(self.base_url + "/service/screening/cal", data=data)
        r2.raise_for_status()

        # 3) ссылка на CSV
        m2 = re.search(r'href="([^"]+\.csv)"', r2.text)
        if not m2:
            raise RuntimeError("Не найден CSV-результат в ответе ADMETlab")

        # 4) скачать и распарсить CSV
        csv_url = self.base_url + m2.group(1)
        r3 = self._client.get(csv_url)
        r3.raise_for_status()
        by_smiles: dict[str, dict] = {}
        for row in csv.DictReader(io.StringIO(r3.text)):
            smi = (row.get("smiles") or "").strip()
            if not smi:
                continue
            by_smiles[smi] = {k: _normalize_value(v) for k, v in row.items() if k != "smiles"}

        return [by_smiles.get(s) for s in smiles_list]


def _chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i : i + size]
