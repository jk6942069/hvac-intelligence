@echo off
cd /d C:\Users\joonk\hvac-intelligence\backend
py -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
