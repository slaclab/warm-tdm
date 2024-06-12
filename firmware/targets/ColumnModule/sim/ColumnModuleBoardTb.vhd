-------------------------------------------------------------------------------
-- Title      : Testbench for design "ColumnModuleBoard"
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

entity ColumnModuleBoardTb is

end entity ColumnModuleBoardTb;

----------------------------------------------------------------------------------------------------

architecture sim of ColumnModuleBoardTb is

   -- component generics
   constant TPD_G                : time    := 1 ns;
   constant NUM_COLUMN_MODULES_C : integer := 1;

   -- component ports
   signal rj45TimingClkP  : slv(NUM_COLUMN_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingClkN  : slv(NUM_COLUMN_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingDataP : slv(NUM_COLUMN_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingDataN : slv(NUM_COLUMN_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingMgtP  : slv(NUM_COLUMN_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingMgtN  : slv(NUM_COLUMN_MODULES_C-1 downto 0);  -- [in]


begin

   -- component instantiation
   ColumnModGen : for i in 0 to NUM_COLUMN_MODULES_C-1 generate
      U_ColumnModuleBoard : entity warm_tdm.ColumnModuleBoard
         generic map (
            TPD_G                   => TPD_G,
            RING_ADDR_0_G           => (i = 0),
            SIMULATE_PGP_G          => false,
            SIM_PGP_PORT_NUM_G      => 7000,  --7000 + (10*i),
            SIM_ETH_SRP_PORT_NUM_G  => 10000 + (1000*i),
            SIM_ETH_DATA_PORT_NUM_G => 20000 + (1000*i))
         port map (
            rj45TimingRxClkP  => rj45TimingClkP(ite(i = 0, NUM_COLUMN_MODULES_C-1, i-1)),   -- [in]
            rj45TimingRxClkN  => rj45TimingClkN(ite(i = 0, NUM_COLUMN_MODULES_C-1, i-1)),   -- [in]
            rj45TimingRxDataP => rj45TimingDataP(ite(i = 0, NUM_COLUMN_MODULES_C-1, i-1)),  -- [in]
            rj45TimingRxDataN => rj45TimingDataN(ite(i = 0, NUM_COLUMN_MODULES_C-1, i-1)),  -- [in]
            rj45TimingRxMgtP  => rj45TimingMgtP(ite(i = 0, NUM_COLUMN_MODULES_C-1, i-1)),   -- [in]
            rj45TimingRxMgtN  => rj45TimingMgtN(ite(i = 0, NUM_COLUMN_MODULES_C-1, i-1)),   -- [in]
            rj45PgpRxMgtP     => '1',   -- [in]
            rj45PgpRxMgtN     => '0',   -- [in]
            rj45TimingTxClkP  => rj45TimingClkP(i),                                         -- [out]
            rj45TimingTxClkN  => rj45TimingClkN(i),                                         -- [out]
            rj45TimingTxDataP => rj45TimingDataP(i),                                        -- [out]
            rj45TimingTxDataN => rj45TimingDataN(i),                                        -- [out]
            rj45TimingTxMgtP  => rj45TimingMgtP(i),
            rj45TimingTxMgtN  => rj45TimingMgtN(i));

   end generate ColumnModGen;


end architecture sim;

----------------------------------------------------------------------------------------------------
