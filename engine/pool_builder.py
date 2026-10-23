import os
import json
import re
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://hanifsalman11.github.io/pool-pump-index").rstrip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "e9d8c7b6a5f4e3d2c1b0a9f8e7d6c5b4").strip()
CUSTOM_POOL = os.environ.get("CUSTOM_POOL", "").strip()
PAGES_PER_RUN = int(os.environ.get("PAGES_PER_RUN", "3"))

DOCS_DIR = "docs"
DATA_DIR = "data"
PUBLISHED_FILE = os.path.join(DATA_DIR, "published_pools.json")
MONETIZATION_FILE = os.path.join(DATA_DIR, "monetization.json")

# Format: (Model / Pool Scenario Name, Pool Volume Gallons, Pump HP, Plumbing Pipe Inches, Pool Type)
SEED_POOLS = [
    ("Pentair IntelliFlo3 VSF 3.0 HP Variable Speed", 25000, 3.0, 2.0, "In-Ground Pool"),
    ("Hayward TriStar VS 900 1.85 HP Variable Speed", 20000, 1.85, 2.0, "In-Ground Pool"),
    ("Hayward Super Pump VS 700 1.65 HP", 16000, 1.65, 1.5, "In-Ground Pool"),
    ("Pentair SuperFlo VST 1.5 HP Variable Speed", 15000, 1.5, 1.5, "In-Ground Pool"),
    ("BLACK+DECKER 2.0 HP Variable Speed Pool Pump", 22000, 2.0, 2.0, "In-Ground Pool"),
    ("BLACK+DECKER 1.5 HP Variable Speed Above-Ground", 12000, 1.5, 1.5, "Above-Ground Pool"),
    ("Jandy ePump 2.7 HP Variable Speed VSSHP270DV2A", 28000, 2.7, 2.0, "In-Ground Pool"),
    ("Hayward AquaRite S3 T-Cell-15 40K Gal System", 25000, 2.0, 2.0, "Saltwater In-Ground Pool"),
    ("Pentair IntelliChlor IC40 Salt Chlorinator Cell", 24000, 2.0, 2.0, "Saltwater In-Ground Pool"),
    ("CircuPool RJ-45 Plus Saltwater Chlorinator", 25000, 2.0, 2.0, "Saltwater In-Ground Pool"),
    ("Intex Krystal Clear 3000 GPH Sand Filter Pump", 10000, 0.75, 1.5, "Above-Ground Pool"),
    ("10,000 Gallon Plunge & Cocktail Pool", 10000, 1.5, 1.5, "Small In-Ground / Plunge"),
    ("15,000 Gallon Residential In-Ground Pool", 15000, 1.5, 1.5, "Standard In-Ground Pool"),
    ("20,000 Gallon Family In-Ground Swimming Pool", 20000, 2.0, 2.0, "Medium In-Ground Pool"),
    ("25,000 Gallon Diving Pool with Spa Spillover", 25000, 2.7, 2.0, "Large In-Ground + Spa"),
    ("30,000 Gallon Lagoon Pool with Waterfalls", 30000, 3.0, 2.5, "Estate In-Ground Pool"),
    ("35,000 Gallon Estate Lap & Diving Pool", 35000, 3.0, 2.5, "Commercial / Estate Pool"),
    ("18-Foot Round Above-Ground Pool (7,600 Gal)", 7600, 1.0, 1.5, "Round Above-Ground"),
    ("24-Foot Round Above-Ground Pool (13,500 Gal)", 13500, 1.5, 1.5, "Round Above-Ground"),
    ("16x32 Rectangular In-Ground Pool (19,200 Gal)", 19200, 2.0, 2.0, "Rectangular In-Ground"),
    ("18x36 Rectangular In-Ground Pool (24,300 Gal)", 24300, 2.5, 2.0, "Rectangular In-Ground"),
    ("20x40 Rectangular In-Ground Pool (30,000 Gal)", 30000, 3.0, 2.5, "Large Rectangular Pool"),
    ("Hayward SwimClear C4030 425 Sq Ft Cartridge Filter", 26000, 2.5, 2.0, "In-Ground Filtration"),
    ("Pentair Clean & Clear Plus 320 Sq Ft Filter", 20000, 2.0, 2.0, "In-Ground Filtration"),
    ("PentairWhisperFlo VST 2.6 HP High-Head Pump", 26000, 2.6, 2.0, "High-Head In-Ground"),
    ("Doheny's Pool Pro 1.5 HP Variable Speed Pump", 15000, 1.5, 1.5, "In-Ground / Above-Ground"),
    ("Harris ProForce 1.5 HP Above Ground Pool Pump", 12000, 1.5, 1.5, "Above-Ground Pool"),
    ("Blue Torrent 2.0 HP Cyclone Variable Speed", 20000, 2.0, 2.0, "In-Ground Pool"),
    ("Waterway Champion 2.7 HP Variable Speed Pump", 24000, 2.7, 2.0, "In-Ground Pool"),
    ("Jacuzzi J-VSP250 2.5 HP Variable Speed Pump", 22000, 2.5, 2.0, "In-Ground Pool")
]


def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Could not parse {filepath}: {e}")
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def safe_float(val, default=20000.0):
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return float(cleaned) if cleaned else float(default)
    except Exception:
        return float(default)


