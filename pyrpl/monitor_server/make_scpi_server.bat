@echo off
setlocal

REM Builds the read-only SCPI server for the Red Pitaya (ARM, hard float).
REM The binary is linked statically so it does not depend on the glibc of the
REM Red Pitaya OS version (works on OS 1.x, 2.x and 3.x).

set "VITIS_VER=2024.2"
set "CC=c:\Xilinx\Vitis\%VITIS_VER%\gnu\aarch32\nt\gcc-arm-linux-gnueabi\bin\arm-linux-gnueabihf-gcc.exe"
set "SRC_DIR=%~dp0"

if not exist "%CC%" (
    echo ARM cross compiler not found at %CC%
    exit /b 1
)

"%CC%" -std=gnu99 -O2 -Wall -Wextra -static -o "%SRC_DIR%pyrpl_scpi_server" "%SRC_DIR%pyrpl_scpi_server.c" -lm
if errorlevel 1 (
    echo Compilation of pyrpl_scpi_server failed.
    exit /b 1
)
echo Compilation finished: %SRC_DIR%pyrpl_scpi_server
endlocal
