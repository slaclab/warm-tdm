-------------------------------------------------------------------------------
-- Title      : Ideal DC SQUID Behavioral Model
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

entity SquidModel is
   generic (
      PARAMS_G : SquidParamsType := SQ1_SQUID_SYNTHETIC_C);
   port (
      biasCurrentAmp      : in  real;
      inputCurrentAmp     : in  real;
      feedbackCurrentAmp  : in  real;
      inputPolarity       : in  integer range -1 to 1 := 1;
      feedbackPolarity    : in  integer range -1 to 1 := -1;
      phaseCycles         : out real;
      criticalCurrentAmp  : out real;
      staticResistanceOhm : out real;
      voltageVolt         : out real);
end entity SquidModel;

architecture sim of SquidModel is
begin

   assert validSquidParams(PARAMS_G)
      report "SquidModel: invalid SQUID parameters"
      severity failure;

   comb : process (all) is
      variable phase : real;
   begin
      phase := squidPhaseCycles(
         PARAMS_G,
         inputCurrentAmp,
         feedbackCurrentAmp,
         inputPolarity,
         feedbackPolarity);

      phaseCycles         <= phase;
      criticalCurrentAmp  <= idealSquidCriticalCurrent(PARAMS_G, phase);
      staticResistanceOhm <= idealSquidStaticResistance(
         PARAMS_G, biasCurrentAmp, phase);
      voltageVolt         <= idealSquidVoltage(PARAMS_G, biasCurrentAmp, phase);
   end process comb;

end architecture sim;

