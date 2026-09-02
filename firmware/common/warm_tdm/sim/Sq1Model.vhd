-------------------------------------------------------------------------------
-- Title      : First-Stage SQUID Branch Behavioral Model
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Simulation
-- Standard   : VHDL-2008
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library warm_tdm;
use warm_tdm.WaferSimPkg.all;

entity Sq1Model is
   generic (
      PARAMS_G : Sq1ParamsType := SQ1_SYNTHETIC_C);
   port (
      biasCurrentAmp     : in  real;
      tesCurrentAmp      : in  real;
      feedbackCurrentAmp : in  real;
      phaseCycles        : out real;
      voltageVolt        : out real);
end entity Sq1Model;

architecture sim of Sq1Model is
begin

   assert validSquidParams(PARAMS_G.squid)
      report "Sq1Model: invalid SQ1 parameters"
      severity failure;
   assert PARAMS_G.tesPolarity /= 0 and PARAMS_G.feedbackPolarity /= 0
      report "Sq1Model: coupling polarity must be +1 or -1"
      severity failure;
   assert PARAMS_G.tesCouplingScale > 0.0 and
          PARAMS_G.feedbackCouplingScale > 0.0
      report "Sq1Model: coupling scale must be positive"
      severity failure;
   assert PARAMS_G.seriesResistanceOhm >= 0.0
      report "Sq1Model: series resistance must be nonnegative"
      severity failure;

   comb : process (all) is
   begin
      phaseCycles <= sq1PhaseCycles(
         PARAMS_G, tesCurrentAmp, feedbackCurrentAmp);
      voltageVolt <= sq1BranchVoltage(
         PARAMS_G, biasCurrentAmp, tesCurrentAmp, feedbackCurrentAmp);
   end process comb;

end architecture sim;

