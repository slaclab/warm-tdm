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

   signal clkx4    : sl;
   signal clkx1    : sl;
   signal pllLocked : sl;
   signal pllRst    : sl;
   signal wordRstInt : sl;

begin

   -------------------------------------------------------------------------------------------------
   -- PLL: 125 MHz -> 625 MHz clkx4
   -------------------------------------------------------------------------------------------------
   U_ClockManagerUsp_1 : entity surf.ClockManagerUltraScale
      generic map (
         TPD_G            => TPD_G,
         TYPE_G           => "PLL",
         INPUT_BUFG_G     => false,
         FB_BUFG_G        => true,
         NUM_CLOCKS_G     => 1,
         BANDWIDTH_G      => "HIGH",
         CLKIN_PERIOD_G   => 8.0,
         DIVCLK_DIVIDE_G  => 1,
         CLKFBOUT_MULT_G  => 10,
         CLKOUT0_DIVIDE_G => 2)
      port map (
         clkIn     => timingRefClk,      -- [in]
         rstIn     => timingRefRst,      -- [in]
         clkOut(0) => clkx4,             -- [out] 625 MHz
         rstOut(0) => open,              -- [out]
         locked    => pllLocked);        -- [out]

   -------------------------------------------------------------------------------------------------
   -- BUFGCE_DIV: 625 MHz / 4 -> 156.25 MHz clkx1
   -------------------------------------------------------------------------------------------------
   U_BUFGCE_DIV_1 : BUFGCE_DIV
      generic map (
         BUFGCE_DIVIDE => 4)
      port map (
         I   => clkx4,
         CE  => '1',
         CLR => '0',
         O   => clkx1);                  -- 156.25 MHz

   -------------------------------------------------------------------------------------------------
   -- Reset synchronizer for clkx1 domain
   -------------------------------------------------------------------------------------------------
   pllRst <= not pllLocked;

   U_RstSync_clkx1 : entity surf.RstSync
      generic map (
         TPD_G => TPD_G)
      port map (
         clk      => clkx1,              -- [in]
         asyncRst => pllRst,             -- [in]
         syncRst  => wordRstInt);        -- [out]

   bitClk  <= clkx4;
   bitRst  <= pllRst;
   wordClk <= clkx1;
   wordRst <= wordRstInt;

   -------------------------------------------------------------------------------------------------
   -- Serializer
   -------------------------------------------------------------------------------------------------
   U_TimingSerializerUsp_1 : entity warm_tdm.TimingSerializerUsp
      generic map (
         TPD_G => TPD_G)
      port map (
         wordClk       => clkx1,            -- [in]
         wordRst       => wordRstInt,       -- [in]
         dataIn        => dataIn,           -- [in]
         clkx4         => clkx4,            -- [in] 625 MHz
         clkx1         => clkx1,            -- [in] 156.25 MHz
         rstx1         => wordRstInt,       -- [in]
         timingTxDataP => timingTxDataP,    -- [out]
         timingTxDataN => timingTxDataN);   -- [out]

end architecture rtl;
