Set-Location $PSScriptRoot
pip install -r requirements.txt
uvicorn app.api.main:app --reload
