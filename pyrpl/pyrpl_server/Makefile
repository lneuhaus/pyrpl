.PHONY: all
SHELL:=/bin/bash
VIVADO_PATH:=/opt/Xilinx/Vivado/2015.4/settings64.sh
SOURCE_FILE=pyrpl_server.c
	
all: clean pyrpl_server_0.92 pyrpl_server_0.95

pyrpl_server_0.92:
	source $(VIVADO_PATH) && arm-xilinx-linux-gnueabi-gcc -o pyrpl_server_0.92 $(SOURCE_FILE)

pyrpl_server_0.95:
	source $(VIVADO_PATH) && arm-linux-gnueabihf-gcc -o pyrpl_server_0.95 $(SOURCE_FILE)

clean: 
	rm -f pyrpl_server_*