def build_amazon_url(search_keywords, mon_cfg):
    domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")
    encoded_q = urllib.parse.quote_plus(search_keywords)
    return f"https://{domain}/s?k={encoded_q}&tag={tag}"


def discover_google_pool_queries():
    """Mengambil kueri ukuran pompa kolam, filter, dan salt cell dari Google Autocomplete US."""
    discovered = []
    seeds = [
        "what size pool pump for ",
        "pool pump gpm calculator for ",
        "salt cell size for ",
        "pentair intelliflo "
    ]
    for seed in seeds:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q={urllib.parse.quote(seed)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for suggestion in data[1]:
                    cleaned = suggestion.lower()
                    for pref in seeds:
                        cleaned = cleaned.replace(pref, "")
                    cleaned = re.sub(
                        r"\b(calculator|size|sizing|gpm|flow|rate|for|how|many)\b",
                        "",
                        cleaned
                    ).strip()
                    if 5 <= len(cleaned) <= 42:
                        gal_match = re.search(r"(\d{2})[,\s]?000", cleaned)
                        gal_val = int(gal_match.group(1)) * 1000 if gal_match else 20000
                        hp_val = 1.5 if gal_val <= 16000 else (2.0 if gal_val <= 24000 else 3.0)
                        pipe_val = 1.5 if gal_val <= 16000 else 2.0
                        discovered.append((cleaned.title(), gal_val, hp_val, pipe_val, "In-Ground / Above-Ground Pool"))
        except Exception as e:
            print(f"[WARN] Google Suggest notice: {e}")
    return discovered


def build_deterministic_pool_data(pool_tuple):
    """Mesin Fisika Hidrolik Kolam APSP/ANSI-15 & Kimia Garam (100% bebas gagal)."""
    item_name, gallons, pump_hp, pipe_in, pool_type = pool_tuple

    # Rumus 8-Hour Turnover Rate: GPM = Gallons / (8 hours * 60 minutes) = Gallons / 480
    gpm_8hr = int(round(gallons / 480.0))
    gph_8hr = gpm_8hr * 60

    # Batas kecepatan aliran pipa PVC (APSP 6 ft/sec suction, 8 ft/sec return)
    # 1.5" PVC safe max = 42 GPM | 2.0" PVC safe max = 73 GPM | 2.5" PVC safe max = 115 GPM
    max_pipe_gpm = 42 if pipe_in <= 1.5 else (73 if pipe_in <= 2.0 else 115)

    # Aturan Salt Chlorinator: Pilih kapasitas cell 1.5x hingga 2.0x dari volume kolam
    salt_cell_rating = 20000 if gallons <= 12000 else (40000 if gallons <= 26000 else 60000)
    # Jumlah kantong garam 40-lb dari 0 ppm ke 3,200 ppm: (Gallons * 8.34 * 0.0032) / 40 = Gallons * 0.000667
    salt_bags_40lb = int(round(gallons * 0.000667))

    # Luas Cartridge Filter minimum (100 sq ft per 10,000 gal + 50% oversize buffer)
    filter_sqft = int(round((gallons / 100.0) * 1.5, -1))

    return {
        "pool_name": item_name,
        "pool_type": pool_type,
        "seo_title": f"{item_name} GPM Flow Rate, Filter & Salt Cell Calculator (2026)",
        "meta_description": f"Calculate exact 8-hour turnover flow rate ({gpm_8hr} GPM), PVC pipe velocity limit ({max_pipe_gpm} GPM), cartridge filter size ({filter_sqft} sq ft), and salt cell rating for {item_name}.",
        "specs": {
            "pool_gallons": gallons,
            "turnover_8hr_gpm": gpm_8hr,
            "turnover_8hr_gph": gph_8hr,
            "recommended_pump_hp": pump_hp,
            "plumbing_pipe_inches": pipe_in,
            "max_safe_pipe_gpm": max_pipe_gpm,
            "recommended_filter_sqft": filter_sqft,
            "recommended_salt_cell_gal": salt_cell_rating,
            "initial_40lb_salt_bags": salt_bags_40lb
        },
        "hydraulic_verdict": f"For a {gallons:,}-gallon setup ({item_name}), achieving a standard 8-hour water turnover requires a continuous flow rate of {gpm_8hr} GPM ({gph_8hr:,} GPH). With {pipe_in}-inch Schedule 40 PVC plumbing (rated up to {max_pipe_gpm} GPM at 6 ft/sec suction velocity), pair a {pump_hp} THP Variable-Speed Pump with a {filter_sqft} sq ft cartridge filter and a {salt_cell_rating:,}-gallon rated Saltwater Chlorinator Cell.",
        "hardware_bundle": [
            {
                "badge": f"{pump_hp} HP Variable Speed Pump",
                "title": f"{pump_hp} THP Energy-Star Variable-Speed Pool Pump (115V/230V Dual Voltage)",
                "price_range": "$469 - $1,399",
                "amazon_query": f"{pump_hp} HP Variable Speed Pool Pump Energy Star",
                "pool_note": f"Cuts electricity consumption by up to 75% by running at low RPM (1,400–1,800 RPM) after the initial high-speed skimmer prime."
            },
            {
                "badge": f"{salt_cell_rating // 1000}K-Gal Salt Chlorinator",
                "title": f"{salt_cell_rating:,}-Gallon Digital Saltwater Chlorinator System & Titanium TurboCell",
                "price_range": "$429 - $999",
                "amazon_query": f"Saltwater Pool Chlorinator System {salt_cell_rating} Gallon Salt Cell",
                "pool_note": f"Oversized by 1.5x–2x for a {gallons:,}-gallon pool so the titanium blades run at 50% output, doubling cell lifespan to 5–7 years."
            },
            {
                "badge": f"{filter_sqft} Sq Ft Cartridge Filter",
                "title": f"{filter_sqft} Sq Ft Heavy-Duty Multi-Element Cartridge Pool Filter Tank",
                "price_range": "$349 - $949",
                "amazon_query": f"{filter_sqft} Sq Ft Cartridge Pool Filter System",
                "pool_note": f"Handles {gpm_8hr}+ GPM with minimal backpressure (PSI), requiring hose-down cleaning only 2 times per swimming season."
            },
            {
                "badge": "Autonomous Robotic Vacuum",
                "title": "Cordless / Swivel-Cable Robotic Pool Vacuum (Floor, Wall & Waterline Scrubber)",
                "price_range": "$399 - $999",
                "amazon_query": "Robotic Pool Cleaner Vacuum In Ground Wall Climbing",
                "pool_note": "Operates independently of your main hydraulic pump, scrubbing algae from tile lines and trapping 2-micron fine silt."
            }
        ],
        "maintenance_checklist": [
            f"Keep suction line velocity below 6 ft/sec ({max_pipe_gpm} GPM on {pipe_in}\" PVC) in compliance with APSP/ANSI-15 and Virginia Graeme Baker safety standards to prevent pump cavitation.",
            f"Program your {pump_hp} HP Variable-Speed Pump for 2 hours at 2,800 RPM (surface skimming & vacuuming) and 8–10 hours at 1,500 RPM (ultra-efficient filtration & salt chlorination).",
            f"When converting {gallons:,} gallons of fresh water to 3,200 ppm salinity, broadcast {salt_bags_40lb} bags (40 lbs each) of 99.8% pure pool-grade evaporated salt with the chlorinator turned OFF for 24 hours.",
            "Install a 2-inch Clear Check Valve between the filter/heater outlet and the salt chlorinator cell to prevent concentrated chlorine gas from back-flowing into heater heat-exchangers."
        ],
        "faqs": [
            {
                "q": f"How many GPM do I need for {item_name} ({gallons:,} gallons)?",
                "a": f"To filter {gallons:,} gallons once every 8 hours (480 minutes), your pump must deliver {gpm_8hr} Gallons Per Minute ({gph_8hr:,} GPH). For a 6-hour commercial/summer turnover, increase flow to {int(round(gallons / 360.0))} GPM."
            },
            {
                "q": f"What size saltwater chlorinator cell do I need for {gallons:,} gallons?",
                "a": f"Always size your salt cell at 1.5x to 2x your actual water volume. For {gallons:,} gallons, install a {salt_cell_rating:,}-gallon rated salt cell (such as a T-Cell-15 or IC40) along with {salt_bags_40lb} bags (40 lbs each) of pool salt to reach 3,200 ppm."
            },
            {
                "q": f"How much electricity does a variable-speed pump save on a {gallons:,}-gallon pool?",
                "a": f"By affinity laws, cutting pump RPM in half reduces power consumption to one-eighth (12.5%). Running a {pump_hp} HP variable-speed pump at low speed draws only 180W–280W compared to 1,800W+ on a single-speed pump, saving $650 to $1,100 per year in utility bills."
            }
        ]
    }


def generate_pool_data(pool_tuple):
    """Memanggil Gemini 2.5 Flash API; jika gagal otomatis memakai Deterministic Pool Hydraulics Engine."""
    if not GEMINI_API_KEY:
        return build_deterministic_pool_data(pool_tuple)

    item_name, gallons, pump_hp, pipe_in, pool_type = pool_tuple
    gpm_8hr = int(round(gallons / 480.0))
    max_pipe_gpm = 42 if pipe_in <= 1.5 else (73 if pipe_in <= 2.0 else 115)
    salt_cell_rating = 20000 if gallons <= 12000 else (40000 if gallons <= 26000 else 60000)
    salt_bags_40lb = int(round(gallons * 0.000667))
    filter_sqft = int(round((gallons / 100.0) * 1.5, -1))

    prompt = f"""
You are a Certified Pool/Spa Operator (CPO) & Hydraulic Mechanical Engineer. Create an accurate 2026 GPM flow rate, turnover, filter area, and saltwater chlorinator sizing guide for: "{item_name}".
Baseline reference specs: Volume={gallons} Gallons, 8-Hr Turnover={gpm_8hr} GPM, Pump={pump_hp} HP, Pipe={pipe_in} Inch PVC (Max {max_pipe_gpm} GPM), Filter={filter_sqft} sq ft, Salt Cell={salt_cell_rating} Gal, Initial Salt={salt_bags_40lb} bags (40lb).
Return ONLY a valid JSON object matching this exact schema:
{{
  "pool_name": "{item_name}",
  "pool_type": "{pool_type}",
  "seo_title": "{item_name} GPM Flow Rate, Filter & Salt Cell Calculator (2026)",
  "meta_description": "Calculate exact 8-hour turnover GPM, PVC pipe velocity limits, cartridge filter square footage, and salt chlorinator sizing for {item_name}.",
  "specs": {{
    "pool_gallons": {gallons},
    "turnover_8hr_gpm": {gpm_8hr},
    "turnover_8hr_gph": {gpm_8hr * 60},
    "recommended_pump_hp": {pump_hp},
    "plumbing_pipe_inches": {pipe_in},
    "max_safe_pipe_gpm": {max_pipe_gpm},
    "recommended_filter_sqft": {filter_sqft},
    "recommended_salt_cell_gal": {salt_cell_rating},
    "initial_40lb_salt_bags": {salt_bags_40lb}
  }},
  "hydraulic_verdict": "3-sentence technical summary stating pool gallons, 8-hour GPM flow rate, PVC pipe velocity limit, filter sq ft, and recommended salt cell capacity.",
  "hardware_bundle": [
    {{
      "badge": "Variable-Speed Pump",
      "title": "Exact Variable-Speed Pool Pump recommendation",
      "price_range": "$479 - $1,399",
      "amazon_query": "{pump_hp} HP Variable Speed Pool Pump",
      "pool_note": "1-sentence DOE energy efficiency note"
    }},
    {{
      "badge": "Saltwater Chlorinator",
      "title": "Exact Saltwater Chlorinator & TurboCell recommendation",
      "price_range": "$429 - $999",
      "amazon_query": "Saltwater Pool Chlorinator System {salt_cell_rating} Gallon",
      "pool_note": "1-sentence 2x cell oversizing note"
    }},
    {{
      "badge": "Cartridge Filter Tank",
      "title": "Exact Cartridge Pool Filter recommendation",
      "price_range": "$349 - $899",
      "amazon_query": "{filter_sqft} Sq Ft Cartridge Pool Filter",
      "pool_note": "1-sentence PSI head loss note"
    }},
    {{
      "badge": "Robotic Pool Cleaner",
      "title": "Automatic Wall-Climbing Robotic Pool Vacuum Cleaner",
      "price_range": "$399 - $949",
      "amazon_query": "Robotic Pool Vacuum Cleaner In Ground",
      "pool_note": "1-sentence independent filtration note"
    }}
  ],
  "maintenance_checklist": [
    "Step 1 regarding PVC pipe velocity and suction head loss",
    "Step 2 regarding 2-stage variable speed RPM scheduling",
    "Step 3 regarding 3,200 ppm salt dosing calculation",
    "Step 4 regarding check valve and sacrificial zinc anode installation"
  ],
  "faqs": [
    {{"q": "How many GPM do I need for {item_name}?", "a": "Exact GPM and GPH for 8-hour and 6-hour turnover."}},
    {{"q": "What size salt cell and how many bags of salt for {gallons} gallons?", "a": "Exact cell gallon rating and number of 40-lb salt bags."}},
    {{"q": "What size pool filter do I need for {gallons} gallons?", "a": "Exact sq ft for cartridge, DE, and sand filters."}}
  ]
}}
"""

    for model_id in ["gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "responseMimeType": "application/json"
                }
            }
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                raw_text = re.sub(r"\s*```$", "", raw_text)
                parsed = json.loads(raw_text)
                if "specs" in parsed and "hardware_bundle" in parsed:
                    return parsed
        except Exception as e:
            print(f"[WARN] Gemini ({model_id}) notice for '{item_name}': {e}")

    return build_deterministic_pool_data(pool_tuple)


