@echo off
if "%~2"=="" (
  echo Usage: run.bat INPUT.txt OUTPUT.docx
  exit /b 2
)
python "%~dp0scripts\format_hadith.py" "%~1" "%~2"
