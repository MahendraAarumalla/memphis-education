"""
build_district_json.py
Generates districts_full.json for the Day 4 interactive dashboard.
Each district gets: name, city, county, income, quartile, TCAP by subject for
every available year, gap vs TN state average.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent
OUT      = DATA_DIR / "districts_full.json"

# ── City / county labels for every TN district ────────────────────────────────
# Format: system_id → {"city": ..., "county": ...}
DISTRICT_CITIES = {
    # Anderson County group
    10:  {"city":"Norris / Lake City area","county":"Anderson"},
    11:  {"city":"Clinton","county":"Anderson"},
    12:  {"city":"Oak Ridge","county":"Anderson"},
    # Bedford
    20:  {"city":"Shelbyville","county":"Bedford"},
    # Benton
    30:  {"city":"Camden","county":"Benton"},
    # Bledsoe
    40:  {"city":"Pikeville","county":"Bledsoe"},
    # Blount
    50:  {"city":"Maryville area","county":"Blount"},
    51:  {"city":"Alcoa","county":"Blount"},
    52:  {"city":"Maryville","county":"Blount"},
    # Bradley
    60:  {"city":"Cleveland area","county":"Bradley"},
    61:  {"city":"Cleveland","county":"Bradley"},
    # Campbell
    70:  {"city":"LaFollette","county":"Campbell"},
    # Cannon
    80:  {"city":"Woodbury","county":"Cannon"},
    # Carroll Co districts
    92:  {"city":"Hollow Rock","county":"Carroll"},
    93:  {"city":"Huntingdon","county":"Carroll"},
    94:  {"city":"McKenzie","county":"Carroll"},
    95:  {"city":"South Carroll","county":"Carroll"},
    97:  {"city":"West Carroll","county":"Carroll"},
    # Carter
    100: {"city":"Elizabethton area","county":"Carter"},
    101: {"city":"Elizabethton","county":"Carter"},
    # Cheatham
    110: {"city":"Ashland City","county":"Cheatham"},
    # Chester
    120: {"city":"Henderson","county":"Chester"},
    # Claiborne
    130: {"city":"Tazewell","county":"Claiborne"},
    # Clay
    140: {"city":"Celina","county":"Clay"},
    # Cocke
    150: {"city":"Newport area","county":"Cocke"},
    151: {"city":"Newport","county":"Cocke"},
    # Coffee
    160: {"city":"Manchester area","county":"Coffee"},
    161: {"city":"Manchester","county":"Coffee"},
    162: {"city":"Tullahoma","county":"Coffee"},
    # Crockett
    170: {"city":"Alamo area","county":"Crockett"},
    171: {"city":"Alamo","county":"Crockett"},
    172: {"city":"Bells","county":"Crockett"},
    # Cumberland
    180: {"city":"Crossville","county":"Cumberland"},
    # Davidson → Nashville
    190: {"city":"Nashville","county":"Davidson"},
    # Decatur
    200: {"city":"Decaturville","county":"Decatur"},
    # DeKalb
    210: {"city":"Smithville","county":"DeKalb"},
    # Dickson
    220: {"city":"Dickson","county":"Dickson"},
    # Dyer
    230: {"city":"Dyersburg area","county":"Dyer"},
    231: {"city":"Dyersburg","county":"Dyer"},
    # Fayette
    240: {"city":"Somerville","county":"Fayette"},
    # Fentress
    250: {"city":"Jamestown","county":"Fentress"},
    # Franklin
    260: {"city":"Winchester","county":"Franklin"},
    # Gibson Co cluster
    271: {"city":"Humboldt","county":"Gibson"},
    272: {"city":"Milan","county":"Gibson"},
    273: {"city":"Trenton","county":"Gibson"},
    274: {"city":"Bradford","county":"Gibson"},
    275: {"city":"Dyer / Kenton area","county":"Gibson"},
    # Giles
    280: {"city":"Pulaski","county":"Giles"},
    # Grainger
    290: {"city":"Rutledge","county":"Grainger"},
    # Greene
    300: {"city":"Greeneville area","county":"Greene"},
    301: {"city":"Greeneville","county":"Greene"},
    # Grundy
    310: {"city":"Altamont","county":"Grundy"},
    # Hamblen
    320: {"city":"Morristown","county":"Hamblen"},
    # Hamilton → Chattanooga
    330: {"city":"Chattanooga","county":"Hamilton"},
    # Hancock
    340: {"city":"Sneedville","county":"Hancock"},
    # Hardeman
    350: {"city":"Bolivar","county":"Hardeman"},
    # Hardin
    360: {"city":"Savannah","county":"Hardin"},
    # Hawkins
    370: {"city":"Rogersville area","county":"Hawkins"},
    371: {"city":"Rogersville","county":"Hawkins"},
    # Haywood
    380: {"city":"Brownsville","county":"Haywood"},
    # Henderson
    390: {"city":"Lexington area","county":"Henderson"},
    391: {"city":"Lexington","county":"Henderson"},
    # Henry
    400: {"city":"Paris area","county":"Henry"},
    401: {"city":"Paris","county":"Henry"},
    # Hickman
    410: {"city":"Centerville","county":"Hickman"},
    # Houston
    420: {"city":"Erin","county":"Houston"},
    # Humphreys
    430: {"city":"Waverly","county":"Humphreys"},
    # Jackson
    440: {"city":"Gainesboro","county":"Jackson"},
    # Jefferson
    450: {"city":"Dandridge","county":"Jefferson"},
    # Johnson
    460: {"city":"Mountain City","county":"Johnson"},
    # Knox → Knoxville
    470: {"city":"Knoxville","county":"Knox"},
    # Lake
    480: {"city":"Tiptonville","county":"Lake"},
    # Lauderdale
    490: {"city":"Ripley","county":"Lauderdale"},
    # Lawrence
    500: {"city":"Lawrenceburg","county":"Lawrence"},
    # Lewis
    510: {"city":"Hohenwald","county":"Lewis"},
    # Lincoln
    520: {"city":"Fayetteville area","county":"Lincoln"},
    521: {"city":"Fayetteville","county":"Lincoln"},
    # Loudon
    530: {"city":"Loudon","county":"Loudon"},
    531: {"city":"Lenoir City","county":"Loudon"},
    # McMinn
    540: {"city":"Athens area","county":"McMinn"},
    541: {"city":"Athens","county":"McMinn"},
    542: {"city":"Etowah","county":"McMinn"},
    # McNairy
    550: {"city":"Selmer","county":"McNairy"},
    # Macon
    560: {"city":"Lafayette","county":"Macon"},
    # Madison → Jackson
    570: {"city":"Jackson","county":"Madison"},
    # Marion
    580: {"city":"Jasper","county":"Marion"},
    581: {"city":"Richard City","county":"Marion"},
    # Marshall
    590: {"city":"Lewisburg","county":"Marshall"},
    # Maury → Columbia
    600: {"city":"Columbia","county":"Maury"},
    # Meigs
    610: {"city":"Decatur","county":"Meigs"},
    # Monroe
    620: {"city":"Madisonville","county":"Monroe"},
    621: {"city":"Sweetwater","county":"Monroe"},
    # Montgomery → Clarksville
    630: {"city":"Clarksville","county":"Montgomery"},
    # Moore (Jack Daniel's county!)
    640: {"city":"Lynchburg","county":"Moore"},
    # Morgan
    650: {"city":"Wartburg","county":"Morgan"},
    # Obion
    660: {"city":"Union City area","county":"Obion"},
    661: {"city":"Union City","county":"Obion"},
    # Overton
    670: {"city":"Livingston","county":"Overton"},
    # Perry
    680: {"city":"Linden","county":"Perry"},
    # Pickett
    690: {"city":"Byrdstown","county":"Pickett"},
    # Polk
    700: {"city":"Benton","county":"Polk"},
    # Putnam → Cookeville
    710: {"city":"Cookeville","county":"Putnam"},
    # Rhea
    720: {"city":"Dayton area","county":"Rhea"},
    721: {"city":"Dayton","county":"Rhea"},
    # Roane
    730: {"city":"Kingston","county":"Roane"},
    # Robertson
    740: {"city":"Springfield","county":"Robertson"},
    # Rutherford → Murfreesboro
    750: {"city":"Murfreesboro area","county":"Rutherford"},
    751: {"city":"Murfreesboro","county":"Rutherford"},
    # Scott
    760: {"city":"Huntsville","county":"Scott"},
    761: {"city":"Oneida","county":"Scott"},
    # Sequatchie
    770: {"city":"Dunlap","county":"Sequatchie"},
    # Sevier
    780: {"city":"Sevierville","county":"Sevier"},
    # Shelby County cluster
    792: {"city":"Memphis","county":"Shelby"},
    793: {"city":"Arlington","county":"Shelby"},
    794: {"city":"Bartlett","county":"Shelby"},
    795: {"city":"Collierville","county":"Shelby"},
    796: {"city":"Germantown","county":"Shelby"},
    797: {"city":"Lakeland","county":"Shelby"},
    798: {"city":"Millington","county":"Shelby"},
    # Smith
    800: {"city":"Carthage","county":"Smith"},
    # Stewart
    810: {"city":"Dover","county":"Stewart"},
    # Sullivan → Kingsport / Bristol area
    820: {"city":"Kingsport area","county":"Sullivan"},
    821: {"city":"Bristol","county":"Sullivan"},
    822: {"city":"Kingsport","county":"Sullivan"},
    # Sumner → Gallatin / Hendersonville
    830: {"city":"Gallatin","county":"Sumner"},
    # Tipton
    840: {"city":"Covington","county":"Tipton"},
    # Trousdale
    850: {"city":"Hartsville","county":"Trousdale"},
    # Unicoi
    860: {"city":"Erwin","county":"Unicoi"},
    # Union
    870: {"city":"Maynardville","county":"Union"},
    # Van Buren
    880: {"city":"Spencer","county":"Van Buren"},
    # Warren
    890: {"city":"McMinnville","county":"Warren"},
    # Washington → Johnson City
    900: {"city":"Jonesborough area","county":"Washington"},
    901: {"city":"Johnson City","county":"Washington"},
    # Wayne
    910: {"city":"Waynesboro","county":"Wayne"},
    # Weakley
    920: {"city":"Dresden","county":"Weakley"},
    # White
    930: {"city":"Sparta","county":"White"},
    # Williamson → Franklin / Brentwood
    940: {"city":"Franklin","county":"Williamson"},
    # Wilson → Lebanon
    950: {"city":"Lebanon","county":"Wilson"},
}

SCHOOL_YEAR = {
    2015:"2014-15", 2017:"2016-17", 2018:"2017-18", 2019:"2018-19",
    2021:"2020-21", 2022:"2021-22", 2023:"2022-23", 2024:"2023-24", 2025:"2024-25"
}
METRIC_ERA = {
    2015:"Old TCAP (Prof/Adv)",
    2017:"TNReady",2018:"TNReady",2019:"TNReady",2021:"TNReady",
    2022:"Met/Exceeded★",2023:"Met/Exceeded",2024:"Met/Exceeded",2025:"Met/Exceeded"
}
SPECIAL_MIN = 900


def main():
    # ── 1. Load master TCAP data ─────────────────────────────────────────────
    print("Loading TCAP master data...")
    all_df = pd.read_excel(DATA_DIR / "tcap_master.xlsx", sheet_name="ALL_DISTRICTS")
    years  = sorted(all_df["year"].unique())
    print(f"  Years: {years}")
    print(f"  Total rows: {len(all_df)}")

    # ── 2. Load income data ──────────────────────────────────────────────────
    print("Loading income data...")
    inc_df = pd.read_csv(DATA_DIR / "tn_districts_tcap_income_2024.csv")
    inc_map = {}  # system → {income, quartile}
    for _, r in inc_df.iterrows():
        inc_map[int(r["system"])] = {
            "income": int(r["county_income"]) if pd.notna(r["county_income"]) else None,
            "quartile": str(r["income_quartile"]) if pd.notna(r["income_quartile"]) else "Unknown"
        }

    # ── 3. Compute TN state averages per year × subject ──────────────────────
    print("Computing TN state averages...")
    subjs = ["ELA","Math","Science","Social Studies"]
    tn_avgs = {}  # year → subject → avg
    for yr in years:
        yr_df = all_df[all_df["year"] == yr]
        regular = yr_df[(yr_df["system"] < SPECIAL_MIN) & yr_df["system"].notna()]
        tn_avgs[int(yr)] = {}
        for s in subjs:
            v = regular[s].mean()
            tn_avgs[int(yr)][s] = round(float(v), 1) if pd.notna(v) else None

    print("  TN averages by year:")
    for yr in years:
        row = {s: tn_avgs[int(yr)][s] for s in subjs}
        print(f"    {yr}: {row}")

    # ── 4. Build per-district records ────────────────────────────────────────
    print("Building district records...")
    # Get unique districts across all years (use latest year for names)
    dist_names = {}
    for _, r in all_df.sort_values("year", ascending=False).iterrows():
        sid = int(r["system"])
        if sid not in dist_names:
            dist_names[sid] = str(r["system_name"]).strip()

    districts = []
    for sys_id, dist_name in sorted(dist_names.items()):
        if sys_id >= SPECIAL_MIN:
            continue

        city_info = DISTRICT_CITIES.get(sys_id, {"city": dist_name, "county": "Unknown"})
        inc_info  = inc_map.get(sys_id, {"income": None, "quartile": "Unknown"})

        # Per-year TCAP data
        trend = {}
        for yr in years:
            yr_int = int(yr)
            yr_df  = all_df[(all_df["year"] == yr) & (all_df["system"] == sys_id)]
            if yr_df.empty:
                continue
            row = yr_df.iloc[0]
            year_data = {
                "sy":  SCHOOL_YEAR[yr_int],
                "era": METRIC_ERA[yr_int],
            }
            for s in subjs:
                v   = row[s]
                av  = tn_avgs[yr_int][s]
                val = round(float(v), 1) if pd.notna(v) else None
                gap = round(float(v - av), 1) if (pd.notna(v) and av is not None) else None
                year_data[s]         = val
                year_data[f"{s}_gap"] = gap
                year_data[f"{s}_tn"]  = av
            trend[str(yr_int)] = year_data

        if not trend:
            continue

        # Use latest year available for the "summary" row
        latest_yr = max(int(y) for y in trend.keys())
        latest = trend[str(latest_yr)]

        districts.append({
            "id":       sys_id,
            "name":     dist_name,
            "city":     city_info["city"],
            "county":   city_info["county"],
            "income":   inc_info["income"],
            "quartile": inc_info["quartile"],
            "latest_year": SCHOOL_YEAR[latest_yr],
            # Flat latest-year values for quick scatter/table access
            "ela":      latest.get("ELA"),
            "math":     latest.get("Math"),
            "sci":      latest.get("Science"),
            "ss":       latest.get("Social Studies"),
            "ela_gap":  latest.get("ELA_gap"),
            "math_gap": latest.get("Math_gap"),
            "sci_gap":  latest.get("Science_gap"),
            "ss_gap":   latest.get("Social Studies_gap"),
            "ela_tn":   latest.get("ELA_tn"),
            "math_tn":  latest.get("Math_tn"),
            "sci_tn":   latest.get("Science_tn"),
            "ss_tn":    latest.get("Social Studies_tn"),
            # All years trend
            "trend": trend
        })

    # ── 5. Also build TN state averages for all years ────────────────────────
    tn_series = {}
    for yr in years:
        tn_series[str(yr)] = {
            "sy":  SCHOOL_YEAR[int(yr)],
            "era": METRIC_ERA[int(yr)],
            **{s: tn_avgs[int(yr)][s] for s in subjs}
        }

    output = {
        "districts": districts,
        "tn_state": tn_series,
        "years": [int(y) for y in years],
        "school_years": [SCHOOL_YEAR[int(y)] for y in years],
        "subjects": subjs
    }

    with open(OUT, "w") as f:
        json.dump(output, f, separators=(',', ':'))

    print(f"\n✅ Saved {OUT}")
    print(f"   Districts: {len(districts)}")
    print(f"   Years:     {years}")

    # ── 6. Summary: key cities ───────────────────────────────────────────────
    key_cities = ["Memphis","Nashville","Knoxville","Chattanooga","Clarksville",
                  "Murfreesboro","Franklin","Cookeville","Jackson","Kingsport"]
    print("\nKey city districts (latest year ELA / Math / Gap):")
    print(f"  {'District':<40} {'City':<18} {'Quartile':<18} {'ELA':>6} {'Math':>6} {'ELA Gap':>8} {'Income':>10}")
    print("  " + "─"*108)
    for d in sorted(districts, key=lambda x: x["city"]):
        if d["city"] in key_cities or d["name"] in key_cities:
            print(f"  {d['name']:<40} {d['city']:<18} {d['quartile']:<18} "
                  f"{str(d['ela'] or 'N/A'):>6} {str(d['math'] or 'N/A'):>6} "
                  f"{str(d['ela_gap'] or 'N/A'):>8} "
                  f"${d['income']:>8,}" if d['income'] else f"{str(d['ela'] or 'N/A'):>6}")

    print("\nIncome quartile distribution:")
    from collections import Counter
    qcounts = Counter(d["quartile"] for d in districts)
    for q, cnt in sorted(qcounts.items()):
        print(f"  {q}: {cnt} districts")


if __name__ == "__main__":
    main()
