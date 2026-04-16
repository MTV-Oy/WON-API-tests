# WON API Test Suite

> **DEV environment** · v1.0 · 2026-04-14
> Smoke and regression tests for the WON (Workflow On Network) platform REST APIs.

---

## Table of Contents

- [Overview](#overview)
- [File Structure](#file-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
  - [smoke_test_dev.py](#smoke_test_devpy)
  - [smoke_test_dev.sh](#smoke_test_devsh)
  - [fetchdata.py](#fetchdatapy)
- [Test Environments](#test-environments)
- [Test Scope](#test-scope)
- [Authentication](#authentication)
- [File Format: testdata JSON](#file-format-testdata-json)

---

## Overview

This repository contains automated smoke tests and a test data fetching tool for six API services on the WON platform:

| Service | Description |
|---|---|
| **NOVA App Gateway (CIM)** | Gateway, port 8080 |
| **BAPI** | Sport data API, port 9000 |
| **COMET** | Trailer search and media indexing, port 8090 |
| **Configurable REST** | Metabank and change log APIs, port 8090 |
| **FENIX** | Media asset and product registry, port 8091 |
| **WON / FRENDS** | Product search and integration layer, port 8092 |

Test coverage: **69 test cases** (49 smoke · 12 regression · 8 negative).

---

## File Structure

```
.
├── smoke_test_dev.py       # Python smoke test (DEV)
├── smoke_test_dev.sh       # Bash smoke test (DEV, CI/CD compatible)
├── fetchdata.py            # Test data fetching tool — writes testdata_<env>.json
└── testdata_dev.json       # Generated test data (not versioned — add to .gitignore)
```

---

## Prerequisites

- Python 3.10+
- `requests` library

```bash
pip install requests
```

For the Bash script, `curl` is required (usually pre-installed on Linux/macOS).

---

## Installation

```bash
git clone <repo-url>
cd <repo-directory>
pip install requests
```

---

## Usage

### smoke_test_dev.py

Runs all smoke tests against the DEV environment and prints results to the console.

```bash
python smoke_test_dev.py
```

**Example output:**

```
🔵 Health checks
------------------------------------------------------------
  ✅ PASS [200] basic healthtest (NOVA App Gateway)
  ✅ PASS [200] BAPI is up and running
  ❌ FAIL [got:503 expected:200] COMET API is up and running

============================================================
  Results: ✅ 48 passed  |  ❌ 1 failed  |  Total: 49
============================================================
```

The script returns exit code `0` if all tests pass, `1` if any test fails.

---

### smoke_test_dev.sh

Bash alternative, suitable for CI/CD pipelines (Jenkins, GitHub Actions, etc.).

```bash
chmod +x smoke_test_dev.sh
./smoke_test_dev.sh
```

Returns exit code `0` / `1` the same way as the Python version.

---

### fetchdata.py

Fetches up-to-date reference values (external reference identifiers, product codes, etc.) from the target environment and writes them to `testdata_<env>.json`. Smoke tests can use this file as dynamic test data instead of hardcoded values.

```bash
# Fetch test data from DEV environment
python fetchdata.py --env dev

# Fetch test data and write to a custom file
python fetchdata.py --env dev --out my_testdata.json
```

**Parameters:**

| Parameter | Required | Description |
|---|---|---|
| `--env` | Yes | Target environment: `dev` \| `test` \| `prod` |
| `--out` | No | Output file path (default: `testdata_<env>.json`) |

> ⚠️ The host addresses for `test` and `prod` environments are marked with `# TODO` comments in `fetchdata.py` — update them before use.

---

## Test Environments

| Environment | Description | Status |
|---|---|---|
| `dev` | `10.200.28.4` — development environment | ✅ Active |
| `test` | Host not updated | ⚠️ TODO |
| `prod` | Host not updated | ⚠️ TODO |

Host addresses are defined as variables at the top of each script (`HOST_CIM`, `HOST_BAPI`, etc.).

---

## Test Scope

All tests are **HTTP GET requests**. Write operations (POST/PUT/DELETE) are not tested in this suite.

**Test types:**

- `@smoke` — service reachability, expected HTTP status code
- `@regression` — schema validation and data correctness (Postman collections)
- `@negative` — error conditions and authentication enforcement

Performance (response times) is not measured — timeout is 10 seconds per request.

---

## Authentication

FRENDS integration layer (`/api/won`) endpoints require API key authentication:

```
Header: X-ApiKey
Value:  <api-key>
```

Other services (CIM, BAPI, FENIX channel lists, etc.) do not require authentication headers on the tested paths.

> 🔐 Do not store the API key in version control. Use environment variables or a dedicated secrets manager.

---

## File Format: testdata JSON

`fetchdata.py` produces a file with the following structure:

```json
{
  "_meta": {
    "env": "dev",
    "fetched_at": "2026-04-14T10:00:00",
    "hosts": { "HOST_WON": "http://10.200.28.4:8092", "..." : "..." },
    "errors": []
  },
  "data": {
    "won_product_code": "2635258",
    "fenix_channel_id_1": "53634538",
    "..."
  }
}
```

The `_meta.errors` list is empty after a successful run. The script returns exit code `1` if any fetch errors occurred.

---

*CONFIDENTIAL — DEV ENVIRONMENT*
