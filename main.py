from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional
import httpx


BASE_URL = "https://api.worldbank.org/v2"

http_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=15.0)
    yield
    await http_client.aclose()


app = FastAPI(title="World Bank Wrapper", lifespan=lifespan)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Indicator name mapping ───────────────────────────────────────────────

INDICATOR_MAPPING = {
    # GDP & Growth
    "gdp": "NY.GDP.MKTP.CD",
    "gdp_growth": "NY.GDP.MKTP.KD.ZG",
    "gdp_per_capita": "NY.GDP.PCAP.CD",
    "gdp_per_capita_ppp": "NY.GDP.PCAP.PP.CD",
    "gni": "NY.GNP.MKTP.CD",
    "gni_per_capita": "NY.GNP.PCAP.CD",
    # Population & Demographics
    "population": "SP.POP.TOTL",
    "population_growth": "SP.POP.GROW",
    "life_expectancy": "SP.DYN.LE00.IN",
    "fertility_rate": "SP.DYN.TFRT.IN",
    "birth_rate": "SP.DYN.CBRT.IN",
    "death_rate": "SP.DYN.CDRT.IN",
    "urban_population_pct": "SP.URB.TOTL.IN.ZS",
    # Economy
    "inflation": "FP.CPI.TOTL.ZG",
    "cpi": "FP.CPI.TOTL",
    "unemployment": "SL.UEM.TOTL.ZS",
    "trade_pct_gdp": "NE.TRD.GNFS.ZS",
    "exports": "NE.EXP.GNFS.CD",
    "imports": "NE.IMP.GNFS.CD",
    "fdi": "BX.KLT.DINV.CD.WD",
    "remittances": "BX.TRF.PWKR.CD.DT",
    "external_debt": "DT.DOD.DECT.CD",
    "current_account": "BN.CAB.XOKA.CD",
    "tax_revenue_pct_gdp": "GC.TAX.TOTL.GD.ZS",
    # Poverty & Inequality
    "poverty": "SI.POV.DDAY",
    "poverty_national": "SI.POV.NAHC",
    "gini": "SI.POV.GINI",
    # Education
    "literacy_rate": "SE.ADT.LITR.ZS",
    "school_enrollment_primary": "SE.PRM.ENRR",
    "school_enrollment_secondary": "SE.SEC.ENRR",
    "school_enrollment_tertiary": "SE.TER.ENRR",
    "education_spending_pct_gdp": "SE.XPD.TOTL.GD.ZS",
    # Health
    "health_spending_pct_gdp": "SH.XPD.CHEX.GD.ZS",
    "infant_mortality": "SP.DYN.IMRT.IN",
    "maternal_mortality": "SH.STA.MMRT",
    "hiv_prevalence": "SH.DYN.AIDS.ZS",
    # Infrastructure & Technology
    "internet_users_pct": "IT.NET.USER.ZS",
    "mobile_subscriptions": "IT.CEL.SETS.P2",
    "electricity_access_pct": "EG.ELC.ACCS.ZS",
    "co2_emissions": "EN.ATM.CO2E.PC",
    "renewable_energy_pct": "EG.FEC.RNEW.ZS",
    # Governance
    "military_spending_pct_gdp": "MS.MIL.XPND.GD.ZS",
    "ease_of_business": "IC.BUS.DFRN.XQ",
}

