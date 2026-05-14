-------------------------------------------------------------------------------
-- Title      : Timing Rx PHY for UltraScale+
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Xilinx UltraScale+
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Extracts the UltraScale+-specific clock and deserializer logic
-- from TimingRx. Contains IBUFDS (NOT IBUFGDS to avoid BUFGCE inference),
-- ClockManagerUltraScale PLL (125 MHz -> 625 MHz), BUFGCE_DIV/4 (156.25 MHz),
-- RstSync, and TimingDeserializerUsp.
--
-- NOTE: The PLL input is the ONLY consumer of timingRxClk. The raw
-- timingRxClk signal must NOT be used as a clock anywhere else to avoid
-- BUFGCE inference.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;

library warm_tdm;

entity TimingRxPhyUsp is
   generic (
      TPD_G : time := 1 ns);
   port (
      timingRxClkP  : in  sl;
      timingRxClkN  : in  sl;
      timingRxDataP : in  sl;
      timingRxDataN : in  sl;
      wordClk       : out sl;
      wordRst       : out sl;
      dataOut       : out slv(9 downto 0);
      dataValid     : out sl;
      slip          : in  sl;
      dlyLoad       : in  sl;
      dlyCfg        : in  slv(8 downto 0);
      locked        : out sl);  -- PLL locked
end entity TimingRxPhyUsp;

architecture rtl of TimingRxPhyUsp is

   signal timingRxClk : sl;
   signal clkx4       : sl;
   signal clkx1       : sl;
   signal rstx1       : sl;
   signal pllLocked   : sl;
   signal pllRst      : sl;

begin

   -------------------------
   -- 125 MHz Timing RX clock input buffer
   -- IBUFDS (NOT IBUFGDS) to avoid BUFGCE inference on US+
   -------------------------
   TIMING_RX_CLK_BUFF : IBUFDS
      port map (
         i  => timingRxClkP,
         ib => timingRxClkN,
         o  => timingRxClk);

   -------------------------
   -- PLL: 125 MHz -> 625 MHz (clkx4)
   -- timingRxClk is ONLY used here as PLL input
   -------------------------
   U_ClockManagerUsp_1 : entity surf.ClockManagerUltraScale
      generic map (
         TPD_G              => TPD_G,
         TYPE_G             => "MMCM",
         INPUT_BUFG_G       => true,
         FB_BUFG_G          => true,
         NUM_CLOCKS_G       => 1,
         BANDWIDTH_G        => "OPTIMIZED",
         CLKIN_PERIOD_G     => 8.0,
         DIVCLK_DIVIDE_G    => 1,
         CLKFBOUT_MULT_F_G  => 10.0,
         CLKOUT0_DIVIDE_F_G => 2.0)
      port map (
         clkIn     => timingRxClk,
         rstIn     => '0',
         clkOut(0) => clkx4,       -- 625 MHz
         rstOut(0) => open,
         locked    => pllLocked);

   locked <= pllLocked;

   -------------------------
   -- BUFGCE_DIV/4: 625 MHz -> 156.25 MHz (clkx1)
   -------------------------
   U_BUFGCE_DIV_1 : BUFGCE_DIV
      generic map (
         BUFGCE_DIVIDE => 4)
      port map (
         I   => clkx4,
         CE  => '1',
         CLR => '0',
         O   => clkx1);            -- 156.25 MHz

   -------------------------
   -- Reset synchronizer for clkx1 domain
   -------------------------
   pllRst <= not pllLocked;

   U_RstSync_clkx1 : entity surf.RstSync
      generic map (
         TPD_G => TPD_G)
      port map (
         clk      => clkx1,
         asyncRst => pllRst,
         syncRst  => rstx1);

   -------------------------
   -- Deserializer
   -------------------------
   U_TimingDeserializerUsp_1 : entity warm_tdm.TimingDeserializerUsp
      port map (
         clkx4         => clkx4,
         clkx1         => clkx1,
         rstx1         => rstx1,
         timingRxDataP => timingRxDataP,
         timingRxDataN => timingRxDataN,
         wordClk       => wordClk,
         wordRst       => wordRst,
         dataOut       => dataOut,
         dataValid     => dataValid,
         slip          => slip,
         dlyLoad       => dlyLoad,
         dlyCfg        => dlyCfg,
         locked        => open);

end architecture rtl;
