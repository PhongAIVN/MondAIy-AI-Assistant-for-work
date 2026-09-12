@echo off
setlocal

title Redeploy Mondaiy Chrome Extension

echo ========================================================
echo       MONDAIY CHROME EXTENSION - PRODUCTION RELEASE
echo ========================================================
echo.

:: 1. Xac dinh thu muc goc project va thu muc extension
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT_DIR=%%~fI"
set "EXT_DIR=%ROOT_DIR%\client\extension"

echo [INFO] Project root: %ROOT_DIR%
echo [INFO] Extension dir: %EXT_DIR%
echo.

if not exist "%EXT_DIR%" (
    echo [ERROR] Khong tim thay thu muc extension tai: "%EXT_DIR%"
    goto :FAIL
)

:: 2. Kiem tra Node.js
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js chua duoc cai dat hoac chua nam trong System PATH
    goto :FAIL
)

:: 3. Kiem tra Package Manager - uu tien pnpm, fallback npm
set "PKG_MGR=npm"
where pnpm >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PKG_MGR=pnpm"
)
echo [INFO] Su dung package manager: %PKG_MGR%

:: 4. Chuyen vao thu muc extension
cd /d "%EXT_DIR%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Khong the cd vao thu muc: "%EXT_DIR%"
    goto :FAIL
)

:: 5. Kiem tra dependencies
if not exist "node_modules" (
    echo [INFO] Thu muc node_modules chua co, dang cai dat dependencies...
    call %PKG_MGR% install
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Cai dat dependencies that bai
        goto :FAIL
    )
)

:: 6. Kiem tra file cau hinh moi truong production
if not exist ".env.production" (
    if not exist ".env" (
        echo [ERROR] Khong tim thay file .env.production hoac .env trong client/extension
        goto :FAIL
    )
)

echo.
echo ========================================================
echo [1/5] Kiem tra TypeCheck - TypeScript
echo ========================================================
call %PKG_MGR% run compile
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] TypeScript compilation that bai. Vui long sua cac loi type truoc khi release.
    goto :FAIL
)
echo [PASS] Typecheck thanh cong.

echo.
echo ========================================================
echo [2/5] Chay bo test Unit - Vitest
echo ========================================================
call %PKG_MGR% test
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Unit test that bai. Vui long kiem tra lai code.
    goto :FAIL
)
echo [PASS] Tat ca unit tests da PASS.

echo.
echo ========================================================
echo [3/5] Build Extension Production - WXT
echo ========================================================
call %PKG_MGR% run build
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Build production that bai.
    goto :FAIL
)
echo [PASS] Build extension production hoan tat.

echo.
echo ========================================================
echo [4/5] Chay Artifact Release Gate
echo ========================================================
node tests\verify-build-artifact.mjs .output\chrome-mv3 production
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Artifact khong vuot qua Release Gate
    goto :FAIL
)
echo [PASS] Artifact Release Gate hop le.

echo.
echo ========================================================
echo [5/5] Dong goi file ZIP cho Chrome Web Store
echo ========================================================
call %PKG_MGR% run zip
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Dong goi ZIP that bai.
    goto :FAIL
)

:: 7. In thong tin ban giao Chrome Web Store
node tests\print-release-summary.mjs

pause
exit /b 0

:FAIL
echo.
echo ========================================================
echo          BUILD/RELEASE FAILED
echo ========================================================
echo Vui long kiem tra log loi o tren.
echo.
pause
exit /b 1
