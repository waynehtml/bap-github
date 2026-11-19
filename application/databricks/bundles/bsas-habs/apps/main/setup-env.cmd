@echo off
rem Keep package-source settings local to this script.
setlocal
set "ENV_NAME=databriks-app-3.11"
set "ENV_LIST=%TEMP%\dataforge-envs-%RANDOM%-%RANDOM%.txt"
rem Resolve dependency files beside this script, regardless of the caller's folder.
pushd "%~dp0"
if errorlevel 1 exit /b 1

where conda >nul 2>&1
if errorlevel 1 (
    echo Conda is not available. Open a Conda-enabled terminal.
    goto failed
)

set "PIP_INDEX_URL=https://fcp4lnexuap01.bocad.bank-banque-canada.ca/nexus/repository/pypi-all/simple"
rem Override configured extra indexes with the same corporate source.
set "PIP_EXTRA_INDEX_URL=%PIP_INDEX_URL%"
rem Match the cluster setup: trust only the corporate Nexus host for pip.
set "PIP_TRUSTED_HOST=fcp4lnexuap01.bocad.bank-banque-canada.ca"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

rem Check the inventory first so a listing failure cannot trigger environment creation.
call conda env list >"%ENV_LIST%"
if errorlevel 1 goto failed
set "ENV_EXISTS="
for /f "usebackq tokens=1" %%E in ("%ENV_LIST%") do if "%%E"=="%ENV_NAME%" set "ENV_EXISTS=1"
rem Updating on every run applies manifest changes without tracking timestamps.
rem CALL also returns here when Conda is exposed through a Windows batch wrapper.
if not defined ENV_EXISTS (
    call conda env create --name "%ENV_NAME%" --file environment.yml
) else (
    call conda env update --name "%ENV_NAME%" --file environment.yml
)
if errorlevel 1 goto failed

rem Use the environment's Python without activating it in the caller's shell.
call conda run -n "%ENV_NAME%" python -m pip install -r requirements.txt
if errorlevel 1 goto failed
rem Catch incompatible installed dependencies before reporting success.
call conda run -n "%ENV_NAME%" python -m pip check
if errorlevel 1 goto failed

del "%ENV_LIST%" >nul 2>&1
popd
echo Setup complete. Run: conda activate %ENV_NAME%
exit /b 0

:failed
rem All failures after PUSHD restore the caller's folder and return a nonzero code.
echo Environment setup failed. Review the error above.
if exist "%ENV_LIST%" del "%ENV_LIST%" >nul 2>&1
popd
exit /b 1
