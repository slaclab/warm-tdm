## 1G Ethernet clock constraints
create_generated_clock -name ethClk     [get_pins -hier -filter {NAME =~ *U_EthCore_1/*U_Phy/GIG_ETH*U_MMCM/*/CLKOUT0}]
create_generated_clock -name ethClkDiv2 [get_pins -hier -filter {NAME =~ *U_EthCore_1/*U_Phy/GIG_ETH*U_MMCM/*/CLKOUT1}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks ethClk]
