-------------------------------------------------------------------------------
-- Title      : 
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: 
-------------------------------------------------------------------------------
-- This file is part of . It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of , including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;

library surf;
use surf.StdRtlPkg.all;

entity TimingDelay is

   generic (
      TPD_G   : time    := 1 ns;
      DELAY_G : integer := 20);

   port (
      clk       : in  sl;
      timingIn  : in  LocalTimingType;
      timingOut : out LocalTimingType);

end entity TimingDelay;

architecture rtl of TimingDelay is

   signal slvIn  : slv(TIMING_NUM_BITS_C -1 downto 0);
   signal slvOut : slv(TIMING_NUM_BITS_C-1 downto 0);

begin

   slvIn <= toSlv(timingIn);

   U_SlvFixedDelay_1 : entity surf.SlvFixedDelay
      generic map (
         TPD_G         => TPD_G,
         XIL_DEVICE_G  => "7SERIES",
         DELAY_STYLE_G => "srl",
         DELAY_G       => DELAY_G,
         WIDTH_G       => TIMING_NUM_BITS_C)
      port map (
         clk  => clk,                   -- [in]
         din  => slvIn,                 -- [in]
         dout => slvOut);               -- [out]

   timingout <= toLocalTimingType(slvOut);

end architecture rtl;
