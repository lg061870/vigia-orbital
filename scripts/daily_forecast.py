"""Daily: issue today's forecast for all cantons with the newest NASA data and save it for the website.

Runs the same code as the live API (api/main.py -> vigia/live.py + vigia/model.py) and writes
site/data/latest.json, the forecast the website shows when the live API is asleep or unreachable.
Used by .github/workflows/pages.yml every morning. Needs env FIRMS_MAP_KEY for fresh fire data.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.main import forecast_all  # noqa: E402

j = forecast_all(None)
out = {"eve": j["eve"], "inputs": j["inputs"], "live": j["live"],
       "cantons": {c["canton_id"]: {"name": c["canton"], "eve": c["eve"], "days": c["days"],
                                    "conditions": c["conditions"]} for c in j["cantons"]}}
(ROOT / "site" / "data" / "latest.json").write_text(json.dumps(out))
meta_p = ROOT / "site" / "data" / "meta.json"
meta = json.loads(meta_p.read_text())
meta["latest_eve"] = j["eve"]
meta_p.write_text(json.dumps(meta, indent=1))
print("issued", j["eve"], j["inputs"], j["live"])
