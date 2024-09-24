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
      STAGE_1_RG_G            : real := 40.2;
      STAGE_1_RFB_G           : real := 100.0;
      STAGE_2_RGND_G          : real := 21.0;
      STAGE_2_ROFFSET_G       : real := 402.0;
      STAGE_2_RFB_G           : real := 100.0);
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

   signal amp1InDiff : real;

   signal amp1OutP    : real;
   signal amp1OutN    : real;
   signal amp1OutDiff : real;

   signal sigOutP      : real;
   signal sigOutN      : real;
   signal saSigOutDiff : real;

begin

   -- Output SA Bias as current
   saBiasOutP <= (
      voltage   => saBiasDacP,
      impedance => SA_BIAS_OUT_IMPEDANCE_G);

   saBiasOutN <= (
      voltage   => saBiasDacP * (-1.0),
      impedance => SA_BIAS_OUT_IMPEDANCE_G);

   amp1InDiff <= saBiasInP - saBiasInN;

   -- First stage amplification
--                  (STAGE_1_RG_G * saBiasInP + STAGE_1_RFB_G * saBiasInP  - STAGE_1_RFB_G*saBiasInN)/STAGE_1_RG_G
   amp1OutP    <= (STAGE_1_RG_G * saBiasInP + STAGE_1_RFB_G * saBiasInP - saBiasInN * STAGE_1_RFB_G) / STAGE_1_RG_G;
   amp1OutN    <= (STAGE_1_RG_G * saBiasInN + STAGE_1_RFB_G * saBiasInN - saBiasInP * STAGE_1_RFB_G) / STAGE_1_RG_G;
   amp1OutDiff <= amp1OutP - amp1OutN;

   -- Second stage amplification   
   sigOutP <= ((-1.0)*STAGE_2_RFB_G*STAGE_2_RGND_G*saOffsetDacP + STAGE_2_RFB_G*STAGE_2_RGND_G*amp1OutP + STAGE_2_RFB_G*STAGE_2_ROFFSET_G*amp1OutP + STAGE_2_RGND_G*STAGE_2_ROFFSET_G*amp1OutP)/(STAGE_2_RGND_G*STAGE_2_ROFFSET_G);
   sigOutN <= ((-1.0)*STAGE_2_RFB_G*STAGE_2_RGND_G*(-1.0)*saOffsetDacP + STAGE_2_RFB_G*STAGE_2_RGND_G*amp1OutN + STAGE_2_RFB_G*STAGE_2_ROFFSET_G*amp1OutN + STAGE_2_RGND_G*STAGE_2_ROFFSET_G*amp1OutN)/(STAGE_2_RGND_G*STAGE_2_ROFFSET_G);

   saSigOutDiff <= sigOutP - sigOutN;

   saSigOutP <= sigOutP;
   saSigOutN <= sigOutN;


end sim;
