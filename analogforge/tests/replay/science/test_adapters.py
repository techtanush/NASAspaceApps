"""SCN-18: live adapters validated against mocked HTTP and format-faithful synthetic files.

No test contacts a real server and none claims validation against one.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import httpx
import numpy as np
import pytest
import rasterio
from adapter_synth import (
    HGT_VOID,
    GranuleSpec,
    World,
    global_heights,
    hgt_bytes,
    install_cmr,
    nasadem_zip,
    pds_index,
    sha256_hex,
    write_emit_nc,
    write_geotiff,
    write_pds3,
    write_pds4,
    zip_with_members,
    zip_with_symlink,
)
from rasterio.transform import from_origin

from analogforge.adapters import diviner, earthdata, emit, pds, user_survey
from analogforge.adapters.source_http import (
    AdapterError,
    ArchiveLimits,
    ExpectedChecksum,
    HttpPolicy,
    SafeHttp,
    safe_extract_zip,
)
from analogforge.adapters.source_http.errors import CODE_RETRYABLE
from analogforge.adapters.source_http.geo import coverage_fraction, split_bbox
from analogforge.ports.domain_models import AreaOfInterest
from analogforge.ports.hashing import file_sha256
from analogforge.ports.science_payloads import ResolveCoverageInput

ROOT = Path(__file__).resolve().parents[3]
CMR = "cmr.earthdata.nasa.gov"
DATA = "data.lpdaac.earthdatacloud.nasa.gov"
URS = "urs.earthdata.nasa.gov"
EARTH_HOSTS = {CMR, DATA, URS}


def request(
    adapter_id: str,
    bbox: list[float],
    *,
    body: str = "EARTH",
    kinds: tuple[str, ...] = ("elevation",),
    convention: str = "NEG180_180",
) -> ResolveCoverageInput:
    aoi = AreaOfInterest(
        body=body,
        bbox=bbox,
        longitude_convention=convention,  # type: ignore[arg-type]
        latitude_type="PLANETOCENTRIC" if body != "EARTH" else "GEODETIC",
        crs_wkt=None,
        vertical_datum="unspecified",
    )
    return ResolveCoverageInput(subject_kind="TARGET", aoi=aoi, adapter_id=adapter_id, measurement_kinds=list(kinds))


def fails(code: str, detail: str | None = None):  # type: ignore[no-untyped-def]
    """Context manager asserting an AdapterError with an exact canonical code (and detail code)."""
    return _Fails(code, detail)


class _Fails:
    def __init__(self, code: str, detail: str | None) -> None:
        self.code, self.detail = code, detail
        self._ctx = pytest.raises(AdapterError)

    def __enter__(self) -> _Fails:
        self.info = self._ctx.__enter__()
        return self

    def __exit__(self, *exc: object) -> bool | None:
        result = self._ctx.__exit__(*exc)  # type: ignore[arg-type]
        if exc[0] is not None:
            assert self.info.value.code == self.code, str(self.info.value)
            if self.detail is not None:
                assert self.info.value.detail_code == self.detail, str(self.info.value)
        return result


# ======================================== source_http
class TestTransport:
    def http(self, world: World, policy_for, hosts=("a.example",), **kw) -> SafeHttp:  # type: ignore[no-untyped-def]
        return SafeHttp(world.client(), policy_for(set(hosts), **kw))

    def test_429_retry_after_is_honoured_not_the_default_backoff(self, world, policy_for):  # type: ignore[no-untyped-def]
        state = {"n": 0}

        def route(req: httpx.Request) -> httpx.Response:
            state["n"] += 1
            if state["n"] == 1:
                return httpx.Response(429, headers={"Retry-After": "7"})
            return httpx.Response(200, json={"ok": True})

        world.routes[("a.example", "/x")] = route
        data, _ = self.http(world, policy_for).get_json("https://a.example/x")
        assert data == {"ok": True}
        assert world.sleeps == [7.0] and state["n"] == 2

    def test_backoff_is_2s_then_4s_and_stops_after_three_attempts(self, world, policy_for):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/x")] = lambda r: httpx.Response(503)
        with fails("SOURCE_UNAVAILABLE", "HTTP_503") as f:
            self.http(world, policy_for).get_json("https://a.example/x")
        assert world.sleeps == [2.0, 4.0]
        assert len(world.calls) == 3
        assert f.info.value.retryable is True

    def test_persistent_429_maps_to_rate_limited(self, world, policy_for):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/x")] = lambda r: httpx.Response(429)
        with fails("PROVIDER_RATE_LIMITED") as f:
            self.http(world, policy_for).get_json("https://a.example/x")
        assert world.sleeps == [2.0, 4.0] and f.info.value.retryable

    def test_retry_after_beyond_cap_is_not_waited_for(self, world, policy_for):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/x")] = lambda r: httpx.Response(429, headers={"Retry-After": "3600"})
        with fails("PROVIDER_RATE_LIMITED"):
            self.http(world, policy_for).get_json("https://a.example/x")
        assert world.sleeps == [] and len(world.calls) == 1

    def test_timeout_is_retried_then_reported_as_tool_timeout(self, world, policy_for):  # type: ignore[no-untyped-def]
        def boom(req: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("slow", request=req)

        world.routes[("a.example", "/x")] = boom
        with fails("TOOL_TIMEOUT") as f:
            self.http(world, policy_for).get_json("https://a.example/x")
        assert len(world.calls) == 3 and f.info.value.retryable

    @pytest.mark.parametrize("status", [401, 403])
    def test_auth_failure_is_not_retried(self, world, policy_for, status):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/x")] = lambda r: httpx.Response(status)
        with fails("PROVIDER_AUTH_FAILED", "AUTH_REQUIRED"):
            self.http(world, policy_for).get_json("https://a.example/x")
        assert len(world.calls) == 1 and world.sleeps == []

    def test_not_found_is_terminal(self, world, policy_for):  # type: ignore[no-untyped-def]
        with fails("SOURCE_UNAVAILABLE", "NOT_FOUND") as f:
            self.http(world, policy_for).get_json("https://a.example/missing")
        assert f.info.value.retryable is False and len(world.calls) == 1

    def test_html_login_page_with_200_is_rejected_for_downloads(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        page = b"<!DOCTYPE html><html><body>Earthdata Login</body></html>"
        world.routes[("a.example", "/f.zip")] = lambda r: httpx.Response(
            200, content=page, headers={"content-type": "text/html"}
        )
        dest = tmp_path / "f.zip"
        with fails("SOURCE_CONTENT_INVALID", "HTML_LOGIN_PAGE"):
            self.http(world, policy_for).download("https://a.example/f.zip", dest)
        assert not dest.exists() and not list(tmp_path.iterdir())

    def test_html_is_sniffed_even_when_content_type_claims_binary(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f.zip")] = lambda r: httpx.Response(
            200, content=b"  <html><form>login</form></html>", headers={"content-type": "application/octet-stream"}
        )
        with fails("SOURCE_CONTENT_INVALID", "HTML_LOGIN_PAGE"):
            self.http(world, policy_for).download("https://a.example/f.zip", tmp_path / "f.zip")

    def test_html_in_a_json_endpoint_is_rejected(self, world, policy_for):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/j")] = lambda r: httpx.Response(200, text="<html>login</html>")
        with fails("SOURCE_CONTENT_INVALID", "HTML_LOGIN_PAGE"):
            self.http(world, policy_for).get_json("https://a.example/j")

    def test_checksum_mismatch_quarantines_the_bytes(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        body = b"A" * 1000
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(200, content=body)
        dest = tmp_path / "sub" / "f.bin"
        wrong = ExpectedChecksum("sha256", "0" * 64)
        with fails("SOURCE_CHECKSUM_MISMATCH") as f:
            self.http(world, policy_for).download("https://a.example/f", dest, expected=wrong)
        assert f.info.value.retryable is False
        assert not dest.exists() and not list(dest.parent.iterdir())
        assert len(world.calls) == 1  # integrity failures are never retried

    @pytest.mark.parametrize("algo", ["sha256", "md5"])
    def test_matching_checksum_is_verified(self, world, policy_for, tmp_path, algo):  # type: ignore[no-untyped-def]
        import hashlib

        body = b"payload-bytes" * 50
        digest = hashlib.new(algo, body).hexdigest().upper()  # case-insensitive compare
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(200, content=body)
        res = self.http(world, policy_for).download(
            "https://a.example/f", tmp_path / "f", expected=ExpectedChecksum(algo, digest)
        )
        assert res.provider_checksum_verified and res.sha256 == sha256_hex(body)
        assert res.size_bytes == len(body) and (tmp_path / "f").read_bytes() == body

    def test_no_provider_checksum_means_not_verified(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(200, content=b"zz")
        res = self.http(world, policy_for).download("https://a.example/f", tmp_path / "f")
        assert res.provider_checksum_verified is False

    def test_redirect_never_forwards_authorization_to_another_host(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(
            302, headers={"location": "https://b.example/blob"}
        )
        world.routes[("b.example", "/blob")] = lambda r: httpx.Response(200, content=b"bytes!")
        http = self.http(world, policy_for, hosts=("a.example", "b.example"))
        res = http.download("https://a.example/f", tmp_path / "f")
        by_host = {c.host: c for c in world.calls}
        assert by_host["a.example"].headers.get("authorization") == "Bearer TEST-TOKEN"
        assert "authorization" not in by_host["b.example"].headers
        assert "cookie" not in by_host["b.example"].headers
        assert res.redirect_hosts == ("a.example", "b.example") and (tmp_path / "f").read_bytes() == b"bytes!"

    def test_redirect_to_an_approved_credential_host_keeps_authorization(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(
            302, headers={"location": "https://urs.example/login"}
        )
        world.routes[("urs.example", "/login")] = lambda r: httpx.Response(200, content=b"ok-bytes")
        http = self.http(world, policy_for, hosts=("a.example", "urs.example"), auth_hosts={"urs.example"})
        http.download("https://a.example/f", tmp_path / "f")
        assert world.calls[-1].headers.get("authorization") == "Bearer TEST-TOKEN"

    def test_client_level_auth_handler_is_also_stripped_on_foreign_hops(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(302, headers={"location": "https://b.example/x"})
        world.routes[("b.example", "/x")] = lambda r: httpx.Response(200, content=b"ok")
        client = httpx.Client(transport=httpx.MockTransport(world.handle), auth=httpx.BasicAuth("u", "secret"))
        SafeHttp(client, policy_for({"a.example", "b.example"})).download("https://a.example/f", tmp_path / "f")
        assert "authorization" in world.calls[0].headers and "authorization" not in world.calls[1].headers

    def test_redirect_to_unlisted_host_is_refused_without_contacting_it(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(
            302, headers={"location": "https://evil.example/x"}
        )
        with fails("SOURCE_CONTENT_INVALID", "HOST_NOT_ALLOWED"):
            self.http(world, policy_for).download("https://a.example/f", tmp_path / "f")
        assert "evil.example" not in world.hosts_called()

    def test_unlisted_initial_host_cinsecure_scheme_and_embedded_credentials_refused(self, world, policy_for):  # type: ignore[no-untyped-def]
        http = self.http(world, policy_for)
        with fails("SOURCE_CONTENT_INVALID", "HOST_NOT_ALLOWED"):
            http.get_bytes("https://other.example/x")
        with fails("SOURCE_CONTENT_INVALID", "INSECURE_SCHEME"):
            http.get_bytes("http://a.example/x")
        with fails("SOURCE_CONTENT_INVALID", "URL_CREDENTIALS"):
            http.get_bytes("https://user:pw@a.example/x")
        assert world.calls == []

    def test_redirect_loop_is_bounded(self, world, policy_for):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(302, headers={"location": "/f"})
        with fails("SOURCE_UNAVAILABLE", "TOO_MANY_REDIRECTS"):
            self.http(world, policy_for, max_redirects=3).get_bytes("https://a.example/f")
        assert len(world.calls) == 4

    def test_declared_and_streamed_size_limits(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/big")] = lambda r: httpx.Response(200, content=b"x" * 5000)
        http = self.http(world, policy_for)
        with fails("RESOURCE_LIMIT"):
            http.download("https://a.example/big", tmp_path / "big", max_bytes=1000)
        assert not (tmp_path / "big").exists() and not list(tmp_path.iterdir())

        def chunked(r: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=(b"y" * 100 for _ in range(50)))  # no content-length

        world.routes[("a.example", "/stream")] = chunked
        with fails("RESOURCE_LIMIT"):
            http.download("https://a.example/stream", tmp_path / "s", max_bytes=1000)
        with fails("RESOURCE_LIMIT"):
            http.get_bytes("https://a.example/big", max_bytes=100)

    def test_truncated_transfer_is_detected_and_retried(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/t")] = lambda r: httpx.Response(
            200, content=b"p" * 100, headers={"content-length": "250"}
        )
        with fails("SOURCE_CONTENT_INVALID", "TRUNCATED_TRANSFER"):
            self.http(world, policy_for).download("https://a.example/t", tmp_path / "t")
        assert len(world.calls) == 3 and world.sleeps == [2.0, 4.0]
        assert not list(tmp_path.iterdir())

    def test_empty_body_and_wrong_magic_and_content_type_rejected(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/e")] = lambda r: httpx.Response(200, content=b"")
        world.routes[("a.example", "/m")] = lambda r: httpx.Response(200, content=b"NOTZIP-DATA")
        world.routes[("a.example", "/c")] = lambda r: httpx.Response(
            200, content=b"PK", headers={"content-type": "image/png"}
        )
        http = self.http(world, policy_for)
        with fails("SOURCE_CONTENT_INVALID", "EMPTY_BODY"):
            http.download("https://a.example/e", tmp_path / "e")
        with fails("SOURCE_CONTENT_INVALID", "MAGIC_MISMATCH"):
            http.download("https://a.example/m", tmp_path / "m", expected_magic=b"PK")
        with fails("SOURCE_CONTENT_INVALID", "CONTENT_TYPE_UNEXPECTED"):
            http.download("https://a.example/c", tmp_path / "c", accept_content_types=("application/zip",))

    def test_policy_rejects_unbounded_retries(self):
        with pytest.raises(ValueError):
            HttpPolicy(allowed_hosts=frozenset({"a"}), max_attempts=4)

    def test_error_codes_are_canonical_and_retryability_matches_the_kit(self):
        kit = {
            c["code"]: c["retryable"] for c in json.loads((ROOT / "contracts/error-codes.json").read_text())["codes"]
        }
        assert set(CODE_RETRYABLE) <= set(kit)
        for code, retryable in CODE_RETRYABLE.items():
            assert kit[code] == retryable, code
        with pytest.raises(ValueError):
            AdapterError("MADE_UP_CODE", "x")
        issue = AdapterError("NO_COVERAGE", "none", detail_code="NO_GRANULES").to_issue()
        assert issue.code == "NO_COVERAGE" and issue.detail_code == "NO_GRANULES" and not issue.retryable


class TestArchiveSafety:
    LIMITS = ArchiveLimits(max_members=8)

    def test_good_archive_extracts_and_dry_run_writes_nothing(self, tmp_path):
        z = zip_with_members(tmp_path / "ok.zip", {"a.hgt": np.random.default_rng(1).bytes(4000), "a.num": b"1" * 50})
        out = safe_extract_zip(z, tmp_path / "out", self.LIMITS)
        assert [p.name for p in out] == ["a.hgt", "a.num"] and (tmp_path / "out" / "a.hgt").stat().st_size == 4000
        safe_extract_zip(z, tmp_path / "dry", self.LIMITS, extract=False)
        assert not (tmp_path / "dry").exists()

    @pytest.mark.parametrize(
        "name", ["../evil.hgt", "/abs/evil.hgt", "a/../../evil.hgt", "..\\evil.hgt", "C:/evil.hgt"]
    )
    def test_path_traversal_variants(self, tmp_path, name):
        z = zip_with_members(tmp_path / "bad.zip", {name: b"x"})
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_PATH_TRAVERSAL"):
            safe_extract_zip(z, tmp_path / "out", self.LIMITS)
        assert not (tmp_path / "evil.hgt").exists()

    def test_symlink_member(self, tmp_path):
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_SYMLINK"):
            safe_extract_zip(zip_with_symlink(tmp_path / "s.zip"), tmp_path / "out", self.LIMITS)

    def test_nested_archive(self, tmp_path):
        inner = zip_with_members(tmp_path / "inner.zip", {"x.hgt": b"1"}).read_bytes()
        z = zip_with_members(tmp_path / "outer.zip", {"inner.zip": inner})
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_NESTED"):
            safe_extract_zip(z, tmp_path / "out", self.LIMITS)

    def test_expansion_bomb_over_20x(self, tmp_path):
        z = zip_with_members(tmp_path / "bomb.zip", {"zeros.hgt": b"\x00" * 2_000_000})
        assert z.stat().st_size * 20 < 2_000_000
        with fails("RESOURCE_LIMIT", "ARCHIVE_EXPANSION_LIMIT"):
            safe_extract_zip(z, tmp_path / "out", ArchiveLimits())
        assert not (tmp_path / "out").exists()

    def test_lying_central_directory_is_caught_while_copying(self, tmp_path):
        z = zip_with_members(tmp_path / "lie.zip", {"zeros.hgt": b"\x00" * 2_000_000})
        raw = bytearray(z.read_bytes())
        # Falsify the declared uncompressed size in both the local header and the central directory.
        for sig, off in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
            i = raw.index(sig)
            raw[i + off : i + off + 4] = (100).to_bytes(4, "little")
        z.write_bytes(bytes(raw))
        with pytest.raises(AdapterError) as err:
            safe_extract_zip(z, tmp_path / "out", ArchiveLimits())
        assert err.value.code in {"RESOURCE_LIMIT", "SOURCE_CONTENT_INVALID"}

    def test_member_count_and_unexpected_member_and_duplicates(self, tmp_path):
        many = zip_with_members(tmp_path / "many.zip", {f"f{i}.hgt": b"a" * 10 for i in range(9)})
        with fails("RESOURCE_LIMIT", "ARCHIVE_MEMBER_LIMIT"):
            safe_extract_zip(many, tmp_path / "o1", self.LIMITS)
        odd = zip_with_members(tmp_path / "odd.zip", {"run.sh": b"echo hi" * 10})
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_UNEXPECTED_MEMBER"):
            safe_extract_zip(odd, tmp_path / "o2", ArchiveLimits(allowed_suffixes=frozenset({".hgt"})))
        dup = tmp_path / "dup.zip"
        with zipfile.ZipFile(dup, "w") as zf:
            zf.writestr("a.hgt", b"1" * 40)
            zf.writestr("A.hgt", b"2" * 40)
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_DUPLICATE_MEMBER"):
            safe_extract_zip(dup, tmp_path / "o3", self.LIMITS)

    def test_not_a_zip_and_corrupt_member(self, tmp_path):
        junk = tmp_path / "junk.zip"
        junk.write_bytes(b"this is not a zip archive at all")
        with fails("SOURCE_CONTENT_INVALID", "BAD_ARCHIVE"):
            safe_extract_zip(junk, tmp_path / "o1", self.LIMITS)
        z = zip_with_members(
            tmp_path / "crc.zip", {"a.hgt": np.random.default_rng(2).bytes(2000)}, compress=zipfile.ZIP_STORED
        )
        raw = bytearray(z.read_bytes())
        raw[60] ^= 0xFF  # flip a payload byte; CRC must now fail
        z.write_bytes(bytes(raw))
        with fails("SOURCE_CONTENT_INVALID", "BAD_ARCHIVE"):
            safe_extract_zip(z, tmp_path / "o2", self.LIMITS)


class TestGeo:
    def test_wraps_and_converts_between_longitude_conventions(self):
        assert split_bbox([350, -10, 10, 10], "ZERO_360", "ZERO_360") == [
            (350.0, -10.0, 360.0, 10.0),
            (0.0, -10.0, 10.0, 10.0),
        ]
        assert split_bbox([350, -10, 10, 10], "ZERO_360", "NEG180_180") == [(-10.0, -10.0, 10.0, 10.0)]
        assert split_bbox([-170, 0, 170, 5], "NEG180_180", "NEG180_180") == [(-170.0, 0.0, 170.0, 5.0)]
        assert split_bbox([170, 0, -170, 5], "NEG180_180", "NEG180_180") == [
            (170.0, 0.0, 180.0, 5.0),
            (-180.0, 0.0, -170.0, 5.0),
        ]
        assert split_bbox([-90, 0, -80, 5], "NEG180_180", "ZERO_360") == [(270.0, 0.0, 280.0, 5.0)]

    def test_invalid_bbox_rejected(self):
        with fails("NO_COVERAGE", "INPUT_INVALID"):
            split_bbox([0, 10, 5, 5], "NEG180_180", "NEG180_180")
        with fails("NO_COVERAGE", "INPUT_INVALID"):
            split_bbox([0, 0, 500, 5], "NEG180_180", "NEG180_180")

    def test_coverage_fraction_is_geometric(self):
        assert coverage_fraction([(0, 0, 2, 2)], [(0, 0, 1, 2)]) == pytest.approx(0.5)
        assert coverage_fraction([(0, 0, 2, 2)], [(0, 0, 1, 2), (1, 0, 2, 1)]) == pytest.approx(0.75)
        assert coverage_fraction([(0, 0, 2, 2)], [(5, 5, 6, 6)]) == 0.0
        assert coverage_fraction([(0, 0, 2, 2)], []) == 0.0


# ======================================== earthdata / NASADEM
class TestNasademDecode:
    N = 11

    def params(self, tmp_path: Path) -> earthdata.NasademParams:
        return earthdata.NasademParams(expected_samples=self.N, work_dir=tmp_path / "members")

    def test_big_endian_int16_voids_num_and_water_stay_separate(self, tmp_path):
        h = global_heights(self.N, self.N)
        h[0, 0] = 0x0102  # distinguishes big- from little-endian decoding
        h[3, 4] = HGT_VOID
        water = np.zeros((self.N, self.N), dtype=bool)
        water[5:7, 5:7] = True
        z = nasadem_zip(tmp_path / "NASADEM_HGT_n30w100.zip", "n30w100", h, water=water)
        out = earthdata.decode(z, self.params(tmp_path))
        assert out.data[0, 0] == 258.0 and out.data[1, 1] == float(h[1, 1])
        assert np.isnan(out.data[3, 4]) and not out.valid[3, 4] and out.valid.sum() == h.size - 1
        np.testing.assert_array_equal(out.data[out.valid], h[out.valid].astype(float))
        assert (
            out.aux["water"].sum() == 4 and out.aux["land"].sum() == h.size - 1 - 4
        )  # water cell valid height but not land
        assert out.valid[5, 5] and not out.aux["land"][5, 5]
        assert out.aux["num"].dtype == np.uint8 and out.aux["num"].shape == h.shape
        assert not np.array_equal(out.aux["num"].astype(float), out.data)  # NUM is not a height/uncertainty
        m = out.metadata
        assert "EGM96" in (m.vertical_reference or "") and m.body == "EARTH" and m.units == "m"
        step = 1.0 / (self.N - 1)
        assert m.transform == (
            pytest.approx(step),
            0.0,
            pytest.approx(-100 - step / 2),
            0.0,
            pytest.approx(-step),
            pytest.approx(31 + step / 2),
        )
        assert any("NUM is a coded source indicator" in n for n in m.notes)

    def test_missing_water_member_is_disclosed_not_assumed_land(self, tmp_path):
        z = nasadem_zip(tmp_path / "t.zip", "s10e020", global_heights(self.N, self.N), num=False)
        out = earthdata.decode(z, self.params(tmp_path))
        assert "num" not in out.aux
        assert any("No water-body" in n for n in out.metadata.notes)
        assert out.metadata.attributes["tile_lat0"] == "-10" and out.metadata.attributes["tile_lon0"] == "20"

    def test_shape_checks(self, tmp_path):
        good = global_heights(self.N, self.N)
        z = zip_with_members(tmp_path / "short.zip", {"n30w100.hgt": hgt_bytes(good)[:-2]})
        with fails("SOURCE_CONTENT_INVALID", "SHAPE_MISMATCH"):
            earthdata.decode(z, self.params(tmp_path))
        z2 = zip_with_members(tmp_path / "rect.zip", {"n30w100.hgt": hgt_bytes(global_heights(4, 6))})
        with fails("SOURCE_CONTENT_INVALID", "SHAPE_MISMATCH"):
            earthdata.decode(z2, earthdata.NasademParams(expected_samples=None, work_dir=tmp_path / "w2"))
        with fails("SOURCE_CONTENT_INVALID", "SHAPE_MISMATCH"):  # standard-size policy rejects an 11x11 tile
            earthdata.decode(
                nasadem_zip(tmp_path / "ok.zip", "n30w100", good), earthdata.NasademParams(work_dir=tmp_path / "w3")
            )
        bad_num = zip_with_members(tmp_path / "num.zip", {"n30w100.hgt": hgt_bytes(good), "n30w100.num": b"\x01" * 7})
        with fails("SOURCE_CONTENT_INVALID", "SHAPE_MISMATCH"):
            earthdata.decode(bad_num, earthdata.NasademParams(expected_samples=self.N, work_dir=tmp_path / "w4"))

    def test_standard_1201_tile_and_bare_hgt(self, tmp_path):
        arr = global_heights(1201, 1201, seed=3)
        (tmp_path / "n45e010.hgt").write_bytes(hgt_bytes(arr))
        out = earthdata.decode(tmp_path / "n45e010.hgt")
        assert out.data.shape == (1201, 1201) and out.data[600, 600] == float(arr[600, 600])
        assert out.metadata.attributes["samples_per_side"] == "1201"

    def test_name_and_member_errors(self, tmp_path):
        with fails("SOURCE_CONTENT_INVALID", "METADATA_INCOMPLETE"):
            earthdata.decode(
                zip_with_members(tmp_path / "x.zip", {"tile.hgt": hgt_bytes(global_heights(self.N, self.N))}),
                self.params(tmp_path),
            )
        with fails("SOURCE_CONTENT_INVALID", "METADATA_INCOMPLETE"):
            earthdata.decode(
                zip_with_members(tmp_path / "y.zip", {"n30w100.num": b"1" * 121}),
                earthdata.NasademParams(expected_samples=self.N, work_dir=tmp_path / "wy"),
            )

    def test_hostile_zip_is_refused_by_decode(self, tmp_path):
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_PATH_TRAVERSAL"):
            earthdata.decode(zip_with_members(tmp_path / "t.zip", {"../n30w100.hgt": b"x"}), self.params(tmp_path))
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_UNEXPECTED_MEMBER"):
            earthdata.decode(zip_with_members(tmp_path / "u.zip", {"n30w100.exe": b"MZ" * 50}), self.params(tmp_path))


class TestNasademMosaic:
    N = 11

    def tiles(self, tmp_path: Path, g: np.ndarray, names: dict[tuple[int, int], str]) -> list:
        out = []
        step = self.N - 1
        for (r, c), name in names.items():
            sub = g[r * step : r * step + self.N, c * step : c * step + self.N]
            z = nasadem_zip(tmp_path / f"{name}.zip", name, sub)
            out.append(earthdata.decode(z, earthdata.NasademParams(expected_samples=self.N, work_dir=tmp_path / name)))
        return out

    def test_seams_are_deduplicated_and_equal_the_source_grid(self, tmp_path):
        step = self.N - 1
        g = global_heights(2 * step + 1, 2 * step + 1, seed=11)  # 2x2 tiles share borders
        # rows: top row = lat 31 tiles (n30), bottom n29; cols: w101 (west), w100 (east)
        names = {(0, 0): "n30w101", (0, 1): "n30w100", (1, 0): "n29w101", (1, 1): "n29w100"}
        merged = earthdata.mosaic(list(reversed(self.tiles(tmp_path, g, names))))  # input order must not matter
        assert merged.data.shape == g.shape == (21, 21)
        np.testing.assert_array_equal(merged.data, g.astype(float))
        assert merged.valid.all()
        assert merged.metadata.attributes["seam_mismatch_cells"] == "0"
        # independent derivation: 4 tiles x 121 samples minus the 21 x 21 unique samples of the mosaic
        assert int(merged.metadata.attributes["seam_deduplicated_samples"]) == 4 * 121 - 21 * 21 == 43
        step_deg = 1.0 / step
        assert merged.metadata.transform == (
            pytest.approx(step_deg),
            0.0,
            pytest.approx(-101 - step_deg / 2),
            0.0,
            pytest.approx(-step_deg),
            pytest.approx(31 + step_deg / 2),
        )

    def test_disagreeing_seam_is_reported_and_first_tile_wins(self, tmp_path):
        step = self.N - 1
        g = global_heights(self.N, 2 * step + 1, seed=5)
        east = g.copy()
        east[:, step] = (east[:, step] + 1).astype(np.int16)  # the shared column of the east tile differs by 1 m
        t_w = nasadem_zip(tmp_path / "w.zip", "n30w101", g[:, : self.N])
        t_e = nasadem_zip(tmp_path / "e.zip", "n30w100", east[:, step:])
        params = lambda n: earthdata.NasademParams(expected_samples=self.N, work_dir=tmp_path / n)  # noqa: E731
        merged = earthdata.mosaic([earthdata.decode(t_e, params("e")), earthdata.decode(t_w, params("w"))])
        assert merged.metadata.attributes["seam_mismatch_cells"] == str(self.N)
        assert any("disagreed" in n for n in merged.metadata.notes)
        # Precedence is lexicographic tile name (n30w100 < n30w101): the east tile's value wins, not an average.
        np.testing.assert_array_equal(merged.data[:, step], east[:, step].astype(float))
        assert not np.array_equal(merged.data[:, step], g[:, step].astype(float))

    def test_missing_tile_leaves_invalid_gap_not_zero(self, tmp_path):
        step = self.N - 1
        g = global_heights(2 * step + 1, 2 * step + 1, seed=2)
        merged = earthdata.mosaic(self.tiles(tmp_path, g, {(0, 0): "n30w101", (1, 1): "n29w100"}))
        assert not merged.valid[0, 20] and np.isnan(merged.data[0, 20])  # NE quadrant has no tile
        assert merged.valid[0, 0] and merged.valid[20, 20]
        assert 0.4 < merged.valid_fraction < 0.6 and not merged.aux["covered"].all()

    def test_duplicate_and_mixed_shape_tiles_rejected(self, tmp_path):
        g = global_heights(self.N, self.N)
        a = self.tiles(tmp_path, g, {(0, 0): "n30w101"})[0]
        with fails("SOURCE_CONTENT_INVALID", "DUPLICATE_TILE"):
            earthdata.mosaic([a, a])
        big = earthdata.decode(
            nasadem_zip(tmp_path / "b.zip", "n30w100", global_heights(13, 13)),
            earthdata.NasademParams(expected_samples=13, work_dir=tmp_path / "bw"),
        )
        with fails("SOURCE_CONTENT_INVALID", "SHAPE_MISMATCH"):
            earthdata.mosaic([a, big])
        with fails("NO_COVERAGE", "NO_GRANULES"):
            earthdata.mosaic([])


# ======================================== earthdata / discovery + fetch
def granules(tmp_path: Path, count: int = 3) -> list[GranuleSpec]:
    out = []
    for i in range(count):
        name = f"n30w{101 - i}"
        z = nasadem_zip(tmp_path / f"{name}.zip", name, global_heights(11, 11, seed=i))
        payload = z.read_bytes()
        out.append(
            GranuleSpec(
                f"G{i:03d}-LPDAAC",
                f"NASADEM_HGT_{name}",
                (-101.0 + i, 30.0, -100.0 + i, 31.0),
                f"https://{DATA}/nasadem/NASADEM_HGT_{name}.zip?token=SIGNED-SECRET",
                payload,
                checksum=sha256_hex(payload),
            )
        )
    return out


class TestEarthdataDiscovery:
    def test_deterministic_sort_is_independent_of_server_order_and_params_are_correct(
        self, world, policy_for, tmp_path
    ):
        gs = granules(tmp_path)
        install_cmr(world, gs, reverse_order=True)
        req = request(earthdata.NASADEM_ADAPTER_ID, [-100.5, 30.2, -99.5, 30.8])
        (sel,) = earthdata.discover(req, world.client(), policy=policy_for(EARTH_HOSTS))
        hit = [g for g in gs if g.box[0] < -99.5 and g.box[2] > -100.5]
        assert sel.granule_ids == [g.concept_id for g in sorted(hit, key=lambda g: g.granule_ur)]
        assert sel.granule_ids == ["G001-LPDAAC", "G000-LPDAAC"]  # ordered by granule_ur, not by server order
        world2 = World()
        install_cmr(world2, gs, reverse_order=False)
        (sel2,) = earthdata.discover(req, world2.client(), policy=policy_for(EARTH_HOSTS))
        assert sel2 == sel  # same selection (incl. key) whatever order the server used
        q = httpx.URL(world.calls[0].url).params
        assert q["short_name"] == "NASADEM_HGT" and q["version"] == "001" and q["bounding_box"].startswith("-100.5")
        assert q["sort_key[]"] == "producer_granule_id"
        assert sel.access_state == "AVAILABLE" and sel.coverage_fraction == pytest.approx(1.0)
        assert sel.native_resolution_m == pytest.approx(30.9)

    def test_partial_coverage_fraction_is_geometric(self, world, policy_for, tmp_path):
        install_cmr(world, granules(tmp_path, 1))  # covers lon -101..-100 only
        req = request(earthdata.NASADEM_ADAPTER_ID, [-101.0, 30.0, -99.0, 31.0])
        (sel,) = earthdata.discover(req, world.client(), policy=policy_for(EARTH_HOSTS))
        assert sel.coverage_fraction == pytest.approx(0.5)

    def test_missing_credential_yields_auth_required_but_keeps_the_coverage(self, world, policy_for, tmp_path):
        install_cmr(world, granules(tmp_path))
        req = request(earthdata.NASADEM_ADAPTER_ID, [-100.5, 30.2, -99.5, 30.8])
        (sel,) = earthdata.discover(req, world.client(bearer=None), policy=policy_for(EARTH_HOSTS))
        assert sel.access_state == "AUTH_REQUIRED" and sel.granule_ids and sel.coverage_fraction == pytest.approx(1.0)
        assert any("Earthdata Login" in n for n in sel.notes)

    def test_no_overlap_is_a_valid_no_coverage_result(self, world, policy_for, tmp_path):
        install_cmr(world, granules(tmp_path))
        req = request(earthdata.NASADEM_ADAPTER_ID, [10.0, 10.0, 11.0, 11.0])
        (sel,) = earthdata.discover(req, world.client(), policy=policy_for(EARTH_HOSTS))
        assert sel.access_state == "NO_COVERAGE" and sel.coverage_fraction == 0.0 and sel.granule_ids == []

    def test_polar_aoi_is_no_coverage_without_any_request(self, world, policy_for):
        req = request(earthdata.NASADEM_ADAPTER_ID, [0.0, 70.0, 5.0, 75.0])
        (sel,) = earthdata.discover(req, world.client(), policy=policy_for(EARTH_HOSTS))
        assert sel.access_state == "NO_COVERAGE" and world.calls == []

    def test_unsupported_measurement_kind_and_wrong_body_and_unknown_adapter(self, world, policy_for):
        (sel,) = earthdata.discover(
            request(earthdata.NASADEM_ADAPTER_ID, [-100, 30, -99, 31], kinds=("rock_abundance",)),
            world.client(),
            policy=policy_for(EARTH_HOSTS),
        )
        assert sel.access_state == "UNSUPPORTED" and world.calls == []
        with fails("UNSUPPORTED_PRODUCT", "BODY_MISMATCH"):
            earthdata.discover(request(earthdata.NASADEM_ADAPTER_ID, [0, 0, 5, 5], body="MARS"), world.client())
        with fails("UNSUPPORTED_PRODUCT"):
            earthdata.discover(request("earth_made_up", [-100, 30, -99, 31]), world.client())

    def test_offline_client_none_is_unavailable(self):
        (sel,) = earthdata.discover(request(earthdata.NASADEM_ADAPTER_ID, [-100, 30, -99, 31]), None)
        assert sel.access_state == "UNAVAILABLE"

    def test_srtm_alternate_is_an_explicit_separate_selector(self, world, policy_for, tmp_path):
        install_cmr(world, granules(tmp_path))
        earthdata.discover(
            request(earthdata.SRTMGL1_ADAPTER_ID, [-100.5, 30.2, -99.5, 30.8]),
            world.client(),
            policy=policy_for(EARTH_HOSTS),
        )
        q = httpx.URL(world.calls[0].url).params
        assert q["short_name"] == "SRTMGL1" and q["version"] == "003"

    def test_page_cap_truncation_is_disclosed(self, world, policy_for, tmp_path):
        gs = [
            GranuleSpec(f"G{i:03d}", f"UR{i:03d}", (-100.0, 30.0, -99.0, 31.0), f"https://{DATA}/f{i}.zip", b"x")
            for i in range(7)
        ]
        install_cmr(world, gs, reverse_order=False)
        req = request(earthdata.NASADEM_ADAPTER_ID, [-100.0, 30.0, -99.0, 31.0])
        (sel,) = earthdata.discover(req, world.client(), policy=policy_for(EARTH_HOSTS), page_size=2, max_pages=2)
        assert sel.granule_ids == ["G000", "G001", "G002", "G003"]
        assert any(n.startswith("DISCOVERY_TRUNCATED") and "4 of 7" in n for n in sel.notes)
        assert sum(1 for c in world.calls) == 2  # the cap stopped paging
        # A cap that is large enough returns everything and discloses nothing.
        w2 = World()
        install_cmr(w2, gs, reverse_order=False)
        (full,) = earthdata.discover(req, w2.client(), policy=policy_for(EARTH_HOSTS), page_size=2, max_pages=10)
        assert len(full.granule_ids) == 7 and not any("TRUNCATED" in n for n in full.notes)

    def test_truncation_is_disclosed_even_without_a_hit_count(self, world, policy_for):
        gs = [
            GranuleSpec(f"G{i:03d}", f"UR{i:03d}", (-100.0, 30.0, -99.0, 31.0), f"https://{DATA}/f{i}.zip", b"x")
            for i in range(5)
        ]
        install_cmr(world, gs, reverse_order=False, hits_header=False)
        (sel,) = earthdata.discover(
            request(earthdata.NASADEM_ADAPTER_ID, [-100, 30, -99, 31]),
            world.client(),
            policy=policy_for(EARTH_HOSTS),
            page_size=2,
            max_pages=2,
        )
        assert len(sel.granule_ids) == 4 and any("DISCOVERY_TRUNCATED" in n for n in sel.notes)

    def test_antimeridian_aoi_queries_two_boxes(self, world, policy_for):
        install_cmr(world, [])
        earthdata.discover(
            request(earthdata.NASADEM_ADAPTER_ID, [179.5, 10.0, -179.5, 11.0]),
            world.client(),
            policy=policy_for(EARTH_HOSTS),
        )
        boxes = sorted(httpx.URL(c.url).params["bounding_box"] for c in world.calls)
        assert boxes == ["-180.000000,10.000000,-179.500000,11.000000", "179.500000,10.000000,180.000000,11.000000"]


class TestEarthdataFetch:
    def selection(self, world, policy_for, tmp_path, count=1, bearer="TEST-TOKEN"):  # type: ignore[no-untyped-def]
        gs = granules(tmp_path, count)
        install_cmr(world, gs)
        req = request(earthdata.NASADEM_ADAPTER_ID, [-100.9, 30.1, -99.1, 30.9])
        client = world.client(bearer=bearer)
        (sel,) = earthdata.discover(req, client, policy=policy_for(EARTH_HOSTS, {URS}))
        return gs, sel, client

    def test_fetch_verifies_checksum_strips_query_and_decodes(self, world, policy_for, tmp_path):
        gs, sel, client = self.selection(world, policy_for, tmp_path)
        scratch = tmp_path / "scratch"
        (asset,) = earthdata.fetch(sel, client, scratch, policy=policy_for(EARTH_HOSTS, {URS}))
        path = earthdata.asset_path(scratch, asset)
        assert asset.validation_status == "VERIFIED" and asset.sha256 == file_sha256(path) == sha256_hex(gs[0].payload)
        assert (
            asset.size_bytes == len(gs[0].payload)
            and asset.source_uri == f"https://{DATA}/nasadem/NASADEM_HGT_n30w101.zip"
        )
        assert "?" not in asset.source_uri and "SIGNED-SECRET" not in asset.model_dump_json()
        assert asset.granule_id == gs[0].concept_id and asset.artifact_key.startswith("source-bytes:")
        assert scratch.resolve() in path.resolve().parents
        dl = [c for c in world.calls if c.host == DATA][-1]
        assert dl.headers["authorization"] == "Bearer TEST-TOKEN"
        decoded = earthdata.decode(path, earthdata.NasademParams(expected_samples=11, work_dir=tmp_path / "w"))
        assert decoded.valid.all()

    def test_provider_without_checksum_is_pending_not_verified(self, world, policy_for, tmp_path):
        g = granules(tmp_path, 1)[0]
        g = GranuleSpec(g.concept_id, g.granule_ur, g.box, g.download_url, g.payload, checksum=None)
        install_cmr(world, [g])
        client = world.client()
        (sel,) = earthdata.discover(
            request(earthdata.NASADEM_ADAPTER_ID, [-100.9, 30.1, -100.1, 30.9]), client, policy=policy_for(EARTH_HOSTS)
        )
        (asset,) = earthdata.fetch(sel, client, tmp_path / "s", policy=policy_for(EARTH_HOSTS))
        assert asset.validation_status == "PENDING"

    def test_fetch_without_credentials_is_auth_required_and_makes_no_download(self, world, policy_for, tmp_path):
        _, sel, _ = self.selection(world, policy_for, tmp_path, bearer=None)
        assert sel.access_state == "AUTH_REQUIRED"
        n_before = len(world.calls)
        with fails("PROVIDER_AUTH_FAILED", "AUTH_REQUIRED"):
            earthdata.fetch(sel, world.client(bearer=None), tmp_path / "s", policy=policy_for(EARTH_HOSTS))
        with fails("PROVIDER_AUTH_FAILED", "AUTH_REQUIRED"):
            earthdata.fetch(sel, None, tmp_path / "s", policy=policy_for(EARTH_HOSTS))
        assert len(world.calls) == n_before

    def test_server_401_on_download_is_auth_required(self, world, policy_for, tmp_path):
        _, sel, client = self.selection(world, policy_for, tmp_path)
        world.routes[(DATA, "/nasadem/NASADEM_HGT_n30w101.zip")] = lambda r: httpx.Response(401)
        with fails("PROVIDER_AUTH_FAILED", "AUTH_REQUIRED"):
            earthdata.fetch(sel, client, tmp_path / "s", policy=policy_for(EARTH_HOSTS))

    def test_html_login_page_instead_of_the_archive(self, world, policy_for, tmp_path):
        _, sel, client = self.selection(world, policy_for, tmp_path)
        world.routes[(DATA, "/nasadem/NASADEM_HGT_n30w101.zip")] = lambda r: httpx.Response(
            200,
            content=b"<html><title>Earthdata Login</title></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )
        with fails("SOURCE_CONTENT_INVALID", "HTML_LOGIN_PAGE"):
            earthdata.fetch(sel, client, tmp_path / "s", policy=policy_for(EARTH_HOSTS))
        assert not list((tmp_path / "s").rglob("*.zip"))

    def test_checksum_mismatch_against_provider_value(self, world, policy_for, tmp_path):
        _, sel, client = self.selection(world, policy_for, tmp_path)
        tampered = b"PK" + b"\x00" * 600
        world.routes[(DATA, "/nasadem/NASADEM_HGT_n30w101.zip")] = lambda r: httpx.Response(200, content=tampered)
        with fails("SOURCE_CHECKSUM_MISMATCH"):
            earthdata.fetch(sel, client, tmp_path / "s", policy=policy_for(EARTH_HOSTS))
        assert not list((tmp_path / "s").rglob("*.zip"))

    def test_bad_archive_with_matching_checksum_is_rejected_at_fetch(self, world, policy_for, tmp_path):
        bad = b"PK\x03\x04" + b"garbage-not-a-real-zip" * 20
        g = GranuleSpec(
            "G900",
            "NASADEM_HGT_n30w100",
            (-100.0, 30.0, -99.0, 31.0),
            f"https://{DATA}/nasadem/NASADEM_HGT_n30w100.zip",
            bad,
            checksum=sha256_hex(bad),
        )
        install_cmr(world, [g])
        client = world.client()
        (sel,) = earthdata.discover(
            request(earthdata.NASADEM_ADAPTER_ID, [-99.9, 30.1, -99.1, 30.9]), client, policy=policy_for(EARTH_HOSTS)
        )
        with fails("SOURCE_CONTENT_INVALID", "BAD_ARCHIVE"):
            earthdata.fetch(sel, client, tmp_path / "s", policy=policy_for(EARTH_HOSTS))

    def test_traversal_archive_with_matching_checksum_is_rejected_at_fetch(self, world, policy_for, tmp_path):
        evil = zip_with_members(tmp_path / "evil.zip", {"../../pwn.hgt": b"x" * 100}).read_bytes()
        g = GranuleSpec(
            "G901",
            "NASADEM_HGT_n30w100",
            (-100.0, 30.0, -99.0, 31.0),
            f"https://{DATA}/nasadem/NASADEM_HGT_n30w100.zip",
            evil,
            checksum=sha256_hex(evil),
        )
        install_cmr(world, [g])
        client = world.client()
        (sel,) = earthdata.discover(
            request(earthdata.NASADEM_ADAPTER_ID, [-99.9, 30.1, -99.1, 30.9]), client, policy=policy_for(EARTH_HOSTS)
        )
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_PATH_TRAVERSAL"):
            earthdata.fetch(sel, client, tmp_path / "s", policy=policy_for(EARTH_HOSTS))
        assert not (tmp_path / "pwn.hgt").exists()

    def test_redirect_from_data_host_to_cdn_does_not_leak_the_token(self, world, policy_for, tmp_path):
        gs, sel, client = self.selection(world, policy_for, tmp_path)
        world.routes[(DATA, "/nasadem/NASADEM_HGT_n30w101.zip")] = lambda r: httpx.Response(
            302, headers={"location": "https://cdn.example/obj?sig=abc"}
        )
        world.routes[("cdn.example", "/obj")] = lambda r: httpx.Response(200, content=gs[0].payload)
        (asset,) = earthdata.fetch(sel, client, tmp_path / "s", policy=policy_for(EARTH_HOSTS | {"cdn.example"}, {URS}))
        cdn = next(c for c in world.calls if c.host == "cdn.example")
        assert "authorization" not in cdn.headers
        assert asset.sha256 == sha256_hex(gs[0].payload) and "cdn.example" not in asset.source_uri

    def test_size_disagreement_with_provider_metadata(self, world, policy_for, tmp_path):
        g = granules(tmp_path, 1)[0]
        g = GranuleSpec(
            g.concept_id,
            g.granule_ur,
            g.box,
            g.download_url,
            g.payload,
            checksum=g.checksum,
            declared_size=len(g.payload) + 5,
        )
        install_cmr(world, [g])
        client = world.client()
        (sel,) = earthdata.discover(
            request(earthdata.NASADEM_ADAPTER_ID, [-100.9, 30.1, -100.1, 30.9]), client, policy=policy_for(EARTH_HOSTS)
        )
        with fails("SOURCE_CONTENT_INVALID", "SIZE_MISMATCH"):
            earthdata.fetch(sel, client, tmp_path / "s", policy=policy_for(EARTH_HOSTS))

    def test_no_coverage_selection_cannot_be_fetched(self, world, policy_for, tmp_path):
        install_cmr(world, [])
        client = world.client()
        (sel,) = earthdata.discover(
            request(earthdata.NASADEM_ADAPTER_ID, [-100, 30, -99, 31]), client, policy=policy_for(EARTH_HOSTS)
        )
        assert sel.access_state == "NO_COVERAGE"
        with fails("NO_COVERAGE", "NO_GRANULES"):
            earthdata.fetch(sel, client, tmp_path / "s", policy=policy_for(EARTH_HOSTS))

    def test_agent_supplied_url_is_never_used(self, world, policy_for, tmp_path):
        """A selection carries ids only; the download URL always comes from CMR, never from the caller."""
        gs, sel, client = self.selection(world, policy_for, tmp_path)
        forged = sel.model_copy(update={"granule_ids": ["https://evil.example/x.zip"]})
        with fails("NO_COVERAGE", "NO_GRANULES"):
            earthdata.fetch(forged, client, tmp_path / "s", policy=policy_for(EARTH_HOSTS))
        assert "evil.example" not in world.hosts_called()


# ======================================== pds / MOLA / LOLA
class TestPdsDecode:
    def raw(self) -> np.ndarray:
        return np.array([[0, 2, 4, 6], [8, 10, -32768, 14], [16, 18, 20, 22], [24, 26, 28, 30]], dtype=np.int16)

    def test_lola_style_radius_scale_and_offset_applied_once(self, tmp_path):
        raw = self.raw()
        lbl = write_pds3(
            tmp_path,
            "ldem",
            raw,
            ">i2",
            scale=0.5,
            offset=1737400.0,
            missing=-32768,
            target="MOON",
            a_radius_km=1737.4,
            east=4.0,
        )
        params = pds.PdsDecodeParams("moon_lola_gdr", "MOON", "radius")
        out = pds.decode(lbl, params)
        expected = raw.astype(float) * 0.5 + 1737400.0 - 1737400.0  # radius minus the reference radius, once
        np.testing.assert_allclose(out.data[out.valid], expected[out.valid], atol=1e-9)
        assert out.data[1, 2] != out.data[1, 2] and not out.valid[1, 2]  # missing constant => NaN, never 0
        assert (
            out.metadata.scale_applied and out.metadata.source_scale == 0.5 and out.metadata.source_offset == 1737400.0
        )
        assert out.metadata.quantity == "relative_height" and "reference sphere" in (
            out.metadata.vertical_reference or ""
        )
        # a double application would be detectable: heights would be raw*0.25 + (1737400*0.5+... ) not raw*0.5
        assert out.data[0, 1] == pytest.approx(1.0) and out.data[3, 3] == pytest.approx(15.0)

    def test_reference_radius_override_and_height_products_are_not_re_referenced(self, tmp_path):
        raw = self.raw()
        lbl = write_pds3(
            tmp_path, "rad", raw, ">i2", scale=1.0, offset=1737400.0, missing=-32768, target="MOON", a_radius_km=1737.4
        )
        out = pds.decode(lbl, pds.PdsDecodeParams("moon_lola_gdr", "MOON", "radius", reference_radius_m=1737000.0))
        assert out.data[0, 1] == pytest.approx(2.0 + 400.0)
        height = pds.decode(lbl, pds.PdsDecodeParams("moon_lola_gdr", "MOON", "height"))
        assert height.data[0, 1] == pytest.approx(2.0 + 1737400.0)  # caller said these are heights: no subtraction
        assert any("no radius subtraction" in n for n in height.metadata.notes)

    def test_mola_style_heights_geometry_and_body_specific_crs(self, tmp_path):
        raw = self.raw()
        lbl = write_pds3(
            tmp_path,
            "megt",
            raw,
            ">i2",
            scale=1.0,
            offset=0.0,
            missing=-32768,
            target="MARS",
            west=0.0,
            east=4.0,
            south=-4.0,
            north=0.0,
            resolution=1.0,
        )
        out = pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height", vertical_reference="areoid"))
        np.testing.assert_array_equal(out.data[out.valid], raw[out.valid].astype(float))
        assert out.metadata.transform == (1.0, 0.0, 0.0, 0.0, -1.0, 0.0) and out.metadata.longitude_domain == "ZERO_360"
        wkt = out.metadata.crs_wkt or ""
        assert "3396000" in wkt and "Mars" in wkt and "WGS 84" not in wkt and "6378137" not in wkt
        from rasterio.crs import CRS

        assert CRS.from_wkt(wkt).is_geographic

    def test_counts_are_not_unit_converted(self, tmp_path):
        counts = np.array([[1, 2], [3, 0]], dtype=np.int16)
        lbl = write_pds3(tmp_path, "cnt", counts, ">i2", unit=None, east=2.0, north=2.0, resolution=1.0)
        out = pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "count"))
        assert out.metadata.quantity == "observation_count" and out.data.tolist() == [[1.0, 2.0], [3.0, 0.0]]

    @pytest.mark.parametrize(
        ("kwargs", "code", "detail"),
        [
            ({"target": "MOON"}, "SOURCE_CONTENT_INVALID", "BODY_MISMATCH"),
            ({"direction": "WEST"}, "UNSUPPORTED_PRODUCT", "UNSUPPORTED_FORMAT"),
            ({"resolution": 2.0}, "SOURCE_CONTENT_INVALID", "GEOMETRY_MISMATCH"),
            ({"north": None}, "SOURCE_CONTENT_INVALID", "METADATA_INCOMPLETE"),
            ({"unit": None}, "SOURCE_CONTENT_INVALID", "METADATA_INCOMPLETE"),
            ({"unit": "DEGREES"}, "SOURCE_CONTENT_INVALID", "METADATA_INCOMPLETE"),
            ({"a_radius_km": None}, "SOURCE_CONTENT_INVALID", "METADATA_INCOMPLETE"),
            ({"sample_type": "VAX_REAL"}, "UNSUPPORTED_PRODUCT", "UNSUPPORTED_FORMAT"),
        ],
    )
    def test_label_failure_modes(self, tmp_path, kwargs, code, detail):
        lbl = write_pds3(tmp_path, "p", self.raw(), ">i2", **kwargs)
        with fails(code, detail):
            pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))

    def test_units_override_rescues_a_label_without_unit(self, tmp_path):
        lbl = write_pds3(tmp_path, "p", self.raw(), ">i2", unit=None)
        out = pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height", units_override="km"))
        assert out.data[0, 1] == pytest.approx(2000.0)  # kilometres converted to metres exactly once

    def test_data_file_problems(self, tmp_path):
        lbl = write_pds3(tmp_path, "p", self.raw(), ">i2")
        (tmp_path / "p.img").write_bytes((tmp_path / "p.img").read_bytes()[:-2])
        with fails("SOURCE_CONTENT_INVALID", "SHAPE_MISMATCH"):
            pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))
        (tmp_path / "p.img").unlink()
        with fails("SOURCE_CONTENT_INVALID", "METADATA_INCOMPLETE"):
            pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))

    def test_pointer_traversal_is_refused(self, tmp_path):
        outside = tmp_path / "secret.img"
        outside.write_bytes(self.raw().astype(">i2").tobytes())
        sub = tmp_path / "sub"
        lbl = write_pds3(sub, "p", self.raw(), ">i2", data_name="../secret.img")
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_PATH_TRAVERSAL"):
            pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))

    def test_case_insensitive_data_file_lookup(self, tmp_path):
        lbl = write_pds3(tmp_path, "p", self.raw(), ">i2", data_name="P.IMG")
        out = pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))
        assert out.valid.sum() == 16

    def test_not_a_pds3_label_and_unknown_suffix(self, tmp_path):
        junk = tmp_path / "x.lbl"
        junk.write_text("hello = world")
        with fails("SOURCE_CONTENT_INVALID", "LABEL_PARSE_ERROR"):
            pds.decode(junk, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))
        other = tmp_path / "x.txt"
        other.write_text("x")
        with fails("UNSUPPORTED_PRODUCT", "UNSUPPORTED_FORMAT"):
            pds.decode(other, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))


class TestPds4:
    def test_xml_label_scale_offset_missing(self, tmp_path):
        raw = np.array([[1, 2, 3, 4], [5, 6, -999, 8], [9, 10, 11, 12], [13, 14, 15, 16]], dtype=np.int16)
        lbl = write_pds4(tmp_path, "m", raw, ">i2", scale=0.5, offset=100.0, missing=-999)
        out = pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))
        np.testing.assert_allclose(out.data[out.valid], (raw.astype(float) * 0.5 + 100.0)[out.valid])
        assert not out.valid[1, 2] and np.isnan(out.data[1, 2]) and out.valid.sum() == 15
        assert out.metadata.product_id == "urn:nasa:pds:syn:data:m::1.0"
        assert out.metadata.longitude_domain == "ZERO_360" and "3396000" in (out.metadata.crs_wkt or "")

    def test_little_endian_float_array(self, tmp_path):
        raw = np.arange(16, dtype="<f4").reshape(4, 4) * 1.5
        lbl = write_pds4(tmp_path, "f", raw, "<f4", data_type="IEEE754LSBSingle")
        out = pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))
        np.testing.assert_allclose(out.data, raw.astype(float))

    def test_an_empty_image_array_is_a_malformed_label_not_a_cue_to_read_another_array(self, tmp_path):
        """Element truthiness means 'has children', not 'exists': an empty Array_2D_Image must not fall through."""
        raw = np.arange(16, dtype=np.int16).reshape(4, 4)
        lbl = write_pds4(tmp_path, "e", raw, ">i2")
        text = lbl.read_text(encoding="utf-8")
        assert "<Array_2D_Image>" in text
        # A valid generic Array_2D follows an empty Array_2D_Image: the specialised element wins, and it is unusable.
        lbl.write_text(
            text.replace("<Array_2D_Image>", "<Array_2D_Image/><Array_2D>", 1).replace(
                "</Array_2D_Image>", "</Array_2D>", 1
            ),
            encoding="utf-8",
        )
        with fails("UNSUPPORTED_PRODUCT", "UNSUPPORTED_FORMAT"):
            pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))

    def test_the_image_array_is_preferred_over_a_generic_array_when_both_are_present(self, tmp_path):
        raw = np.arange(16, dtype=np.int16).reshape(4, 4)
        lbl = write_pds4(tmp_path, "p", raw, ">i2")
        text = lbl.read_text(encoding="utf-8")
        decoy = (
            "<Array_2D><axes>2</axes>"
            "<Axis_Array><axis_name>Line</axis_name><elements>1</elements></Axis_Array></Array_2D>"
        )
        lbl.write_text(text.replace("<Array_2D_Image>", decoy + "<Array_2D_Image>", 1), encoding="utf-8")
        out = pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))
        assert out.valid.sum() == 16 and out.data.shape == (4, 4)

    def test_external_entity_and_dtd_are_never_processed(self, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("TOP-SECRET")
        raw = np.zeros((4, 4), dtype=np.int16)
        doctype = f'<!DOCTYPE Product_Observational [<!ENTITY xxe SYSTEM "file://{secret}">]>\n'
        lbl = write_pds4(tmp_path / "x", "x", raw, ">i2", doctype=doctype)
        with fails("SOURCE_CONTENT_INVALID", "XML_DTD_FORBIDDEN") as f:
            pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))
        assert "TOP-SECRET" not in str(f.info.value)
        bomb = '<!DOCTYPE b [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]>\n'
        lbl2 = write_pds4(tmp_path / "y", "y", raw, ">i2", doctype=bomb)
        with fails("SOURCE_CONTENT_INVALID", "XML_DTD_FORBIDDEN"):
            pds.decode(lbl2, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))

    def test_malformed_and_unsupported(self, tmp_path):
        bad = tmp_path / "bad.xml"
        bad.write_text("<a><b></a>")
        with fails("SOURCE_CONTENT_INVALID", "LABEL_PARSE_ERROR"):
            pds.decode(bad, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))
        raw = np.zeros((4, 4), dtype=np.int16)
        lbl = write_pds4(tmp_path / "z", "z", raw, ">i2", data_type="ComplexMSB16")
        with fails("UNSUPPORTED_PRODUCT", "UNSUPPORTED_FORMAT"):
            pds.decode(lbl, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))
        lbl2 = write_pds4(tmp_path / "w", "w", raw, ">i2", target="Moon")
        with fails("SOURCE_CONTENT_INVALID", "BODY_MISMATCH"):
            pds.decode(lbl2, pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))


PDS_HOST = "pds-geosciences.wustl.edu"
BASE = f"https://{PDS_HOST}/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/"


def install_index(world: World, rows, *, base_path="/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x"):  # type: ignore[no-untyped-def]
    label, table = pds_index(rows)
    world.routes[(PDS_HOST, f"{base_path}/index/index.lbl")] = lambda r: httpx.Response(200, text=label)
    world.routes[(PDS_HOST, f"{base_path}/index/INDEX.TAB")] = lambda r: httpx.Response(200, text=table)


class TestPdsDiscoveryFetch:
    ROWS = [
        ("megt00n000.lbl", 0, 44, 0, 90),
        ("megt44n000.lbl", 44, 88, 0, 90),
        ("megt00n090.lbl", 0, 44, 90, 180),
        ("megt00n270.lbl", 0, 44, 270, 360),
    ]

    def test_discovery_respects_longitude_convention_and_sorts(self, world, policy_for):
        install_index(world, self.ROWS)
        pol = policy_for({PDS_HOST})
        (sel,) = pds.discover(
            request("mars_mola_megdr", [10, 10, 100, 30], body="MARS", convention="ZERO_360"),
            world.client(bearer=None),
            policy=pol,
        )
        assert sel.granule_ids == ["megt00n000.lbl", "megt00n090.lbl"] and sel.access_state == "AVAILABLE"
        assert sel.coverage_fraction == pytest.approx(1.0) and sel.native_resolution_m == 463.0
        # The same place expressed with -180..180 longitudes must select the same products.
        (neg,) = pds.discover(
            request("mars_mola_megdr", [-90, 10, -80, 30], body="MARS", convention="NEG180_180"),
            world.client(bearer=None),
            policy=pol,
        )
        assert neg.granule_ids == ["megt00n270.lbl"]

    def test_seam_crossing_aoi_and_partial_coverage(self, world, policy_for):
        install_index(world, self.ROWS)
        (sel,) = pds.discover(
            request("mars_mola_megdr", [250, 10, 100, 30], body="MARS", convention="ZERO_360"),
            world.client(bearer=None),
            policy=policy_for({PDS_HOST}),
        )
        assert sel.granule_ids == ["megt00n000.lbl", "megt00n090.lbl", "megt00n270.lbl"]
        # 250..270 is not indexed: AOI width is 210 deg, indexed overlap is 90 (270..360) + 100 (0..100)
        assert sel.coverage_fraction == pytest.approx(190.0 / 210.0)

    def test_no_coverage_and_body_mismatch_and_offline(self, world, policy_for):
        install_index(world, self.ROWS)
        (sel,) = pds.discover(
            request("mars_mola_megdr", [200, 10, 210, 30], body="MARS", convention="ZERO_360"),
            world.client(bearer=None),
            policy=policy_for({PDS_HOST}),
        )
        assert sel.access_state == "NO_COVERAGE" and sel.coverage_fraction == 0.0
        with fails("UNSUPPORTED_PRODUCT", "BODY_MISMATCH"):
            pds.discover(request("mars_mola_megdr", [0, 0, 5, 5], body="MOON"), world.client(bearer=None))
        (off,) = pds.discover(request("moon_lola_gdr", [0, 0, 5, 5], body="MOON"), None)
        assert off.access_state == "UNAVAILABLE"

    def test_cap_truncation_disclosed(self, world, policy_for):
        install_index(world, self.ROWS)
        (sel,) = pds.discover(
            request("mars_mola_megdr", [0, 0, 360, 50], body="MARS", convention="ZERO_360"),
            world.client(bearer=None),
            policy=policy_for({PDS_HOST}),
            max_products=2,
        )
        assert len(sel.granule_ids) == 2 and any("DISCOVERY_TRUNCATED" in n and "of 4" in n for n in sel.notes)

    def test_index_validation(self, world, policy_for):
        label, table = pds_index(self.ROWS)
        world.routes[(PDS_HOST, "/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/index/index.lbl")] = lambda r: httpx.Response(
            200, text=label
        )
        world.routes[(PDS_HOST, "/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/index/INDEX.TAB")] = lambda r: httpx.Response(
            200, text="\n".join(table.splitlines()[:-1]) + "\n"
        )
        req = request("mars_mola_megdr", [0, 0, 10, 10], body="MARS", convention="ZERO_360")
        with fails("SOURCE_CONTENT_INVALID", "SHAPE_MISMATCH"):
            pds.discover(req, world.client(bearer=None), policy=policy_for({PDS_HOST}))
        evil_label, evil_table = pds_index([("../../etc/passwd", 0, 10, 0, 10)])
        world.routes[(PDS_HOST, "/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/index/index.lbl")] = lambda r: httpx.Response(
            200, text=evil_label
        )
        world.routes[(PDS_HOST, "/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/index/INDEX.TAB")] = lambda r: httpx.Response(
            200, text=evil_table
        )
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_PATH_TRAVERSAL"):
            pds.discover(req, world.client(bearer=None), policy=policy_for({PDS_HOST}))

    def test_index_served_as_html_login_page(self, world, policy_for):
        world.routes[(PDS_HOST, "/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/index/index.lbl")] = lambda r: httpx.Response(
            200, text="<html><body>maintenance</body></html>"
        )
        with fails("SOURCE_CONTENT_INVALID", "HTML_LOGIN_PAGE"):
            pds.discover(
                request("mars_mola_megdr", [0, 0, 10, 10], body="MARS", convention="ZERO_360"),
                world.client(bearer=None),
                policy=policy_for({PDS_HOST}),
            )

    def test_fetch_label_and_image_then_decode_end_to_end(self, world, policy_for, tmp_path):
        raw = np.arange(16, dtype=np.int16).reshape(4, 4)
        src = tmp_path / "src"
        lbl = write_pds3(
            src,
            "megt00n000",
            raw,
            ">i2",
            scale=2.0,
            offset=10.0,
            data_name="megt00n000.img",
            east=4.0,
            south=0.0,
            north=4.0,
        )
        install_index(world, [("megt00n000.lbl", 0, 4, 0, 4)])
        base = "/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x"
        world.routes[(PDS_HOST, f"{base}/megt00n000.lbl")] = lambda r: httpx.Response(200, content=lbl.read_bytes())
        world.routes[(PDS_HOST, f"{base}/megt00n000.img")] = lambda r: httpx.Response(
            200, content=(src / "megt00n000.img").read_bytes()
        )
        client = world.client(bearer=None)
        pol = policy_for({PDS_HOST})
        (sel,) = pds.discover(
            request("mars_mola_megdr", [0, 0, 4, 4], body="MARS", convention="ZERO_360"), client, policy=pol
        )
        scratch = tmp_path / "scratch"
        assets = pds.fetch(sel, client, scratch, policy=pol)
        assert [a.granule_id for a in assets] == ["megt00n000.lbl", "megt00n000.img"]
        assert assets[1].sha256 == file_sha256(src / "megt00n000.img") and assets[0].validation_status == "PENDING"
        out = pds.decode(pds.asset_path(scratch, assets[0]), pds.PdsDecodeParams("mars_mola_megdr", "MARS", "height"))
        np.testing.assert_allclose(out.data, raw.astype(float) * 2.0 + 10.0)

    def test_fetch_refuses_traversal_in_the_label_pointer_and_forged_ids(self, world, policy_for, tmp_path):
        src = tmp_path / "src"
        lbl = write_pds3(src, "evil", np.zeros((4, 4), dtype=np.int16), ">i2", data_name="../../etc/passwd")
        base = "/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x"
        world.routes[(PDS_HOST, f"{base}/evil.lbl")] = lambda r: httpx.Response(200, content=lbl.read_bytes())
        client = world.client(bearer=None)
        sel = pds.discover(request("mars_mola_megdr", [0, 0, 4, 4], body="MARS", convention="ZERO_360"), None)[0]
        forged = sel.model_copy(update={"access_state": "AVAILABLE", "granule_ids": ["evil.lbl"]})
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_PATH_TRAVERSAL"):
            pds.fetch(forged, client, tmp_path / "s", policy=policy_for({PDS_HOST}))
        for bad in ("../x.lbl", "/etc/passwd", "http://evil.example/x.lbl", "a//b.lbl"):
            with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_PATH_TRAVERSAL"):
                pds.fetch(
                    forged.model_copy(update={"granule_ids": [bad]}),
                    client,
                    tmp_path / "s",
                    policy=policy_for({PDS_HOST}),
                )

    def test_fetch_with_no_coverage_selection(self, world, policy_for, tmp_path):
        install_index(world, self.ROWS)
        client = world.client(bearer=None)
        (sel,) = pds.discover(
            request("mars_mola_megdr", [200, 10, 210, 30], body="MARS", convention="ZERO_360"),
            client,
            policy=policy_for({PDS_HOST}),
        )
        with fails("NO_COVERAGE", "NO_GRANULES"):
            pds.fetch(sel, client, tmp_path / "s", policy=policy_for({PDS_HOST}))


# ======================================== diviner
class TestDiviner:
    VAR = "bolometric_brightness_temperature_min"

    def raw(self) -> np.ndarray:
        return np.arange(16, dtype=np.int16).reshape(4, 4) * 10 + 40

    def label(self, tmp_path, **kw):  # type: ignore[no-untyped-def]
        kw = {"target": "MOON", "scale": 0.5, "offset": 0.0, "unit": "K", "a_radius_km": 1737.4, "missing": -1, **kw}
        raw = self.raw()
        raw[2, 2] = -1
        return write_pds3(tmp_path, "tmin", raw, ">i2", **kw), raw

    def test_kelvin_with_explicit_variable(self, tmp_path):
        lbl, raw = self.label(tmp_path)
        out = diviner.decode(lbl, diviner.DivinerDecodeParams(self.VAR))
        np.testing.assert_allclose(out.data[out.valid], (raw.astype(float) * 0.5)[out.valid])
        assert out.metadata.units == "K" and out.metadata.quantity == "temperature_min" and not out.valid[2, 2]
        assert out.metadata.attributes["variable"] == self.VAR and out.metadata.body == "MOON"
        assert any("not comparable to an Earth air temperature" in n for n in out.metadata.notes)

    def test_celsius_label_is_converted_and_unknown_unit_refused(self, tmp_path):
        lbl, raw = self.label(tmp_path, unit="CELSIUS", scale=1.0, offset=-200.0)
        out = diviner.decode(lbl, diviner.DivinerDecodeParams(self.VAR))
        assert out.data[0, 0] == pytest.approx(40.0 - 200.0 + 273.15) and any(
            "Celsius" in n for n in out.metadata.notes
        )
        lbl2, _ = self.label(tmp_path / "u", unit="DN")
        with fails("UNSUPPORTED_PRODUCT"):
            diviner.decode(lbl2, diviner.DivinerDecodeParams(self.VAR))

    def test_non_physical_temperatures_masked_not_kept(self, tmp_path):
        lbl, _ = self.label(tmp_path, scale=1.0, offset=-50.0)  # raw 40..190 -> some <= 0 K values
        out = diviner.decode(lbl, diviner.DivinerDecodeParams(self.VAR))
        assert not out.valid[0, 0] and np.isnan(out.data[0, 0]) and out.valid[3, 3]
        assert any("non-physical" in n for n in out.metadata.notes)

    def test_unsupported_variable_is_unsupported_product(self, tmp_path):
        lbl, _ = self.label(tmp_path)
        with fails("UNSUPPORTED_PRODUCT", "UNSUPPORTED_FORMAT"):
            diviner.decode(lbl, diviner.DivinerDecodeParams("channel_7_radiance_average"))
        with fails("UNSUPPORTED_PRODUCT"):
            diviner.fetch(
                diviner.discover(
                    request("moon_diviner_derived", [0, 0, 5, 5], body="MOON", kinds=("raw_radiance",)), None
                )[0],
                None,
                tmp_path,
            )

    def test_discovery_reports_unsupported_without_network_and_picks_the_requested_variable(self, world, policy_for):
        (sel,) = diviner.discover(
            request("moon_diviner_derived", [0, 0, 5, 5], body="MOON", kinds=("raw_radiance",)),
            world.client(bearer=None),
            policy=policy_for({PDS_HOST}),
        )
        assert sel.access_state == "UNSUPPORTED" and world.calls == []
        (none,) = diviner.discover(request("moon_diviner_derived", [0, 0, 5, 5], body="MOON", kinds=()), None)
        assert none.access_state == "UNSUPPORTED" and "explicitly" in none.notes[0]
        base = "/lro/lro-l-dlre-4-rdr-v1/lrodlr_1001/min"
        label, table = pds_index([("tmin_000.lbl", 0, 10, 0, 10)])
        world.routes[(PDS_HOST, f"{base}/index/index.lbl")] = lambda r: httpx.Response(200, text=label)
        world.routes[(PDS_HOST, f"{base}/index/INDEX.TAB")] = lambda r: httpx.Response(200, text=table)
        (ok,) = diviner.discover(
            request(
                "moon_diviner_derived", [1, 1, 5, 5], body="MOON", convention="ZERO_360", kinds=(f"diviner:{self.VAR}",)
            ),
            world.client(bearer=None),
            policy=policy_for({PDS_HOST}),
        )
        assert ok.granule_ids == ["tmin_000.lbl"] and ok.product_id == self.VAR
        with fails("UNSUPPORTED_PRODUCT", "BODY_MISMATCH"):
            diviner.discover(request("moon_diviner_derived", [1, 1, 5, 5], body="MARS", kinds=(self.VAR,)), None)


# ======================================== emit
class TestEmit:
    def scene(self, tmp_path):  # type: ignore[no-untyped-def]
        ids = np.array([[1, 2, 2, -9999], [0, 3, 1, 1], [2, 2, 3, 0], [-9999, 1, 1, 2]], dtype=np.int16)
        mask = np.zeros(ids.shape, dtype=np.uint8)
        mask[0, 0] = 1  # cloud
        mask[1, 3] = 4
        lat = np.linspace(31.0, 30.0, 4)[:, None] * np.ones((1, 4))
        lon = np.ones((4, 1)) * np.linspace(-100.0, -99.0, 4)[None, :]
        names = {0: "None", 1: "Kaolinite", 2: "Goethite", 3: "Calcite"}
        path = write_emit_nc(tmp_path / "EMIT_L2B_MIN.nc", ids, mask=mask, names=names, lat=lat, lon=lon)
        return path, ids, mask, lat, lon

    def test_categorical_ids_mask_and_valid_retrieval_fraction(self, tmp_path):
        path, ids, mask, _, _ = self.scene(tmp_path)
        out = emit.decode(path, emit.EmitDecodeParams(mask_variable="mask"))
        expected_valid = (ids != -9999) & (mask == 0)
        np.testing.assert_array_equal(out.valid, expected_valid)
        assert out.data.dtype.kind == "i" and set(np.unique(out.data[out.valid])) <= {0, 1, 2, 3}
        assert (out.data[~out.valid] == emit.INVALID_ID).all()
        assert out.valid_fraction == pytest.approx(expected_valid.sum() / 16)
        assert float(out.metadata.attributes["valid_retrieval_fraction"]) == pytest.approx(expected_valid.mean())
        ident = expected_valid & (ids != 0)
        assert float(out.metadata.attributes["identified_fraction"]) == pytest.approx(ident.mean())
        assert out.dictionary == {0: "None", 1: "Kaolinite", 2: "Goethite", 3: "Calcite"}
        assert np.isnan(out.aux["band_depth"][~out.valid]).all() and np.isfinite(out.aux["band_depth"][out.valid]).all()
        assert out.metadata.units == "categorical" and out.metadata.transform is None
        assert any("not proof" in n for n in out.metadata.notes)

    def test_without_mask_only_fill_is_invalid_and_that_is_disclosed(self, tmp_path):
        path, ids, _, _, _ = self.scene(tmp_path)
        out = emit.decode(path)
        np.testing.assert_array_equal(out.valid, ids != -9999)
        assert any("No quality mask" in n for n in out.metadata.notes)

    def test_external_mask_array_and_bad_value_set(self, tmp_path):
        path, ids, mask, _, _ = self.scene(tmp_path)
        out = emit.decode(path, emit.EmitDecodeParams(mask_array=mask, mask_bad_values=frozenset({4})))
        np.testing.assert_array_equal(out.valid, (ids != -9999) & (mask != 4))
        with fails("SOURCE_CONTENT_INVALID", "SHAPE_MISMATCH"):
            emit.decode(path, emit.EmitDecodeParams(mask_array=np.zeros((2, 2), dtype=np.uint8)))

    def test_variable_path_selection_and_failures(self, tmp_path):
        path, *_ = self.scene(tmp_path)
        with fails("UNSUPPORTED_PRODUCT", "UNSUPPORTED_FORMAT"):
            emit.decode(path, emit.EmitDecodeParams(group_prefix="group_9"))
        with fails("UNSUPPORTED_PRODUCT", "UNSUPPORTED_FORMAT"):
            emit.decode(path, emit.EmitDecodeParams(mask_variable="no_such/group/mask"))
        junk = tmp_path / "junk.nc"
        junk.write_bytes(b"not an hdf5 file" * 10)
        with fails("SOURCE_CONTENT_INVALID"):
            emit.decode(junk)

    def test_unknown_ids_are_reported(self, tmp_path):
        ids = np.array([[1, 7], [0, 1]], dtype=np.int16)
        path = write_emit_nc(tmp_path / "u.nc", ids, names={0: "None", 1: "Kaolinite"})
        out = emit.decode(path)
        assert any("absent from the product dictionary: [7]" in n for n in out.metadata.notes)

    def test_aoi_valid_retrieval_fraction_uses_geolocation_and_unknown_is_none(self, tmp_path):
        path, ids, mask, lat, lon = self.scene(tmp_path)
        out = emit.decode(path, emit.EmitDecodeParams(mask_variable="mask"))
        box = (-100.0, 30.0, -99.5, 31.0)  # left two columns
        res = emit.retrieval_in_bbox(out, box)
        inside = (lon >= box[0]) & (lon <= box[2])
        assert res.pixels_in_box == int(inside.sum()) == 8
        assert res.valid_pixels == int((inside & out.valid).sum())
        assert res.fraction == pytest.approx(res.valid_pixels / 8)
        empty = emit.retrieval_in_bbox(out, (10.0, 10.0, 11.0, 11.0))
        assert empty.fraction is None and empty.pixels_in_box == 0  # unknown, not zero
        fr = emit.class_area_fractions(out)
        assert sum(fr.values()) == pytest.approx(1.0) and set(fr) <= {0, 1, 2, 3}  # no interpolated ids appear
        no_geo = emit.decode(write_emit_nc(tmp_path / "ng.nc", ids))
        with fails("SOURCE_CONTENT_INVALID", "METADATA_INCOMPLETE"):
            emit.retrieval_in_bbox(no_geo, box)

    def test_discovery_and_fetch_over_mocked_cmr(self, world, policy_for, tmp_path):
        path, *_ = self.scene(tmp_path)
        payload = path.read_bytes()
        g = GranuleSpec(
            "G700-LPDAAC",
            "EMIT_L2B_MIN_001_20230101T000000_0000000",
            (-100.5, 29.5, -98.5, 31.5),
            f"https://{DATA}/emit/EMIT_L2B_MIN_001_X.nc",
            payload,
            checksum=sha256_hex(payload),
        )
        install_cmr(world, [g])
        client = world.client()
        pol = policy_for(EARTH_HOSTS, {URS})
        (sel,) = emit.discover(
            request(emit.EMIT_ADAPTER_ID, [-100.0, 30.0, -99.0, 31.0], kinds=("mineral_id",)), client, policy=pol
        )
        assert sel.granule_ids == ["G700-LPDAAC"] and sel.native_resolution_m == 60.0
        assert httpx.URL(world.calls[0].url).params["short_name"] == "EMITL2BMIN"
        assert any("swath intersection" in n for n in sel.notes)
        (asset,) = emit.fetch(sel, client, tmp_path / "s", policy=pol)
        assert asset.validation_status == "VERIFIED"
        out = emit.decode(emit.asset_path(tmp_path / "s", asset), emit.EmitDecodeParams(mask_variable="mask"))
        assert out.valid.sum() == 12  # 14 non-fill retrievals minus 2 masked
        # login page instead of the NetCDF
        world.routes[(DATA, "/emit/EMIT_L2B_MIN_001_X.nc")] = lambda r: httpx.Response(
            200, content=b"<html>login</html>", headers={"content-type": "application/octet-stream"}
        )
        with fails("SOURCE_CONTENT_INVALID", "HTML_LOGIN_PAGE"):
            emit.fetch(sel, client, tmp_path / "s2", policy=pol)
        # right checksum claim but not HDF5 bytes => magic check
        junk = b"JUNKJUNKJUNK" * 20
        g2 = GranuleSpec(
            "G701",
            "EMIT_X",
            (-100.5, 29.5, -98.5, 31.5),
            f"https://{DATA}/emit/junk.nc",
            junk,
            checksum=sha256_hex(junk),
        )
        w2 = World()
        install_cmr(w2, [g2])
        c2 = w2.client()
        (sel2,) = emit.discover(
            request(emit.EMIT_ADAPTER_ID, [-100, 30, -99, 31], kinds=("mineral_id",)), c2, policy=pol
        )
        with fails("SOURCE_CONTENT_INVALID", "MAGIC_MISMATCH"):
            emit.fetch(sel2, c2, tmp_path / "s3", policy=pol)

    def test_discovery_states(self, world, policy_for):
        install_cmr(world, [])
        pol = policy_for(EARTH_HOSTS)
        (none,) = emit.discover(
            request(emit.EMIT_ADAPTER_ID, [-100, 30, -99, 31], kinds=("mineral_id",)), world.client(), policy=pol
        )
        assert none.access_state == "NO_COVERAGE"
        (unsupported,) = emit.discover(
            request(emit.EMIT_ADAPTER_ID, [-100, 30, -99, 31], kinds=("elevation",)), world.client(), policy=pol
        )
        assert unsupported.access_state == "UNSUPPORTED"
        (noauth,) = emit.discover(
            request(emit.EMIT_ADAPTER_ID, [-100, 30, -99, 31], kinds=("mineral_id",)), None, policy=pol
        )
        assert noauth.access_state == "UNAVAILABLE"
        with fails("UNSUPPORTED_PRODUCT", "BODY_MISMATCH"):
            emit.discover(request(emit.EMIT_ADAPTER_ID, [0, 0, 5, 5], body="MARS", kinds=("mineral_id",)), None)


# ======================================== user_survey
class TestUserSurvey:
    FULL = dict(
        body="EARTH",
        horizontal_reference="EPSG:32612",
        vertical_reference="NAVD88 height",
        vertical_units="m",
        acquisition_time="2026-05-01T00:00:00Z",
        cell_support_m=10.0,
        provenance="drone photogrammetry, vendor X",
        rights_declaration="owned by uploader",
        stated_uncertainty_m=0.3,
    )

    def dem(self, tmp_path, **kw):  # type: ignore[no-untyped-def]
        arr = (np.arange(36, dtype=np.float32).reshape(6, 6) * 2.0) + 1000.0
        arr[2, 2] = -9999.0
        return write_geotiff(tmp_path / "dem.tif", arr, **kw), arr

    def test_complete_metadata_allows_quantitative_use(self, tmp_path):
        path, arr = self.dem(tmp_path)
        md = user_survey.SurveyMetadata(**self.FULL)
        out = user_survey.decode(path, user_survey.SurveyDecodeParams(md))
        assert out.metadata.quantitative_use_allowed and out.metadata.issues == ()
        assert not out.valid[2, 2] and np.isnan(out.data[2, 2]) and out.data[0, 1] == 1002.0
        assert out.metadata.vertical_reference == "NAVD88 height" and out.metadata.body == "EARTH"
        assert any("USER-SUPPLIED" in n for n in out.metadata.notes)
        assert out.metadata.attributes["stated_uncertainty_m"] == "0.3"

    def test_missing_metadata_is_preview_only(self, tmp_path):
        path, _ = self.dem(tmp_path)
        md = user_survey.SurveyMetadata(
            **{**self.FULL, "rights_declaration": None, "stated_uncertainty_m": None, "provenance": "  "}
        )
        out = user_survey.decode(path, user_survey.SurveyDecodeParams(md))
        assert not out.metadata.quantitative_use_allowed
        assert set(out.metadata.issues) == {
            "missing:rights_declaration",
            "missing:stated_uncertainty_m",
            "missing:provenance",
        }
        assert out.valid.sum() == 35  # preview data is still decoded

    def test_feet_are_converted_unknown_units_refused(self, tmp_path):
        path, arr = self.dem(tmp_path)
        out = user_survey.decode(
            path, user_survey.SurveyDecodeParams(user_survey.SurveyMetadata(**{**self.FULL, "vertical_units": "ft"}))
        )
        assert out.data[0, 1] == pytest.approx(1002.0 * 0.3048) and any("converted" in n for n in out.metadata.notes)
        with fails("UNSUPPORTED_PRODUCT", "UNSUPPORTED_FORMAT"):
            user_survey.decode(
                path,
                user_survey.SurveyDecodeParams(
                    user_survey.SurveyMetadata(**{**self.FULL, "vertical_units": "furlongs"})
                ),
            )

    def test_body_and_crs_checks(self, tmp_path):
        path, _ = self.dem(tmp_path)
        with fails("SOURCE_CONTENT_INVALID", "BODY_MISMATCH"):
            user_survey.decode(
                path, user_survey.SurveyDecodeParams(user_survey.SurveyMetadata(**{**self.FULL, "body": "MARS"}))
            )
        mars_wkt = (
            'PROJCRS["mars",BASEGEOGCRS["Mars",DATUM["Mars",ELLIPSOID["Mars",3396190,0,LENGTHUNIT["metre",1]]]],'
            'CONVERSION["eqc",METHOD["Equidistant Cylindrical"],PARAMETER["Latitude of 1st standard parallel",0],'
            'PARAMETER["Longitude of natural origin",0],PARAMETER["False easting",0],PARAMETER["False northing",0]],'
            'CS[Cartesian,2],AXIS["easting",east],AXIS["northing",north],LENGTHUNIT["metre",1]]'
        )
        planetary = write_geotiff(
            tmp_path / "mars.tif", np.ones((4, 4), dtype=np.float32), crs=mars_wkt, pixel=100.0, west=0.0, north=0.0
        )
        with fails("UNSUPPORTED_CRS", "BODY_MISMATCH"):
            user_survey.decode(planetary, user_survey.SurveyDecodeParams(user_survey.SurveyMetadata(**self.FULL)))
        nocrs = write_geotiff(tmp_path / "nocrs.tif", np.ones((4, 4), dtype=np.float32), crs=None)
        with fails("UNSUPPORTED_CRS", "METADATA_INCOMPLETE"):
            user_survey.decode(nocrs, user_survey.SurveyDecodeParams(user_survey.SurveyMetadata(**self.FULL)))
        junk = tmp_path / "junk.tif"
        junk.write_bytes(b"not a tiff")
        with fails("SOURCE_CONTENT_INVALID"):
            user_survey.decode(junk, user_survey.SurveyDecodeParams(user_survey.SurveyMetadata(**self.FULL)))

    def test_declared_cell_size_must_match_the_raster_and_nodata_must_be_declared(self, tmp_path):
        path, _ = self.dem(tmp_path)
        out = user_survey.decode(
            path, user_survey.SurveyDecodeParams(user_survey.SurveyMetadata(**{**self.FULL, "cell_support_m": 1.0}))
        )
        assert "cell_support_mismatch" in out.metadata.issues and not out.metadata.quantitative_use_allowed
        undeclared = write_geotiff(tmp_path / "nn.tif", np.ones((4, 4), dtype=np.float32), nodata=None)
        out2 = user_survey.decode(undeclared, user_survey.SurveyDecodeParams(user_survey.SurveyMetadata(**self.FULL)))
        assert "nodata_not_declared" in out2.metadata.issues and not out2.metadata.quantitative_use_allowed
        out3 = user_survey.decode(
            undeclared, user_survey.SurveyDecodeParams(user_survey.SurveyMetadata(**{**self.FULL, "nodata_value": 1.0}))
        )
        assert "nodata_not_declared" not in out3.metadata.issues and out3.valid.sum() == 0

    def test_discover_fetch_without_any_network(self, tmp_path):
        path, _ = self.dem(tmp_path, west=500000.0, north=3900000.0)
        up = user_survey.UserSurveyUpload(path, user_survey.SurveyMetadata(**self.FULL))

        def forbidden(request: httpx.Request) -> httpx.Response:
            raise AssertionError("user_survey must not touch the network")

        client = httpx.Client(transport=httpx.MockTransport(forbidden))
        from pyproj import Transformer

        lon, lat = Transformer.from_crs("EPSG:32612", "EPSG:4326", always_xy=True).transform(500030.0, 3899970.0)
        req = request(user_survey.USER_SURVEY_ADAPTER_ID, [lon - 0.0005, lat - 0.0005, lon + 0.0005, lat + 0.0005])
        (sel,) = user_survey.discover(req, client, uploads=[up])
        assert sel.access_state == "AVAILABLE" and sel.coverage_fraction and 0 < sel.coverage_fraction <= 1
        assert any("USER-SUPPLIED" in n for n in sel.notes)
        (asset,) = user_survey.fetch(sel, client, tmp_path / "s", uploads=[up])
        copy = user_survey.asset_path(tmp_path / "s", asset)
        assert asset.sha256 == file_sha256(path) == file_sha256(copy) and asset.validation_status == "VERIFIED"
        assert asset.source_uri.startswith("user-upload:") and "?" not in asset.source_uri
        far = request(user_survey.USER_SURVEY_ADAPTER_ID, [10, 10, 11, 11])
        (none,) = user_survey.discover(far, None, uploads=[up])
        assert none.access_state == "NO_COVERAGE"
        with fails("NO_COVERAGE", "NO_GRANULES"):
            user_survey.fetch(none, None, tmp_path / "s", uploads=[up])
        incomplete = user_survey.UserSurveyUpload(path, user_survey.SurveyMetadata(body="EARTH"))
        (prev,) = user_survey.discover(req, None, uploads=[incomplete])
        assert any("Preview only" in n for n in prev.notes)
        (a2,) = user_survey.fetch(prev, None, tmp_path / "s2", uploads=[incomplete])
        assert a2.validation_status == "PENDING"
        with fails("UNSUPPORTED_PRODUCT", "BODY_MISMATCH"):
            user_survey.discover(request(user_survey.USER_SURVEY_ADAPTER_ID, [0, 0, 1, 1], body="MARS"), None)

    def test_metadata_file_loader(self, tmp_path):
        good = tmp_path / "m.json"
        good.write_text(json.dumps(self.FULL))
        assert user_survey.load_metadata(good).missing_fields() == []
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({**self.FULL, "surprise": 1}))
        with fails("SOURCE_CONTENT_INVALID", "METADATA_INCOMPLETE"):
            user_survey.load_metadata(bad)


# ======================================== purity / policy
ADAPTER_ROOT = ROOT / "src/analogforge/adapters"
OWNED = ("earthdata", "pds", "emit", "diviner", "user_survey", "source_http")
FORBIDDEN_IMPORTS = (
    "fastapi",
    "sqlalchemy",
    "psycopg",
    "openai",
    "analogforge.api",
    "analogforge.db",
    "analogforge.jobs",
    "analogforge.application",
    "analogforge.agents",
    "analogforge.tools",
    "analogforge.rendering.passport",
)


def owned_files() -> list[Path]:
    return sorted(p for pkg in OWNED for p in (ADAPTER_ROOT / pkg).rglob("*.py"))


class TestPurity:
    def test_no_forbidden_imports_or_environment_access(self):
        files = owned_files()
        assert len(files) > 20
        for path in files:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    assert not name.startswith(FORBIDDEN_IMPORTS), f"{path}: imports {name}"
                if isinstance(node, ast.Attribute) and node.attr in {"environ", "getenv"}:
                    pytest.fail(f"{path}: reads the environment")
                if isinstance(node, ast.Name) and node.id in {"getenv", "environ"}:
                    pytest.fail(f"{path}: reads the environment")

    def test_importing_every_adapter_opens_no_socket_and_loads_no_platform_modules(self):
        code = (
            "import socket, sys\n"
            "def boom(*a, **k):\n    raise RuntimeError('network at import time')\n"
            "socket.socket.connect = boom; socket.create_connection = boom; socket.getaddrinfo = boom\n"
            "import analogforge.adapters.earthdata, analogforge.adapters.pds, analogforge.adapters.emit\n"
            "import analogforge.adapters.diviner, analogforge.adapters.user_survey, analogforge.adapters.source_http\n"
            "bad = [m for m in sys.modules if m.split('.')[0] in ('fastapi','sqlalchemy','psycopg','openai')]\n"
            "bad += [m for m in sys.modules if m.startswith(('analogforge.api','analogforge.db','analogforge.jobs',"
            "'analogforge.application','analogforge.agents','analogforge.tools'))]\n"
            "print('LOADED_BAD=' + ','.join(sorted(bad)))\n"
        )
        res = subprocess.run(  # noqa: S603 - fixed interpreter and inline code, no external input
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=120, cwd=ROOT, check=False
        )
        assert res.returncode == 0, res.stderr
        assert res.stdout.strip().endswith("LOADED_BAD=")

    def test_credentials_only_come_from_the_injected_client_never_the_environment(
        self, world, policy_for, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("EARTHDATA_TOKEN", "FROM-ENVIRONMENT")
        monkeypatch.setenv("NASA_API_KEY", "FROM-ENVIRONMENT")
        install_cmr(world, granules(tmp_path, 1))
        req = request(earthdata.NASADEM_ADAPTER_ID, [-100.9, 30.1, -100.1, 30.9])
        (sel,) = earthdata.discover(req, world.client(bearer=None), policy=policy_for(EARTH_HOSTS))
        assert sel.access_state == "AUTH_REQUIRED"  # the env token was ignored
        with fails("PROVIDER_AUTH_FAILED", "AUTH_REQUIRED"):
            earthdata.fetch(sel, world.client(bearer=None), tmp_path / "s", policy=policy_for(EARTH_HOSTS))
        assert all("FROM-ENVIRONMENT" not in str(c.headers) for c in world.calls)

    def test_secrets_never_appear_in_errors_or_assets(self, world, policy_for, tmp_path):
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(503)
        http = SafeHttp(world.client(bearer="SUPER-SECRET"), policy_for({"a.example"}))
        with pytest.raises(AdapterError) as err:
            http.get_bytes("https://a.example/f?X-Amz-Signature=SIGSECRET")
        assert "SIGSECRET" not in str(err.value) and "SUPER-SECRET" not in str(err.value)


# ======================================== review-wave hardening
class TestTransportHardening:
    def http(self, world, policy_for, hosts=("a.example",), **kw):  # type: ignore[no-untyped-def]
        return SafeHttp(world.client(), policy_for(set(hosts), **kw))

    @pytest.mark.parametrize(
        "payload",
        [
            b"\xef\xbb\xbf<!DOCTYPE html><html>",
            b"<!-- c --><html><body>",
            b"<!-- a -->\n<!-- b --> <html>",
            b'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml">',
            "<html><body>login".encode("utf-16"),
            b" " * 1500 + b"<html>",
        ],
        ids=["bom", "comment", "two-comments", "xml-prolog", "utf16", "late"],
    )
    def test_disguised_html_is_rejected_by_download_and_get_bytes(self, world, policy_for, tmp_path, payload):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(
            200, content=payload, headers={"content-type": "application/octet-stream"}
        )
        http = self.http(world, policy_for)
        with fails("SOURCE_CONTENT_INVALID", "HTML_LOGIN_PAGE"):
            http.download("https://a.example/f", tmp_path / "f")
        assert not list(tmp_path.iterdir())
        with fails("SOURCE_CONTENT_INVALID", "HTML_LOGIN_PAGE"):
            http.get_bytes("https://a.example/f")

    def test_binary_and_xml_labels_are_not_mistaken_for_html(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/b")] = lambda r: httpx.Response(200, content=b"II*\x00" + bytes(100))
        world.routes[("a.example", "/x")] = lambda r: httpx.Response(
            200, content=b'<?xml version="1.0"?><!-- c --><Product_Observational/>'
        )
        http = self.http(world, policy_for)
        assert http.download("https://a.example/b", tmp_path / "b").size_bytes == 104
        assert http.download("https://a.example/x", tmp_path / "x").size_bytes > 10

    def test_every_credential_like_header_is_stripped_on_a_foreign_hop(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(302, headers={"location": "https://b.example/x"})
        world.routes[("b.example", "/x")] = lambda r: httpx.Response(200, content=b"ok")
        client = httpx.Client(
            transport=httpx.MockTransport(world.handle),
            headers={
                "Authorization": "Bearer S1", "X-Api-Key": "S2", "X-Custom-Token": "S3", "Cookie": "s=S4",
                "Accept": "*/*",
            },
        )  # fmt: skip
        policy = policy_for({"a.example", "b.example"}, sensitive_headers=frozenset({"x-corp-id"}))
        SafeHttp(client, policy).download(
            "https://a.example/f", tmp_path / "f", headers={"X-Corp-Id": "S5", "Api-Key": "S6"}
        )
        first, second = world.calls
        assert first.headers["x-api-key"] == "S2" and first.headers["x-corp-id"] == "S5"
        assert second.headers.get("accept") == "*/*"
        leaked = {
            k: v for k, v in second.headers.items() if "S" in v and v[-2:] in {"S1", "S2", "S3", "S4", "S5", "S6"}
        }
        assert leaked == {}, leaked
        for name in ("authorization", "x-api-key", "x-custom-token", "cookie", "x-corp-id", "api-key"):
            assert name not in second.headers

    def test_allow_list_is_port_aware(self, world, policy_for, tmp_path):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(200, content=b"ok")
        http = self.http(world, policy_for)
        with fails("SOURCE_CONTENT_INVALID", "PORT_NOT_ALLOWED"):
            http.get_bytes("https://a.example:8443/f")
        assert world.calls == []
        assert http.get_bytes("https://a.example:443/f").content == b"ok"
        explicit = self.http(world, policy_for, allowed_ports=frozenset({443, 8443}))
        assert explicit.get_bytes("https://a.example:8443/f").content == b"ok"

    def test_redirect_to_another_port_of_an_allowed_host_is_refused(self, world, policy_for):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/f")] = lambda r: httpx.Response(
            302, headers={"location": "https://b.example:8443/x"}
        )
        with fails("SOURCE_CONTENT_INVALID", "PORT_NOT_ALLOWED"):
            self.http(world, policy_for, hosts=("a.example", "b.example")).get_bytes("https://a.example/f")
        assert "b.example" not in world.hosts_called()

    @pytest.mark.parametrize("value", ["²", "٣", "1e3", "nan", "-1", "", "9" * 400])
    def test_retry_after_with_odd_digits_never_crashes(self, world, policy_for, value):  # type: ignore[no-untyped-def]
        world.routes[("a.example", "/x")] = lambda r: httpx.Response(
            429, headers=[(b"Retry-After", value.encode("utf-8"))]
        )
        with fails("PROVIDER_RATE_LIMITED"):
            self.http(world, policy_for).get_json("https://a.example/x")

    @pytest.mark.parametrize("url", ["https://a.example:99999/x", "https://a.example:abc/x", "https://[::1/x"])
    def test_invalid_port_or_url_is_an_adapter_error(self, world, policy_for, tmp_path, url):  # type: ignore[no-untyped-def]
        http = self.http(world, policy_for)
        with fails("SOURCE_CONTENT_INVALID", "INVALID_URL"):
            http.get_bytes(url)
        with fails("SOURCE_CONTENT_INVALID", "INVALID_URL"):
            http.download(url, tmp_path / "o.zip")
        assert world.calls == []

    def test_redact_url_tolerates_an_invalid_port(self):
        from analogforge.adapters.source_http import redact_url

        assert "token" not in redact_url("https://a.example:99999999/x?token=1")


class TestGeoHardening:
    def test_coverage_fraction_handles_antimeridian_wrapping_product_boxes(self):
        aoi = split_bbox([175, 0, -175, 5], "NEG180_180", "NEG180_180")
        wrapped = coverage_fraction(aoi, [(170, 0, -170, 10)])  # west > east: crosses the seam
        split = coverage_fraction(aoi, [(170, 0, 180, 10), (-180, 0, -170, 10)])
        assert wrapped == pytest.approx(1.0) and split == pytest.approx(1.0)
        half = coverage_fraction(aoi, [(178, 0, -178, 5)])  # covers 4 of the 10 degrees
        assert half == pytest.approx(0.4)
        zero360 = split_bbox([355, 0, 5, 5], "ZERO_360", "ZERO_360")
        assert coverage_fraction(zero360, [(350, 0, 10, 5)]) == pytest.approx(1.0)
        assert coverage_fraction(zero360, [(358, 0, 2, 5)]) == pytest.approx(0.4)

    def test_zero_width_bbox_is_rejected(self):
        with fails("NO_COVERAGE", "INPUT_INVALID"):
            split_bbox([10, 0, 10, 5], "NEG180_180", "NEG180_180")


class TestArchiveHardening:
    def test_file_then_directory_collision_is_rejected_and_leaves_nothing(self, tmp_path):
        z = zip_with_members(tmp_path / "c.zip", {"x.hgt": b"a" * 100, "x.hgt/y.hgt": b"b" * 100})
        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_DUPLICATE_MEMBER"):
            safe_extract_zip(z, tmp_path / "out", ArchiveLimits())
        assert not (tmp_path / "out").exists() or not list((tmp_path / "out").rglob("*"))

    def test_partial_files_are_cleaned_when_a_later_member_fails(self, tmp_path):
        z = tmp_path / "p.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("a.hgt", np.random.default_rng(1).bytes(2000))
            zf.writestr("b.hgt", np.random.default_rng(2).bytes(2000))
        raw = bytearray(z.read_bytes())
        raw[raw.index(b"b.hgt") + 60] ^= (
            0xFF  # corrupt the second member's payload (CRC failure after a.hgt is written)
        )
        z.write_bytes(bytes(raw))
        with fails("SOURCE_CONTENT_INVALID", "BAD_ARCHIVE"):
            safe_extract_zip(z, tmp_path / "out", ArchiveLimits())
        assert not list((tmp_path / "out").rglob("*.hgt")) if (tmp_path / "out").exists() else True

    def test_constant_nasadem_tiles_are_not_mistaken_for_bombs(self, tmp_path):
        flat = np.full((1201, 1201), 5, dtype=np.int16)  # a legitimate all-sea / all-flat tile compresses ~500x
        z = nasadem_zip(tmp_path / "n00e000.zip", "n00e000", flat, num=False)
        assert z.stat().st_size * 20 < 1201 * 1201 * 2
        out = earthdata.decode(z, earthdata.NasademParams(work_dir=tmp_path / "w"))
        assert out.data.shape == (1201, 1201) and float(out.data[0, 0]) == 5.0
        # the same ratio is still refused for any other member type
        bomb = zip_with_members(tmp_path / "bomb.zip", {"zeros.hgt": b"\x00" * 2_000_000})
        with fails("RESOURCE_LIMIT", "ARCHIVE_EXPANSION_LIMIT"):
            safe_extract_zip(bomb, tmp_path / "o", ArchiveLimits())


class TestNasademHardening:
    @pytest.mark.parametrize("name", ["n95e010", "s91w010", "n10e181", "n10w181", "n90e010"])
    def test_tile_corner_out_of_range_is_an_adapter_error(self, name):
        with fails("SOURCE_CONTENT_INVALID", "METADATA_INCOMPLETE"):
            earthdata.nasadem.parse_tile_name(name)

    def test_tile_corner_in_range_parses(self):
        assert earthdata.nasadem.parse_tile_name("n89w180") == (89, -180)
        assert earthdata.nasadem.parse_tile_name("s90e179") == (-90, 179)

    def test_decode_of_a_zip_writes_nothing_next_to_the_source(self, tmp_path):
        src = tmp_path / "in"
        src.mkdir()
        arr = global_heights(11, 11, seed=4)
        z = nasadem_zip(src / "n30w100.zip", "n30w100", arr)
        before = sorted(p.name for p in src.iterdir())
        out = earthdata.decode(z, earthdata.NasademParams(expected_samples=11))
        assert sorted(p.name for p in src.iterdir()) == before and out.data.shape == (11, 11)

    def test_mosaic_over_the_cell_budget_is_refused_before_allocation(self, tmp_path):
        def tile(name: str) -> object:
            z = nasadem_zip(tmp_path / f"{name}.zip", name, global_heights(11, 11, seed=5))
            return earthdata.decode(z, earthdata.NasademParams(expected_samples=11, work_dir=tmp_path / name))

        far = [tile("n00w179"), tile("n00e178")]  # 358 degrees apart: ~(359 x 10) cells at N=11
        with fails("RESOURCE_LIMIT", "MOSAIC_TOO_LARGE"):
            earthdata.mosaic(far, max_cells=1000)
        assert earthdata.mosaic(far, max_cells=1_000_000).data.shape[1] == 358 * 10 + 1

    def test_default_budget_refuses_a_world_strip_of_standard_tiles(self, tmp_path):
        paths = []
        for name in ("n00w179", "n00e178"):
            (tmp_path / f"{name}.hgt").write_bytes(hgt_bytes(global_heights(1201, 1201, seed=6)))
            paths.append(earthdata.decode(tmp_path / f"{name}.hgt"))
        with fails("RESOURCE_LIMIT", "MOSAIC_TOO_LARGE"):
            earthdata.mosaic(paths)


class TestPdsAndCmrHardening:
    @pytest.mark.parametrize(
        "path",
        ["a/b.lbl\n", "a/./b.lbl", "./a/b.lbl", "a/b.lbl/", "a//b.lbl", "../a.lbl", "a/../b.lbl", "a/b.lbl\x00", ""],
    )
    def test_validate_relative_rejects_ambiguous_paths(self, path):
        from analogforge.adapters.pds.index import validate_relative

        with fails("SOURCE_CONTENT_INVALID", "ARCHIVE_PATH_TRAVERSAL"):
            validate_relative(path)

    def test_validate_relative_accepts_plain_paths(self):
        from analogforge.adapters.pds.index import validate_relative

        assert validate_relative("data/mola_001.lbl") == "data/mola_001.lbl"

    @pytest.mark.parametrize("granule_ur", ["..", ".", "", "...", "x" * 5000])
    def test_asset_directory_rejects_traversal_and_empty_names(self, tmp_path, granule_ur):
        from analogforge.adapters.source_http.cmr import asset_directory

        with fails("SOURCE_CONTENT_INVALID", "PATH_ESCAPE"):
            asset_directory(tmp_path, "adapter", granule_ur)

    def test_asset_directory_normal_name_stays_below_the_adapter_directory(self, tmp_path):
        from analogforge.adapters.source_http.cmr import asset_directory

        d = asset_directory(tmp_path, "adapter", "NASADEM_HGT_n30w100")
        assert d.parent == tmp_path / "source_bytes" / "adapter"
        flat = asset_directory(tmp_path, "adapter", "a/../..")  # separators are flattened, never followed
        assert flat.parent == tmp_path / "source_bytes" / "adapter" and "/" not in flat.name

    def test_pds4_label_downloads_must_start_like_xml(self, world, policy_for, tmp_path):
        src = pds.DEFAULT_SOURCES[pds.MOLA_ADAPTER_ID]
        rel = "data/m.xml"
        world.routes[(PDS_HOST, f"/mgs/mgs-m-mola-5-megdr-l3-v1/mgsl_300x/{rel}")] = lambda r: httpx.Response(
            200, content=b"\x00\x01binary-not-a-label" * 8
        )
        from analogforge.ports.science_payloads import CoverageSelection

        selection = CoverageSelection(
            selection_key="k", adapter_id=src.adapter_id, product_id=src.product_id, version=None,
            granule_ids=[rel], access_state="AVAILABLE", coverage_fraction=1.0,
        )  # fmt: skip
        http = SafeHttp(world.client(bearer=None), policy_for({PDS_HOST}))
        with fails("SOURCE_CONTENT_INVALID", "MAGIC_MISMATCH"):
            pds.adapter.fetch_pds_products(http, src, selection, tmp_path / "s")


class TestXmlSafeHardening:
    @pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be", "utf-32"])
    def test_doctype_and_entities_are_refused_in_wide_encodings(self, tmp_path, encoding):
        body = '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><r>&b;</r>'
        path = tmp_path / "x.xml"
        path.write_bytes(body.encode(encoding))
        with fails("SOURCE_CONTENT_INVALID", "XML_DTD_FORBIDDEN"):
            pds.xml_safe.parse_xml_file(path)

    def test_declared_non_ascii_compatible_encoding_without_a_bom_is_refused(self, tmp_path):
        body = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE r [<!ENTITY a "x">]><r>&a;</r>'
        path = tmp_path / "x.xml"
        path.write_bytes(body.encode("utf-16-le"))  # no BOM at all
        with pytest.raises(AdapterError) as err:
            pds.xml_safe.parse_xml_file(path)
        assert err.value.detail_code in {"XML_DTD_FORBIDDEN", "LABEL_PARSE_ERROR"}

    def test_plain_utf8_and_utf16_labels_without_dtd_still_parse(self, tmp_path):
        path = tmp_path / "ok.xml"
        path.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?><r><a>1</a></r>')
        assert pds.xml_safe.parse_xml_file(path).tag == "r"
        path.write_bytes('<?xml version="1.0" encoding="UTF-16"?><r><a>1</a></r>'.encode("utf-16"))
        assert pds.xml_safe.parse_xml_file(path).tag == "r"


class TestUserSurveyHardening:
    MD = TestUserSurvey.FULL

    def _scaled(self, tmp_path, scale, offset):  # type: ignore[no-untyped-def]
        raw = (np.arange(36).reshape(6, 6) + 10).astype("int16")
        raw[2, 2] = -9999
        path = tmp_path / "s.tif"
        with rasterio.open(
            path, "w", driver="GTiff", width=6, height=6, count=1, dtype="int16", crs="EPSG:32612",
            transform=from_origin(500000, 3900000, 10, 10), nodata=-9999,
        ) as dst:  # fmt: skip
            dst.write(raw, 1)
            if (scale, offset) != (1.0, 0.0):
                dst.scales = (scale,)
                dst.offsets = (offset,)
        return path, raw

    def test_gdal_scale_and_offset_are_applied_once_and_reported(self, tmp_path):
        path, raw = self._scaled(tmp_path, 0.1, 100.0)
        out = user_survey.decode(path, user_survey.SurveyDecodeParams(user_survey.SurveyMetadata(**self.MD)))
        assert out.data[0, 0] == pytest.approx(101.0) and out.data[1, 1] == pytest.approx(raw[1, 1] * 0.1 + 100.0)
        assert not out.valid[2, 2] and np.isnan(out.data[2, 2])  # nodata matched on the RAW value
        assert out.metadata.scale_applied is True
        assert (out.metadata.source_scale, out.metadata.source_offset) == (pytest.approx(0.1), pytest.approx(100.0))

    def test_scale_is_applied_before_the_feet_conversion(self, tmp_path):
        path, raw = self._scaled(tmp_path, 2.0, 5.0)
        md = user_survey.SurveyMetadata(**{**self.MD, "vertical_units": "ft"})
        out = user_survey.decode(path, user_survey.SurveyDecodeParams(md))
        assert out.data[0, 0] == pytest.approx((raw[0, 0] * 2.0 + 5.0) * 0.3048)

    def test_without_file_scale_nothing_is_applied_and_it_says_so(self, tmp_path):
        path, raw = self._scaled(tmp_path, 1.0, 0.0)
        out = user_survey.decode(path, user_survey.SurveyDecodeParams(user_survey.SurveyMetadata(**self.MD)))
        assert out.data[0, 0] == float(raw[0, 0]) and out.metadata.scale_applied is False


# ======================================== RESOLVE_COVERAGE / FETCH_SOURCE source-policy enforcement
class TestSourcePolicyEnforcement:
    @staticmethod
    def _ctx(tmp_path, mode, calls):  # type: ignore[no-untyped-def]
        import uuid

        from analogforge.ports.science import LocalScienceContext

        def handler(req: httpx.Request) -> httpx.Response:
            calls.append(str(req.url))
            return httpx.Response(200, json={"items": []}, headers={"CMR-Hits": "0"})

        class Ctx(LocalScienceContext):
            def http_client(self):  # type: ignore[no-untyped-def]
                return httpx.Client(transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer x"})

        return Ctx(scratch=tmp_path / "s", workspace_id=uuid.uuid4(), job_id=uuid.uuid4(), mode=mode)

    @staticmethod
    def _aoi(body="EARTH", bbox=(-112.0, 36.0, -111.0, 37.0), convention="NEG180_180"):  # type: ignore[no-untyped-def]
        return AreaOfInterest(
            body=body, bbox=list(bbox), longitude_convention=convention,
            latitude_type="GEODETIC" if body == "EARTH" else "PLANETOCENTRIC", crs_wkt=None, vertical_datum="u",
        )  # fmt: skip

    def _run(self, tmp_path, adapter, mode, *, allow=False, allowed=(), extents=(), aoi=None, fixtures=()):  # type: ignore[no-untyped-def]
        import uuid

        from analogforge.ports.science import ExtentBox, ScienceOperation, ScienceRequest, SourcePolicy
        from analogforge.science.facade import create_science_service

        calls: list[str] = []
        req = ScienceRequest(
            request_id=uuid.uuid4(), operation=ScienceOperation.RESOLVE_COVERAGE, mode=mode,
            inputs=ResolveCoverageInput(
                subject_kind="TARGET", aoi=aoi or self._aoi(), adapter_id=adapter, measurement_kinds=["elevation"]
            ),
            source_policy=SourcePolicy(
                policy_id="p", policy_sha256="0" * 64, allow_network=allow, allowed_adapter_ids=list(allowed),
                allowed_extents=[ExtentBox(body=b, bbox=bb) for b, bb in extents], synthetic_fixture_ids=list(fixtures),
            ),
        )  # fmt: skip
        result = create_science_service().execute(req, self._ctx(tmp_path, mode, calls))
        return result, calls

    def test_network_adapter_without_allow_network_is_blocked_and_makes_no_request(self, tmp_path):
        result, calls = self._run(tmp_path, "earth_nasadem_hgt_v001", "live", allow=False, allowed=["local_dataset"])
        assert result.status == "BLOCKED" and calls == []
        assert result.issues and result.issues[0].detail_code == "POLICY_DENIED"

    def test_network_adapter_not_in_the_allow_list_is_blocked(self, tmp_path):
        for allowed in ([], ["local_dataset"], ["earth_srtmgl1_v003"]):
            result, calls = self._run(tmp_path, "earth_nasadem_hgt_v001", "live", allow=True, allowed=allowed)
            assert result.status == "BLOCKED" and calls == [], allowed
            assert result.issues[0].detail_code == "POLICY_DENIED"

    def test_aoi_outside_the_allowed_extents_is_blocked_and_inside_is_served(self, tmp_path):
        outside = [("EARTH", (10.0, 0.0, 20.0, 10.0))]
        result, calls = self._run(
            tmp_path, "earth_nasadem_hgt_v001", "live", allow=True, allowed=["earth_nasadem_hgt_v001"], extents=outside
        )
        assert result.status == "BLOCKED" and calls == [] and result.issues[0].detail_code == "POLICY_DENIED"
        wrong_body = [("MARS", (-180.0, -90.0, 180.0, 90.0))]
        result, calls = self._run(
            tmp_path,
            "earth_nasadem_hgt_v001",
            "live",
            allow=True,
            allowed=["earth_nasadem_hgt_v001"],
            extents=wrong_body,
        )
        assert result.status == "BLOCKED" and calls == []
        straddling = [("EARTH", (-111.5, 36.0, -100.0, 37.0))]  # covers only half of the AOI
        result, calls = self._run(
            tmp_path,
            "earth_nasadem_hgt_v001",
            "live",
            allow=True,
            allowed=["earth_nasadem_hgt_v001"],
            extents=straddling,
        )
        assert result.status == "BLOCKED" and calls == []
        inside = [("EARTH", (-113.0, 35.0, -110.0, 38.0))]
        result, calls = self._run(
            tmp_path, "earth_nasadem_hgt_v001", "live", allow=True, allowed=["earth_nasadem_hgt_v001"], extents=inside
        )
        assert result.status != "BLOCKED" and calls  # permitted: the (mocked) provider was asked

    def test_synthetic_practice_is_blocked_outside_synthetic_mode(self, tmp_path):
        result, calls = self._run(
            tmp_path, "synthetic_practice", "live", allow=True, allowed=["synthetic_practice"], aoi=self._aoi("MARS")
        )
        assert result.status == "BLOCKED" and calls == []
        assert result.issues[0].detail_code == "MODE_MISMATCH"
        assert result.payload is None and not result.evidence_drafts
        replay, _ = self._run(tmp_path, "synthetic_practice", "replay", aoi=self._aoi("MARS"))
        assert replay.status == "BLOCKED" and replay.issues[0].detail_code == "MODE_MISMATCH"

    def test_synthetic_practice_still_works_in_synthetic_mode(self, tmp_path):
        result, _ = self._run(
            tmp_path, "synthetic_practice", "synthetic", aoi=self._aoi("MARS", (0.0, 0.0, 4.0, 4.0), "ZERO_360")
        )
        assert result.status != "BLOCKED" or result.issues[0].detail_code != "MODE_MISMATCH"

    def test_adapter_outside_a_non_empty_allow_list_is_blocked_for_local_sources_too(self, tmp_path):
        result, _ = self._run(
            tmp_path, "synthetic_practice", "synthetic", allowed=["local_dataset"], aoi=self._aoi("MARS")
        )
        assert result.status == "BLOCKED" and result.issues[0].detail_code == "POLICY_DENIED"

    @pytest.mark.parametrize(
        "bbox", [(10.0, 0.0, 10.0, 5.0), (0.0, 5.0, 5.0, 5.0), (0.0, -91.0, 5.0, 5.0), (0.0, 0.0, 5.0, 95.0)]
    )
    def test_degenerate_or_off_globe_aoi_is_blocked(self, tmp_path, bbox):
        result, calls = self._run(
            tmp_path, "earth_nasadem_hgt_v001", "live", allow=True, allowed=["earth_nasadem_hgt_v001"],
            aoi=self._aoi(bbox=bbox, convention="ZERO_360"),
        )  # fmt: skip
        assert result.status == "BLOCKED" and calls == []

    def test_fetch_source_enforces_the_same_policy(self, tmp_path):
        import uuid

        from analogforge.ports.science import ScienceOperation, ScienceRequest, SourcePolicy
        from analogforge.ports.science_payloads import CoverageSelection, FetchSourceInput
        from analogforge.science.facade import create_science_service

        selection = CoverageSelection(
            selection_key="k", adapter_id="earth_nasadem_hgt_v001", product_id="NASADEM_HGT", version="001",
            granule_ids=["G1-LPCLOUD"], access_state="AVAILABLE", coverage_fraction=1.0,
        )  # fmt: skip

        def go(allow, allowed, extents):  # type: ignore[no-untyped-def]
            from analogforge.ports.science import ExtentBox

            calls: list[str] = []
            req = ScienceRequest(
                request_id=uuid.uuid4(), operation=ScienceOperation.FETCH_SOURCE, mode="live",
                inputs=FetchSourceInput(selection=selection, aoi=self._aoi()),
                source_policy=SourcePolicy(
                    policy_id="p", policy_sha256="0" * 64, allow_network=allow, allowed_adapter_ids=list(allowed),
                    allowed_extents=[ExtentBox(body=b, bbox=bb) for b, bb in extents],
                ),
            )  # fmt: skip
            return create_science_service().execute(req, self._ctx(tmp_path, "live", calls)), calls

        for allow, allowed, extents in [
            (False, ["earth_nasadem_hgt_v001"], []),
            (True, [], []),
            (True, ["earth_srtmgl1_v003"], []),
            (True, ["earth_nasadem_hgt_v001"], [("EARTH", (10.0, 0.0, 20.0, 10.0))]),
        ]:
            result, calls = go(allow, allowed, extents)
            assert result.status == "BLOCKED" and calls == [], (allow, allowed, extents)
            assert result.issues[0].detail_code == "POLICY_DENIED"