# Country name → ISO code mapping for common queries
COUNTRY_ALIASES = {
    "US": "USA", "USA": "USA", "UNITED STATES": "USA", "AMERICA": "USA",
    "UK": "GBR", "UNITED KINGDOM": "GBR", "BRITAIN": "GBR", "ENGLAND": "GBR",
    "CHINA": "CHN", "JAPAN": "JPN", "GERMANY": "DEU", "FRANCE": "FRA",
    "INDIA": "IND", "BRAZIL": "BRA", "CANADA": "CAN", "AUSTRALIA": "AUS",
    "SOUTH KOREA": "KOR", "KOREA": "KOR", "MEXICO": "MEX", "RUSSIA": "RUS",
    "INDONESIA": "IDN", "TURKEY": "TUR", "SAUDI ARABIA": "SAU",
    "NIGERIA": "NGA", "SOUTH AFRICA": "ZAF", "EGYPT": "EGY",
    "KENYA": "KEN", "ETHIOPIA": "ETH", "GHANA": "GHA", "TANZANIA": "TZA",
    "ARGENTINA": "ARG", "COLOMBIA": "COL", "CHILE": "CHL", "PERU": "PER",
    "VIETNAM": "VNM", "THAILAND": "THA", "MALAYSIA": "MYS",
    "PHILIPPINES": "PHL", "SINGAPORE": "SGP", "TAIWAN": "TWN",
    "ISRAEL": "ISR", "UAE": "ARE", "POLAND": "POL", "SWEDEN": "SWE",
    "SWITZERLAND": "CHE", "NORWAY": "NOR", "NETHERLANDS": "NLD",
    "ITALY": "ITA", "SPAIN": "ESP", "IRELAND": "IRL", "PORTUGAL": "PRT",
    "BANGLADESH": "BGD", "PAKISTAN": "PAK", "SRI LANKA": "LKA",
    "MOROCCO": "MAR", "ALGERIA": "DZA", "TUNISIA": "TUN",
    "WORLD": "WLD", "GLOBAL": "WLD",
}

# Region/aggregate codes
REGION_CODES = {
    "WORLD": "WLD",
    "EAST ASIA": "EAS",
    "EUROPE": "ECS",
    "LATIN AMERICA": "LCN",
    "MIDDLE EAST": "MEA",
    "NORTH AMERICA": "NAC",
    "SOUTH ASIA": "SAS",
    "SUB-SAHARAN AFRICA": "SSF",
    "AFRICA": "SSF",
    "LOW INCOME": "LIC",
    "LOWER MIDDLE INCOME": "LMC",
    "UPPER MIDDLE INCOME": "UMC",
    "HIGH INCOME": "HIC",
    "OECD": "OED",
    "EU": "EUU",
    "EURO AREA": "EMU",
}


def _resolve_country(country: str) -> str:
    """Resolve a country name/alias to an ISO code."""
    upper = country.upper().strip()
    if upper in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[upper]
    if upper in REGION_CODES:
        return REGION_CODES[upper]
    # If it's already a 2 or 3 letter code, pass through
    if len(upper) <= 3 and upper.isalpha():
        return upper
    # Try as-is
    return country.strip()


def _resolve_indicator(name: str) -> str:
    """Resolve an indicator name to a World Bank indicator code."""
    lower = name.lower().strip()
    if lower in INDICATOR_MAPPING:
        return INDICATOR_MAPPING[lower]
    # If it looks like a code already (contains dots), pass through
    if "." in name:
        return name.strip()
    raise HTTPException(
        status_code=404,
        detail=f"Indicator '{name}' not found. Available: {', '.join(sorted(INDICATOR_MAPPING.keys()))}",
    )


async def _wb_get(path: str, params: dict = None) -> list:
    """Make a request to the World Bank API. Returns the data portion (index 1)."""
    url = f"{BASE_URL}{path}"
    base_params = {"format": "json", "per_page": "100"}
    if params:
        base_params.update(params)

    try:
        r = await http_client.get(url, params=base_params)
        if r.status_code == 429:
            raise HTTPException(status_code=429, detail="World Bank rate limit exceeded")
        r.raise_for_status()
        data = r.json()

        # World Bank API returns [metadata, data] array
        if isinstance(data, list) and len(data) >= 2:
            return data[1] if data[1] else []
        # Sometimes returns a single error object
        if isinstance(data, list) and len(data) == 1:
            msg = data[0].get("message", [{}])
            if msg:
                detail = msg[0].get("value", "Unknown error") if isinstance(msg, list) else str(msg)
                raise HTTPException(status_code=400, detail=detail)
        return []

    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Network error: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Unexpected error: {e}")


