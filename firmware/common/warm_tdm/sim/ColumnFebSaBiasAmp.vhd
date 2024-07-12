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
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;

library surf;
use surf.StdRtlPkg.all;

library warm_tdm;
use warm_tdm.SimPkg.all;

entity ColumnFebSaBiasAmp is

   generic (
      SA_BIAS_OUT_IMPEDANCE_G : real := 14.99e3;
      AMP_1_GAIN_G            : real := 11.99;
      AMP_2_GAIN_G            : real := (100.0 / 33.0));

   port (
      -- DAC inputs
      saOffsetDacP : in real;
      saOffsetDacN : in real;
      saBiasDacP   : in real;
      saBiasDacN   : in real;

      -- SA Bias Current out
      saBiasOutP : out CurrentType;
      saBiasOutN : out CurrentType;

      -- Developed SA Bias Voltage
      saBiasInP : in real;
      saBiasInN : in real;

      -- Amplifier output to ADC
      saSigOutP : out real;
      saSigOutN : out real);


end entity ColumnFebSaBiasAmp;

architecture sim of ColumnFebSaBiasAmp is

   signal amp1InP : real;
   signal amp1InN : real;

   signal amp1OutP : real;
   signal amp1OutN : real;

begin

   -- Output SA Bias as current
   saBiasOutP <= (
      voltage   => saBiasDacP,
      impedance => SA_BIAS_OUT_IMPEDANCE_G);

   saBiasOutN <= (
      voltage   => saBiasDacN,
      impedance => SA_BIAS_OUT_IMPEDANCE_G);


   -- First stage amplification
   amp1OutP <= saBiasInP * AMP_1_GAIN_G;
   amp1OutN <= saBiasInN * AMP_1_GAIN_G;

   -- Second stage amplification
   saSigOutP <= (amp1OutP * AMP_2_GAIN_G) - (saOffsetDacP * AMP_2_GAIN_G);
   saSigOutN <= (amp1OutN * AMP_2_GAIN_G) - (saOffsetDacN * AMP_2_GAIN_G);

end sim;
