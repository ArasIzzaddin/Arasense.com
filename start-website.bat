@echo off
set PYTHONPATH=C:\Users\Aras\Arasense\src
cd /d C:\Users\Aras\Arasense
start "" http://127.0.0.1:8080/
powershell -NoExit -ExecutionPolicy Bypass -File C:\Users\Aras\Arasense\start-website.ps1
