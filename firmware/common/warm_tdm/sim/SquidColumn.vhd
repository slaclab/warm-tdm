-------------------------------------------------------------------------------
-- Title      : SQ1 Model
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
use ieee.math_real.all;

library surf;
use surf.StdRtlPkg.all;

library warm_tdm;
use warm_tdm.SimPkg.all;

entity SquidColumn is

   generic (
      NUM_ROWS_G : integer range 1 to 32 := 4;
      R_SHUNT_G  : real                  := 1.0;

      SSA_RN_G     : real := 1.0e-6;
      SSA_IC0_G    : real := 55.0e-6;
      SSA_PHINOT_G : real := 35.0e-6;

      SQ1_RN_G     : real := 1.0e-6;
      SQ1_IC0_G    : real := 55.0e-6;
      SQ1_PHINOT_G : real := 35.0e-6;

      RS_RN_G     : real := 1.0e-6;
      RS_IC0_G    : real := 55.0e-6;
      RS_PHINOT_G : real := 35.0e-6
      );

   port (
      ssaBias : in real;
      ssaFb   : in real;

      sq1Bias : in  real;
      sq1Fb   : in  real;
      iRs     : in  realArray(NUM_ROWS_G-1 downto 0);
      rEff    : out real;
      vOut    : out real);

end entity SquidColumn;

architecture sim of SquidColumn is

   signal sq1Reff    : RealArray(NUM_ROWS_G-1 downto 0);
   signal sq1TotReff : real;
   signal sq1TotG    : real;
   signal iSq1Bias   : real;

   function sum (
      arr : RealArray)
      return real is
      variable ret : real;
   begin
      ret := 0.0;
      for i in arr'range loop
         ret := ret + arr(i);
      end loop;
      return ret;
   end function sum;

begin

   U_SSA_SQUID_1 : entity warm_tdm.Squid
      generic map (
         RN_G     => SSA_RN_G,
         IC0_G    => SSA_IC0_G,
         PHINOT_G => SSA_PHINOT_G)
      port map (
         iBias => ssaBias,              -- [in]
         iFb   => ssaFb,                -- [in]
         iMeas => iSq1Bias,             -- [in]
         rEff  => rEff,                 -- [out]
         vOut  => vOut);                -- [out]

   SQ1_GEN : for i in NUM_ROWS_G-1 downto 0 generate

      U_SQ1_SQUID_1 : entity warm_tdm.Sq1
         generic map (
            SQ1_RN_G     => SQ1_RN_G,
            SQ1_IC0_G    => SQ1_IC0_G,
            SQ1_PHINOT_G => SQ1_PHINOT_G,
            RS_RN_G      => RS_RN_G,
            RS_IC0_G     => RS_IC0_G,
            RS_PHINOT_G  => RS_PHINOT_G)
         port map (
            iBias => iSq1Bias,          -- [in]
            iFb   => sq1Fb,             -- [in]
            iMeas => 0.0,               -- [in]
            iRs   => iRs(i),            -- [in]
            rEff  => sq1Reff(i),        -- [out]
            vOut  => open);             -- [out]

   end generate SQ1_GEN;

   comb : process (sq1Bias, sq1Reff) is
      variable sq1TotalReff : real;
      variable sq1TotalG    : real;
   begin
      sq1TotalReff := sum(sq1Reff);
      sq1TotalG    := 1.0 / sq1TotalReff;

      iSq1Bias <= sq1Bias * sq1TotalG / (sq1TotalG + R_SHUNT_G) after 1 ns;
   end process comb;
end sim;
