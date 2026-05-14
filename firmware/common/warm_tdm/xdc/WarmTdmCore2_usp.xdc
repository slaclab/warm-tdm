## fabRefClk: auto-derived by Vivado from IBUFDS_GTE4 ODIV2 → BUFG_GT
## No explicit create_generated_clock needed; use -include_generated_clocks gtRefClk0/1 in groups

## UltraScale+ timing clocks
create_generated_clock -name timingTxBitClk  [get_pins -hier -filter {NAME =~ *U_TimingTx*PhyUsp*/CLKOUT0}]
create_generated_clock -name timingTxWordClk [get_pins -hier -filter {NAME =~ *U_TimingTx*BUFGCE_DIV*/O}]
create_generated_clock -name timingRxWordClk [get_pins -hier -filter {NAME =~ *U_TimingRx*BUFGCE_DIV*/O}]

## ADC clocks (BUFGCE_DIV output in Ad9681Readout UltraScale)
create_generated_clock -name adcBitClkDiv4_0 [get_pins -hier -filter {NAME =~ *Ad9681Readout*GEN_PARTS[0]*AdcBitClkDiv4/O}]
create_generated_clock -name adcBitClkDiv4_1 [get_pins -hier -filter {NAME =~ *Ad9681Readout*GEN_PARTS[1]*AdcBitClkDiv4/O}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingTxWordClk] \
    -group [get_clocks timingRxWordClk]
