.. _building_fpga:
Building the FPGA firmware
****************************


Compiling the FPGA code
=========================

- Install Vivado 2015.4 from `the xilinx website <https://www.xilinx.com/support/download/index.html/content/xilinx/en/downloadNav/vivado-design-tools/archive.html>`_, or directly use the `windows web-installer <https://www.xilinx.com/member/forms/download/xef.html?filename=Xilinx_Vivado_SDK_2015.4_1118_2_Win64.exe&akdm=0>`_ or the `linux web installer <https://www.xilinx.com/member/forms/download/xef.html?filename=Xilinx_Vivado_SDK_2015.4_1118_2_Lin64.bin&akdm=1>`_.
- Get a license as described at ":ref:`fpga_license`".
- Navigate into :code:`your_pyrpl_root_directory/pyrpl/fpga` and execute :code:`make` (in linux) or :code:`make.bat` (windows).
- The compilation of the FPGA code should take between 10 and 30 minutes, depending on your computer, and finish successfully.


.. _fpga_license:

How to get the right license for Vivado 2015.4
=================================================

- After having created an account on `xilinx.com <www.xilinx.com>`_, go to `<https://www.xilinx.com/member/forms/license-form.html>`_.
- Fill out your name and address and click "next".
- select Certificate Based Licenses/Vivado Design Suite: HL WebPACK 2015 and Earlier License
- click Generate Node-locked license
- click Next
- get congratulated for having the new license file 'xilinx.lic' mailed to you. Download the license file and import it with Xilinx license manager.
- for later download: the license appears under the tab 'Managed licenses' with asterisks (*) in each field except for 'license type'='Node', 'created by'='your name', and the creation date.

The license problem is also discussed in issue `#272 <https://github.com/lneuhaus/pyrpl/issues/272>`_ with screenshots of successful installations.
