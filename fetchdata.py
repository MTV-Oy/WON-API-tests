#!/usr/bin/env python3
"""
fetchdata.py — Live test data fetcher for WONT smoke/regression tests
Fetches fresh reference IDs from the target environment and writes
them to testdata_<env>.json for use by the test suite.

Usage:
    python fetchdata.py --env dev
    python fetchdata.py --env test
    python fetchdata.py --env prod

ENV-tiedostot: env/wont_dev.env  env/wont_test.env  env/wont_prod.env
"""

import argparse
import json
import sys
import os
import socket
import pathlib
import logging
import datetime
import time
import xml.etree.ElementTree as ET
import requests

# ============================================================
# CLI
# ============================================================
VALID_ENVS = ["dev", "test", "prod"]

parser = argparse.ArgumentParser(
    description="Fetch fresh test data from a WONT environment."
)
parser.add_argument(
    "--env",
    required=True,
    choices=VALID_ENVS,
    help="Target environment: dev | test | prod",
)
parser.add_argument(
    "--out",
    default=None,
    help="Output file path (default: testdata_<env>.json)",
)
args = parser.parse_args()

ENV = args.env
OUT = args.out or f"testdata_{ENV}.json"

# ============================================================
# Ladataan ympäristömuuttujat .env-tiedostosta
# ============================================================
SCRIPT_DIR = pathlib.Path(__file__).parent
ENV_FILE = SCRIPT_DIR / "env" / f"wont_{ENV}.env"
if not ENV_FILE.exists():
    ENV_FILE = SCRIPT_DIR / f"wont_{ENV}.env"

if not ENV_FILE.exists():
    print(f"❌ ENV-tiedostoa ei löydy: {ENV_FILE}")
    print(f"   Odotettiin tiedostoa: wont_{{dev|test|prod}}.env tai env/wont_{{dev|test|prod}}.env")
    sys.exit(1)

with open(ENV_FILE) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

HOST = {
    "HOST_BAPI":      os.environ["HOST_BAPI"],
    "HOST_COMET":     os.environ["HOST_COMET"],
    "HOST_CONF_REST": os.environ["HOST_CONF_REST"],
    "HOST_CIM":       os.environ["HOST_CIM"],
    "HOST_FENIX":     os.environ["HOST_FENIX"],
    "HOST_WON":       os.environ["HOST_WON"],
}

TIMEOUT = 10  # seconds
RUN_START    = datetime.datetime.now()
RUN_START_TS = RUN_START.isoformat(timespec="milliseconds")

# ============================================================
# Lokitus — konsoli + logs/fetchdata_<env>_<aikaleima>.log + .html
# ============================================================
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
timestamp     = RUN_START.strftime("%Y%m%d_%H%M%S")
LOG_FILE      = LOG_DIR / f"fetchdata_{ENV}_{timestamp}.log"
HTML_LOG_FILE = LOG_DIR / f"fetchdata_{ENV}_{timestamp}.html"

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger()

log.info(f"\n🔍 Fetching test data from environment: {ENV}  ({ENV_FILE})")
log.info(f"   Output file:       {OUT}")
log.info(f"   Lokitiedosto:      {LOG_FILE}")
log.info(f"   HTML-lokitiedosto: {HTML_LOG_FILE}")
log.info("=" * 60)

# ============================================================
# Event collector — TCP probes & requests
# ============================================================
all_events = []
raw_lines  = []

def _now_ts():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:12]

def _log(msg):
    log.info(msg)
    raw_lines.append(msg)

# ============================================================
# TCP probe helper
# ============================================================
def tcp_probe(key: str, url: str):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    ts = _now_ts()
    t0 = time.perf_counter()
    try:
        sock = socket.create_connection((host, port), timeout=3)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        sock.close()
        msg = f"TCP OK ({ms} ms)"
        ok  = True
    except ConnectionRefusedError:
        ms  = -1
        msg = "TCP REFUSED — port closed or service not listening"
        ok  = False
    except OSError as e:
        ms  = -1
        msg = f"TCP ERROR — {e}"
        ok  = False
    icon = "✅" if ok else "❌"
    _log(f"  {icon} TCP {key} ({host}:{port}) — {msg}")
    all_events.append({
        "type": "tcp_probe",
        "host": host, "port": port, "key": key,
        "ok": ok, "msg": msg, "ms": ms, "ts": ts,
    })
    return ok, ms

# ============================================================
# Run TCP probes for all services
# ============================================================
_log("\n[INFO] TCP probes")
_log("-" * 40)
tcp_cache = {}
for key, url in HOST.items():
    ok, ms = tcp_probe(key, url)
    tcp_cache[key] = {"ok": ok, "ms": ms}

# ============================================================
# Fetch helpers
# ============================================================
errors           = []
_current_section = "(none)"

def set_section(name: str):
    global _current_section
    _current_section = name


