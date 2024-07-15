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

entity ColumnFebTesBiasAmp is
   port (
      -- DAC inputs
      tesBiasDacP : in real;
      tesBiasDacN : in real;

      delatch : in sl;

      -- TES Bias Current
      tesBiasP : out real;
      tesBiasN : out real);

end entity ColumnFebTesBiasAmp;

architecture sim of ColumnFebTesBiasAmp is

   signal tesN2          : real;
   signal tesN3          : real;
   signal gainResistance : real;

begin

   tesN2 <= tesBiasDacP - tesBiasDacN;
   tesN3 <= tesN2 / 2.0;

   gainResistance <= ite(delatch = '0', 1.0e3, (1.0e3 * 174.0) / (1.0e3 + 174.0));

   -- Schematic swaps P and N
   tesBiasP <= (tesN3 / gainResistance) * (-1.0);
   tesBiasN <= (tesN3 / gainResistance);

end sim;
