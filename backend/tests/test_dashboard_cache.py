"""Tests for dashboard caching, compression, and compaction logic."""

import gzip

import orjson

from app.routes import dashboard as dash_mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _sample_dashboard_data() -> dict:
    """Minimal dashboard payload with a mix of valid and all-null tickers."""
    return {
        "dates": ["2024-01-01", "2024-02-01"],
        "tickers": ["AAPL", "MSFT", "DEAD"],
        "industries": {"AAPL": "Tech", "MSFT": "Tech", "DEAD": "Unknown"},
        "fm": {
            "AAPL": {
                "er": [1.23456789, 2.34567891],
                "eg": [3.0, 4.0],
                "pe": [10.0, 20.0],
                "rg": [0.05123, 0.06789],
                "xg": [0.10, 0.20],
                "fe": [5.0, 6.0],
            },
            "MSFT": {
                "er": [2.0, None],
                "eg": [None, 4.0],
                "pe": [15.0, 25.0],
                "rg": [0.04, 0.05],
                "xg": [0.12, 0.22],
                "fe": [7.0, 8.0],
            },
            "DEAD": {
                "er": [None, None],
                "eg": [None, None],
                "pe": [None, None],
                "rg": [None, None],
                "xg": [None, None],
                "fe": [None, None],
            },
        },
    }


# ---------------------------------------------------------------------------
# _compact_data tests
# ---------------------------------------------------------------------------


class TestCompactData:
    def test_rounds_floats_to_4dp(self) -> None:
        data = _sample_dashboard_data()
        result = dash_mod._compact_data(data)
        assert result["fm"]["AAPL"]["er"][0] == round(1.23456789, 4)
        assert result["fm"]["AAPL"]["rg"][0] == round(0.05123, 4)

    def test_strips_all_null_tickers(self) -> None:
        data = _sample_dashboard_data()
        result = dash_mod._compact_data(data)
        assert "DEAD" not in result["fm"]
        assert "DEAD" not in result["tickers"]

    def test_strips_industries_for_removed_tickers(self) -> None:
        data = _sample_dashboard_data()
        result = dash_mod._compact_data(data)
        assert "DEAD" not in result["industries"]
        assert "AAPL" in result["industries"]

    def test_preserves_valid_tickers(self) -> None:
        data = _sample_dashboard_data()
        result = dash_mod._compact_data(data)
        assert "AAPL" in result["fm"]
        assert "MSFT" in result["fm"]
        assert "AAPL" in result["tickers"]
        assert "MSFT" in result["tickers"]

    def test_preserves_none_values(self) -> None:
        data = _sample_dashboard_data()
        result = dash_mod._compact_data(data)
        assert result["fm"]["MSFT"]["er"][1] is None

    def test_no_fm_returns_unchanged(self) -> None:
        data = {"dates": [], "tickers": []}
        result = dash_mod._compact_data(data)
        assert result == data


# ---------------------------------------------------------------------------
# _make_cached_response tests
# ---------------------------------------------------------------------------


class _FakeRequest:
    """Minimal request stub for testing _make_cached_response."""

    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


class TestMakeCachedResponse:
    def _raw_and_compressed(self) -> tuple[bytes, bytes]:
        raw = orjson.dumps({"hello": "world"})
        compressed = gzip.compress(raw, compresslevel=1)
        return raw, compressed

    def test_returns_304_on_etag_match(self) -> None:
        raw, compressed = self._raw_and_compressed()
        dash_mod._cache_version = 0
        req = _FakeRequest({"if-none-match": '"42-0"'})
        resp = dash_mod._make_cached_response(req, raw, compressed, 42)
        assert resp.status_code == 304

    def test_returns_gzipped_when_accepted(self) -> None:
        raw, compressed = self._raw_and_compressed()
        req = _FakeRequest({"accept-encoding": "gzip, deflate, br"})
        resp = dash_mod._make_cached_response(req, raw, compressed, 1)
        assert resp.status_code == 200
        assert resp.headers["content-encoding"] == "gzip"
        assert gzip.decompress(resp.body) == raw

    def test_returns_raw_when_gzip_not_accepted(self) -> None:
        raw, compressed = self._raw_and_compressed()
        req = _FakeRequest({"accept-encoding": "identity"})
        resp = dash_mod._make_cached_response(req, raw, compressed, 1)
        assert resp.status_code == 200
        assert "content-encoding" not in resp.headers
        assert resp.body == raw

    def test_returns_raw_when_no_accept_encoding(self) -> None:
        raw, compressed = self._raw_and_compressed()
        req = _FakeRequest({})
        resp = dash_mod._make_cached_response(req, raw, compressed, 1)
        assert resp.body == raw

    def test_etag_includes_snapshot_id_and_version(self) -> None:
        raw, compressed = self._raw_and_compressed()
        dash_mod._cache_version = 5
        req = _FakeRequest({"accept-encoding": "gzip"})
        resp = dash_mod._make_cached_response(req, raw, compressed, 99)
        assert resp.headers["etag"] == '"99-5"'


# ---------------------------------------------------------------------------
# Cache behavior tests
# ---------------------------------------------------------------------------


class TestCacheBehavior:
    def setup_method(self) -> None:
        dash_mod._cache.clear()
        dash_mod._cache_version = 0
        dash_mod._latest_snapshot_id = None

    def test_invalidate_cache_clears_all(self) -> None:
        raw = b'{"test": true}'
        compressed = gzip.compress(raw, compresslevel=1)
        dash_mod._cache[1] = (raw, compressed)
        dash_mod._latest_snapshot_id = 1
        dash_mod.invalidate_cache()
        assert len(dash_mod._cache) == 0
        assert dash_mod._latest_snapshot_id is None

    def test_invalidate_cache_increments_version(self) -> None:
        v = dash_mod._cache_version
        dash_mod.invalidate_cache()
        assert dash_mod._cache_version == v + 1

    def test_cache_eviction_at_max(self) -> None:
        for i in range(dash_mod._MAX_CACHE + 2):
            raw = orjson.dumps({"id": i})
            gz = gzip.compress(raw, compresslevel=1)
            dash_mod._cache[i] = (raw, gz)
            if len(dash_mod._cache) > dash_mod._MAX_CACHE:
                dash_mod._cache.popitem(last=False)
        assert len(dash_mod._cache) == dash_mod._MAX_CACHE
        # Oldest entries (0, 1) should be evicted
        assert 0 not in dash_mod._cache
        assert 1 not in dash_mod._cache
