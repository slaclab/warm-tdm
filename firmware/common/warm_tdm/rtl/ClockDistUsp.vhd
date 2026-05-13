-------------------------------------------------------------------------------
-- Title      : Clock Distribution for UltraScale+
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Xilinx UltraScale+
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

entity ClockDistUsp is
   generic (
      TPD_G        : time    := 1 ns;
      CLK_0_DIV2_G : boolean := false;
      CLK_1_DIV2_G : boolean := false);
   port (
      gtRefClk0P : in  sl;
      gtRefClk0N : in  sl;
      gtRefClk0  : out sl;
      fabRefClk0 : out sl;
      gtRefClk1P : in  sl;
      gtRefClk1N : in  sl;
      gtRefClk1  : out sl;
      fabRefClk1 : out sl);
end entity;

architecture rtl of ClockDistUsp is
   signal intDiv2Clk0  : sl;
   signal intDiv2Clk1  : sl;
   signal intGtRefClk0 : sl;
   signal intGtRefClk1 : sl;
begin

   gtRefClk0 <= intGtRefClk0;
   gtRefClk1 <= intGtRefClk1;

   U_IBUFDS_GTE4_0 : IBUFDS_GTE4
      generic map (
         REFCLK_EN_TX_PATH  => '0',
         REFCLK_HROW_CK_SEL => "00",
         REFCLK_ICNTL_RX    => "00")
      port map (
         I     => gtRefClk0P,
         IB    => gtRefClk0N,
         CEB   => '0',
         O     => intGtRefClk0,
         ODIV2 => intDiv2Clk0);

   -- On US+, IBUFDS_GTE4 O can only drive GT primitives.
   -- ODIV2 always divides by 2; use BUFG_GT to reach fabric.
   U_BUFG_GT_0 : BUFG_GT
      port map (
         I       => intDiv2Clk0,
         CE      => '1',
         CEMASK  => '0',
         CLR     => '0',
         CLRMASK => '0',
         DIV     => "000",
         O       => fabRefClk0);

   U_IBUFDS_GTE4_1 : IBUFDS_GTE4
      generic map (
         REFCLK_EN_TX_PATH  => '0',
         REFCLK_HROW_CK_SEL => "00",
         REFCLK_ICNTL_RX    => "00")
      port map (
         I     => gtRefClk1P,
         IB    => gtRefClk1N,
         CEB   => '0',
         O     => intGtRefClk1,
         ODIV2 => intDiv2Clk1);

   U_BUFG_GT_1 : BUFG_GT
      port map (
         I       => intDiv2Clk1,
         CE      => '1',
         CEMASK  => '0',
         CLR     => '0',
         CLRMASK => '0',
         DIV     => "000",
         O       => fabRefClk1);

end architecture rtl;
