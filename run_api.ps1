Set-Location $PSScriptRoot
pip install -r requirements.txt
python -m uvicorn app.api.main:app --app-dir $PSScriptRoot --reload --reload-dir $PSScriptRoot --host 127.0.0.1 --port 8000
