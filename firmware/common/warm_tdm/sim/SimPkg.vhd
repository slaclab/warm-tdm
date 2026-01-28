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

package SimPkg is

   type CurrentType is record
      voltage   : real;
      impedance : real;
   end record CurrentType;

   type CurrentArray is array (natural range <>) of CurrentType;

   function current (
      c    : CurrentType;
      load : real := 0.0)
      return real;

   function currentDiff (
      p    : CurrentType;
      n    : CurrentType;
      load : real := 0.0)
      return real;


end package SimPkg;

package body SimPkg is

   function current (
      c    : CurrentType;
      load : real := 0.0)
      return real is
   begin
      return (c.voltage / (c.impedance + load));
   end function current;

   function currentDiff (
      p    : CurrentType;
      n    : CurrentType;
      load : real := 0.0)
      return real is
   begin
      return (p.voltage - n.voltage) / (p.impedance + n.impedance + load);
   end function currentDiff;

end package body SimPkg;
