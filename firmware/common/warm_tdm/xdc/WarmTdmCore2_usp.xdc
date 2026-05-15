## Primary clocks (from ports)
create_clock -name timingRxClk -period 8.000 [get_ports {timingRxClkP}]
create_clock -name gtRefClk0 -period 4.000 [get_ports {gtRefClk0P}]
create_clock -name gtRefClk1 -period 6.400 [get_ports {gtRefClk1P}]

## fabRefClk: IBUFDS_GTE4 ODIV2 (÷2) → BUFG_GT
create_generated_clock -name fabRefClk0 -source [get_ports {gtRefClk0P}] -divide_by 2 \
    [get_pins -hier -filter {NAME =~ *U_ClockDist_1*U_BUFG_GT_0/O}]
create_generated_clock -name fabRefClk1 -source [get_ports {gtRefClk1P}] -divide_by 2 \
    [get_pins -hier -filter {NAME =~ *U_ClockDist_1*U_BUFG_GT_1/O}]

## UltraScale+ timing clocks
create_generated_clock -name timingTxBitClk  [get_pins -hier -filter {NAME =~ *U_TimingTx*PhyUsp*U_Pll/CLKOUT0}]
create_generated_clock -name timingTxWordClk [get_pins -hier -filter {NAME =~ *U_TimingTx*PhyUsp*U_Pll/CLKOUT1}]
create_generated_clock -name timingRxBitClk  [get_pins -hier -filter {NAME =~ *U_TimingRx*PhyUsp*U_Mmcm/CLKOUT0}]
create_generated_clock -name timingRxWordClk [get_pins -hier -filter {NAME =~ *U_TimingRx*PhyUsp*U_Mmcm/CLKOUT1}]
create_generated_clock -name timingRxClk125  [get_pins -hier -filter {NAME =~ *U_TimingRx*PhyUsp*U_Mmcm/CLKOUT2}]
## Async clock groups that only reference clocks defined in this file
set_clock_groups -asynchronous \
    -group [get_clocks fabRefClk0] \
    -group [get_clocks timingTxWordClk]

set_clock_groups -asynchronous \
    -group [get_clocks timingRxWordClk] \
    -group [get_clocks timingRxClk125]
