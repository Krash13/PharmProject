from __future__ import annotations

import hashlib

import httpx
import pytest

from pharmproject.adapters.zinc22 import Zinc22Client

BODY = b"hello-zinc-data-0123456789"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_download_writes_file(tmp_path):
    def handler(request):
        return httpx.Response(200, content=BODY)

    client = Zinc22Client(client=_client(handler))
    dest = tmp_path / "tranche.smi"
    result = client.download("https://example.test/tranche.smi", dest)

    assert dest.read_bytes() == BODY
    assert result.bytes == len(BODY)
    assert result.resumed is False


def test_download_resume(tmp_path):
    ranges_seen = []

    def handler(request):
        rng = request.headers.get("Range")
        ranges_seen.append(rng)
        if rng:
            offset = int(rng.split("=")[1].split("-")[0])
            return httpx.Response(206, content=BODY[offset:])
        return httpx.Response(200, content=BODY)

    client = Zinc22Client(client=_client(handler))
    dest = tmp_path / "tranche.smi"
    part = tmp_path / "tranche.smi.part"
    part.write_bytes(BODY[:5])

    result = client.download("https://example.test/tranche.smi", dest)

    assert dest.read_bytes() == BODY
    assert result.resumed is True
    assert any(rng is not None for rng in ranges_seen)


def test_download_retries_on_5xx(tmp_path):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(200, content=BODY)

    client = Zinc22Client(client=_client(handler), max_retries=3, retry_wait=0.0)
    dest = tmp_path / "tranche.smi"
    client.download("https://example.test/tranche.smi", dest)

    assert calls["n"] == 2
    assert dest.read_bytes() == BODY


def test_download_checksum_ok(tmp_path):
    digest = "sha256:" + hashlib.sha256(BODY).hexdigest()

    def handler(request):
        return httpx.Response(200, content=BODY)

    client = Zinc22Client(client=_client(handler))
    dest = tmp_path / "tranche.smi"
    client.download("https://example.test/tranche.smi", dest, checksum=digest)


def test_download_checksum_mismatch(tmp_path):
    def handler(request):
        return httpx.Response(200, content=BODY)

    client = Zinc22Client(client=_client(handler))
    dest = tmp_path / "tranche.smi"
    with pytest.raises(RuntimeError):
        client.download("https://example.test/tranche.smi", dest, checksum="sha256:deadbeef")


def test_build_url():
    client = Zinc22Client(base_url="https://files.docking.org/")
    assert (
        client.build_url("lead-like/AA/AAAA.smi.gz")
        == "https://files.docking.org/lead-like/AA/AAAA.smi.gz"
    )
    assert client.build_url("https://other.example/x.smi") == "https://other.example/x.smi"