def _parse_response(r, label: str):
    ct = r.headers.get("Content-Type", "").lower()
    if "json" in ct or r.text.lstrip().startswith("{") or r.text.lstrip().startswith("["):
        try:
            data = r.json()
            return ("json", data)
        except Exception:
            pass
    try:
        raw = r.content
        if raw.startswith(b'\xef\xbb\xbf'):
            raw = raw[3:]
        text = raw.decode(r.apparent_encoding or "utf-8", errors="replace")
        root = ET.fromstring(text)
        return ("xml", root)
    except ET.ParseError:
        pass
    _log(f"     ⚠️  Could not parse response as JSON or XML")
    _log(f"        Content-Type: {ct}")
    _log(f"        Body preview: {r.text[:120]!r}")
    errors.append(f"{label}: unparseable response (not JSON or XML)")
    return None


def _host_key_for_url(url: str) -> str:
    for k, v in HOST.items():
        if url.startswith(v):
            return k
    return None


def fetch(label: str, url: str):
    from urllib.parse import urlparse
    ts       = _now_ts()
    host_key = _host_key_for_url(url)
    parsed   = urlparse(url)
    service  = f"{parsed.hostname}:{parsed.port}"

    # Skip HTTP if TCP already failed for this host
    if host_key and not tcp_cache.get(host_key, {}).get("ok", True):
        tcp_ms = tcp_cache[host_key]["ms"]
        err    = "TCP REFUSED — port closed or service not listening"
        _log(f"  ❌ {label} — TCP_FAIL (skipped HTTP)")
        errors.append(f"{label}: TCP_FAIL")
        all_events.append({
            "type": "request", "label": label, "url": url,
            "service": service, "section": _current_section,
            "status": "TCP_FAIL", "tcp_ms": tcp_ms,
            "http_status": None, "elapsed_ms": None,
            "fmt": None, "error": err, "headers": {}, "ts": ts,
        })
        return None

    tcp_ms = tcp_cache.get(host_key, {}).get("ms") if host_key else None
    t0 = time.perf_counter()
    try:
        r = requests.get(url, timeout=TIMEOUT)
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        if r.status_code == 200:
            result = _parse_response(r, label)
            if result:
                fmt = result[0]
                _log(f"  ✅ {label}  [{fmt.upper()}]  ({elapsed_ms} ms)")
                all_events.append({
                    "type": "request", "label": label, "url": url,
                    "service": service, "section": _current_section,
                    "status": "OK", "tcp_ms": tcp_ms,
                    "http_status": r.status_code, "elapsed_ms": elapsed_ms,
                    "fmt": fmt.upper(), "error": None,
                    "headers": dict(r.headers), "ts": ts,
                })
                return result
            all_events.append({
                "type": "request", "label": label, "url": url,
                "service": service, "section": _current_section,
                "status": "PARSE_ERROR", "tcp_ms": tcp_ms,
                "http_status": r.status_code, "elapsed_ms": elapsed_ms,
                "fmt": None, "error": "unparseable response",
                "headers": dict(r.headers), "ts": ts,
            })
            return None
        else:
            _log(f"  ❌ {label} — HTTP {r.status_code}  ({elapsed_ms} ms)")
            errors.append(f"{label}: HTTP {r.status_code}")
            all_events.append({
                "type": "request", "label": label, "url": url,
                "service": service, "section": _current_section,
                "status": f"HTTP_{r.status_code}", "tcp_ms": tcp_ms,
                "http_status": r.status_code, "elapsed_ms": elapsed_ms,
                "fmt": None, "error": f"HTTP {r.status_code}",
                "headers": dict(r.headers), "ts": ts,
            })
            return None
    except requests.exceptions.ConnectionError as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        err = str(e)[:120]
        _log(f"  ❌ {label} — CONNECTION ERROR: {err}")
        errors.append(f"{label}: connection error")
        all_events.append({
            "type": "request", "label": label, "url": url,
            "service": service, "section": _current_section,
            "status": "ERROR", "tcp_ms": tcp_ms,
            "http_status": None, "elapsed_ms": elapsed_ms,
            "fmt": None, "error": err, "headers": {}, "ts": ts,
        })
        return None
    except requests.exceptions.Timeout:
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        err = f"HTTP timeout after {TIMEOUT}s" + (f" (TCP OK in {tcp_ms}ms)" if tcp_ms and tcp_ms > 0 else "")
        _log(f"  ❌ {label} — TIMEOUT after {TIMEOUT}s")
        errors.append(f"{label}: timeout")
        all_events.append({
            "type": "request", "label": label, "url": url,
            "service": service, "section": _current_section,
            "status": "TIMEOUT", "tcp_ms": tcp_ms,
            "http_status": None, "elapsed_ms": elapsed_ms,
            "fmt": None, "error": err, "headers": {}, "ts": ts,
        })
        return None


# ── JSON helpers ─────────────────────────────────────────────

def first(data, *keys):
    current = data
    for key in keys:
        if current is None:
            return None
        if isinstance(current, list):
            if not current:
                return None
            current = current[0]
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    if isinstance(current, list):
        return current[0] if current else None
    return current


def collect_list(data, *keys, limit=5):
    current = data
    for key in keys:
        if current is None:
            return []
        if isinstance(current, list):
            current = current[0] if current else None
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return []
    if isinstance(current, list):
        return current[:limit]
    return []


# ── XML helpers ──────────────────────────────────────────────

