#######################################
#
# Authors: Matej Oblak, Iztok Jeras
# (C) Red Pitaya 2013-2015
#
# Red Pitaya FPGA/SoC Makefile 
#

# build results
FPGA_BIN=out/red_pitaya.bin

#logfile for stdout and stderr
LOG=>> fpga.log 2>&1

# Vivado from Xilinx provides IP handling, FPGA compilation
# hsi (hardware software interface) provides software integration
# both tools are run in batch mode with an option to avoid log/journal files
VIVADO = vivado -nolog -nojournal -mode batch

all: clean $(FPGA_BIN) postclean

clean:
	rm -rf out .Xil .srcs sdk

$(FPGA_BIN):
	$(VIVADO) -source red_pitaya_vivado.tcl $(LOG)

postclean:
	mv *.xml out/
	mv *.prm out/
	mv *.html out/
	mv *.log out/
