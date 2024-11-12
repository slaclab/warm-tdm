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

entity RowLoadBoard is

   generic (
      RS_LOADS_G  : RealArray(31 downto 0) := (others => 200.0));
   port (
      rsP   : in  CurrentArray(31 downto 0);
      rsN   : in  CurrentArray(31 downto 0));

end entity RowLoadBoard;

architecture sim of RowLoadBoard is

   signal rsCurrent  : RealArray(31 downto 0);

begin

   GEN_CURRENTS : for i in 31 downto 0 generate
      rsCurrent(i)    <= (rsP(i).voltage - rsN(i).voltage) / (rsP(i).impedance + rsN(i).impedance + RS_LOADS_G(i));
   end generate GEN_CURRENTS;

end architecture sim;

