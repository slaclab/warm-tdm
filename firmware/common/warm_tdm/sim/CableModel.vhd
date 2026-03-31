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

library surf;
use surf.StdRtlPkg.all;

library warm_tdm;
use warm_tdm.SimPkg.all;

entity CableModel is

   generic (
      CABLE_R_G : real := 30.0);
   port (
      v_in      : in  CurrentType;
      v_out     : out CurrentType;
      vload_in  : in  real;
      vload_out : out real);


end entity CableModel;

architecture sim of CableModel is

   signal sumImpedance : real;

begin

   sumImpedance <= vin.impedance + CABLE_R_G;

   -- Add resistance for output
   v_out <= (voltage => v_in.voltage, impedance => sumImpedance);

   -- Load module returns vload
   -- Calculate load back to source including cable resistance
   vload_out <= ((CABLE_R_G*vin.voltage) + (vin.impedance*vload_in)) / (sumImpedance);

end architecture sim;