def xml_text(root: ET.Element, *tags) -> str | None:
    if root is None:
        return None
    for tag in tags:
        el = root.find(f".//{tag}")
        if el is not None and el.text:
            return el.text.strip()
        tag_lower = tag.lower()
        for el in root.iter():
            local = el.tag.split("}")[-1] if "}" in el.tag else el.tag
            if local.lower() == tag_lower and el.text:
                return el.text.strip()
    return None


def xml_collect(root: ET.Element, item_tag: str, *field_tags, limit=5) -> list:
    if root is None:
        return []
    results = []
    for item in root.iter():
        local = item.tag.split("}")[-1] if "}" in item.tag else item.tag
        if local.lower() == item_tag.lower():
            val = xml_text(item, *field_tags)
            if val:
                results.append(val)
            if len(results) >= limit:
                break
    return results


# ── Unified accessors ─────────────────────────────────────────

def get_field(result, *json_keys, xml_tags=None, fallback=None):
    if result is None:
        return fallback
    fmt, data = result
    if fmt == "json":
        val = first(data, *json_keys)
        return val if val is not None else fallback
    else:
        tags = xml_tags if xml_tags else list(json_keys)
        val = xml_text(data, *tags)
        return val if val is not None else fallback


def get_list(result, item_tag, *field_tags, json_key=None, limit=5):
    if result is None:
        return []
    fmt, data = result
    if fmt == "xml":
        return xml_collect(data, item_tag, *field_tags, limit=limit)
    else:
        key = json_key or item_tag
        return collect_list(data, key, limit=limit)


# ============================================================
# Section: FENIX — products
# ============================================================
set_section("FENIX products")
_log("\n📦 FENIX — products")
_log("-" * 40)

td = {}

fenix_products_raw = fetch(
    "FENIX /products/search (productCode=2635258)",
    f"{HOST['HOST_FENIX']}/api/v1/products/search?searchParameters=eq(productCodeSelection,2635258)"
)
td["fenix_product_external_reference"] = get_field(
    fenix_products_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
)
td["fenix_product_code"] = get_field(
    fenix_products_raw, "productCode",
    xml_tags=["productCode", "product_code"],
    fallback="2635258",
)

fenix_products_raw2 = fetch(
    "FENIX /products/search (productCode=2084741)",
    f"{HOST['HOST_FENIX']}/api/v1/products/search?searchParameters=eq(productCodeSelection,2084741)"
)
td["fenix_product_external_reference_2"] = get_field(
    fenix_products_raw2, "externalReference",
    xml_tags=["externalReference", "external_reference"],
)
td["fenix_product_code_2"] = "2084741"

fenix_product_ref_raw = fetch(
    "FENIX /products/externalReference/4986920692527 (product-type ref probe)",
    f"{HOST['HOST_FENIX']}/api/v1/products/externalReference/4986920692527"
)
td["fenix_product_ext_ref_527"] = get_field(
    fenix_product_ref_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
    fallback="4986920692527",
)

set_section("WON products")
won_product_ref_raw = fetch(
    "WON /products/externalReference/6562484569527 (product-type ref probe)",
    f"{HOST['HOST_WON']}/api/won/products/externalReference/6562484569527"
)
td["won_product_ext_ref_527"] = get_field(
    won_product_ref_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
    fallback="6562484569527",
)


# ============================================================
# Section: FENIX — medias
# ============================================================
set_section("FENIX medias")
_log("\n🎬 FENIX — medias")
_log("-" * 40)

fenix_media_raw = fetch(
    "FENIX /media/search (label=M0492294, mediaType=784165)",
    f"{HOST['HOST_FENIX']}/api/v1/media/search?searchParameters=eq(labelSelection,M0492294);eq(mediaTypeSelection,784165)"
)
td["fenix_media_label"]        = "M0492294"
td["fenix_media_type"]         = "784165"
td["fenix_media_external_ref"] = get_field(
    fenix_media_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
)

fenix_mediainfo_raw = fetch(
    "FENIX /mediainfo/search (label=M0528056)",
    f"{HOST['HOST_FENIX']}/api/v1/mediainfo/search?searchParameters=eq(labelSelection,M0528056)"
)
td["fenix_mediainfo_label"]   = "M0528056"
td["fenix_mediainfo_ext_ref"] = get_field(
    fenix_mediainfo_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
)

fenix_mediaassets_raw = fetch(
    "FENIX /mediaAssetsMM/search (label=M0302295)",
    f"{HOST['HOST_FENIX']}/api/v1/mediaAssetsMM/search?searchParameters=eq(labelSelection,M0302295)"
)
td["fenix_media_asset_label"] = "M0302295"
td["fenix_media_asset_oid"]   = get_field(
    fenix_mediaassets_raw, "oid",
    xml_tags=["oid"],
    fallback="5054797793000",
)

fenix_won_medias_raw = fetch(
    "FENIX /won_medias/search (mediaType=784165, label=M0471288)",
    f"{HOST['HOST_FENIX']}/api/v1/won_medias/search?searchParameters=eq(mediaTypeSelection,784165);eq(labelSelection,M0471288)"
)
td["fenix_won_media_label"]        = "M0471288"
td["fenix_won_media_type"]         = "784165"
td["fenix_won_media_external_ref"] = get_field(
    fenix_won_medias_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
)


