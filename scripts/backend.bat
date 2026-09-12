@echo off
REM Chạy backend FastAPI (uvicorn --reload) dùng venv chung ở
REM C:\Users\THIS PC\Desktop\envs\python_all. Bấm đúp file này hoặc chạy
REM scripts\backend.bat từ terminal, mở tại thư mục gốc project.

set "VENV_DIR=C:\Users\THIS PC\Desktop\IT\AI THUC CHIEN\P-004\.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo [backend.bat] Khong thay venv tai "%VENV_DIR%".
    echo [backend.bat] Kiem tra lai duong dan hoac tao venv truoc.
    exit /b 1
)

cd /d "%~dp0.."

echo [backend.bat] Dung venv: %VENV_DIR%
echo [backend.bat] Chay: uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

"%PYTHON_EXE%" -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
