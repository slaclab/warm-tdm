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

entity RowFebFastDacAmp is
   generic (
      IN_LOAD_R_G  : real := 24.9;
      FB_R_G       : real := 402.0;
      INPUT_R_G     : real := 100.0;
      FILTER_R_G : real := 49.9 * 3;
      SHUNT_R_G    : real := 1.00e3);
--      CABLE_R_G : real := 100.0);
   port (
      -- DAC input currents
      dacP : in real;
      dacN : in real;

      -- Output currents
      outP : out CurrentType;
      outN : out CurrentType);

end entity RowFebFastDacAmp;

architecture sim of RowFebFastDacAmp is

   constant GAIN_C : real := 1.0 + (FB_R_G / INPUT_R_G);

   signal ampInP : real;
   signal ampInN : real;

   signal ampOutP : real;
   signal ampOutN : real;

begin



   ampInP <= dacP * IN_LOAD_R_G;
   ampInN <= dacN * IN_LOAD_R_G;

   ampOutP <= ampInP * GAIN_C;
   ampOutN <= ampInN * GAIN_C;

   outP <= (
      voltage => ampOutP,
      impedance => FILTER_R_G + SHUNT_R_G);

   outN <= (
      voltage => ampOutN,
      impedance => FILTER_R_G + SHUNT_R_G);

end sim;
