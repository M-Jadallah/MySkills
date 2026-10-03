@echo off
if "%~2"=="" (
  echo Usage: run.bat INPUT.txt^|INPUT_DIR OUTPUT.docx [extra options]
  exit /b 2
)
if exist "%~1\*" (
  python "%~dp0scripts\format_hadith_batch.py" "%~1" "%~2" %3 %4 %5 %6 %7 %8 %9
) else (
  python "%~dp0scripts\format_hadith.py" "%~1" "%~2" %3 %4 %5 %6 %7 %8 %9
)