# ============================================================
# Section: FENIX — editorials
# ============================================================
set_section("FENIX editorials")
_log("\n📝 FENIX — editorials")
_log("-" * 40)

fenix_editorial_utf8_raw = fetch(
    "FENIX /editorials/externalReference (UTF-8 known ref)",
    f"{HOST['HOST_FENIX']}/api/v1/editorials/externalReference/7877090496527"
)
td["fenix_editorial_ext_ref_utf8"] = get_field(
    fenix_editorial_utf8_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
    fallback="7877090496527",
)

fenix_editorial_iso_raw = fetch(
    "FENIX /editorials/externalReference (iso-8859-1 known ref)",
    f"{HOST['HOST_FENIX']}/api/v1/editorials/externalReference/5913039660527"
)
td["fenix_editorial_ext_ref_iso"] = get_field(
    fenix_editorial_iso_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
    fallback="5913039660527",
)


# ============================================================
# Section: FENIX — channels
# ============================================================
set_section("FENIX channels")
_log("\n📡 FENIX — channels")
_log("-" * 40)

fenix_channels_raw = fetch(
    "FENIX /channel/list",
    f"{HOST['HOST_FENIX']}/api/v1/channel/list"
)
td["fenix_channel_ids"] = get_list(
    fenix_channels_raw,
    "channel",
    "externalReference", "id", "channelId",
    json_key="channels",
    limit=3,
)
td["fenix_channel_id_1"] = td["fenix_channel_ids"][0] if td["fenix_channel_ids"] else "53634538"


# ============================================================
# Section: FENIX — video & subtitling components
# ============================================================
set_section("FENIX video")
_log("\n🎥 FENIX — video & subtitling components")
_log("-" * 40)

fenix_video_raw = fetch(
    "FENIX /videoComponentsMM/externalReference/7505782762000",
    f"{HOST['HOST_FENIX']}/api/v1/videoComponentsMM/externalReference/7505782762000"
)
td["fenix_video_component_ext_ref"] = get_field(
    fenix_video_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
    fallback="7505782762000",
)

fenix_sub_raw = fetch(
    "FENIX /subtitlingComponentsMM/externalReference/7505782770000",
    f"{HOST['HOST_FENIX']}/api/v1/subtitlingComponentsMM/externalReference/7505782770000"
)
td["fenix_subtitling_component_ext_ref"] = get_field(
    fenix_sub_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
    fallback="7505782770000",
)


# ============================================================
# Section: WON API — metabank products
# ============================================================
set_section("WON metabank")
_log("\n🏦 WON API — metabank products")
_log("-" * 40)

won_metabank_raw = fetch(
    "WON /metabank/products (productCode=2084741)",
    f"{HOST['HOST_WON']}/api/won/metabank/products?searchParameters=eq(productCodeSelection,2084741)"
)
td["won_metabank_product_code"] = "2084741"
td["won_metabank_ext_ref"]      = get_field(
    won_metabank_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
)

set_section("WON products")
won_products_raw = fetch(
    "WON /products/search (productCode=2635258)",
    f"{HOST['HOST_WON']}/api/won/products/search?searchParameters=eq(productCodeSelection,2635258)"
)
td["won_product_code"]    = "2635258"
td["won_product_ext_ref"] = get_field(
    won_products_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
    fallback="6562484569527",
)


# ============================================================
# Section: Configurable REST — trailers
# ============================================================
set_section("ConfREST trailers")
_log("\n🎞️  Configurable REST — trailers")
_log("-" * 40)

conf_trailers_raw = fetch(
    "ConfREST /trailers/search (mediaLabel=722874)",
    f"{HOST['HOST_CONF_REST']}/WONREST/trailers/search?searchParameters=eq(mediaQuerySelection,withMedia);eq(mediaLabelSelection,722874)"
)
td["conf_rest_trailer_media_label"] = "722874"
td["conf_rest_trailer_ext_ref"]     = get_field(
    conf_trailers_raw, "externalReference",
    xml_tags=["externalReference", "external_reference", "mediaExternalReference"],
)

set_section("ConfREST products")
conf_product_raw = fetch(
    "ConfREST /metabank_prod_getProduct/externalReference/4986920692527",
    f"{HOST['HOST_CONF_REST']}/WONREST/metabank_prod_getProduct/externalReference/4986920692527"
)
td["conf_rest_product_ext_ref"] = get_field(
    conf_product_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
    fallback="4986920692527",
)

set_section("ConfREST series")
conf_series_raw = fetch(
    "ConfREST /metabank_prod_getSeries/externalReference/2392281679527",
    f"{HOST['HOST_CONF_REST']}/WONREST/metabank_prod_getSeries/externalReference/2392281679527"
)
td["conf_rest_series_ext_ref"] = get_field(
    conf_series_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
    fallback="2392281679527",
)

