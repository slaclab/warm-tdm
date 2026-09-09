-------------------------------------------------------------------------------
-- Title      : Row-Select Flux-Activated Switch Behavioral Model
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

entity RowFasModel is
   generic (
      PARAMS_G : RowFasParamsType := ROW_FAS_SYNTHETIC_C);
   port (
      biasCurrentAmp      : in  real;
      selectCurrentAmp    : in  real;
      phaseCycles         : out real;
      staticResistanceOhm : out real;
      voltageVolt         : out real);
end entity RowFasModel;

architecture sim of RowFasModel is
begin

   assert validSquidParams(PARAMS_G.squid)
      report "RowFasModel: invalid row-FAS SQUID parameters"
      severity failure;
   assert PARAMS_G.selectPolarity /= 0
      report "RowFasModel: select polarity must be +1 or -1"
      severity failure;
   assert PARAMS_G.seriesResistanceOhm >= 0.0
      report "RowFasModel: series resistance must be nonnegative"
      severity failure;

   comb : process (all) is
      variable voltage : real;
   begin
      phaseCycles <= rowFasPhaseCycles(PARAMS_G, selectCurrentAmp);
      voltage := rowFasBranchVoltage(
         PARAMS_G, biasCurrentAmp, selectCurrentAmp);
      voltageVolt <= voltage;
      if abs(biasCurrentAmp) > 1.0E-30 then
         staticResistanceOhm <= abs(voltage / biasCurrentAmp);
      else
         staticResistanceOhm <= PARAMS_G.seriesResistanceOhm;
      end if;
   end process comb;

end architecture sim;

