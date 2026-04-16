#!/usr/bin/env bash
# ============================================================
# Smoke Tests — WONT (DEV)
# Host: 10.200.28.4
# Generated: 2026-04-14
# ============================================================

HOST_BAPI="http://10.200.28.4:9000"
HOST_COMET="http://10.200.28.4:8090"
HOST_CONF_REST="http://10.200.28.4:8090"
HOST_CIM="http://10.200.28.4:8080"
HOST_FENIX="http://10.200.28.4:8091"
HOST_WON="http://10.200.28.4:8092"

PASS=0
FAIL=0

run_test() {
  local name="$1"
  local expected="$2"
  local url="$3"

  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url")

  if [ "$status" -eq "$expected" ]; then
    echo "  ✅ PASS [$status] $name"
    ((PASS++))
  else
    echo "  ❌ FAIL [got:$status expected:$expected] $name"
    echo "         URL: $url"
    ((FAIL++))
  fi
}

# ------------------------------------------------------------
echo ""
echo "🔵 Health checks"
echo "------------------------------------------------------------"
run_test "basic healthtest (NOVA App Gateway)" \
  200 \
  "${HOST_CIM}/"

run_test "BAPI is up and running" \
  200 \
  "${HOST_BAPI}/sport/v1/seasons"

run_test "COMET API is up and running" \
  200 \
  "${HOST_COMET}/WONREST/trailers/search?searchParameters=eq(mediaQuerySelection,withMedia);eq(availableDateBlackoutSelection,true);eq(mediaLabelSelection,722874)"

run_test "Configurable REST is up and running" \
  200 \
  "${HOST_CONF_REST}/WONREST/trailers/search?searchParameters=eq(mediaQuerySelection,withMedia);eq(mediaLabelSelection,722874)"

run_test "FENIX API is up and running" \
  200 \
  "${HOST_FENIX}/api/v1/channel/list"

run_test "WON API is up and running" \
  200 \
  "${HOST_WON}/api/won/metabank/products?searchParameters=eq(productCodeSelection,2084741)"

# ------------------------------------------------------------
echo ""
echo "🔵 WON COMET API"
echo "------------------------------------------------------------"
run_test "/trailers/search w/ specific mediaId" \
  200 \
  "${HOST_COMET}/WONREST/trailers/search?searchParameters=eq(mediaQuerySelection,withMedia);eq(availableDateBlackoutSelection,true);eq(mediaLabelSelection,722874)"

# ------------------------------------------------------------
echo ""
echo "🔵 WON Configurable REST"
echo "------------------------------------------------------------"
run_test "/customChanges/search" \
  200 \
  "${HOST_CONF_REST}/WONREST/customChanges/search?searchParameters=eq(loggingGroupSelection,8573244808809);ge(timestampSelection,2022-03-05 18:38:00.000)"

run_test "/trailers/search w/ specific mediaId" \
  200 \
  "${HOST_CONF_REST}/WONREST/trailers/search?searchParameters=eq(mediaQuerySelection,withMedia);eq(mediaLabelSelection,722874)"

run_test "/metabank_prod_searchProductChanges/search" \
  200 \
  "${HOST_CONF_REST}/WONREST/metabank_prod_searchProductChanges/search?searchParameters=eq(productCodeSelection,2085140)"

run_test "/metabank_prod_getMediaAssetSequence/externalReference" \
  200 \
  "${HOST_CONF_REST}/WONREST/metabank_prod_getMediaAssetSequence/externalReference/5054797794000"

run_test "/metabank_prod_getProduct/externalReference" \
  200 \
  "${HOST_CONF_REST}/WONREST/metabank_prod_getProduct/externalReference/4986920692527"

run_test "/metabank_prod_getSeries/externalReference" \
  200 \
  "${HOST_CONF_REST}/WONREST/metabank_prod_getSeries/externalReference/2392281679527"

run_test "/metabank_prod_getTx/externalReference" \
  200 \
  "${HOST_CONF_REST}/WONREST/metabank_prod_getTx/externalReference/2378023463813"

run_test "/metabank_prod_searchTxPlan/search" \
  200 \
  "${HOST_CONF_REST}/WONREST/metabank_prod_searchTxPlan/search?searchParameters=eq(channelSelection,53634538);eq(dateSelection,20210901)"

# ------------------------------------------------------------
echo ""
echo "🔵 WON FENIX API"
echo "------------------------------------------------------------"
run_test "/customChanges/search" \
  200 \
  "${HOST_FENIX}/api/v1/customChanges/search?searchParameters=eq(loggingGroupSelection,8573244808809);ge(timestampSelection,2022-03-05 18:38:00.000)"

run_test "/videoComponentsMM/externalReference" \
  200 \
  "${HOST_FENIX}/api/v1/videoComponentsMM/externalReference/7505782762000"

run_test "/subtitlingComponentsMM/externalReference" \
  200 \
  "${HOST_FENIX}/api/v1/subtitlingComponentsMM/externalReference/7505782770000"