set_section("ConfREST tx")
conf_tx_raw = fetch(
    "ConfREST /metabank_prod_getTx/externalReference/2378023463813",
    f"{HOST['HOST_CONF_REST']}/WONREST/metabank_prod_getTx/externalReference/2378023463813"
)
td["conf_rest_tx_ext_ref"] = get_field(
    conf_tx_raw, "externalReference",
    xml_tags=["externalReference", "external_reference"],
    fallback="2378023463813",
)


# ============================================================
# Section: COMET — trailers
# ============================================================
set_section("COMET trailers")
_log("\n📺 COMET — trailers")
_log("-" * 40)

comet_raw = fetch(
    "COMET /trailers/search (mediaLabel=722874)",
    f"{HOST['HOST_COMET']}/WONREST/trailers/search?searchParameters=eq(mediaQuerySelection,withMedia);eq(availableDateBlackoutSelection,true);eq(mediaLabelSelection,722874)"
)
td["comet_trailer_media_label"] = "722874"
td["comet_trailer_ext_ref"]     = get_field(
    comet_raw, "externalReference",
    xml_tags=["externalReference", "external_reference", "mediaExternalReference"],
)


# ============================================================
# Section: BAPI — seasons
# ============================================================
set_section("BAPI seasons")
_log("\n🏟️  BAPI — seasons")
_log("-" * 40)

bapi_raw = fetch(
    "BAPI /sport/v1/seasons",
    f"{HOST['HOST_BAPI']}/sport/v1/seasons"
)
td["bapi_season_ids"] = get_list(
    bapi_raw,
    "season",
    "id", "seasonId",
    json_key="seasons",
    limit=3,
)


# ============================================================
# Write output JSON
# ============================================================
RUN_DURATION = round((datetime.datetime.now() - RUN_START).total_seconds(), 1)