def build_pool_html_page(data, slug, mon_cfg):
    pool_name = data.get("pool_name", "Swimming Pool")
    sp = data.get("specs", {})
    gallons = int(safe_float(sp.get("pool_gallons", 20000), 20000))
    gpm_8hr = int(safe_float(sp.get("turnover_8hr_gpm", int(gallons / 480)), 42))
    pump_hp = round(safe_float(sp.get("recommended_pump_hp", 2.0), 2.0), 2)
    pipe_in = round(safe_float(sp.get("plumbing_pipe_inches", 2.0), 2.0), 1)
    max_pipe_gpm = int(safe_float(sp.get("max_safe_pipe_gpm", 73), 73))
    filter_sqft = int(safe_float(sp.get("recommended_filter_sqft", 300), 300))
    salt_cell_gal = int(safe_float(sp.get("recommended_salt_cell_gal", 40000), 40000))

    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "Variable+Speed+Pool+Pump"), mon_cfg)

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": f"{pool_name} GPM Flow Rate & Salt Cell Sizing Calculator",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "Web Browser",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.get("q", ""),
                        "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")}
                    } for f in data.get("faqs", [])
                ]
            }
        ]
    }

    bundle_html = ""
    for item in data.get("hardware_bundle", []):
        amz_url = build_amazon_url(item.get("amazon_query", item.get("title", "Variable Speed Pool Pump")), mon_cfg)
        bundle_html += f"""
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-blue-500/60 transition">
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-xs font-bold uppercase tracking-wider bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2.5 py-0.5 rounded">{item.get('badge', 'Pool Gear')}</span>
              <span class="text-sm font-bold text-emerald-400">{item.get('price_range', '$349+')}</span>
            </div>
            <h3 class="text-base font-bold text-white mt-2">{item.get('title', '')}</h3>
            <p class="text-xs text-slate-400 mt-2 leading-relaxed">💧 {item.get('pool_note', '')}</p>
          </div>
          <a href="{amz_url}" target="_blank" rel="nofollow sponsored" class="mt-5 block text-center bg-blue-500 hover:bg-blue-400 text-slate-950 font-extrabold py-2.5 px-4 rounded-lg text-sm transition shadow-lg">
            Check Price on Amazon →
          </a>
        </div>"""

    # Build Pool Volume vs Hydraulics Reference Matrix
    matrix_rows_html = ""
    for vol_g in [10000, 15000, 20000, 25000, 30000, 35000]:
        gpm_v = int(round(vol_g / 480.0))
        pipe_v = '1.5" or 2.0" PVC' if gpm_v <= 42 else ('2.0" Schedule 40 PVC' if gpm_v <= 73 else '2.5" Schedule 40 PVC')
        flt_v = int(round((vol_g / 100.0) * 1.5, -1))
        cell_v = "20,000 Gal Cell" if vol_g <= 12000 else ("40,000 Gal Cell (T-15/IC40)" if vol_g <= 26000 else "60,000 Gal Commercial Cell")
        bags_v = int(round(vol_g * 0.000667))
        matrix_rows_html += f"""
        <tr class="border-b border-slate-800 hover:bg-slate-800/40">
          <td class="py-3 px-4 font-bold text-white">{vol_g:,} Gallons</td>
          <td class="py-3 px-4 font-bold text-blue-400">{gpm_v} GPM ({gpm_v*60:,} GPH)</td>
          <td class="py-3 px-4 text-slate-300">{pipe_v}</td>
          <td class="py-3 px-4 text-emerald-400 font-semibold">{flt_v} Sq Ft Cartridge</td>
          <td class="py-3 px-4 text-xs text-slate-300">{cell_v} ({bags_v} Bags)</td>
        </tr>"""

    checklist_html = ""
    for idx, step_text in enumerate(data.get("maintenance_checklist", []), start=1):
        checklist_html += f"""
        <label class="flex items-start gap-3.5 bg-slate-900 border border-slate-800 rounded-xl p-4 cursor-pointer hover:border-slate-700 transition">
          <input type="checkbox" class="mt-1 w-5 h-5 accent-blue-500 rounded cursor-pointer pool-check">
          <span class="text-sm text-slate-200 leading-relaxed"><strong>Step {idx}:</strong> {step_text}</span>
        </label>"""

    faqs_html = "".join([
        f"<div class='bg-slate-900 border border-slate-800 rounded-xl p-5'><h3 class='font-bold text-white text-base mb-2'>{f.get('q', '')}</h3><p class='text-sm text-slate-300 leading-relaxed'>{f.get('a', '')}</p></div>"
        for f in data.get("faqs", [])
    ])

    canonical_url = f"{SITE_BASE_URL}/{slug}.html"
    amz_domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    amz_tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")

    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('seo_title', pool_name)}</title>
  <meta name="description" content="{data.get('meta_description', '')}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{data.get('seo_title', pool_name)}">
  <meta property="og:description" content="{data.get('meta_description', '')}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="application/ld+json">{json.dumps(schema_graph)}</script>
