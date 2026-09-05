Set-Location $PSScriptRoot
$env:PYTHONPATH = $PSScriptRoot
streamlit run app\dashboard.py
