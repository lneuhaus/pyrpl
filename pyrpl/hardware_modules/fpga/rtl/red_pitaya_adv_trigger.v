//////////////////////////////////////////////////////////////////////////////////
// Company: LKB
// Engineer: Leonhard Neuhaus
// 
// Create Date: 12.08.2015 17:40:42
// Design Name: 
// Module Name: i_adv_trigger
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////
/*
###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
############################################################################### 
*/

// Usage of the module:
// feed the on_clockcycles into hysteresis_i
// feed the raw trigger input into trig_i
// connect trig_o to the device to be triggered
// optionally set invert flag and the flag rearm_i if you want the trigger to rearm by itself
// set reset flag to true to reset the trigger. set it then to false to arm it.

// once trig_i goes high, trig_o will remain high for hysteresis_i cycles and then go low
// if the rearl_i flag is set, trigger will automatically rearm
// otherwise, reset must be manually set to true and then to false to rearm the trigger 



module red_pitaya_adv_trigger #(
    parameter COUNTERSZ = 64
)
(
    input           dac_clk_i,
    input           reset_i,  
    input           trig_i,
    output          trig_o,
    input           rearm_i,
    input           invert_i,
    input [COUNTERSZ-1:0]  hysteresis_i //stay on for hysteresis_i cycles
    );

reg [COUNTERSZ-1:0] counter;
reg triggered;
reg armed;

always @(posedge dac_clk_i) begin
    //reset
    if (reset_i == 1'b1) begin
        triggered <= 1'b0;
        armed <= 1'b1;
        counter <= hysteresis_i;
        end
    //system is armed, and therefore copies the incident trigger 
    else if (armed&(!triggered)) begin
        triggered <= trig_i;
        counter <= hysteresis_i;
        end
    //system has been triggered in a previous cycle
    else if (triggered) begin
        if ( counter != {COUNTERSZ{1'b0}} ) //normal countdown in progress, nothing to change
            counter <= counter - {{COUNTERSZ-1{1'b0}},1'b1};
        else begin               //countdown arrived at zero
            if (rearm_i) begin    //automatic rearming is configured
                triggered <= trig_i; // prepare for the next trigger. This can already happen next cycle, i.e. without interruption
                armed <= 1'b1;       //
                counter <= hysteresis_i; //reset the counter nevertheless 
                end
            else begin  //no auto rearm. Stall the trigger until it is reset
                triggered <= 1'b0; //un-trigger
                armed <= 1'b0;     //un-arm
                //counter <= hysteresis_i
                end
        end
    end
end

assign trig_o = reset_i ? trig_i : (invert_i ^ triggered);

endmodule
