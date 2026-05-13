-------------------------------------------------------------------------------
-- Title      : Clock Distribution
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

library surf;
use surf.StdRtlPkg.all;

entity ClockDist is
   generic (
      TPD_G         : time    := 1 ns;
      FPGA_FAMILY_G : string  := "7SERIES";
      CLK_0_DIV2_G  : boolean := false;
      CLK_1_DIV2_G  : boolean := false);
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

architecture rtl of ClockDist is

   component ClockDist7s is
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
   end component;

   component ClockDistUsp is
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
   end component;

begin

   GEN_7SERIES : if (FPGA_FAMILY_G = "7SERIES") generate
      U_Impl : ClockDist7s
         generic map (
            TPD_G        => TPD_G,
            CLK_0_DIV2_G => CLK_0_DIV2_G,
            CLK_1_DIV2_G => CLK_1_DIV2_G)
         port map (
            gtRefClk0P => gtRefClk0P,
            gtRefClk0N => gtRefClk0N,
            gtRefClk0  => gtRefClk0,
            fabRefClk0 => fabRefClk0,
            gtRefClk1P => gtRefClk1P,
            gtRefClk1N => gtRefClk1N,
            gtRefClk1  => gtRefClk1,
            fabRefClk1 => fabRefClk1);
   end generate;

   GEN_ULTRASCALE_PLUS : if (FPGA_FAMILY_G = "ULTRASCALE_PLUS") generate
      U_Impl : ClockDistUsp
         generic map (
            TPD_G        => TPD_G,
            CLK_0_DIV2_G => CLK_0_DIV2_G,
            CLK_1_DIV2_G => CLK_1_DIV2_G)
         port map (
            gtRefClk0P => gtRefClk0P,
            gtRefClk0N => gtRefClk0N,
            gtRefClk0  => gtRefClk0,
            fabRefClk0 => fabRefClk0,
            gtRefClk1P => gtRefClk1P,
            gtRefClk1N => gtRefClk1N,
            gtRefClk1  => gtRefClk1,
            fabRefClk1 => fabRefClk1);
   end generate;

end architecture rtl;
