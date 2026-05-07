$env:PYTHONPATH = 'C:\Users\Aras\Arasense\src'
Set-Location 'C:\Users\Aras\Arasense'
python -m uvicorn api.main:app --host 127.0.0.1 --port 8080
