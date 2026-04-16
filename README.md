# WON API Test Suite

> **DEV ympäristö** · v1.0 · 2026-04-14  
> Smoke- ja regressiotestit WON (Workflow On Network) -alustan REST-rajapinnoille.

---

## Sisällysluettelo

- [Yleiskuvaus](#yleiskuvaus)
- [Tiedostorakenne](#tiedostorakenne)
- [Esivaatimukset](#esivaatimukset)
- [Asennus](#asennus)
- [Käyttö](#käyttö)
  - [smoke_test_dev.py](#smoke_test_devpy)
  - [smoke_test_dev.sh](#smoke_test_devsh)
  - [fetchdata.py](#fetchdatapy)
- [Testiympäristöt](#testiympäristöt)
- [Testauksen laajuus](#testauksen-laajuus)
- [Tunnistautuminen](#tunnistautuminen)
- [Tiedostomuoto: testdata JSON](#tiedostomuoto-testdata-json)

---

## Yleiskuvaus

Tämä repositorio sisältää automaattiset smoke-testit ja testidatan hakutyökalun WON-alustan kuudelle API-palvelulle:

| Palvelu | Kuvaus |
|---|---|
| **NOVA App Gateway (CIM)** | Yhdyskäytävä, portti 8080 |
| **BAPI** | Sport-data API, portti 9000 |
| **COMET** | Trailer-haku ja mediaindeksointi, portti 8090 |
| **Configurable REST** | Metapankki- ja muutosloki-rajapinnat, portti 8090 |
| **FENIX** | Media-asset ja tuoterekisteri, portti 8091 |
| **WON / FRENDS** | Tuotehaku ja integraatiokerros, portti 8092 |

Testikattavuus: **69 testitapausta** (49 smoke · 12 regressio · 8 negatiivinen).

---

## Tiedostorakenne

```
.
├── smoke_test_dev.py       # Python smoke-testi (DEV)
├── smoke_test_dev.sh       # Bash smoke-testi (DEV, CI/CD-yhteensopiva)
├── fetchdata.py            # Testidatan hakutyökalu — kirjoittaa testdata_<env>.json
└── testdata_dev.json       # Generoitu testitestausdata (ei versioitua — lisää .gitignore)
```

---

## Esivaatimukset

- Python 3.10+
- `requests`-kirjasto

```bash
pip install requests
```

Bash-skriptiä varten tarvitaan `curl` (yleensä valmiiksi asennettuna Linux/macOS-ympäristöissä).

---

## Asennus

```bash
git clone <repo-url>
cd <repo-hakemisto>
pip install requests
```

---

## Käyttö

### smoke_test_dev.py

Ajaa kaikki smoke-testit DEV-ympäristöä vastaan ja tulostaa tulokset konsoliin.

```bash
python smoke_test_dev.py
```

**Esimerkkituloste:**

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

Skripti palauttaa exit-koodin `0` kaikkien testien läpäistyä, `1` jos jokin testi epäonnistuu.

---

### smoke_test_dev.sh

Bash-vaihtoehto, sopii CI/CD-putkiin (Jenkins, GitHub Actions jne.).

```bash
chmod +x smoke_test_dev.sh
./smoke_test_dev.sh
```

Palauttaa exit-koodin `0` / `1` samoin kuin Python-versio.

---

### fetchdata.py

Hakee ajantasaiset viitearvot (external reference -tunnisteet, product code -arvot jne.) kohdeympäristöstä ja kirjoittaa ne `testdata_<env>.json`-tiedostoon. Smoke-testit voivat käyttää tätä tiedostoa dynaamisina testitietoina kiinteiden arvojen sijaan.

```bash
# Hae testdata DEV-ympäristöstä
python fetchdata.py --env dev

# Hae testdata ja kirjoita mukautettuun tiedostoon
python fetchdata.py --env dev --out my_testdata.json
```

**Parametrit:**

| Parametri | Pakollinen | Kuvaus |
|---|---|---|
| `--env` | Kyllä | Kohdeympäristö: `dev` \| `test` \| `prod` |
| `--out` | Ei | Tulostiedoston polku (oletus: `testdata_<env>.json`) |

> ⚠️ `test`- ja `prod`-ympäristöjen host-osoitteet on merkitty `# TODO`-kommenteilla `fetchdata.py`-tiedostossa — päivitä ne ennen käyttöä.

---

## Testiympäristöt

| Ympäristö | Kuvaus | Tila |
|---|---|---|
| `dev` | `10.200.28.4` — kehitysympäristö | ✅ Toiminnassa |
| `test` | Host päivittämättä | ⚠️ TODO |
| `prod` | Host päivittämättä | ⚠️ TODO |

Host-osoitteet on määritelty kunkin skriptin alussa muuttujina (`HOST_CIM`, `HOST_BAPI` jne.).

---

## Testauksen laajuus

Kaikki testit ovat **HTTP GET -pyyntöjä**. Kirjoitusoperaatioita (POST/PUT/DELETE) ei testata tässä suiteessa.

**Testityypit:**

- `@smoke` — palvelun saavutettavuus, odotettu HTTP-statuskoodi
- `@regression` — schemavalidointi ja datan oikeellisuus (Postman-kokoelmat)
- `@negative` — virhetilanteet ja autentikaation valvonta

Suorituskykyä (vasteajat) ei mitata — timeout on 10 sekuntia pyyntöä kohden.

---

## Tunnistautuminen

FRENDS-integraatiokerroksen (`/api/won`) endpointit vaativat API-avainautentikaation:

```
Header: X-ApiKey
Value:  <api-avain>
```

Muut palvelut (CIM, BAPI, FENIX kanavalistat jne.) eivät vaadi autentikaatioheadereita testatuissa poluissa.

> 🔐 Älä tallenna API-avainta versionhallintaan. Käytä ympäristömuuttujia tai erillistä secrets-hallintaa.

---

## Tiedostomuoto: testdata JSON

`fetchdata.py` tuottaa rakenteeltaan seuraavan tiedoston:

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

`_meta.errors`-lista on tyhjä onnistuneen ajon jälkeen. Skripti palauttaa exit-koodin `1` jos hakuvirheitä esiintyi.

---

*CONFIDENTIAL — DEV ENVIRONMENT*
