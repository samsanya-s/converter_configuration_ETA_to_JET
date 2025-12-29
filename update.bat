@echo off
setlocal

REM === Путь к текущей папке программы ===
set "APP_DIR=%~dp0"

REM === Путь к скачанному zip ===
set "ZIP_FILE=%APP_DIR%update.zip"

REM === Временная папка для распаковки ===
set "TMP_DIR=%APP_DIR%tmp_update"

REM Проверка на существование ZIP файла
if not exist "%ZIP_FILE%" (
    echo Ошибка: файл обновления "%ZIP_FILE%" не найден.
    exit /b
)

REM Удаляем старую временную папку
if exist "%TMP_DIR%" rmdir /s /q "%TMP_DIR%"

REM Распаковываем архив (нужен PowerShell)
powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%TMP_DIR%' -Force"

REM Если в архиве одна папка — переходим внутрь
for /d %%D in ("%TMP_DIR%\*") do (
    set "TMP_DIR=%%~fD"
    goto after_dir_detect
)

REM Если папка не найдена
if not exist "%TMP_DIR%" (
    echo Ошибка: не удалось распаковать архив или не найдена нужная папка.
    exit /b
)

:after_dir_detect

REM Ждём, пока exe освободится
if not exist "%APP_DIR%mytool.exe" (
    echo Ошибка: файл mytool.exe не найден в текущей папке.
    exit /b
)

:wait_for_close
tasklist /FI "IMAGENAME eq mytool.exe" | find /I "mytool.exe" >nul
if %ERRORLEVEL%==0 (
    timeout /t 1 >nul
    goto wait_for_close
)

REM Копируем новый exe и папку _internal
if exist "%TMP_DIR%\*.exe" (
    xcopy "%TMP_DIR%\*.exe" "%APP_DIR%" /Y
) else (
    echo Ошибка: exe файл не найден в архиве.
    exit /b
)

if exist "%TMP_DIR%\_internal" (
    xcopy "%TMP_DIR%\_internal" "%APP_DIR%\_internal" /E /I /Y
) else (
    echo Ошибка: папка _internal не найдена в архиве.
    exit /b
)

REM Удаляем временные файлы
rmdir /s /q "%TMP_DIR%"
del "%ZIP_FILE%"

REM Запускаем новую версию
start "" "%APP_DIR%\converter.exe"

endlocal
