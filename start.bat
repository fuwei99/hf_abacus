@echo off
chcp 65001 > nul

echo checking python version...
python --version > nul 2>&1
if errorlevel 1 (
    echo No python found. Please install python and add it to the PATH.
    echo After installation, please restart the command prompt.
    pause
    exit /b
)

echo checking pip version...
pip --version > nul 2>&1
if errorlevel 1 (
    echo No pip found. Please install pip.
    echo After installation, please restart the command prompt.
    pause
    exit /b
)

echo checking venv module...
python -m venv venv
if errorlevel 1 (
    echo No venv module found. Please upgrade your python to 3.3+.
    pause
    exit /b
)

echo activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
 echo Failed to activate virtual environment, trying to install dependencies in global environment...
 goto install_dependencies
)

echo virtual environment activated.

:install_dependencies
echo installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies. Please check your network connection and try again.
    pause
    exit /b
)

echo dependencies installed.

:menu
cls
echo ================================
echo        Abacus Chat Proxy
echo ================================
echo [0] 配置代理 (运行config_editor)
echo [1] 启动代理 (运行app.py)
echo ================================
set /p choice="请选择操作 (0/1): "

if "%choice%"=="0" (
    echo 启动配置程序...
    python config_editor.py
    if errorlevel 1 (
        echo 配置程序运行失败，请检查错误信息。
        pause
        exit /b
    )
    echo 配置完成，是否要立即启动代理？(Y/N)
    set /p start_proxy="输入选择: "
    if /i "%start_proxy%"=="Y" goto start_proxy
    goto menu
)

if "%choice%"=="1" (
    :start_proxy
    echo 启动代理服务器...
    python app.py
    if errorlevel 1 (
        echo 代理服务器启动失败，请检查错误信息。
        pause
        exit /b
    )
    echo 代理服务器正在运行: http://127.0.0.1:9876/
    pause
    exit /b
)

echo 无效的选择，请重试！
timeout /t 2 > nul
goto menu