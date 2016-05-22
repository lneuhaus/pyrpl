#######################################
#
# Authors: Matej Oblak, Iztok Jeras
# (C) Red Pitaya 2013-2015
#
# Red Pitaya FPGA/SoC Makefile 
#

# build results
FPGA_BIN=out/red_pitaya.bin


# Vivado from Xilinx provides IP handling, FPGA compilation
# hsi (hardware software interface) provides software integration
# both tools are run in batch mode with an option to avoid log/journal files
VIVADO = vivado -nolog -nojournal -mode batch

all: clean $(FPGA_BIN)

clean:
	rm -rf out .Xil .srcs sdk

$(FPGA_BIN):
	$(VIVADO) -source red_pitaya_vivado.tcl
	# cp $(FPGA_BIN) ./red_pitaya.bin
