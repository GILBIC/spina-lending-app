from pathlib import Path
import json

APPLY = Path("tools/apply_clients_feature_wave_19.py")
MANIFEST = Path("tools/fixtures/clients_feature_wave_19_manifest.json")

text = APPLY.read_text(encoding="utf-8")
old = '    "_spina_v23_refresh_clients",\n'
count = text.count(old)
if count != 1:
    raise RuntimeError(f"Expected one obsolete protected entry, found {count}")
APPLY.write_text(text.replace(old, "", 1), encoding="utf-8")

data = json.loads(MANIFEST.read_text(encoding="utf-8"))
items = data.get("protected_functions_kept_in_desktop", [])
data["protected_functions_kept_in_desktop"] = [x for x in items if x != "_spina_v23_refresh_clients"]
MANIFEST.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print("Removed obsolete refresh wrapper guard")
