@RD /S /Q out
@RD /S /Q .Xil
@RD /S /Q .srcs
@RD /S /Q sdk

c:/Xilinx/Vivado/2015.4/bin/vivado.bat -nolog -nojournal -mode tcl -source red_pitaya_vivado.tcl

COPY ".\out\red_pitaya.bin" ".\red_pitaya.bin"