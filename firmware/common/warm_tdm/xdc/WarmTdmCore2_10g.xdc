## 10G Ethernet clock constraints
create_generated_clock -name ethClk156 [get_pins -hier -filter {NAME =~ *U_EthCore_1*TEN_GIG*U_MMCM*U_Mmcm/CLKOUT0}]

## 10G GT recovered clocks
create_clock -name ethRxOutClk   -period 3.103 [get_pins -hier -filter {NAME =~ *U_EthCore_1/*TEN_GIG*/*RXOUTCLK}]
create_clock -name ethTxOutClk   -period 3.103 [get_pins -hier -filter {NAME =~ *U_EthCore_1/*TEN_GIG*/*TXOUTCLK}]
create_clock -name ethTxPcsClk   -period 6.206 [get_pins -hier -filter {NAME =~ *U_EthCore_1/*TEN_GIG*/*txoutclkpcs*}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks ethClk156]

set_clock_groups -asynchronous \
    -group [get_clocks ethClk156] \
    -group [get_clocks ethRxOutClk] \
    -group [get_clocks ethTxOutClk]

set_clock_groups -asynchronous \
    -group [get_clocks ethClk156] \
    -group [get_clocks ethTxPcsClk] \
    -group [get_clocks ethTxOutClk]
