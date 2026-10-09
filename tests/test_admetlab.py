from __future__ import annotations

import httpx

from pharmproject.adapters.admetlab import AdmetlabAdapter, _normalize_value
from pharmproject.chemistry.filters import passes_admet_filters
from pharmproject.config import AdmetRule


def test_normalize_value():
    v = _normalize_value("0.554")
    assert v == 0.554 and isinstance(v, float)
    assert _normalize_value("Accepted") == "Accepted"
    assert _normalize_value("59.4%") == "59.4%"
    assert _normalize_value("") is None


def test_string_rule():
    rules = [AdmetRule(property="Lipinski", op="==", value="Accepted")]
    assert passes_admet_filters({"Lipinski": "Accepted"}, rules) is True
    assert passes_admet_filters({"Lipinski": "Rejected"}, rules) is False


CSV = (
    "smiles,LogP,hERG,Lipinski\n"
    "CC(=O)Oc1ccccc1C(=O)O,1.237,0.015,Accepted\n"
    "CCO,-0.1,0.2,Rejected\n"
)


def test_adapter_predict_flow():
    def handler(request):
        path = request.url.path
        if path == "/service/screening/index":
            return httpx.Response(
                200, text='<input type="hidden" name="csrfmiddlewaretoken" value="TOK123">'
            )
        if path == "/service/screening/cal":
            return httpx.Response(200, text='<a href="/static/files/result.csv">download</a>')
        if path == "/static/files/result.csv":
            return httpx.Response(200, text=CSV)
        return httpx.Response(404)

    adapter = AdmetlabAdapter()
    adapter._client = httpx.Client(transport=httpx.MockTransport(handler))

    preds = adapter.predict(["CC(=O)Oc1ccccc1C(=O)O", "CCO"])
    assert len(preds) == 2
    assert preds[0]["hERG"] == 0.015
    assert preds[0]["Lipinski"] == "Accepted"
    assert preds[1]["hERG"] == 0.2
    assert preds[1]["Lipinski"] == "Rejected"
