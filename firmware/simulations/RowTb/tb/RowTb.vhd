-------------------------------------------------------------------------------
-- Description: Simulation Testbed for testing Row Module firmware
-------------------------------------------------------------------------------
-- This file is part of 'Warm TDM'.
-- It is subject to the license terms in the LICENSE.txt file found in the 
-- top-level directory of this distribution and at: 
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
-- No part of 'Warm TDM', including this file, 
-- may be copied, modified, propagated, or distributed except according to 
-- the terms contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.std_logic_unsigned.all;
use ieee.std_logic_arith.all;


library surf;
use surf.StdRtlPkg.all;

library warm_tdm;

entity RowTb is
end RowTb;

architecture sim of RowTb is

   constant TPD_G : time := 1 ns;

   signal rj45TimingClkP  : slv(0 downto 0);
   signal rj45TimingClkN  : slv(0 downto 0);
   signal rj45TimingDataP : slv(0 downto 0);
   signal rj45TimingDataN : slv(0 downto 0);
   signal rj45TimingMgtP  : slv(0 downto 0);
   signal rj45TimingMgtN  : slv(0 downto 0);
   signal rj45PgpP        : slv(0 downto 0);
   signal rj45PgpN        : slv(0 downto 0);

begin




   U_RowModuleBoard_4 : entity warm_tdm.RowModuleBoard
      generic map (
         TPD_G                   => TPD_G,
         RING_ADDR_0_G           => true,
         SIM_PGP_PORT_NUM_G      => 7000 ,
         SIM_ETH_SRP_PORT_NUM_G  => 10000,
         SIM_ETH_DATA_PORT_NUM_G => 20000)
      port map (
         rj45TimingRxClkP  => rj45TimingClkP(0),   -- [in]
         rj45TimingRxClkN  => rj45TimingClkN(0),   -- [in]
         rj45TimingRxDataP => rj45TimingDataP(0),  -- [in]
         rj45TimingRxDataN => rj45TimingDataN(0),  -- [in]
         rj45TimingRxMgtP  => rj45TimingMgtP(0),   -- [in]
         rj45TimingRxMgtN  => rj45TimingMgtN(0),   -- [in]
         rj45PgpRxP        => rj45PgpP(0),         -- [in]
         rj45PgpRxN        => rj45PgpN(0),         -- [in]
         rj45TimingTxClkP  => rj45TimingClkP(0),   -- [out]
         rj45TimingTxClkN  => rj45TimingClkN(0),   -- [out]
         rj45TimingTxDataP => rj45TimingDataP(0),  -- [out]
         rj45TimingTxDataN => rj45TimingDataN(0),  -- [out]
         rj45TimingTxMgtP  => rj45TimingMgtP(0),   -- [out]
         rj45TimingTxMgtN  => rj45TimingMgtN(0),   -- [out]
         rj45PgpTxP        => rj45PgpP(0),         -- [out]
         rj45PgpTxN        => rj45PgpN(0));        -- [out]


end sim;