run_test "/editorials (DEV only) UTF-8" \
  200 \
  "${HOST_FENIX}/api/v1/editorials/externalReference/7877090496527"

run_test "/editorials (DEV only) iso-8859-1" \
  200 \
  "${HOST_FENIX}/api/v1/editorials/externalReference/5913061874527"

run_test "/asrun_channels/list" \
  200 \
  "${HOST_FENIX}/api/v1/asrun_channels/list"

run_test "/channel/list" \
  200 \
  "${HOST_FENIX}/api/v1/channel/list"

run_test "/changes/search" \
  200 \
  "${HOST_FENIX}/api/v1/changes/search?searchParameters=eq(productCodeSelection,2085140)"

run_test "/evergreen/search" \
  200 \
  "${HOST_FENIX}/api/v1/evergreen/search"

run_test "/editorials/externalReference" \
  200 \
  "${HOST_FENIX}/api/v1/editorials/externalReference/5913039660527"

run_test "/media/search" \
  200 \
  "${HOST_FENIX}/api/v1/media/search?searchParameters=eq(labelSelection,M0492294);eq(mediaTypeSelection,784165)"

run_test "/mediasMM/search" \
  200 \
  "${HOST_FENIX}/api/v1/mediasMM/search?searchParameters=eq(labelSelection,M0492294);eq(mediaTypeSelection,784165)"

run_test "/medias/externalReference" \
  200 \
  "${HOST_FENIX}/api/v1/medias/externalReference/8229718976000"

run_test "/mediainfo/search" \
  200 \
  "${HOST_FENIX}/api/v1/mediainfo/search?searchParameters=eq(labelSelection,M0528056)"

run_test "/mediaAssetsMM/search" \
  200 \
  "${HOST_FENIX}/api/v1/mediaAssetsMM/search?searchParameters=eq(labelSelection,M0302295)"

run_test "/mediaAssets/oid" \
  200 \
  "${HOST_FENIX}/api/v1/mediaAssets/oid/5054797793000"

run_test "/metabank_prod_getProduct/externalReference" \
  200 \
  "${HOST_FENIX}/api/v1/metabank_prod_getProduct/externalReference/4986920692527"

run_test "/missingmedia/search" \
  200 \
  "${HOST_FENIX}/api/v1/missingmedia/search?searchParameters=eq(labelSelection,M0528056)"

run_test "/livesources/list" \
  200 \
  "${HOST_FENIX}/api/v1/livesources/list"

run_test "/preliminary/search" \
  200 \
  "${HOST_FENIX}/api/v1/preliminary/search?searchParameters=eq(scheduleVersionSelection,activeTxSchedule);eq(txDateSelection,20210923);eq(channelSelection,53543538)"

run_test "/purge/search" \
  200 \
  "${HOST_FENIX}/api/v1/purge/search?limit=1"

run_test "/products/search" \
  200 \
  "${HOST_FENIX}/api/v1/products/search?searchParameters=eq(productCodeSelection,2635258)"

run_test "/products/externalReference" \
  200 \
  "${HOST_FENIX}/api/v1/products/externalReference/4986920692527"

run_test "/productsAndPress/externalReference" \
  200 \
  "${HOST_FENIX}/api/v1/productsAndPress/externalReference/4986920692527"

run_test "/titles/externalReference (expect 404)" \
  404 \
  "${HOST_FENIX}/api/v1/titles/externalReference/4986920697544"

run_test "/tobepurged/search" \
  200 \
  "${HOST_FENIX}/api/v1/tobepurged/search?limit=10"

run_test "/vodXmlChannels/list" \
  200 \
  "${HOST_FENIX}/api/v1/vodXmlChannels/list"

run_test "/won_medias/externalReference" \
  200 \
  "${HOST_FENIX}/api/v1/won_medias/externalReference/8231920221000"

run_test "/won_medias/search" \
  200 \
  "${HOST_FENIX}/api/v1/won_medias/search?searchParameters=eq(mediaTypeSelection,784165);eq(labelSelection,M0471288)"

# ------------------------------------------------------------
echo ""
echo "🔵 WON API"
echo "------------------------------------------------------------"
run_test "/metabank/products/search" \
  200 \
  "${HOST_WON}/api/won/metabank/products?searchParameters=eq(productCodeSelection,2084741)"

run_test "/test/products/externalReference" \
  200 \
  "${HOST_WON}/api/won/test/products/externalReference/8063432082527"

run_test "/products/search" \
  200 \
  "${HOST_WON}/api/won/products/search?searchParameters=eq(productCodeSelection,2635258)"

run_test "/products/externalReference" \
  200 \
  "${HOST_WON}/api/won/products/externalReference/6562484569527"

# ------------------------------------------------------------
echo ""
echo "============================================================"
echo "  Results: ✅ $PASS passed  |  ❌ $FAIL failed  |  Total: $((PASS + FAIL))"
echo "============================================================"
echo ""

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
