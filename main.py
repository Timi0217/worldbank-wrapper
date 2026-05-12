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
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>World Bank — Global Development Data</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e8e8e8;padding:40px 20px;line-height:1.5}
.container{max-width:680px;margin:0 auto;opacity:0;animation:fadeIn .5s ease forwards}
@keyframes fadeIn{to{opacity:1}}
@keyframes slideUp{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}

/* Header */
.header-card{background:linear-gradient(135deg,rgba(0,159,218,.4),rgba(0,120,180,.2));border:1px solid rgba(0,159,218,.15);border-radius:20px;padding:28px 28px 0;margin-bottom:16px;overflow:hidden}
.header-row{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px}
.brand{display:flex;align-items:center;gap:12px}
.brand-icon{width:42px;height:42px;background:linear-gradient(135deg,#009FDA,#0080C0);border-radius:10px;display:flex;align-items:center;justify-content:center;font-family:'Courier New',monospace;font-weight:900;font-size:16px;color:#fff;letter-spacing:-1px}
.brand-text .title{font-size:22px;font-weight:700;color:#fff;letter-spacing:-.5px}
.brand-text .org{font-size:12px;color:rgba(0,159,218,.8);font-weight:500;letter-spacing:.5px}
.health-badge{display:flex;align-items:center;gap:6px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:6px 14px;font-size:12px;color:#888;backdrop-filter:blur(10px)}
.health-dot{width:7px;height:7px;background:#555;border-radius:50%;transition:background .3s}
.health-dot.on{background:#4CAF50;box-shadow:0 0 8px rgba(76,175,80,.4)}
.tagline{color:#888;font-size:14px;margin-bottom:20px;margin-left:54px}

/* Stats grid */
.grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:rgba(255,255,255,.04);border-radius:0 0 20px 20px;overflow:hidden;margin:0 -28px}
.stat{background:#0a0a0a;padding:20px;text-align:center;position:relative;transition:background .2s;opacity:0;animation:slideUp .4s ease forwards}
.stat:nth-child(1){animation-delay:.1s}
.stat:nth-child(2){animation-delay:.15s}
.stat:nth-child(3){animation-delay:.2s}
.stat:hover{background:rgba(0,159,218,.04)}
.stat-label{font-size:10px;color:#666;text-transform:uppercase;letter-spacing:1.2px;font-weight:600;margin-bottom:10px}
.stat-val{font-family:'Courier New',monospace;font-size:28px;font-weight:700;color:#fff;line-height:1;margin-bottom:2px}
.stat-unit{font-size:13px;color:#555;font-weight:400}
.stat-meta{font-size:11px;color:#555;margin-top:8px}
.stat.warm .stat-val{color:#555;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:.6}50%{opacity:.3}}

/* Secondary cards */
.card{background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:20px 24px;margin-bottom:12px;animation:slideUp .5s ease backwards}

/* Search */
.search-row{display:flex;gap:8px;margin-bottom:10px}
.search-input{flex:1;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:10px;padding:11px 16px;color:#fff;font-size:14px;outline:none;transition:all .2s}
.search-input:focus{border-color:rgba(0,159,218,.5);background:rgba(255,255,255,.06);box-shadow:0 0 0 3px rgba(0,159,218,.1)}
.search-input::placeholder{color:#444}
.search-btn{background:linear-gradient(135deg,#009FDA,#0080C0);color:#fff;border:none;border-radius:10px;padding:11px 20px;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s;white-space:nowrap}
.search-btn:hover{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,159,218,.3)}
.quick-links{display:flex;gap:6px;flex-wrap:wrap}
.quick-link{background:rgba(255,255,255,.04);color:#666;padding:5px 10px;border-radius:6px;font-size:11px;cursor:pointer;transition:all .15s;border:1px solid transparent;font-family:'Courier New',monospace}
.quick-link:hover{background:rgba(0,159,218,.1);color:#009FDA;border-color:rgba(0,159,218,.2)}
.section-label{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;margin-bottom:12px}

/* Results */
#res{margin-top:14px;display:none}
.res-ui{padding:16px 18px;background:rgba(0,159,218,.06);border:1px solid rgba(0,159,218,.15);border-radius:10px}
.res-hd{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.res-title{font-size:16px;font-weight:700;color:#fff}
.res-sub{font-size:12px;color:#009FDA;font-family:'Courier New',monospace}
.res-tbl{width:100%;border-collapse:collapse}
.res-tbl th{text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.08)}
.res-tbl td{padding:8px 0;font-family:'Courier New',monospace;font-size:14px;border-bottom:1px solid rgba(255,255,255,.04)}
.res-tbl td:last-child{text-align:right;font-weight:600;color:#009FDA}
.res-tbl tr:last-child td{border-bottom:none}
.bar-wrap{display:flex;align-items:center;gap:8px}
.bar{height:6px;border-radius:3px;background:rgba(0,159,218,.3);flex-shrink:0}
.bar-pos{background:rgba(0,159,218,.6)}.bar-neg{background:rgba(255,68,68,.4)}
.toggle-raw{margin-top:12px;font-size:12px;color:#666;cursor:pointer;user-select:none;transition:color .15s}
.toggle-raw:hover{color:#009FDA}
.raw-json{margin-top:8px;padding:12px;background:rgba(0,0,0,.3);border-radius:8px;font-family:'Courier New',monospace;font-size:11px;line-height:1.5;white-space:pre-wrap;word-break:break-all;max-height:300px;overflow-y:auto;color:#888;display:none}

@media(max-width:480px){
.grid{grid-template-columns:1fr}
.search-row{flex-direction:column}
.brand-text .title{font-size:18px}
}
</style>
</head>
<body>
<div class="container">

<div class="header-card">
<div class="header-row">
<div class="brand">
<div class="brand-icon">WB</div>
<div class="brand-text">
<div class="title">World Bank</div>
<div class="org">Global Development Data</div>
</div>
</div>
<div class="health-badge"><span class="health-dot" id="dot"></span><span id="health-text">checking...</span></div>
</div>
<div class="tagline">1,400+ development indicators across 200+ countries</div>
<div class="grid" id="grid">
<div class="stat warm"><div class="stat-label">GLOBAL GDP</div><div class="stat-val" id="gdp">...</div><div class="stat-meta">Loading...</div></div>
<div class="stat warm"><div class="stat-label">WORLD POP.</div><div class="stat-val" id="pop">...</div><div class="stat-meta">Loading...</div></div>
<div class="stat"><div class="stat-label">INDICATORS</div><div class="stat-val">1,400<span class="stat-unit">+</span></div><div class="stat-meta">Available</div></div>
</div>
</div>

<div class="card" style="animation-delay:.15s">
<div class="section-label">Search Indicators</div>
<div class="search-row">
<input type="text" class="search-input" id="country" placeholder="Country (e.g., Nigeria, Kenya, India)" value="Nigeria">
<input type="text" class="search-input" id="indicator" placeholder="Indicator (e.g., gdp_growth, inflation)" value="gdp_growth">
<button class="search-btn" onclick="fetchD()">Fetch &rarr;</button>
</div>
<div class="quick-links">
<span style="color:#444;font-size:11px;margin-right:2px">Try:</span>
<span class="quick-link" onclick="ts('Kenya','gdp_growth')">Kenya GDP growth</span>
<span class="quick-link" onclick="ts('India','population')">India population</span>
<span class="quick-link" onclick="ts('Brazil','inflation')">Brazil inflation</span>
<span class="quick-link" onclick="ts('Nigeria','literacy_rate')">Nigeria literacy</span>
</div>
<div id="res"></div>
</div>

</div>
<script>
function fmt(n){if(n==null)return'--';if(n>=1e12)return'$'+(n/1e12).toFixed(1)+'T';if(n>=1e9)return(n/1e9).toFixed(1)+'B';if(n>=1e6)return(n/1e6).toFixed(1)+'M';return n.toLocaleString('en-US',{maximumFractionDigits:1})}

async function init(){
 const t0=Date.now();
 try{
  await fetch('/health');
  const ms=Date.now()-t0;
  document.getElementById('dot').classList.add('on');
  document.getElementById('health-text').textContent='online \\u00b7 '+ms+'ms';
 }catch(e){
  document.getElementById('health-text').textContent='offline';
 }

 try{
  const d=await fetch('/dashboard').then(r=>r.json());
  const gdpEl=document.getElementById('gdp');
  const popEl=document.getElementById('pop');
  const gdpStat=gdpEl.parentElement;
  const popStat=popEl.parentElement;

  if(d.gdp&&d.gdp.value){
   gdpEl.innerHTML=fmt(parseFloat(d.gdp.value));
   gdpStat.classList.remove('warm');
   const meta=gdpStat.querySelector('.stat-meta');
   if(meta)meta.textContent=d.gdp.year||'';
  }else{
   gdpEl.textContent='--';
   gdpStat.classList.remove('warm');
  }

  if(d.population&&d.population.value){
   popEl.textContent=fmt(parseFloat(d.population.value));
   popStat.classList.remove('warm');
   const meta=popStat.querySelector('.stat-meta');
   if(meta)meta.textContent=d.population.year||'';
  }else{
   popEl.textContent='--';
   popStat.classList.remove('warm');
  }
 }catch(e){
  document.getElementById('gdp').textContent='--';
  document.getElementById('pop').textContent='--';
  document.getElementById('gdp').parentElement.classList.remove('warm');
  document.getElementById('pop').parentElement.classList.remove('warm');
 }
}

function ts(c,i){document.getElementById('country').value=c;document.getElementById('indicator').value=i;fetchD()}

function fmtVal(v){if(v==null)return'--';const n=parseFloat(v);if(isNaN(n))return v;if(Math.abs(n)>=1e12)return(n/1e12).toFixed(2)+'T';if(Math.abs(n)>=1e9)return(n/1e9).toFixed(2)+'B';if(Math.abs(n)>=1e6)return(n/1e6).toFixed(1)+'M';if(Math.abs(n)>=1e3)return n.toLocaleString('en-US',{maximumFractionDigits:2});return n.toFixed(2)}
function renderIndicator(d){
 const obs=d.observations||[];if(!obs.length)return'<div class="res-ui"><div style="color:#888;text-align:center;padding:20px">No data available</div></div>';
 const vals=obs.map(o=>parseFloat(o.value)).filter(v=>!isNaN(v));
 const maxAbs=Math.max(...vals.map(v=>Math.abs(v)),1);
 const minVal=Math.min(...vals);const maxVal=Math.max(...vals);
 const latest=vals[0];const prev=vals.length>1?vals[1]:null;
 const chg=prev!=null&&prev!==0?((latest-prev)/Math.abs(prev)*100):null;
 const chgStr=chg!=null?((chg>=0?'+':'')+chg.toFixed(1)+'%'):'';
 const chgCls=chg!=null?(chg>=0?'color:#4CAF50':'color:#ef5350'):'color:#888';
 let rows='';
 obs.forEach(o=>{
  const v=parseFloat(o.value);const pct=Math.min(Math.abs(v)/maxAbs*120,120);
  const cls=v>=0?'bar-pos':'bar-neg';
  rows+='<tr><td>'+o.year+'</td><td><div class="bar-wrap"><div class="bar '+cls+'" style="width:'+pct+'px"></div></div></td><td>'+fmtVal(o.value)+'</td></tr>';
 });
 const latestStr=obs[0]?fmtVal(obs[0].value):'--';
 return '<div class="res-ui">'
  +'<div class="res-hd"><div><div class="res-title">'+(d.country||'')+'</div><div class="res-sub">'+(d.indicator||d.indicator_code||'')+'</div></div><div style="text-align:right"><div style="font-family:Courier New,monospace;font-size:28px;font-weight:700;color:#fff">'+latestStr+'</div><div style="font-size:11px;color:#666">'+(obs[0]?obs[0].year:'')+(chgStr?' &middot; <span style="'+chgCls+'">'+chgStr+' YoY</span>':'')+'</div></div></div>'
  +'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;margin-bottom:14px">'
  +'<div style="background:rgba(0,159,218,.08);border-radius:8px;padding:10px 12px;text-align:center"><div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Range High</div><div style="font-family:Courier New,monospace;font-size:16px;font-weight:700;color:#4CAF50">'+fmtVal(maxVal)+'</div></div>'
  +'<div style="background:rgba(0,159,218,.08);border-radius:8px;padding:10px 12px;text-align:center"><div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Range Low</div><div style="font-family:Courier New,monospace;font-size:16px;font-weight:700;color:#ef5350">'+fmtVal(minVal)+'</div></div>'
  +'<div style="background:rgba(0,159,218,.08);border-radius:8px;padding:10px 12px;text-align:center"><div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Data Points</div><div style="font-family:Courier New,monospace;font-size:16px;font-weight:700;color:#009FDA">'+d.count+'</div></div>'
  +'</div>'
  +'<div style="font-size:12px;color:#666;margin-bottom:8px">'+d.country_code+' &middot; '+(d.indicator_code||'')+'</div>'
  +'<table class="res-tbl"><thead><tr><th>Year</th><th></th><th style="text-align:right">Value</th></tr></thead><tbody>'+rows+'</tbody></table>'
  +'<div class="toggle-raw" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display===\\x27none\\x27?\\x27block\\x27:\\x27none\\x27">Show raw JSON</div>'
  +'<div class="raw-json">'+JSON.stringify(d,null,2)+'</div>'
  +'</div>';
}
async function fetchD(){
 const c=document.getElementById('country').value.trim();
 const i=document.getElementById('indicator').value.trim();
 if(!c||!i)return;
 const res=document.getElementById('res');res.style.display='block';res.innerHTML='<div class="res-ui" style="color:#888;text-align:center;padding:20px">Fetching '+i+' for '+c+'...</div>';
 try{const d=await fetch('/indicator?country='+encodeURIComponent(c)+'&name='+encodeURIComponent(i)).then(r=>{if(!r.ok)throw new Error(r.status);return r.json()});
  res.innerHTML=renderIndicator(d)}
 catch(e){res.innerHTML='<div class="res-ui"><span style="color:#ef5350">Error: '+e.message+'</span></div>'}
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


@app.get("/dashboard")
async def dashboard():
    """
    Get all homepage data in a single request (health check, global GDP, world population).
    This endpoint aggregates multiple API calls server-side with small delays between them.
    """
    import asyncio

    result = {
        "health": {"status": "healthy", "timestamp": _ts()},
        "gdp": None,
        "population": None,
    }

    # Add small delay for health check simulation
    await asyncio.sleep(0.05)

    # Fetch global GDP
    try:
        current_year = datetime.now(timezone.utc).year
        date_range = f"{current_year - 10}:{current_year}"
        gdp_data = await _wb_get(
            "/country/WLD/indicator/NY.GDP.MKTP.CD",
            params={"date": date_range},
        )
        if gdp_data:
            for item in gdp_data:
                if item.get("value") is not None:
                    result["gdp"] = {
                        "value": item["value"],
                        "year": item.get("date"),
                    }
                    break
    except Exception:
        pass

    # Small delay between requests
    await asyncio.sleep(0.05)

    # Fetch world population
    try:
        current_year = datetime.now(timezone.utc).year
        date_range = f"{current_year - 10}:{current_year}"
        pop_data = await _wb_get(
            "/country/WLD/indicator/SP.POP.TOTL",
            params={"date": date_range},
        )
        if pop_data:
            for item in pop_data:
                if item.get("value") is not None:
                    result["population"] = {
                        "value": item["value"],
                        "year": item.get("date"),
                    }
                    break
    except Exception:
        pass

    result["timestamp"] = _ts()
    return result


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
