@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Use the same short-path workaround as make_bin.bat. Vivado 2024.2 can
REM otherwise bake an invalid working directory into the XSim snapshot.
if not defined PYRPL_FPGA_SIM_SHORT_PATH (
    set "FPGA_PHYSICAL_DIR=%~dp0"
    set "FPGA_PHYSICAL_DIR=!FPGA_PHYSICAL_DIR:~0,-1!"
    for %%I in ("!FPGA_PHYSICAL_DIR!\..\..") do set "FPGA_REPOSITORY_DIR=%%~fI"
    set "FPGA_SIM_DRIVE="
    for %%D in (R S T U V W X Y Z) do (
        if not defined FPGA_SIM_DRIVE (
            subst %%D: "!FPGA_REPOSITORY_DIR!" >nul 2>&1
            if !ERRORLEVEL! equ 0 set "FPGA_SIM_DRIVE=%%D:"
        )
    )
    if not defined FPGA_SIM_DRIVE exit /b 3
    set "PYRPL_FPGA_SIM_SHORT_PATH=1"
    call "!FPGA_SIM_DRIVE!\pyrpl\fpga\run_arithmetic_tb.bat"
    set "FPGA_SIM_EXIT=!ERRORLEVEL!"
    subst !FPGA_SIM_DRIVE! /D >nul 2>&1
    exit /b !FPGA_SIM_EXIT!
)

set "VIVADO_VER=2024.2"
set "FPGA_DIR=%~dp0"
set "VIVADO_BIN=C:\Xilinx\Vivado\%VIVADO_VER%\bin"
set "SIM_DIR=%FPGA_DIR%build\arithmetic_sim"
set "TCL_BATCH=%FPGA_DIR:\=/%sim/run_all.tcl"

if not exist "%VIVADO_BIN%\xvlog.bat" (
    echo Vivado %VIVADO_VER% was not found under C:\Xilinx\Vivado.
    exit /b 2
)

if not exist "%SIM_DIR%" mkdir "%SIM_DIR%"
pushd "%SIM_DIR%"

call "%VIVADO_BIN%\xvlog.bat" --sv "%FPGA_DIR%rtl\red_pitaya_arithmetic_block.v" "%FPGA_DIR%sim\red_pitaya_arithmetic_block_tb.sv"
if errorlevel 1 goto :failed

call "%VIVADO_BIN%\xelab.bat" red_pitaya_arithmetic_block_tb -s arithmetic_block_tb
if errorlevel 1 goto :failed

call "%VIVADO_BIN%\xsim.bat" arithmetic_block_tb -tclbatch "%TCL_BATCH%"
if errorlevel 1 goto :failed
findstr /C:"ARITHMETIC_TEST_PASS" xsim.log >nul
if errorlevel 1 (
    echo XSim did not report ARITHMETIC_TEST_PASS. See %SIM_DIR%\xsim.log
    goto :failed
)

popd
echo Arithmetic RTL simulation passed.
exit /b 0

:failed
set "SIM_EXIT=%ERRORLEVEL%"
popd
echo Arithmetic RTL simulation failed with exit code %SIM_EXIT%.
exit /b %SIM_EXIT%
