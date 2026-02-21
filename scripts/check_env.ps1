$env:OPENROUTER_API_KEY = "test" | Out-Null
python - <<'PY'
import os
print(os.getenv("OPENROUTER_API_KEY"))
PY