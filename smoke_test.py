#!/usr/bin/env python3
"""
Smoke Tests — WONT
Usage:  python smoke_test.py [dev|test|prod]
        ENV-tiedostot: env/wont_dev.env  env/wont_test.env  env/wont_prod.env
"""

import sys
import os
import pathlib
import argparse
import logging
import datetime
import requests

# ============================================================
# CLI
# ============================================================
parser = argparse.ArgumentParser(
    prog="smoke_test.py",
    description="WONT smoke test suite — tarkistaa kaikkien API-palveluiden tilan.",
    epilog=(
        "Esimerkit:\n"
        "  python smoke_test.py dev\n"
        "  python smoke_test.py test\n"
        "  python smoke_test.py prod\n"
        "\n"
        "ENV-tiedostot: env/wont_dev.env  env/wont_test.env  env/wont_prod.env"
    ),
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument(
    "env",
    nargs="?",
    default="dev",
    choices=["dev", "test", "prod"],
    metavar="ENV",
    help="Kohdeympäristö: dev | test | prod  (oletus: dev)",
)
args = parser.parse_args()

# ============================================================
# Ladataan ympäristö
# ============================================================
ENV = args.env
SCRIPT_DIR = pathlib.Path(__file__).parent
ENV_FILE = SCRIPT_DIR / "env" / f"wont_{ENV}.env"
if not ENV_FILE.exists():
    ENV_FILE = SCRIPT_DIR / f"wont_{ENV}.env"

if not ENV_FILE.exists():
    log.info(f"❌ ENV-tiedostoa ei löydy: {ENV_FILE}")
    log.info(f"   Käyttö: python {sys.argv[0]} [dev|test|prod]")
    sys.exit(1)

# Parsi .env → os.environ
with open(ENV_FILE) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

HOST_BAPI      = os.environ["HOST_BAPI"]
HOST_COMET     = os.environ["HOST_COMET"]
HOST_CONF_REST = os.environ["HOST_CONF_REST"]
HOST_CIM       = os.environ["HOST_CIM"]
HOST_FENIX     = os.environ["HOST_FENIX"]
HOST_WON       = os.environ["HOST_WON"]

TIMEOUT = 10  # seconds

# ============================================================
# Lokitus — konsoli + logs/smoke_<env>_<aikaleima>.log
# ============================================================
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"smoke_{ENV}_{timestamp}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger()

log.info(f"\n🌍 Ympäristö: {ENV}  ({ENV_FILE})")
log.info(f"   Lokitiedosto: {LOG_FILE}")
log.info("=" * 60)

# ============================================================
# Test runner
# ============================================================
passed = []
failed = []

def run_test(name: str, url: str, expected: int = 200) -> None:
    try:
        response = requests.get(url, timeout=TIMEOUT)
        status = response.status_code
        if status == expected:
            log.info(f"  ✅ PASS [{status}] {name}")
            passed.append(name)
        else:
            log.info(f"  ❌ FAIL [got:{status} expected:{expected}] {name}")
            log.info(f"         URL: {url}")
            failed.append(name)
    except requests.exceptions.ConnectionError:
        log.info(f"  ❌ FAIL [CONNECTION ERROR] {name}")
        log.info(f"         URL: {url}")
        failed.append(name)
    except requests.exceptions.Timeout:
        log.info(f"  ❌ FAIL [TIMEOUT after {TIMEOUT}s] {name}")
        log.info(f"         URL: {url}")
        failed.append(name)


# ============================================================
# Health checks
# ============================================================
log.info("\n🔵 Health checks")
log.info("------------------------------------------------------------")

run_test("NOVA App Gateway /",
         f"{HOST_CIM}/")

run_test("BAPI /sport/v1/seasons",
         f"{HOST_BAPI}/sport/v1/seasons")

run_test("COMET /trailers/search",
         f"{HOST_COMET}/WONREST/trailers/search?searchParameters=eq(mediaQuerySelection,withMedia);eq(availableDateBlackoutSelection,true);eq(mediaLabelSelection,722874)")

run_test("Configurable REST /trailers/search",
         f"{HOST_CONF_REST}/WONREST/trailers/search?searchParameters=eq(mediaQuerySelection,withMedia);eq(mediaLabelSelection,722874)")

run_test("FENIX /channel/list",
         f"{HOST_FENIX}/api/v1/channel/list")

run_test("WON /metabank/products",
         f"{HOST_WON}/api/won/metabank/products?searchParameters=eq(productCodeSelection,2084741)")


# ============================================================
# WON COMET API
# ============================================================
log.info("\n🔵 WON COMET API")
log.info("------------------------------------------------------------")

run_test("/trailers/search w/ specific mediaId",
         f"{HOST_COMET}/WONREST/trailers/search?searchParameters=eq(mediaQuerySelection,withMedia);eq(availableDateBlackoutSelection,true);eq(mediaLabelSelection,722874)")


# ============================================================
# WON Configurable REST
# ============================================================
log.info("\n🔵 WON Configurable REST")
log.info("------------------------------------------------------------")

run_test("/customChanges/search",
         f"{HOST_CONF_REST}/WONREST/customChanges/search?searchParameters=eq(loggingGroupSelection,8573244808809);ge(timestampSelection,2022-03-05 18:38:00.000)")

run_test("/trailers/search w/ specific mediaId",
         f"{HOST_CONF_REST}/WONREST/trailers/search?searchParameters=eq(mediaQuerySelection,withMedia);eq(mediaLabelSelection,722874)")

run_test("/metabank_prod_searchProductChanges/search",
         f"{HOST_CONF_REST}/WONREST/metabank_prod_searchProductChanges/search?searchParameters=eq(productCodeSelection,2085140)")

run_test("/metabank_prod_getMediaAssetSequence/externalReference",
         f"{HOST_CONF_REST}/WONREST/metabank_prod_getMediaAssetSequence/externalReference/5054797794000")

run_test("/metabank_prod_getProduct/externalReference",
         f"{HOST_CONF_REST}/WONREST/metabank_prod_getProduct/externalReference/4986920692527")

run_test("/metabank_prod_getSeries/externalReference",
         f"{HOST_CONF_REST}/WONREST/metabank_prod_getSeries/externalReference/2392281679527")

run_test("/metabank_prod_getTx/externalReference",
         f"{HOST_CONF_REST}/WONREST/metabank_prod_getTx/externalReference/2378023463813")

run_test("/metabank_prod_searchTxPlan/search",
         f"{HOST_CONF_REST}/WONREST/metabank_prod_searchTxPlan/search?searchParameters=eq(channelSelection,53634538);eq(dateSelection,20210901)")


# ============================================================
# WON FENIX API
# ============================================================
log.info("\n🔵 WON FENIX API")
log.info("------------------------------------------------------------")

run_test("/customChanges/search",
         f"{HOST_FENIX}/api/v1/customChanges/search?searchParameters=eq(loggingGroupSelection,8573244808809);ge(timestampSelection,2022-03-05 18:38:00.000)")

run_test("/videoComponentsMM/externalReference",
         f"{HOST_FENIX}/api/v1/videoComponentsMM/externalReference/7505782762000")

run_test("/subtitlingComponentsMM/externalReference",
         f"{HOST_FENIX}/api/v1/subtitlingComponentsMM/externalReference/7505782770000")

run_test("/editorials (DEV only) UTF-8",
         f"{HOST_FENIX}/api/v1/editorials/externalReference/7877090496527")

run_test("/editorials (DEV only) iso-8859-1",
         f"{HOST_FENIX}/api/v1/editorials/externalReference/5913061874527")

run_test("/asrun_channels/list",
         f"{HOST_FENIX}/api/v1/asrun_channels/list")

run_test("/channel/list",
         f"{HOST_FENIX}/api/v1/channel/list")

run_test("/changes/search",
         f"{HOST_FENIX}/api/v1/changes/search?searchParameters=eq(productCodeSelection,2085140)")

run_test("/evergreen/search",
         f"{HOST_FENIX}/api/v1/evergreen/search")

run_test("/editorials/externalReference",
         f"{HOST_FENIX}/api/v1/editorials/externalReference/5913039660527")

run_test("/media/search",
         f"{HOST_FENIX}/api/v1/media/search?searchParameters=eq(labelSelection,M0492294);eq(mediaTypeSelection,784165)")

run_test("/mediasMM/search",
         f"{HOST_FENIX}/api/v1/mediasMM/search?searchParameters=eq(labelSelection,M0492294);eq(mediaTypeSelection,784165)")

run_test("/medias/externalReference",
         f"{HOST_FENIX}/api/v1/medias/externalReference/8229718976000")

run_test("/mediainfo/search",
         f"{HOST_FENIX}/api/v1/mediainfo/search?searchParameters=eq(labelSelection,M0528056)")

run_test("/mediaAssetsMM/search",
         f"{HOST_FENIX}/api/v1/mediaAssetsMM/search?searchParameters=eq(labelSelection,M0302295)")

run_test("/mediaAssets/oid",
         f"{HOST_FENIX}/api/v1/mediaAssets/oid/5054797793000")

run_test("/metabank_prod_getProduct/externalReference",
         f"{HOST_FENIX}/api/v1/metabank_prod_getProduct/externalReference/4986920692527")

run_test("/missingmedia/search",
         f"{HOST_FENIX}/api/v1/missingmedia/search?searchParameters=eq(labelSelection,M0528056)")

run_test("/livesources/list",
         f"{HOST_FENIX}/api/v1/livesources/list")

run_test("/preliminary/search",
         f"{HOST_FENIX}/api/v1/preliminary/search?searchParameters=eq(scheduleVersionSelection,activeTxSchedule);eq(txDateSelection,20210923);eq(channelSelection,53543538)")

run_test("/purge/search",
         f"{HOST_FENIX}/api/v1/purge/search?limit=1")

run_test("/products/search",
         f"{HOST_FENIX}/api/v1/products/search?searchParameters=eq(productCodeSelection,2635258)")

run_test("/products/externalReference",
         f"{HOST_FENIX}/api/v1/products/externalReference/4986920692527")

run_test("/productsAndPress/externalReference",
         f"{HOST_FENIX}/api/v1/productsAndPress/externalReference/4986920692527")

run_test("/titles/externalReference (expect 404)",
         f"{HOST_FENIX}/api/v1/titles/externalReference/4986920697544",
         expected=404)

run_test("/tobepurged/search",
         f"{HOST_FENIX}/api/v1/tobepurged/search?limit=10")

run_test("/vodXmlChannels/list",
         f"{HOST_FENIX}/api/v1/vodXmlChannels/list")

run_test("/won_medias/externalReference",
         f"{HOST_FENIX}/api/v1/won_medias/externalReference/8231920221000")

run_test("/won_medias/search",
         f"{HOST_FENIX}/api/v1/won_medias/search?searchParameters=eq(mediaTypeSelection,784165);eq(labelSelection,M0471288)")


# ============================================================
# WON API
# ============================================================
log.info("\n🔵 WON API")
log.info("------------------------------------------------------------")

run_test("/metabank/products/search",
         f"{HOST_WON}/api/won/metabank/products?searchParameters=eq(productCodeSelection,2084741)")

run_test("/test/products/externalReference",
         f"{HOST_WON}/api/won/test/products/externalReference/8063432082527")

run_test("/products/search",
         f"{HOST_WON}/api/won/products/search?searchParameters=eq(productCodeSelection,2635258)")

run_test("/products/externalReference",
         f"{HOST_WON}/api/won/products/externalReference/6562484569527")


# ============================================================
# Summary
# ============================================================
total = len(passed) + len(failed)
log.info("\n============================================================")
log.info(f"  Results: ✅ {len(passed)} passed  |  ❌ {len(failed)} failed  |  Total: {total}")
log.info("============================================================\n")

if failed:
    log.info("Failed tests:")
    for name in failed:
        log.info(f"  - {name}")
    log.info()

sys.exit(0 if not failed else 1)