output = {
    "_meta": {
        "env":        ENV,
        "fetched_at": RUN_START.isoformat(timespec="seconds"),
        "hosts":      HOST,
        "errors":     errors,
    },
    "data": td,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

_log(f"\n{'=' * 60}")
_log(f"  ✅ Wrote {len(td)} data keys to {OUT}")
nulls = [k for k, v in td.items() if v is None or v == []]
if nulls:
    _log(f"  ⚠️  {len(nulls)} key(s) are still null/empty:")
    for k in nulls:
        _log(f"     - {k}")
if errors:
    _log(f"  ❌ {len(errors)} fetch error(s):")
    for e in errors:
        _log(f"     - {e}")
_log(f"{'=' * 60}\n")


# ============================================================
# Write HTML log
# ============================================================
req_events = [e for e in all_events if e["type"] == "request"]
tcp_events = [e for e in all_events if e["type"] == "tcp_probe"]

n_total  = len(req_events)
n_ok     = sum(1 for e in req_events if e["status"] == "OK")
n_fail   = n_total - n_ok
ms_list  = [e["elapsed_ms"] for e in req_events if e.get("elapsed_ms") is not None]
avg_ms   = round(sum(ms_list) / len(ms_list)) if ms_list else 0
max_ms   = max(ms_list) if ms_list else 0

sections     = sorted(set(e.get("section", "") for e in req_events if e.get("section")))
services     = sorted(set(e.get("service", "")  for e in req_events if e.get("service")))
statuses     = sorted(set(e["status"] for e in req_events if e["status"] != "OK"))
hostname     = socket.gethostname()
csv_filename = f"fetchdata_{ENV}_{timestamp}.csv"

section_opts = "".join(f'<option value="{s}">{s}</option>' for s in sections)
service_opts = "".join(f'<option value="{s}">{s}</option>' for s in services)
status_opts  = "".join(f'<option value="{s}">{s}</option>' for s in statuses)

events_json   = json.dumps(all_events,  ensure_ascii=False)
rawlines_json = json.dumps(raw_lines,   ensure_ascii=False)
max_bar_ms    = max_ms or 10000

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>fetchdata log — {ENV} — {RUN_START_TS}</title>
<style>
:root {{
  --bg:#0f1117;--surface:#1a1d27;--border:#2d3148;
  --text:#e2e8f0;--muted:#6b7280;
  --ok:#22c55e;--fail:#ef4444;--warn:#f59e0b;--info:#60a5fa;--timeout:#f97316;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;font-size:13px}}
header{{background:var(--surface);border-bottom:1px solid var(--border);padding:18px 24px}}
header h1{{font-size:18px;font-weight:700;color:#a78bfa}}
.meta{{color:var(--muted);margin-top:4px;font-size:12px}}
.summary-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;padding:20px 24px}}
.stat-card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 16px}}
.stat-card .val{{font-size:26px;font-weight:700}}
.stat-card .lbl{{color:var(--muted);font-size:11px;margin-top:2px}}
.stat-card.ok .val{{color:var(--ok)}}
.stat-card.fail .val{{color:var(--fail)}}
.stat-card.warn .val{{color:var(--warn)}}
.stat-card.info .val{{color:var(--info)}}
.toolbar{{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-end;padding:14px 24px;background:var(--surface);border-bottom:1px solid var(--border)}}
.toolbar label{{color:var(--muted);font-size:11px;display:block;margin-bottom:4px}}
.toolbar input,.toolbar select{{background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:6px 10px;font-size:12px}}
.toolbar input{{width:220px}}
.btn{{background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:6px 14px;cursor:pointer;font-size:12px}}
.btn:hover{{border-color:#a78bfa}}
.tabs{{display:flex;gap:2px;padding:12px 24px 0;border-bottom:1px solid var(--border)}}
.tab{{padding:7px 16px;cursor:pointer;border-radius:6px 6px 0 0;color:var(--muted);font-size:13px;border:1px solid transparent;border-bottom:none;margin-bottom:-1px}}
.tab.active{{background:var(--surface);border-color:var(--border);color:var(--text)}}
.tab-content{{display:none;padding:16px 24px 32px}}
.tab-content.active{{display:block}}
.tbl-wrap{{overflow-x:auto;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{background:var(--surface);color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:8px 10px;border-bottom:1px solid var(--border);cursor:pointer;white-space:nowrap;user-select:none}}
th:hover{{color:var(--text)}}
.si{{opacity:.35;margin-left:3px}}
th.asc .si::after{{content:" ▲";opacity:1}}
th.desc .si::after{{content:" ▼";opacity:1}}
td{{padding:7px 10px;border-bottom:1px solid #1e2235;vertical-align:top}}
tr:hover td{{background:#151827}}
.url-cell{{font-family:monospace;font-size:11px;word-break:break-all;max-width:380px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:10px;font-weight:600;white-space:nowrap}}
.b-ok{{background:#14532d;color:#4ade80}}
.b-fail{{background:#450a0a;color:#f87171}}
.b-timeout{{background:#431407;color:#fb923c}}
.b-warn{{background:#422006;color:#fbbf24}}
.ms-bar{{display:inline-block;height:8px;border-radius:4px;vertical-align:middle;margin-left:6px;opacity:.7}}
.tcp-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}}
.tcp-card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 16px}}
.tcp-card .host{{font-family:monospace;font-weight:600}}
.tcp-card .msg{{color:var(--muted);font-size:11px;margin-top:4px}}
#raw-log{{font-family:monospace;font-size:11px;line-height:1.65;background:#090b10;border:1px solid var(--border);border-radius:8px;padding:16px;white-space:pre-wrap;word-break:break-all;max-height:600px;overflow-y:auto}}
.ll-OK{{color:#4ade80}}.ll-ERROR{{color:#f87171}}.ll-WARN{{color:#fbbf24}}
.ll-REQUEST{{color:#93c5fd}}.ll-RESPONSE{{color:#c4b5fd}}
.ll-TCP_OK{{color:#34d399}}.ll-TCP_FAIL{{color:#f87171}}
.ll-DEBUG{{color:#6b7280}}.ll-INFO{{color:#e2e8f0}}
#no-results{{color:var(--muted);padding:24px;text-align:center;display:none}}
</style>
</head>
<body>
<header>
  <h1>fetchdata.py &mdash; run log</h1>
  <div class="meta">
    Environment: <strong>{ENV}</strong> &nbsp;|&nbsp;
    Started: <strong>{RUN_START_TS}</strong> &nbsp;|&nbsp;
    Duration: <strong>{RUN_DURATION}s</strong> &nbsp;|&nbsp;
    Host: <strong>{hostname}</strong>
  </div>
</header>

<div class="summary-grid">
  <div class="stat-card info"><div class="val">{n_total}</div><div class="lbl">Total requests</div></div>
  <div class="stat-card ok">  <div class="val">{n_ok}</div>  <div class="lbl">Succeeded</div></div>
  <div class="stat-card fail"><div class="val">{n_fail}</div><div class="lbl">Failed</div></div>
  <div class="stat-card warn"><div class="val">{avg_ms}</div><div class="lbl">Avg resp ms</div></div>
  <div class="stat-card warn"><div class="val">{max_ms}</div><div class="lbl">Max resp ms</div></div>
  <div class="stat-card fail"><div class="val">{len(errors)}</div><div class="lbl">Errors</div></div>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('requests',this)">Requests</div>
  <div class="tab" onclick="showTab('sections',this)">By Section</div>
  <div class="tab" onclick="showTab('tcp',this)">TCP Probes</div>
  <div class="tab" onclick="showTab('rawlog',this)">Raw Log</div>
</div>

<!-- REQUESTS TAB -->
<div id="tab-requests" class="tab-content active">
  <div class="toolbar">
    <div><label>Search</label><input id="q" placeholder="label, URL, status, error…" oninput="applyFilters()"></div>
    <div><label>Status</label>
      <select id="f-status" onchange="applyFilters()">
        <option value="">All</option>{status_opts}
      </select>
    </div>
    <div><label>Section</label>
      <select id="f-section" onchange="applyFilters()">
        <option value="">All sections</option>{section_opts}
      </select>
    </div>
    <div><label>Service</label>
      <select id="f-service" onchange="applyFilters()">
        <option value="">All services</option>{service_opts}
      </select>
    </div>
    <div style="display:flex;gap:8px">
      <button class="btn" onclick="resetFilters()">Reset</button>
      <button class="btn" onclick="exportCSV()">Export CSV</button>
    </div>
  </div>
  <div class="tbl-wrap">
    <table id="req-tbl">
      <thead><tr>
        <th onclick="srt(0)">#<span class="si"></span></th>
        <th onclick="srt(1)">Time<span class="si"></span></th>
        <th onclick="srt(2)">Section<span class="si"></span></th>
        <th onclick="srt(3)">Label<span class="si"></span></th>
        <th onclick="srt(4)">Status<span class="si"></span></th>
        <th onclick="srt(5)">HTTP<span class="si"></span></th>
        <th onclick="srt(6)">Fmt<span class="si"></span></th>
        <th onclick="srt(7)">TCP ms<span class="si"></span></th>
        <th onclick="srt(8)">Elapsed ms<span class="si"></span></th>
        <th>URL</th>
        <th>Error / detail</th>
      </tr></thead>
      <tbody id="req-tbody"></tbody>
    </table>
    <div id="no-results">No rows match the current filters.</div>
  </div>
</div>

<!-- SECTIONS TAB -->
<div id="tab-sections" class="tab-content">
  <div class="tbl-wrap">
    <table id="sec-tbl">
      <thead><tr>
        <th onclick="srtAgg('sec-tbl',0)">Section<span class="si"></span></th>
        <th onclick="srtAgg('sec-tbl',1)">Total<span class="si"></span></th>
        <th onclick="srtAgg('sec-tbl',2)">OK<span class="si"></span></th>
        <th onclick="srtAgg('sec-tbl',3)">Failed<span class="si"></span></th>
        <th onclick="srtAgg('sec-tbl',4)">Avg ms<span class="si"></span></th>
        <th onclick="srtAgg('sec-tbl',5)">Max ms<span class="si"></span></th>
        <th onclick="srtAgg('sec-tbl',6)">Timeouts<span class="si"></span></th>
      </tr></thead>
      <tbody id="sec-tbody"></tbody>
    </table>
  </div>
</div>

<!-- TCP TAB -->
<div id="tab-tcp" class="tab-content">
  <div class="tcp-grid" id="tcp-grid"></div>
</div>

<!-- RAW LOG TAB -->
<div id="tab-rawlog" class="tab-content">
  <div id="raw-log"></div>
</div>

<script>
const ALL_EVENTS = {events_json};
const reqEvents = ALL_EVENTS.filter(e => e.type === 'request');
const tcpEvents = ALL_EVENTS.filter(e => e.type === 'tcp_probe');
const RAW_LINES = {rawlines_json};
const MAX_BAR_MS = {max_bar_ms};

function showTab(id, el) {{
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + id).classList.add('active');
  el.classList.add('active');
}}

function badge(s) {{
  const c = s==='OK'?'b-ok':s.includes('TIMEOUT')?'b-timeout':'b-fail';
  return `<span class="badge ${{c}}">${{s}}</span>`;
}}

function msCell(ms) {{
  if (ms==null) return '<span style="color:var(--muted)">—</span>';
  const w = Math.min(60, Math.round((ms / MAX_BAR_MS) * 60));
  const col = ms>5000?'#ef4444':ms>1000?'#f59e0b':'#3b82f6';
  return `${{ms}}<span class="ms-bar" style="width:${{w}}px;background:${{col}}"></span>`;
}}

let currentRows = [];
function renderTable(rows) {{
  currentRows = rows;
  const nr = document.getElementById('no-results');
  const tb = document.getElementById('req-tbody');
  if (!rows.length) {{ tb.innerHTML=''; nr.style.display='block'; return; }}
  nr.style.display='none';
  tb.innerHTML = rows.map((e,i) => `<tr>
    <td>${{i+1}}</td>
    <td style="white-space:nowrap;color:var(--muted);font-size:11px">${{e.ts||''}}</td>
    <td style="white-space:nowrap">${{e.section||''}}</td>
    <td style="max-width:200px;word-break:break-word">${{e.label}}</td>
    <td>${{badge(e.status)}}</td>
    <td>${{e.http_status??'<span style="color:var(--muted)">—</span>'}}</td>
    <td style="font-family:monospace">${{e.fmt??'—'}}</td>
    <td style="font-variant-numeric:tabular-nums">${{msCell(e.tcp_ms)}}</td>
    <td style="font-variant-numeric:tabular-nums">${{msCell(e.elapsed_ms)}}</td>
    <td class="url-cell"><a href="${{e.url}}" style="color:var(--info);text-decoration:none" target="_blank">${{e.url}}</a></td>
    <td style="color:var(--fail);font-size:11px;max-width:220px;word-break:break-word">${{e.error||''}}</td>
  </tr>`).join('');
}}

function applyFilters() {{
  const q  = document.getElementById('q').value.toLowerCase();
  const fs = document.getElementById('f-status').value;
  const fc = document.getElementById('f-section').value;
  const fv = document.getElementById('f-service').value;
  const rows = reqEvents.filter(e => {{
    if (fs && e.status  !==fs) return false;
    if (fc && e.section !==fc) return false;
    if (fv && e.service !==fv) return false;
    if (q && !JSON.stringify(e).toLowerCase().includes(q)) return false;
    return true;
  }});
  renderTable(rows);
}}

function resetFilters() {{
  ['q','f-status','f-section','f-service'].forEach(id => {{
    const el = document.getElementById(id);
    if (el.tagName==='INPUT') el.value=''; else el.value='';
  }});
  renderTable(reqEvents);
}}

let srtCol=-1, srtDir=1;
const COL_KEYS=['_i','ts','section','label','status','http_status','fmt','tcp_ms','elapsed_ms'];
function srt(col) {{
  srtDir = srtCol===col ? -srtDir : 1;
  srtCol = col;
  document.querySelectorAll('#req-tbl th').forEach((th,i)=>{{
    th.classList.remove('asc','desc');
    if(i===col) th.classList.add(srtDir===1?'asc':'desc');
  }});
  const key = COL_KEYS[col];
  const sorted = [...currentRows].sort((a,b)=>{{
    const av = col===0?reqEvents.indexOf(a):(a[key]??'');
    const bv = col===0?reqEvents.indexOf(b):(b[key]??'');
    if(av<bv) return -srtDir; if(av>bv) return srtDir; return 0;
  }});
  renderTable(sorted);
}}

function srtAgg(tblId, col) {{
  const tbl = document.getElementById(tblId);
  const tb  = tbl.querySelector('tbody');
  const rows = Array.from(tb.querySelectorAll('tr'));
  const prev = parseInt(tbl.dataset.sc||'-1');
  const dir  = prev===col ? (parseInt(tbl.dataset.sd||'1')*-1) : 1;
  tbl.dataset.sc=col; tbl.dataset.sd=dir;
  rows.sort((a,b)=>{{
    const av=a.cells[col].textContent.trim(), bv=b.cells[col].textContent.trim();
    const an=parseFloat(av), bn=parseFloat(bv);
    if(!isNaN(an)&&!isNaN(bn)) return dir*(an-bn);
    return dir*av.localeCompare(bv);
  }});
  rows.forEach(r=>tb.appendChild(r));
  tbl.querySelectorAll('th').forEach((th,i)=>{{
    th.classList.remove('asc','desc');
    if(i===col) th.classList.add(dir===1?'asc':'desc');
  }});
}}

function exportCSV() {{
  const hdr=['ts','section','label','status','http_status','fmt','tcp_ms','elapsed_ms','url','error'];
  const rows=[hdr.join(','),...currentRows.map(e=>hdr.map(h=>JSON.stringify(e[h]??'')).join(','))];
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([rows.join('\\n')],{{type:'text/csv'}}));
  a.download='{csv_filename}'; a.click();
}}

function buildSections() {{
  const m={{}};
  reqEvents.forEach(e=>{{
    const s=e.section||'(none)';
    if(!m[s]) m[s]={{total:0,ok:0,fail:0,ms:[],timeouts:0}};
    m[s].total++;
    if(e.status==='OK') m[s].ok++; else m[s].fail++;
    if(e.status==='TIMEOUT') m[s].timeouts++;
    if(e.elapsed_ms!=null) m[s].ms.push(e.elapsed_ms);
  }});
  document.getElementById('sec-tbody').innerHTML=Object.entries(m).map(([s,d])=>{{
    const avg=d.ms.length?(d.ms.reduce((a,b)=>a+b,0)/d.ms.length).toFixed(0):'—';
    const max=d.ms.length?Math.max(...d.ms).toFixed(0):'—';
    return `<tr>
      <td>${{s}}</td><td>${{d.total}}</td>
      <td style="color:var(--ok)">${{d.ok}}</td>
      <td style="color:${{d.fail>0?'var(--fail)':'inherit'}}">${{d.fail}}</td>
      <td>${{avg}}</td><td>${{max}}</td>
      <td style="color:${{d.timeouts>0?'var(--timeout)':'inherit'}}">${{d.timeouts}}</td>
    </tr>`;
  }}).join('');
}}

function buildTCP() {{
  document.getElementById('tcp-grid').innerHTML=tcpEvents.map(e=>{{
    const col=e.ok?'var(--ok)':'var(--fail)';
    return `<div class="tcp-card">
      <div class="host" style="color:${{col}}">${{e.host}}:${{e.port}}</div>
      <div class="msg"><strong>${{e.key}}</strong></div>
      <div class="msg">${{e.msg}}</div>
      ${{e.ms>0?`<div class="msg">Latency: <strong>${{e.ms}} ms</strong></div>`:''}}
    </div>`;
  }}).join('');
}}

function buildRaw() {{
  document.getElementById('raw-log').innerHTML=RAW_LINES.map(line=>{{
    const m=line.match(/\\[([A-Z_]+)\\s*\\]/);
    const cls=m?'ll-'+m[1].trim():'ll-INFO';
    return `<span class="${{cls}}">${{line.replace(/&/g,'&amp;').replace(/</g,'&lt;')}}</span>`;
  }}).join('\\n');
}}

renderTable(reqEvents);
buildSections();
buildTCP();
buildRaw();
</script>
</body>
</html>"""

with open(HTML_LOG_FILE, "w", encoding="utf-8") as f:
    f.write(html)

_log(f"  📄 HTML-loki kirjoitettu: {HTML_LOG_FILE}")

sys.exit(0 if not errors else 1)
