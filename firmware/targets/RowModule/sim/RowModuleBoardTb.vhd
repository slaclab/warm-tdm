-------------------------------------------------------------------------------
-- Title      : Testbench for design "RowModuleBoard"
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
----------------------------------------------------------------------------------------------------

entity RowModuleBoardTb is

end entity RowModuleBoardTb;

----------------------------------------------------------------------------------------------------

architecture sim of RowModuleBoardTb is

   -- component generics
   constant TPD_G             : time    := 1 ns;
   constant NUM_ROW_MODULES_C : integer := 4;

   -- component ports
   signal rj45TimingClkP  : slv(NUM_ROW_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingClkN  : slv(NUM_ROW_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingDataP : slv(NUM_ROW_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingDataN : slv(NUM_ROW_MODULES_C-1 downto 0);  -- [in]

begin

   -- component instantiation
   RowModGen : for i in 0 to NUM_ROW_MODULES_C-1 generate
      U_RowModuleBoard : entity warm_tdm.RowModuleBoard
         generic map (
            TPD_G              => TPD_G,
            RING_ADDR_0_G      => (i =0),
            SIM_PGP_PORT_NUM_G => 7000 + (20*i),
            SIM_ETH_PORT_NUM_G => 10000 + (1000*i))
         port map (
            rj45TimingRxClkP  => rj45TimingClkP(ite(i = 0, NUM_ROW_MODULES_C-1, i-1)),   -- [in]
            rj45TimingRxClkN  => rj45TimingClkN(ite(i = 0, NUM_ROW_MODULES_C-1, i-1)),   -- [in]
            rj45TimingRxDataP => rj45TimingDataP(ite(i = 0, NUM_ROW_MODULES_C-1, i-1)),  -- [in]
            rj45TimingRxDataN => rj45TimingDataN(ite(i = 0, NUM_ROW_MODULES_C-1, i-1)),  -- [in]
            rj45TimingTxClkP  => rj45TimingClkP(i),                                      -- [out]
            rj45TimingTxClkN  => rj45TimingClkN(i),                                      -- [out]
            rj45TimingTxDataP => rj45TimingDataP(i),                                     -- [out]
            rj45TimingTxDataN => rj45TimingDataN(i));                                    -- [out]
   end generate RowModGen;


end architecture sim;

----------------------------------------------------------------------------------------------------