</head>
<body class="bg-slate-950 text-slate-100 antialiased min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <a href="index.html" class="text-lg font-black tracking-tight text-white flex items-center gap-2">
        <span class="bg-blue-500 text-slate-950 px-2 py-0.5 rounded font-black">POOL</span>PumpIndex
      </a>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-blue-500 hover:bg-blue-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Variable-Speed Pool Pumps →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-10 flex-1 w-full">
    <div class="mb-8">
      <div class="flex flex-wrap items-center gap-2.5 mb-3">
        <span class="text-xs font-extrabold uppercase tracking-widest bg-blue-500 text-slate-950 px-3 py-1 rounded-full">{gallons:,} Gallons | {gpm_8hr} GPM</span>
        <span class="text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-full">Pump: {pump_hp} HP | Pipe: {pipe_in}" PVC</span>
        <span class="text-xs font-semibold bg-slate-800 text-slate-300 px-3 py-1 rounded-full">Filter: {filter_sqft} Sq Ft | Salt Cell: {salt_cell_gal:,} Gal</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-black text-white leading-tight">{data.get('seo_title', pool_name)}</h1>
      <div class="mt-4 bg-slate-900 border-l-4 border-blue-500 p-4 rounded-r-xl text-sm text-slate-200 leading-relaxed">
        <strong>CPO Hydraulic & Filtration Summary:</strong> {data.get('hydraulic_verdict', '')}
      </div>
    </div>

    <!-- INTERACTIVE GPM FLOW RATE, FILTER & SALT CELL CALCULATOR -->
    <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 mb-12 shadow-2xl">
      <h2 class="text-xl font-extrabold text-white mb-2">Interactive {pool_name} GPM, Filter & Salt Dosing Calculator</h2>
      <p class="text-xs text-slate-400 mb-6">Adjust your pool volume (gallons), desired turnover cycle, PVC suction pipe diameter, and current salt ppm to calculate required GPM flow, filter area, and 40-lb salt bags.</p>

      <div class="grid md:grid-cols-2 gap-8 items-center">
        <div class="space-y-5">
          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="galSlider" class="text-slate-300">Swimming Pool Water Volume (Gallons)</label>
              <span class="text-blue-400 font-bold"><span id="galVal">{gallons:,}</span> Gal</span>
            </div>
            <input id="galSlider" type="range" min="5000" max="45000" step="1000" value="{gallons}" class="w-full accent-blue-500 cursor-pointer">
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="turnSelect" class="block text-xs font-medium text-slate-400 mb-1">Target Turnover Cycle</label>
              <select id="turnSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500">
                <option value="360">6 Hours (Heavy Swim / Hot)</option>
                <option value="480" selected>8 Hours (APSP Standard)</option>
                <option value="600">10 Hours (Variable Low-RPM)</option>
              </select>
            </div>
            <div>
              <label for="pipeSelect" class="block text-xs font-medium text-slate-400 mb-1">Suction PVC Pipe Size</label>
              <select id="pipeSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500">
                <option value="42" {"selected" if pipe_in <= 1.5 else ""}>1.5" Schedule 40 PVC (Max 42 GPM)</option>
                <option value="73" {"selected" if 1.5 < pipe_in <= 2.0 else ""}>2.0" Schedule 40 PVC (Max 73 GPM)</option>
                <option value="115" {"selected" if pipe_in > 2.0 else ""}>2.5" Schedule 40 PVC (Max 115 GPM)</option>
              </select>
            </div>
          </div>

          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="ppmSlider" class="text-slate-300">Current Pool Salt Level (Target = 3,200 ppm)</label>
              <span class="text-blue-400 font-bold"><span id="ppmVal">400</span> ppm</span>
            </div>
            <input id="ppmSlider" type="range" min="0" max="3000" step="200" value="400" class="w-full accent-blue-500 cursor-pointer">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="bg-slate-950 border border-blue-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-blue-400 font-bold">Required Flow Rate</span>
            <div class="text-2xl sm:text-3xl font-black text-white mt-1"><span id="gpmOut">{gpm_8hr}</span> <span class="text-sm font-normal text-slate-400">GPM</span></div>
            <p id="pipeStatusOut" class="text-xs text-emerald-400 font-semibold mt-1">✅ Safe for 2.0" PVC</p>
          </div>

          <div class="bg-slate-950 border border-emerald-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-emerald-400 font-bold">Salt & Filter Spec</span>
            <div class="text-xl sm:text-2xl font-black text-emerald-400 mt-1"><span id="bagsOut">12</span> <span class="text-xs font-normal text-slate-400">Bags (40lb)</span></div>
            <p id="filterSpecOut" class="text-xs text-slate-400 mt-1">Min Filter: {filter_sqft} Sq Ft</p>
          </div>
        </div>
      </div>

      <div class="mt-6 bg-blue-950/40 border border-blue-500/30 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div id="poolAdviceBanner" class="text-sm text-blue-100 font-medium"></div>
        <a id="dynamicPumpBtn" href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="shrink-0 bg-blue-500 hover:bg-blue-400 text-slate-950 font-extrabold px-4 py-2.5 rounded-lg text-xs uppercase tracking-wider transition">
          Shop Matched Pool Equipment on Amazon →
        </a>
      </div>
    </section>

    <!-- 4-CARD HARDWARE BUNDLE -->
    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">Recommended Pump, Salt Cell & Filter Bundle for {pool_name}</h2>
        <span class="text-xs text-slate-400">DOE Energy-Star & NSF-50 Certified</span>
      </div>
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{bundle_html}</div>
    </section>

    <!-- POOL VOLUME & HYDRAULICS MATRIX TABLE -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-4">Pool Volume, 8-Hour GPM, PVC Pipe & Salt Cell Sizing Chart</h2>
      <div class="overflow-x-auto bg-slate-900 border border-slate-800 rounded-xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase text-xs">
              <th class="py-3.5 px-4">Pool Volume</th>
              <th class="py-3.5 px-4 text-blue-400">8-Hour Turnover Flow</th>
              <th class="py-3.5 px-4">Min Suction PVC Pipe</th>
              <th class="py-3.5 px-4 text-emerald-400">Cartridge Filter Area</th>
              <th class="py-3.5 px-4">Salt Cell & Initial Salt</th>
            </tr>
          </thead>
          <tbody>{matrix_rows_html}</tbody>
        </table>
      </div>
    </section>

    <!-- MAINTENANCE CHECKLIST -->
    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">CPO Hydraulic & Saltwater Setup Checklist</h2>
        <span id="poolBadge" class="text-xs font-bold bg-slate-800 text-blue-400 px-3 py-1 rounded-full">0 / 4 Completed</span>
      </div>
      <div class="space-y-3">{checklist_html}</div>
    </section>

    <!-- FAQ -->
    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-5">Frequently Asked Questions ({pool_name})</h2>
      <div class="space-y-4">{faqs_html}</div>
    </section>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500 px-4">
    <p>© {datetime.now(timezone.utc).year} PoolPumpIndex. Independent Swimming Pool Hydraulics & Filtration Engineering Database. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const amzDomain = "{amz_domain}";
    const amzTag = "{amz_tag}";

    const galSlider = document.getElementById('galSlider');
    const turnSelect = document.getElementById('turnSelect');
    const pipeSelect = document.getElementById('pipeSelect');
    const ppmSlider = document.getElementById('ppmSlider');
    const galVal = document.getElementById('galVal');
    const ppmVal = document.getElementById('ppmVal');
    const gpmOut = document.getElementById('gpmOut');
    const pipeStatusOut = document.getElementById('pipeStatusOut');
    const bagsOut = document.getElementById('bagsOut');
    const filterSpecOut = document.getElementById('filterSpecOut');
    const poolAdviceBanner = document.getElementById('poolAdviceBanner');
    const dynamicPumpBtn = document.getElementById('dynamicPumpBtn');

    function recalculatePool() {{
      const gals = parseInt(galSlider.value, 10);
      const turnMins = parseInt(turnSelect.value, 10);
      const maxPipeGpm = parseInt(pipeSelect.value, 10);
      const currentPpm = parseInt(ppmSlider.value, 10);

      galVal.textContent = gals.toLocaleString();
      ppmVal.textContent = currentPpm.toLocaleString();

      const reqGpm = Math.round(gals / turnMins);
      const ppmDeficit = Math.max(0, 3200 - currentPpm);
      const lbsSalt = (gals * 8.34 * (ppmDeficit / 1000000.0));
      const bags40lb = Math.ceil(lbsSalt / 40.0);
      const recFilterSqft = Math.round((gals / 100.0) * 1.5 / 10) * 10;

      gpmOut.textContent = reqGpm;
      bagsOut.textContent = bags40lb;
      filterSpecOut.textContent = `Min Filter: ${{recFilterSqft}} Sq Ft`;

      if (reqGpm <= maxPipeGpm) {{
        pipeStatusOut.textContent = `✅ Safe (${{reqGpm}} / ${{maxPipeGpm}} GPM Pipe Limit)`;
        pipeStatusOut.className = "text-xs text-emerald-400 font-semibold mt-1";
      }} else {{
        pipeStatusOut.textContent = `⚠️ Exceeds ${{maxPipeGpm}} GPM Pipe Velocity!`;
        pipeStatusOut.className = "text-xs text-amber-400 font-bold mt-1";
      }}

      let recHp = "1.5 HP";
      let recCell = "20,000-Gallon";
      if (gals <= 16000) {{
        recHp = "1.5 HP";
        recCell = "25,000-Gallon";
      }} else if (gals <= 26000) {{
        recHp = "2.0 HP";
        recCell = "40,000-Gallon (T-15 / IC40)";
      }} else {{
        recHp = "3.0 HP";
        recCell = "60,000-Gallon";
      }}

      poolAdviceBanner.innerHTML = `💧 <strong>Recommended Equipment Spec:</strong> Pair a <strong>${{recHp}} Variable-Speed Pool Pump</strong> with a <strong>${{recFilterSqft}} Sq Ft Cartridge Filter</strong> and a <strong>${{recCell}} Salt Chlorinator</strong>.`;
      dynamicPumpBtn.href = `https://${{amzDomain}}/s?k=${{encodeURIComponent(recHp)}}+Variable+Speed+Pool+Pump+Salt+Chlorinator&tag=${{amzTag}}`;
    }}

    galSlider.addEventListener('input', recalculatePool);
    turnSelect.addEventListener('change', recalculatePool);
    pipeSelect.addEventListener('change', recalculatePool);
    ppmSlider.addEventListener('input', recalculatePool);
    recalculatePool();

    const checks = document.querySelectorAll('.pool-check');
    const badge = document.getElementById('poolBadge');
    checks.forEach(ch => {{
      ch.addEventListener('change', () => {{
        const done = Array.from(checks).filter(c => c.checked).length;
        badge.textContent = `${{done}} / ${{checks.length}} Completed`;
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def rebuild_portal_sitemap_and_rss(published, mon_cfg):
    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "Variable+Speed+Pool+Pump"), mon_cfg)

    cards_html = ""
    for item in reversed(published):
        cards_html += f"""
        <a href="{item['slug']}.html" class="block bg-slate-900 border border-slate-800 hover:border-blue-500/60 rounded-xl p-5 transition group">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-black uppercase bg-blue-500 text-slate-950 px-2.5 py-0.5 rounded">{item.get('gallons', 20000):,} Gal | {item.get('gpm', 42)} GPM</span>
            <span class="text-xs text-slate-400">{item.get('pump_hp', 2.0)} HP Pump</span>
          </div>
          <h2 class="text-base font-bold text-white group-hover:text-blue-400 transition">{item['pool_name']} GPM & Salt Calculator</h2>
          <p class="text-xs text-slate-400 mt-2 line-clamp-2">{item['description']}</p>
          <span class="inline-block mt-4 text-xs font-extrabold text-blue-400">Calculate Flow Rate, Filter & Salt →</span>
        </a>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PoolPumpIndex — Swimming Pool Pump GPM, Filter & Salt Chlorinator Calculator (2026)</title>
  <meta name="description" content="Calculate exact swimming pool 8-hour turnover GPM, PVC pipe flow velocity, cartridge filter square footage, and saltwater chlorinator sizing for Pentair, Hayward, Jandy, and Black+Decker systems.">
  <link rel="canonical" href="{SITE_BASE_URL}/">
  <link rel="alternate" type="application/rss+xml" title="PoolPumpIndex RSS Feed" href="{SITE_BASE_URL}/rss.xml">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 sticky top-0 z-30 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <div class="text-lg font-black text-white flex items-center gap-2">
        <span class="bg-blue-500 text-slate-950 px-2 py-0.5 rounded font-black">POOL</span>PumpIndex
      </div>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-blue-500 hover:bg-blue-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Variable-Speed Pool Pumps →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-12 flex-1 w-full">
    <div class="text-center max-w-2xl mx-auto mb-10">
      <h1 class="text-3xl sm:text-5xl font-black text-white tracking-tight">Pool Pump GPM, Filter & Salt Chlorinator Sizing Database</h1>
      <p class="text-slate-400 mt-3 text-base sm:text-lg">Select your pool pump model or pool gallon size below to calculate 8-hour turnover GPM, Schedule 40 PVC pipe limits, cartridge filter area, and 40-lb salt bags required.</p>
      <div class="mt-6">
        <input id="filterInput" type="text" placeholder="Search pump model or pool size (e.g. Pentair IntelliFlo3, Hayward TriStar, 20,000 Gallon, Salt Cell...)" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-blue-500">
      </div>
    </div>

    <div id="poolGrid" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{cards_html}</div>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500">
    <p>© {datetime.now(timezone.utc).year} PoolPumpIndex. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const filterInput = document.getElementById('filterInput');
    const cards = Array.from(document.getElementById('poolGrid').children);
    filterInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase();
      cards.forEach(c => {{
        c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none';
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls_xml = f"""  <url>
    <loc>{SITE_BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>\n"""

    for item in published:
        urls_xml += f"""  <url>
    <loc>{SITE_BASE_URL}/{item['slug']}.html</loc>
    <lastmod>{item.get('date', today)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>\n"""

    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls_xml}</urlset>""")

    rss_items = ""
    for item in list(reversed(published))[:30]:
        rss_items += f"""    <item>
      <title>{item['title']}</title>
      <link>{SITE_BASE_URL}/{item['slug']}.html</link>
      <guid>{SITE_BASE_URL}/{item['slug']}.html</guid>
      <description>{item['description']}</description>
    </item>\n"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>PoolPumpIndex Swimming Pool Hydraulics & Salt Sizing Database</title>
    <link>{SITE_BASE_URL}/</link>
    <description>Interactive Swimming Pool Pump GPM, Filter Area & Saltwater Chlorinator Calculators</description>
    <atom:link href="{SITE_BASE_URL}/rss.xml" rel="self" type="application/rss+xml" />
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
{rss_items}  </channel>
</rss>"""

    with open(os.path.join(DOCS_DIR, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml)

    with open(os.path.join(DOCS_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n")

    with open(os.path.join(DOCS_DIR, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)


def notify_search_engines(new_urls):
    if not SITE_BASE_URL or not new_urls:
        return
    parsed_host = urllib.parse.urlparse(SITE_BASE_URL).netloc
    payload = {
        "host": parsed_host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_BASE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": new_urls
    }
    try:
        req = urllib.request.Request(
            "https://api.indexnow.org/indexnow",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[INDEXNOW] Pushed {len(new_urls)} URLs (HTTP {resp.status})")
    except Exception as e:
        print(f"[WARN] IndexNow ping notice: {e}")

    try:
        hub_data = urllib.parse.urlencode({
            "hub.mode": "publish",
            "hub.url": f"{SITE_BASE_URL}/rss.xml"
        }).encode("utf-8")
        req_hub = urllib.request.Request(
            "https://pubsubhubbub.appspot.com/",
            data=hub_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req_hub, timeout=15) as resp_hub:
            print(f"[WEBSUB] Google PubSubHubbub ping status: {resp_hub.status}")
    except Exception as e:
        print(f"[WARN] WebSub ping notice: {e}")


def main():
    published = load_json(PUBLISHED_FILE, [])
    mon_cfg = load_json(MONETIZATION_FILE, {})
    published_slugs = {item["slug"] for item in published}

    candidates = []
    if CUSTOM_POOL:
        candidates.append((CUSTOM_POOL.strip(), 20000, 2.0, 2.0, "In-Ground Pool"))
    candidates.extend(SEED_POOLS)
    candidates.extend(discover_google_pool_queries())

    new_urls = []
    count = 0

    for pool_tuple in candidates:
        if count >= PAGES_PER_RUN:
            break
        pool_name = pool_tuple[0]
        slug = slugify(f"{pool_name}-gpm-filter-salt-calculator")
        if slug in published_slugs:
            continue

        print(f"[ENGINE] Generating pool GPM & salt cell calculator for: {pool_name}...")
        try:
            data = generate_pool_data(pool_tuple)
            build_pool_html_page(data, slug, mon_cfg)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sp = data.get("specs", {})

            published.append({
                "pool_name": data.get("pool_name", pool_name),
                "slug": slug,
                "title": data.get("seo_title", f"{pool_name} GPM Calculator"),
                "description": data.get("meta_description", ""),
                "gallons": int(safe_float(sp.get("pool_gallons", pool_tuple[1]), pool_tuple[1])),
                "gpm": int(safe_float(sp.get("turnover_8hr_gpm", int(pool_tuple[1] / 480)), 42)),
                "pump_hp": round(safe_float(sp.get("recommended_pump_hp", pool_tuple[2]), pool_tuple[2]), 2),
                "date": today
            })
            published_slugs.add(slug)
            if SITE_BASE_URL:
                new_urls.append(f"{SITE_BASE_URL}/{slug}.html")
            count += 1
            time.sleep(2)
        except Exception as e:
            print(f"[ERROR] Failed building {pool_name}: {e}")

    save_json(PUBLISHED_FILE, published)
    rebuild_portal_sitemap_and_rss(published, mon_cfg)
    if new_urls and SITE_BASE_URL:
        new_urls.append(f"{SITE_BASE_URL}/")
        notify_search_engines(new_urls)
    print(f"[DONE] Published {count} new pool pump & salt calculator pages.")


if __name__ == "__main__":
    main()
