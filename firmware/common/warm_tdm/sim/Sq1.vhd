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

library warm_tdm;
use warm_tdm.SimPkg.all;

entity Sq1 is

   generic (
      SQ1_RN_G     : real := 1.0e-6;
      SQ1_IC0_G    : real := 55.0e-6;
      SQ1_PHINOT_G : real := 35.0e-6;

      RS_RN_G     : real := 1.0e-6;
      RS_IC0_G    : real := 55.0e-6;
      RS_PHINOT_G : real := 35.0e-6
      );

   port (
      iBias : in  real;
      iFb   : in  real;
      iMeas : in  real;
      iRs   : in  real;
      rEff  : out real;
      vOut  : out real);

end entity Sq1;

architecture sim of Sq1 is

   signal iSq1Bias : real;
   signal iRsBias  : real;

   signal rSq1 : real;
   signal rRs  : real;

begin

   comb : process (iBias, rRs, rSq1) is
      variable gSq1 : real;
      variable gRs  : real;
   begin
      gSq1 := 1.0 / rSq1;
      gRs  := 1.0 / rRs;

      iSq1Bias <= iBias * gSq1 / (gSq1 + gRs) after 1 ns;
      iRsBias  <= iBias * gRs / (gSq1 + gRs)  after 1 ns;

      rEff <= 1.0 / (gSq1 + gRs) after 1 ns;
   end process comb;

   U_SQ1_1 : entity warm_tdm.Squid
      generic map (
         R_SERIES_G => 1.0,
         RN_G       => SQ1_RN_G,
         IC0_G      => SQ1_IC0_G,
         PHINOT_G   => SQ1_PHINOT_G)
      port map (
         iBias => iSq1Bias,             -- [in]
         iFb   => iFb,                  -- [in]
         iMeas => iMeas,                -- [in]
         rEff  => rSq1,                 -- [out]
         vOut  => open);                -- [out]

   U_RS_2 : entity warm_tdm.Squid
      generic map (
         R_SERIES_G => 0.1,
         RN_G     => RS_RN_G,
         IC0_G    => RS_IC0_G,
         PHINOT_G => RS_PHINOT_G)
      port map (
         iBias => iRsBias,              -- [in]
         iFb   => 0.0,                  -- [in]
         iMeas => iRs,                  -- [in]
         rEff  => rRs,                  -- [out]
         vOut  => open);                -- [out]

end architecture sim;
