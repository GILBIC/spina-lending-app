# Reading the module-separation JSON

Key sections:

- `summary`: counts by risk, dependency signal, and suggested module
- `recommended_first_wave_review`: small low-risk helpers to inspect first
- `large_definitions`: definitions at least 200 lines long
- `global_dependency_hotspots`: globals referenced by many top-level definitions
- `definitions`: full top-level map
- `recommended_phases`: safe order for later extraction work

A suggested module is not an approval. Confirm callers, globals, and behavior before moving code.
