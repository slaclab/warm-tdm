-------------------------------------------------------------------------------
-- Title      : Timing Tx PHY for UltraScale+
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Standard   : VHDL'93/02
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

entity TimingTxPhyUsp is
   generic (
      TPD_G : time := 1 ns);
   port (
      timingRefClk  : in  sl;
      timingRefRst  : in  sl;
      bitClk        : out sl;
      bitRst        : out sl;
      wordClk       : out sl;
      wordRst       : out sl;
      dataIn        : in  slv(9 downto 0);
      enable        : in  sl;
      timingTxDataP : out sl;
      timingTxDataN : out sl);
end entity TimingTxPhyUsp;

architecture rtl of TimingTxPhyUsp is

   signal clkx4      : sl;
   signal clkx1      : sl;
   signal pllLocked  : sl;
   signal pllRst     : sl;
   signal wordRstInt : sl;
   signal rstx1      : sl;

begin

   -------------------------------------------------------------------------------------------------
   -- PLL: 125 MHz -> 625 MHz (OSERDES CLK) + 156.25 MHz (OSERDES CLKDIV + gearbox)
   -- VCO = 125 x 10 = 1250 MHz
   -------------------------------------------------------------------------------------------------
   U_ClockManagerUsp_1 : entity surf.ClockManagerUltraScale
      generic map (
         TPD_G            => TPD_G,
         TYPE_G           => "PLL",
         INPUT_BUFG_G     => false,
         FB_BUFG_G        => true,
         NUM_CLOCKS_G     => 2,
         BANDWIDTH_G      => "HIGH",
         CLKIN_PERIOD_G   => 8.0,
         DIVCLK_DIVIDE_G  => 1,
         CLKFBOUT_MULT_G  => 10,
         CLKOUT0_DIVIDE_G => 2,
         CLKOUT1_DIVIDE_G => 8)
      port map (
         clkIn     => timingRefClk,   -- [in]
         rstIn     => timingRefRst,   -- [in]
         clkOut(0) => clkx4,          -- [out]
         clkOut(1) => clkx1,          -- [out]
         rstOut(0) => open,           -- [out]
         rstOut(1) => open,           -- [out]
         locked    => pllLocked);     -- [out]

   -------------------------------------------------------------------------------------------------
   -- wordClk = timingRefClk passthrough (125 MHz to TimingTx logic)
   -------------------------------------------------------------------------------------------------
   pllRst <= not pllLocked;

   wordClk <= timingRefClk;
   bitClk  <= clkx4;
   bitRst  <= pllRst;

   U_RstSync_wordClk : entity surf.RstSync
      generic map (
         TPD_G => TPD_G)
      port map (
         clk      => timingRefClk,   -- [in]
         asyncRst => pllRst,         -- [in]
         syncRst  => wordRstInt);    -- [out]

   wordRst <= wordRstInt;

   U_RstSync_clkx1 : entity surf.RstSync
      generic map (
         TPD_G => TPD_G)
      port map (
         clk      => clkx1,    -- [in]
         asyncRst => pllRst,   -- [in]
         syncRst  => rstx1);   -- [out]

   -------------------------------------------------------------------------------------------------
   -- Serializer
   -- CDC FIFO crosses from timingRefClk (125 MHz) to clkx1 (156.25 MHz)
   -------------------------------------------------------------------------------------------------
   U_TimingSerializerUsp_1 : entity warm_tdm.TimingSerializerUsp
      generic map (
         TPD_G => TPD_G)
      port map (
         wordClk       => timingRefClk,    -- [in]
         wordRst       => wordRstInt,      -- [in]
         dataIn        => dataIn,          -- [in]
         clkx4         => clkx4,           -- [in]
         clkx1         => clkx1,           -- [in]
         rstx1         => rstx1,           -- [in]
         timingTxDataP => timingTxDataP,   -- [out]
         timingTxDataN => timingTxDataN);  -- [out]

end architecture rtl;
