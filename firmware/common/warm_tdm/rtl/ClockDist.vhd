-------------------------------------------------------------------------------
-- Title      : 
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

library warm_tdm;

entity ClockDist is

   generic (
      TPD_G         : time    := 1 ns;
      FPGA_FAMILY_G : string  := "7SERIES";
      CLK_0_DIV2_G  : boolean := false;
      CLK_1_DIV2_G  : boolean := false);
   port (
      -- Clocks
      gtRefClk0P : in sl;
      gtRefClk0N : in sl;

      gtRefClk0  : out sl;
      fabRefClk0 : out sl;

      gtRefClk1P : in sl;
      gtRefClk1N : in sl;

      gtRefClk1  : out sl;
      fabRefClk1 : out sl);

end entity;

architecture rtl of ClockDist is

   signal intDiv2Clk0  : sl;
   signal intDiv2Clk1  : sl;
   signal intGtRefClk0 : sl;
   signal intGtRefClk1 : sl;

begin

   gtRefClk0 <= intGtRefClk0;
   gtRefClk1 <= intGtRefClk1;

   GEN_7SERIES : if (FPGA_FAMILY_G = "7SERIES") generate

      U_IBUFDS_GTE2_0 : IBUFDS_GTE2
         port map (
            I     => gtRefClk0P,
            IB    => gtRefClk0N,
            CEB   => '0',
            ODIV2 => intDiv2Clk0,
            O     => intGtRefClk0);

      FAB_0_DIV2_GEN : if (CLK_0_DIV2_G) generate
         U_BUFG_0 : BUFG
            port map (
               I => intDiv2Clk0,
               O => fabRefClk0);
      end generate;

      FAB_0_GEN : if (not CLK_0_DIV2_G) generate
         U_BUFG_0 : BUFG
            port map (
               I => intGtRefClk0,
               O => fabRefClk0);
      end generate;

      U_IBUFDS_GTE2_1 : IBUFDS_GTE2
         port map (
            I     => gtRefClk1P,
            IB    => gtRefClk1N,
            CEB   => '0',
            ODIV2 => intDiv2Clk1,
            O     => intGtRefClk1);

      FAB_1_DIV2_GEN : if (CLK_1_DIV2_G) generate
         U_BUFG_1 : BUFG
            port map (
               I => intDiv2Clk1,
               O => fabRefClk1);
      end generate;

      FAB_1_GEN : if (not CLK_1_DIV2_G) generate
         U_BUFG_1 : BUFG
            port map (
               I => intGtRefClk1,
               O => fabRefClk1);
      end generate;

   end generate GEN_7SERIES;

   GEN_ULTRASCALE_PLUS : if (FPGA_FAMILY_G = "ULTRASCALE_PLUS") generate

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

      FAB_0_DIV2_GEN : if (CLK_0_DIV2_G) generate
         U_BUFG_GT_0 : BUFG_GT
            port map (
               I       => intDiv2Clk0,
               CE      => '1',
               CEMASK  => '0',
               CLR     => '0',
               CLRMASK => '0',
               DIV     => "000",
               O       => fabRefClk0);
      end generate;

      FAB_0_GEN : if (not CLK_0_DIV2_G) generate
         U_BUFG_GT_0 : BUFG_GT
            port map (
               I       => intGtRefClk0,
               CE      => '1',
               CEMASK  => '0',
               CLR     => '0',
               CLRMASK => '0',
               DIV     => "000",
               O       => fabRefClk0);
      end generate;

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

      FAB_1_DIV2_GEN : if (CLK_1_DIV2_G) generate
         U_BUFG_GT_1 : BUFG_GT
            port map (
               I       => intDiv2Clk1,
               CE      => '1',
               CEMASK  => '0',
               CLR     => '0',
               CLRMASK => '0',
               DIV     => "000",
               O       => fabRefClk1);
      end generate;

      FAB_1_GEN : if (not CLK_1_DIV2_G) generate
         U_BUFG_GT_1 : BUFG_GT
            port map (
               I       => intGtRefClk1,
               CE      => '1',
               CEMASK  => '0',
               CLR     => '0',
               CLRMASK => '0',
               DIV     => "000",
               O       => fabRefClk1);
      end generate;

   end generate GEN_ULTRASCALE_PLUS;


end architecture rtl;

