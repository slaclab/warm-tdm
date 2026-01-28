-------------------------------------------------------------------------------
-- Title      : SQUID Model
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

entity Squid is
   
   generic (
      R_SERIES_G : real := 1.0e-6;
      RN_G  : real := 1.0e-6;
      IC0_G : real := 55.0e-6;
      PHINOT_G : real := 35.0e-6);

   port (
      iBias : in  real;
      iFb   : in  real;
      iMeas : in  real;
      rEff  : out real;
      vOut  : out real);

end entity Squid;

architecture sim of Squid is

   signal ic : real;
   signal flux : real;

begin

   flux <= iMeas - iFb;

   ic <= IC0_G * abs(cos(MATH_PI * (flux / PHINOT_G)));

   vOut <= RN_G * sqrt(iBias**2 - ic**2) when abs(iBias) >= ic else iBias * R_SERIES_G;
      
   rEff <= R_SERIES_G + (RN_G * sqrt(1.0 - (ic/ibias)**2)) when abs(iBias) >= ic else R_SERIES_G;  -- Avoid divide
                                                                                    -- by zero
   

end architecture sim;
