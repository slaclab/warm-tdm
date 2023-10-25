-------------------------------------------------------------------------------
-- Title      : RowSelectDiffAmp
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
library warm_tdm;

library ieee;
use ieee.std_logic_1164.all;
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;

entity RowSelectDiffAmp is

   generic (
      R_DAC_LOAD_G : real := 24.9;
      AMP_GAIN_G   : real := (4.02+1.00);
      R_SHUNT_G    : real := 1.0e3;
      R_CABLE_G    : real := 200.0);
   port (
      iInP : in  real;
      iInN : in  real;
      iOut : out real);
end entity RowSelectDiffAmp;

architecture sim of RowSelectDiffAmp is

   signal ampInDiff : real;
   signal ampVout   : real;

begin

   ampInDiff <= (iInP * R_DAC_LOAD_G) - (iInN * R_DAC_LOAD_G);
   ampVout   <= ampInDiff * AMP_GAIN_G;
   iOut      <= (2.0 * ampVout) / ((2*49.9*3) + (2.0*R_SHUNT_G) + R_CABLE_G);

end architecture sim;