# ── HTML home page ───────────────────────────────────────────────────────

HOME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>World Bank · Chekk</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0a0a;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh;display:flex;justify-content:center;padding:32px 16px}
.w{max-width:640px;width:100%;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:16px;padding:32px;height:fit-content}
.hd{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}
.t{font-family:'Courier New',monospace;font-size:28px;font-weight:700;color:#009FDA}
.st{font-family:'Courier New',monospace;font-size:13px;color:#555;display:flex;align-items:center;gap:6px}
.st .d{width:8px;height:8px;border-radius:50%;background:#555;transition:background .3s}
.st .d.on{background:#4CAF50}
.sub{color:#666;font-size:14px;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid rgba(255,255,255,.06)}
.stats{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:14px}
.sc{background:rgba(0,159,218,.06);border:1px solid rgba(0,159,218,.15);border-radius:12px;padding:14px 16px;text-align:center;opacity:0;animation:fi .4s ease forwards}
.sc:nth-child(1){animation-delay:.1s}.sc:nth-child(2){animation-delay:.15s}.sc:nth-child(3){animation-delay:.2s}
.sl{color:#009FDA;font-size:9px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:6px}
.sv{font-family:'Courier New',monospace;font-size:20px;font-weight:700;color:#fff}
.sv sub{font-size:12px;color:#888}
hr.dv{border:none;border-top:1px solid rgba(255,255,255,.06);margin:18px 0}
.fm{display:flex;gap:10px;margin-bottom:8px}
.ip{flex:1;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:10px;padding:13px 16px;color:#fff;font-family:'Courier New',monospace;font-size:14px;outline:none;transition:border-color .2s}
.ip:focus{border-color:rgba(0,159,218,.5)}
.bt{background:#009FDA;color:#fff;border:none;border-radius:10px;padding:13px 18px;font-weight:700;font-size:14px;cursor:pointer;font-family:'Courier New',monospace;white-space:nowrap;transition:opacity .15s}
.bt:hover{opacity:.85}
.try{color:#555;font-size:12px;margin-top:4px}.try a{color:#666;text-decoration:none;cursor:pointer;transition:color .15s}.try a:hover{color:#009FDA}
#res{margin-top:14px;padding:14px 16px;background:rgba(0,159,218,.06);border:1px solid rgba(0,159,218,.15);border-radius:10px;display:none;font-family:'Courier New',monospace;font-size:13px;line-height:1.6;white-space:pre-wrap;word-break:break-all;max-height:400px;overflow-y:auto}
@keyframes fi{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@media(max-width:480px){.stats{grid-template-columns:1fr}.w{padding:20px}.fm{flex-direction:column}}
</style>
</head>
<body>
<div class="w">
 <div class="hd"><div class="t">World Bank</div><div class="st"><span class="d" id="dot"></span><span id="stx">connecting...</span></div></div>
 <div class="sub">Global development data &mdash; GDP, poverty, health, education across 200+ countries</div>
 <div class="stats" id="stats">
  <div class="sc"><div class="sl">GLOBAL GDP</div><div class="sv" id="gdp">...</div></div>
  <div class="sc"><div class="sl">WORLD POP.</div><div class="sv" id="pop">...</div></div>
  <div class="sc"><div class="sl">INDICATORS</div><div class="sv">1,400+</div></div>
 </div>
 <hr class="dv">
 <div class="fm">
  <input class="ip" id="country" placeholder="Nigeria" value="Nigeria">
  <input class="ip" id="indicator" placeholder="gdp_growth" value="gdp_growth">
  <button class="bt" onclick="fetchD()">&rarr;</button>
 </div>
 <div class="try">Try: <a onclick="ts('Kenya','gdp_growth')">Kenya GDP growth</a> &middot; <a onclick="ts('India','population')">India population</a> &middot; <a onclick="ts('Brazil','inflation')">Brazil inflation</a> &middot; <a onclick="ts('Nigeria','literacy_rate')">Nigeria literacy</a></div>
 <div id="res"></div>
</div>
<script>
function fmt(n){if(n==null)return'--';if(n>=1e12)return'$'+(n/1e12).toFixed(1)+'T';if(n>=1e9)return(n/1e9).toFixed(1)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';return n.toLocaleString('en-US',{maximumFractionDigits:1})}
async function init(){
 const t0=Date.now();
 try{await fetch('/health');const ms=Date.now()-t0;document.getElementById('dot').classList.add('on');document.getElementById('stx').textContent='online \\u00B7 '+ms+'ms'}catch(e){document.getElementById('stx').textContent='offline'}
 try{const d=await fetch('/indicator?country=world&name=gdp').then(r=>r.json());
  if(d.observations&&d.observations.length){const v=parseFloat(d.observations[0].value);document.getElementById('gdp').innerHTML=fmt(v)}}catch(e){document.getElementById('gdp').textContent='--'}
 try{const d=await fetch('/indicator?country=world&name=population').then(r=>r.json());
  if(d.observations&&d.observations.length){const v=parseFloat(d.observations[0].value);document.getElementById('pop').textContent=fmt(v)}}catch(e){document.getElementById('pop').textContent='--'}
}
function ts(c,i){document.getElementById('country').value=c;document.getElementById('indicator').value=i;fetchD()}
async function fetchD(){
 const c=document.getElementById('country').value.trim();
 const i=document.getElementById('indicator').value.trim();
 if(!c||!i)return;
 const res=document.getElementById('res');res.style.display='block';res.textContent='Fetching '+i+' for '+c+'...';
 try{const d=await fetch('/indicator?country='+encodeURIComponent(c)+'&name='+encodeURIComponent(i)).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()});
  res.textContent=JSON.stringify(d,null,2)}
 catch(e){res.innerHTML='<span style="color:#ef5350">Error: '+e.message+'</span>'}
}
init();
</script>
</body></html>"""


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return HTMLResponse(content=HOME_HTML)


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": _ts()}


@app.get("/indicator")
async def get_indicator(
    country: str = Query(..., description="Country name or ISO code (e.g., Nigeria, NGA, Kenya, KEN)"),
    name: str = Query(..., description="Indicator name or World Bank code (e.g., gdp_growth, NY.GDP.MKTP.KD.ZG)"),
    years: int = Query(10, description="Number of years of data", ge=1, le=60),
):
    """
    Get a development indicator for a country over time.
    Example: /indicator?country=Nigeria&name=gdp_growth&years=10
    """
    country_code = _resolve_country(country)
    indicator_code = _resolve_indicator(name)

    current_year = datetime.now(timezone.utc).year
    date_range = f"{current_year - years}:{current_year}"

    data = await _wb_get(
        f"/country/{country_code}/indicator/{indicator_code}",
        params={"date": date_range},
    )

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for {country} / {name}. Check country code and indicator name.",
        )

    # Extract country info from first record
    first = data[0] if data else {}
    country_info = first.get("country", {})

    observations = []
    for item in data:
        if item.get("value") is not None:
            observations.append({
                "year": item.get("date"),
                "value": item.get("value"),
            })

    # Sort by year descending (most recent first)
    observations.sort(key=lambda x: x.get("year", ""), reverse=True)

    # Get indicator metadata
    indicator_info = first.get("indicator", {})

    return {
        "country": country_info.get("value"),
        "country_code": country_info.get("id"),
        "indicator": indicator_info.get("value"),
        "indicator_code": indicator_info.get("id"),
        "observations": observations,
        "count": len(observations),
        "timestamp": _ts(),
    }


@app.get("/compare")
async def compare_countries(
    countries: str = Query(..., description="Semicolon-separated country names or codes (e.g., Nigeria;Kenya;Ghana)"),
    name: str = Query(..., description="Indicator name or code"),
    years: int = Query(10, description="Number of years of data", ge=1, le=60),
):
    """
    Compare an indicator across multiple countries.
    Example: /compare?countries=Nigeria;Kenya;Ghana&name=gdp_growth&years=10
    """
    country_list = [c.strip() for c in countries.split(";") if c.strip()]
    if len(country_list) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 countries per comparison")

    indicator_code = _resolve_indicator(name)
    current_year = datetime.now(timezone.utc).year
    date_range = f"{current_year - years}:{current_year}"

    # Build semicolon-separated country codes for the World Bank API
    codes = [_resolve_country(c) for c in country_list]
    codes_str = ";".join(codes)

    data = await _wb_get(
        f"/country/{codes_str}/indicator/{indicator_code}",
        params={"date": date_range},
    )

    if not data:
        raise HTTPException(status_code=404, detail="No data found for the given countries/indicator")

    # Group by country
    by_country = {}
    indicator_label = ""
    for item in data:
        country_info = item.get("country", {})
        cid = country_info.get("id", "")
        cname = country_info.get("value", "")
        if not indicator_label:
            indicator_label = item.get("indicator", {}).get("value", "")

        if cid not in by_country:
            by_country[cid] = {"country": cname, "country_code": cid, "observations": []}

        if item.get("value") is not None:
            by_country[cid]["observations"].append({
                "year": item.get("date"),
                "value": item.get("value"),
            })

    # Sort observations within each country
    for entry in by_country.values():
        entry["observations"].sort(key=lambda x: x.get("year", ""), reverse=True)

    return {
        "indicator": indicator_label,
        "indicator_code": indicator_code,
        "countries": list(by_country.values()),
        "timestamp": _ts(),
    }


@app.get("/country")
async def get_country(
    name: str = Query(..., description="Country name or ISO code (e.g., Nigeria, NGA)"),
):
    """
    Get country metadata and key indicators snapshot.
    Example: /country?name=Nigeria
    """
    country_code = _resolve_country(name)
    data = await _wb_get(f"/country/{country_code}")

    if not data:
        raise HTTPException(status_code=404, detail=f"Country '{name}' not found")

    c = data[0] if data else {}

    # Fetch a few key indicators in parallel-ish (sequential for simplicity)
    snapshot = {}
    key_indicators = {
        "gdp": "NY.GDP.MKTP.CD",
        "gdp_per_capita": "NY.GDP.PCAP.CD",
        "population": "SP.POP.TOTL",
        "life_expectancy": "SP.DYN.LE00.IN",
        "inflation": "FP.CPI.TOTL.ZG",
    }

    current_year = datetime.now(timezone.utc).year

    for label, code in key_indicators.items():
        try:
            ind_data = await _wb_get(
                f"/country/{country_code}/indicator/{code}",
                params={"date": f"{current_year - 5}:{current_year}", "per_page": "5"},
            )
            for item in (ind_data or []):
                if item.get("value") is not None:
                    snapshot[label] = {
                        "value": item["value"],
                        "year": item.get("date"),
                    }
                    break
        except Exception:
            continue

    return {
        "name": c.get("name"),
        "country_code": c.get("id"),
        "iso2": c.get("iso2Code"),
        "capital": c.get("capitalCity"),
        "region": c.get("region", {}).get("value"),
        "income_level": c.get("incomeLevel", {}).get("value"),
        "lending_type": c.get("lendingType", {}).get("value"),
        "longitude": c.get("longitude"),
        "latitude": c.get("latitude"),
        "snapshot": snapshot,
        "timestamp": _ts(),
    }


@app.get("/search")
async def search_indicators(
    query: str = Query(..., description="Search query (e.g., 'poverty', 'education', 'emissions')"),
    limit: int = Query(10, description="Number of results", ge=1, le=50),
):
    """
    Search World Bank indicators by keyword.
    Example: /search?query=poverty
    """
    data = await _wb_get(
        "/indicator",
        params={"source": "2", "per_page": str(limit)},
    )

    # The World Bank API indicator search doesn't have a query param,
    # so we fetch and filter client-side
    # Use the topic-based search instead
    try:
        r = await http_client.get(
            f"{BASE_URL}/indicator",
            params={
                "format": "json",
                "per_page": "1000",
                "source": "2",
            },
        )
        r.raise_for_status()
        resp = r.json()
        all_indicators = resp[1] if isinstance(resp, list) and len(resp) >= 2 else []
    except Exception:
        all_indicators = []

    query_lower = query.lower()
    results = []
    for ind in all_indicators:
        name = (ind.get("name") or "").lower()
        source_note = (ind.get("sourceNote") or "").lower()
        if query_lower in name or query_lower in source_note:
            results.append({
                "indicator_code": ind.get("id"),
                "name": ind.get("name"),
                "unit": ind.get("unit"),
                "source": ind.get("source", {}).get("value"),
            })
            if len(results) >= limit:
                break

    return {"query": query, "results": results, "count": len(results), "timestamp": _ts()}


@app.get("/rankings")
async def get_rankings(
    name: str = Query(..., description="Indicator name or code (e.g., gdp, gdp_per_capita, life_expectancy)"),
    limit: int = Query(20, description="Number of countries", ge=1, le=50),
    order: str = Query("desc", description="Sort order: desc (highest first) or asc (lowest first)"),
):
    """
    Rank countries by a specific indicator (most recent data).
    Example: /rankings?name=gdp_per_capita&limit=10&order=desc
    """
    indicator_code = _resolve_indicator(name)
    current_year = datetime.now(timezone.utc).year

    # Fetch data for all countries for the most recent year available
    data = await _wb_get(
        f"/country/all/indicator/{indicator_code}",
        params={"date": f"{current_year - 3}:{current_year}", "per_page": "300"},
    )

    if not data:
        raise HTTPException(status_code=404, detail="No data found for this indicator")

    # Get most recent value per country (skip aggregates)
    latest = {}
    aggregate_codes = {"WLD", "EAS", "ECS", "LCN", "MEA", "NAC", "SAS", "SSF",
                       "LIC", "LMC", "UMC", "HIC", "OED", "EUU", "EMU",
                       "ARB", "CSS", "CEB", "EAP", "ECA", "LAC", "MNA", "SSA",
                       "PST", "PRE", "TSA", "TSS", "IBD", "IBT", "IDA", "IDB",
                       "IDX", "FCS", "LDC", "OSS", "TEA", "TEC", "TLA", "TMN"}

    indicator_label = ""
    for item in data:
        cid = item.get("countryiso3code") or item.get("country", {}).get("id", "")
        if cid in aggregate_codes:
            continue
        if item.get("value") is None:
            continue
        if not indicator_label:
            indicator_label = item.get("indicator", {}).get("value", "")
        # Keep only most recent year per country
        if cid not in latest or item.get("date", "") > latest[cid].get("year", ""):
            latest[cid] = {
                "country": item.get("country", {}).get("value"),
                "country_code": cid,
                "value": item["value"],
                "year": item.get("date"),
            }

    ranked = sorted(
        latest.values(),
        key=lambda x: x.get("value") or 0,
        reverse=(order == "desc"),
    )[:limit]

    # Add rank numbers
    for i, entry in enumerate(ranked, 1):
        entry["rank"] = i

    return {
        "indicator": indicator_label,
        "indicator_code": indicator_code,
        "order": order,
        "rankings": ranked,
        "count": len(ranked),
        "timestamp": _ts(),
    }
