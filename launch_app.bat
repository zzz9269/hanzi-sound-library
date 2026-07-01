@echo off
title Hanzi Sound Library
cd /d "%~dp0"
echo Starting Hanzi Sound Library...
echo A browser tab will open at http://localhost:8501
echo Close this window to stop the app.
echo.
"C:\Users\zacha\miniconda3\envs\env1\python.exe" -m streamlit run app.py
pause
