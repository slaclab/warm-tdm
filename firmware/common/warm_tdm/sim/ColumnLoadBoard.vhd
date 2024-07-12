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

entity ColumnLoadBoard is

   generic (
      SA_BIAS_LOADS_G  : RealArray(7 downto 0) := (others => 100.0);
      SA_FB_LOADS_G    : RealArray(7 downto 0) := (others => 100.0);
      SQ1_BIAS_LOADS_G : RealArray(7 downto 0) := (others => 100.0);
      SQ1_FB_LOADS_G   : RealArray(7 downto 0) := (others => 100.0));
   port (
      tesBiasP   : in  RealArray(7 downto 0);
      tesBiasN   : in  RealArray(7 downto 0);
      saBiasOutP : in  CurrentArray(7 downto 0);
      saBiasOutN : in  CurrentArray(7 downto 0);
      saBiasInP  : out RealArray(7 downto 0);
      saBiasInN  : out RealArray(7 downto 0);
      saFbP      : in  CurrentArray(7 downto 0);
      saFbN      : in  CurrentArray(7 downto 0);
      sq1BiasP   : in  CurrentArray(7 downto 0);
      sq1BiasN   : in  CurrentArray(7 downto 0);
      sq1FbP     : in  CurrentArray(7 downto 0);
      sq1FbN     : in  CurrentArray(7 downto 0));

end entity ColumnLoadBoard;

architecture sim of ColumnLoadBoard is

   signal saBiasCurrent  : RealArray(7 downto 0);
   signal saFbCurrent    : RealArray(7 downto 0);
   signal sq1BiasCurrent : RealArray(7 downto 0);
   signal sq1FbCurrent   : RealArray(7 downto 0);

begin

   GEN_CURRENTS : for i in 7 downto 0 generate
      saBiasCurrent(i)  <= (saBiasOutP(i).voltage - saBiasOutN(i).voltage) / (saBiasOutP(i).impedance + saBiasOutN(i).impedance + SA_BIAS_LOAD_G(i));
      saFbCurrent(i)    <= (saFbOutP(i).voltage - saFbOutN(i).voltage) / (saFbOutP(i).impedance + saFbOutN(i).impedance + SA_FB_LOAD_G(i));
      sq1BiasCurrent(i) <= (sq1BiasOutP(i).voltage - sq1BiasOutN(i).voltage) / (sq1BiasOutP(i).impedance + sq1BiasOutN(i).impedance + SQ1_BIAS_LOAD_G(i));
      sq1FbCurrent(i)   <= (sq1FbOutP(i).voltage - sq1FbOutN(i).voltage) / (sq1FbOutP(i).impedance + sq1FbOutN(i).impedance + SQ_FB_LOAD_G(i));

      saBiasInP(i) <= (saBiasOutP(i).voltage * (SA_BIAS_LOAD_G(i) + saBiasOutP(i).impedance) + saBiasOutN(i).voltage * saBiasOutN(i).impedance) /
                      (SA_BIAS_LOAD_G(i) + saBiasOutP(i).impedance + saBiasOutN(i).impedance);
      saBiasInN(i) <= (saBiasOutN(i).voltage * (SA_BIAS_LOAD_G(i) + saBiasOutN(i).impedance) + saBiasOutP(i).voltage * saBiasOutP(i).impedance) /
                      (SA_BIAS_LOAD_G(i) + saBiasOutP(i).impedance + saBiasOutN(i).impedance);
   end generate GEN_CURRENTS;

end architecture sim;

