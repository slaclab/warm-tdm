-------------------------------------------------------------------------------
-- Title      : Timing MMCM
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: 
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

entity TimingMmcm is

   generic (
      TPD_G : time := 1 ns);

   port (
      timingRxClk : in  sl;
      timingRxRst : in  sl;
      bitClk      : out sl;
      bitClkInv   : out sl;
      wordClk     : out sl;
      wordRst     : out sl);

end entity TimingMmcm;

architecture rtl of TimingMmcm is

   signal bitClkLoc  : sl;
   signal bitClkRaw  : sl;
   signal wordClkLoc : sl;
   signal wordClkRaw : sl;
   signal fbClkRaw   : sl;
   signal fbClk      : sl;
   signal locked     : sl;


begin


   -------------------------------------------------------------------------------------------------
   -- Use MMCM to create DDR Bit clock
   -------------------------------------------------------------------------------------------------
   U_Mmcm : MMCME2_ADV
      generic map (
         BANDWIDTH        => "OPTIMIZED",
         CLKOUT4_CASCADE  => false,
         STARTUP_WAIT     => false,
         CLKIN1_PERIOD    => 8.0,
         DIVCLK_DIVIDE    => 1,
         CLKFBOUT_MULT_F  => 10.0,
         CLKOUT0_DIVIDE_F => 4.0,
         CLKOUT1_DIVIDE   => 10)
      port map (
         DCLK     => '0',
         DEN      => '0',
         DWE      => '0',
         DADDR    => (others => '0'),
         DI       => (others => '0'),
         DO       => open,
         PSCLK    => '0',
         PSEN     => '0',
         PSINCDEC => '0',
         PWRDWN   => '0',
         RST      => timingRxRst,
         CLKIN1   => timingRxClk,
         CLKIN2   => '0',
         CLKINSEL => '1',
         CLKFBOUT => fbClkRaw,
         CLKFBIN  => fbClk,
         LOCKED   => locked,
         CLKOUT0  => bitClkRaw,
         CLKOUT1  => wordClkRaw);

   BIT_CLK_BUFIO : BUFIO
      port map(
         i => bitClkRaw,
         o => bitClkLoc);

   bitClk    <= bitClkLoc;
   bitClkInv <= not bitClkLoc;


   WORD_CLK_BUFR : BUFR
      port map (
         i   => wordClkRaw,
         o   => wordClkLoc,
         ce  => '0',
         clr => '0');

   wordClk <= wordClkLoc;

   FB_BUFR : BUFR
      port map (
         i   => fbClkRaw,
         o   => fbClk,
         ce  => '0',
         clr => '0');

   RstSync_1 : entity surf.RstSync
      generic map (
         TPD_G => TPD_G)
      port map (
         clk      => wordClkLoc,
         asyncRst => locked,
         syncRst  => wordRst);



end architecture rtl;
