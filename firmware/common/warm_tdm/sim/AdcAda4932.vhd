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
library ieee;
use ieee.std_logic_1164.all;
use ieee.std_logic_arith.all;

library surf;
use surf.StdRtlPkg.all;

entity AdcAda4932 is
   generic (
      TPD_G    : time := 1 ns;
      R_GAIN_G : real := 4.99e3;
      R_FB_G   : real := 4.99e3);
   port (
      ainP  : in  real;
      ainN  : in  real;
      vocm  : in  real;
      aoutP : out real;
      aoutN : out real);
end entity AdcAda4932;

architecture sim of AdcAda4932 is

   signal vout : real;

begin

   vout <= (ainP - ainN) * (R_FB_G / R_GAIN_G);

   aoutP <= (vout * 0.5) + vocm;
   aoutN <= (vout * (-0.5)) + vocm;

end architecture sim;
