.PHONY: all
SHELL:=/bin/bash
VIVADO_PATH:=/opt/Xilinx/Vivado/2015.4/settings64.sh
SOURCE_FILE=monitor_server.c
	
all: clean monitor_server monitor_server_0.95 pyrpl_scpi_server

monitor_server:  # for version 0.92
	source $(VIVADO_PATH) && arm-xilinx-linux-gnueabi-gcc -o monitor_server $(SOURCE_FILE)

monitor_server_0.95:
	source $(VIVADO_PATH) && arm-linux-gnueabihf-gcc -o monitor_server_0.95 $(SOURCE_FILE)

# read-only SCPI server, linked statically so that it runs on every Red Pitaya OS
# (on Windows use make_scpi_server.bat)
pyrpl_scpi_server: pyrpl_scpi_server.c
	source $(VIVADO_PATH) && arm-linux-gnueabihf-gcc -std=gnu99 -O2 -Wall -Wextra -static -o pyrpl_scpi_server pyrpl_scpi_server.c -lm

# native build, used by the unit tests through the -m simulation option
pyrpl_scpi_server_host: pyrpl_scpi_server.c
	gcc -std=gnu99 -O2 -Wall -Wextra -o pyrpl_scpi_server_host pyrpl_scpi_server.c -lm

clean: 
	rm -f monitor_server_* pyrpl_scpi_server_host
