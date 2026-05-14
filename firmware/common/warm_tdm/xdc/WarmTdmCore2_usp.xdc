## fabRefClk: IBUFDS_GTE4 ODIV2 (÷2) → BUFG_GT
create_generated_clock -name fabRefClk0 -source [get_ports {gtRefClk0P}] -divide_by 2 \
    [get_pins -hier -filter {NAME =~ *U_ClockDist_1*U_BUFG_GT_0/O}]
create_generated_clock -name fabRefClk1 -source [get_ports {gtRefClk1P}] -divide_by 2 \
    [get_pins -hier -filter {NAME =~ *U_ClockDist_1*U_BUFG_GT_1/O}]

## UltraScale+ timing clocks
create_generated_clock -name timingTxBitClk  [get_pins -hier -filter {NAME =~ *U_TimingTx*PhyUsp*U_Pll/CLKOUT0}]
create_generated_clock -name timingTxWordClk [get_pins -hier -filter {NAME =~ *U_TimingTx*PhyUsp*U_BUFGCE_DIV*/O}]
create_generated_clock -name timingRxBitClk  [get_pins -hier -filter {NAME =~ *U_TimingRx*PhyUsp*U_Mmcm/CLKOUT0}]
create_generated_clock -name timingRxWordClk [get_pins -hier -filter {NAME =~ *U_TimingRx*PhyUsp*U_BUFGCE_DIV*/O}]

## ADC clocks (BUFGCE_DIV output in Ad9681Readout UltraScale)
create_generated_clock -name adcBitClkDiv4_a \
    -source [get_ports {adcDClkP[0]}] \
    -divide_by 4 \
    [get_pins {U_DataPath_1/U_Ad9681Readout_1/GEN_PARTS[0].U_AdcBitClkDiv4/O}]

create_generated_clock -name adcBitClkDiv4_b \
    -source [get_ports {adcDClkP[1]}] \
    -divide_by 4 \
    [get_pins {U_DataPath_1/U_Ad9681Readout_1/GEN_PARTS[1].U_AdcBitClkDiv4/O}]

##create_generated_clock -name adcBitClkDiv4_a [get_pins -hier -filter {NAME =~ U_DataPath_1/U_Ad9681Readout_1/GEN_PARTS[0].U_AdcBitClkDiv4/O}]
##create_generated_clock -name adcBitClkDiv4_1 [get_pins -hier -filter {NAME =~ *Ad9681Readout*GEN_PARTS[1]*AdcBitClkDiv4/O}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingTxWordClk] \
    -group [get_clocks timingRxWordClk]
