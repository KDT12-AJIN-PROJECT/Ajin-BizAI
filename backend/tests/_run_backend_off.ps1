$env:FORM_NORMALIZE_TABLE = "false"
$env:FORM_AUTO_PROMOTE_TABLE = "false"
Set-Location "c:\Users\KDS10\work\AJIN\AJIN_PROJECT\backend"
& "C:\Users\KDS10\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn main:app --port 8000
