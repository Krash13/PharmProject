"""Адаптер загрузки файлов ZINC22.

Скачивание потоковое, с ретраями и докачкой (HTTP Range). Данные раздаются
tranche-файлами (например .smi.gz) с files.docking.org.
"""

from __future__ import annotations

import hashlib
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

import httpx
import tenacity

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return False


@dataclass
class DownloadResult:
    path: Path
    bytes: int
    resumed: bool


class Zinc22Client:
    """Скачивает файлы из ZINC22 с ретраями и докачкой."""

    def __init__(
        self,
        base_url: str = "https://files.docking.org/",
        timeout: float = 60.0,
        max_retries: int = 5,
        retry_wait: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_wait = retry_wait
        self._client = client

    def _make_client(self):
        if self._client is not None:
            return nullcontext(self._client)
        # trust_env=False: обходим системный прокси Windows (VPN прописывает прокси,
        # который ломает TLS-рукопожатие до docking.org).
        return httpx.Client(timeout=self.timeout, follow_redirects=True, trust_env=False)

    def build_url(self, tranche: str) -> str:
        if tranche.startswith(("http://", "https://")):
            return tranche
        return self.base_url.rstrip("/") + "/" + tranche.lstrip("/")

    def download(
        self,
        url: str,
        dest: Path,
        expected_size: int | None = None,
        checksum: str | None = None,
    ) -> DownloadResult:
        """Скачивает файл в dest. При обрыве докачивает с места остановки."""
        part = Path(str(dest) + ".part")
        dest.parent.mkdir(parents=True, exist_ok=True)
        start = part.stat().st_size if part.exists() else 0

        self._stream_to_part(url, part)

        part.replace(dest)
        size = dest.stat().st_size
        if expected_size is not None and size != expected_size:
            raise RuntimeError(f"Размер {dest.name} = {size}, ожидалось {expected_size}")
        if checksum is not None:
            self._verify_checksum(dest, checksum)
        return DownloadResult(path=dest, bytes=size, resumed=start > 0)

    def _stream_to_part(self, url: str, part: Path) -> None:
        retrying = tenacity.Retrying(
            retry=tenacity.retry_if_exception(_retryable),
            wait=tenacity.wait_exponential_jitter(multiplier=self.retry_wait, max=30.0),
            stop=tenacity.stop_after_attempt(self.max_retries),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                self._download_once(url, part)

    def _download_once(self, url: str, part: Path) -> None:
        resumed = part.exists() and part.stat().st_size > 0
        headers = {"Range": f"bytes={part.stat().st_size}-"} if resumed else {}
        with self._make_client() as client:
            with client.stream("GET", url, headers=headers) as resp:
                if resp.status_code == 416:
                    return  # файл уже полный
                resp.raise_for_status()
                mode = "ab" if resp.status_code == 206 else "wb"
                with part.open(mode) as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)

    def _verify_checksum(self, path: Path, checksum: str) -> None:
        algo, _, expected = checksum.partition(":")
        if not expected:
            expected, algo = checksum, "sha256"
        h = hashlib.new(algo)
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != expected:
            raise RuntimeError(f"Контрольная сумма {path.name} не совпала")
