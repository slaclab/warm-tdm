## 10G Ethernet clock constraints
create_generated_clock -name ethClk156 [get_pins -hier -filter {NAME =~ *U_EthCore_1/*U_Phy/TEN_GIG*U_MMCM/*/CLKOUT0}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks ethClk156]

## 10G GT recovered clocks async to ethClk156 and axilClk
set_clock_groups -asynchronous \
    -group [get_clocks ethClk156] \
    -group [get_clocks -quiet -of_objects [get_pins -quiet -hier -filter {NAME =~ *U_EthCore_1/*TEN_GIG*/*RXOUTCLK*}]] \
    -group [get_clocks -quiet -of_objects [get_pins -quiet -hier -filter {NAME =~ *U_EthCore_1/*TEN_GIG*/*TXOUTCLK*}]]

## 10G PCS clocks async to all 10G clocks
set_clock_groups -asynchronous \
    -group [get_clocks ethClk156] \
    -group [get_clocks -quiet -of_objects [get_pins -quiet -hier -filter {NAME =~ *U_EthCore_1/*TEN_GIG*/*txoutclkpcs*}]] \
    -group [get_clocks -quiet -of_objects [get_pins -quiet -hier -filter {NAME =~ *U_EthCore_1/*TEN_GIG*/*TXOUTCLK*}]]
