-------------------------------------------------------------------------------
-- Title      : AwaXe
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Simulation model for AwaXe ASIC
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
use ieee.std_logic_unsigned.all;
use ieee.std_logic_arith.all;

library surf;
use surf.StdRtlPkg.all;
use surf.I2cPkg.all;

entity AwaXe is
   generic (
      TPD_G      : time            := 1 ns;
      ADDR_G     : slv(2 downto 0) := "000";
      LNA_FB_R_G : real            := 17.1e3;
      LNA_RS_R_G : real            := 20.0e3);
   port (
      sda     : inout sl;
      scl     : inout sl;
      saBias  :       RealArray(1 downto 0);
      saFb    :       RealArray(1 downto 0);
      sq1Bias :       RealArray(1 downto 0);
      sq1Fb   :       RealArray(1 downto 0);
      tesBias :       RealArray(1 downto 0);
      lnaInP  :       RealArray(1 downto 0);
      lnaInN  :       RealArray(1 downto 0);
      lnaOutP :       RealArray(1 downto 0);
      lnaOutN :       RealArray(1 downto 0));
end entity AwaXe;


architecture rtl of AwaXe is

   constant LNA_GAIN_C : real := ((2 * LNA_FB_R_G) / LNA_RS_R_G) - 1;

   type CurrentArray is array (1 downto 0) of RealArray(4 downto 0);
   signal current CurrentArray;

begin

   U_ClkRst_1 : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G => 10 ns)
      port map (
         clkP => clk,                   -- [out]
         rst  => rst);                  -- [out]

   GEN_CHANNEL : for ch in 1 downto 0 generate
      GEN_DACS : for dac in 4 downto 0 generate
         U_AwaXeChannel_1 : entity warm_tdm.AwaXeChannel
            generic map (
               TPD_G      => TPD_G,
               RANGE_G    => ite(dac = 0, 1.8e3, 300e6),
               I2C_ADDR_G => toSl(dac = 0) & toSl(ch = 0) & ite(dac > 0, toSlv(dac-1, 2), "00") & ADDR_G,
               ADDR_G     => ADDR_G)
            port map (
               clk     => clk,                -- [in]
               rst     => rst,                -- [in]
               sda     => sda,                -- [inout]
               scl     => scl,                -- [inout]
               current => current(ch)(dac));  -- [out]
      end generate GEN_DACS;

      tesBias(ch) <= current(ch)(0);
      saBias(ch)  <= current(ch)(4);
      saFb(ch)    <= current(ch)(3);
      sq1Bias(ch) <= current(ch)(1);
      sq1Fb(ch)   <= current(ch)(2);

      lnaInDiff(ch)  <= lnaInP(ch) - lnaInN(ch);
      lnaOutDiff(ch) <= lnaInDiff(ch) * LNA_GAIN_C;

      lnaOutP(ch) <= lnaOutDiff(ch) / 2
         lnaOutN(ch) <= lnaInN(ch) * LNA_GAIN_C;

   end generate GEN_CHANNEL;

end architecture rtl;
