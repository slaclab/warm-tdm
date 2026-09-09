-------------------------------------------------------------------------------
-- Title      : Series SQUID Array Behavioral Model
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

entity SsaModel is
   generic (
      PARAMS_G : SsaParamsType := SSA_SYNTHETIC_C);
   port (
      biasCurrentAmp     : in  real;
      inputCurrentAmp    : in  real;
      feedbackCurrentAmp : in  real;
      phaseCycles        : out real;
      voltageVolt        : out real);
end entity SsaModel;

architecture sim of SsaModel is
begin

   assert validSquidParams(PARAMS_G.squid)
      report "SsaModel: invalid SSA SQUID parameters"
      severity failure;
   assert PARAMS_G.inputPolarity /= 0 and PARAMS_G.feedbackPolarity /= 0
      report "SsaModel: coupling polarity must be +1 or -1"
      severity failure;
   assert PARAMS_G.inputCouplingScale > 0.0 and
          PARAMS_G.feedbackCouplingScale > 0.0
      report "SsaModel: coupling scale must be positive"
      severity failure;
   assert PARAMS_G.outputClampVolt > 0.0
      report "SsaModel: output clamp must be positive"
      severity failure;

   comb : process (all) is
   begin
      phaseCycles <= ssaPhaseCycles(
         PARAMS_G, inputCurrentAmp, feedbackCurrentAmp);
      voltageVolt <= ssaVoltage(
         PARAMS_G, biasCurrentAmp, inputCurrentAmp, feedbackCurrentAmp);
   end process comb;

end architecture sim;

