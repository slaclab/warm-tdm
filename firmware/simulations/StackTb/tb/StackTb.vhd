-------------------------------------------------------------------------------
-- File       : RceSimTb.vhd
-- Company    : SLAC National Accelerator Laboratory
-- Created    : 2018-06-23
-- Last update: 2021-05-21
-------------------------------------------------------------------------------
-- Description: Simulation Testbed for testing the SimpleRogueSim module
-------------------------------------------------------------------------------
-- This file is part of 'ATLAS RD53 DEV'.
-- It is subject to the license terms in the LICENSE.txt file found in the 
-- top-level directory of this distribution and at: 
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html. 
-- No part of 'ATLAS RD53 DEV', including this file, 
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

entity StackTb is
end StackTb;

architecture sim of StackTb is

   constant TPD_G : time := 1 ns;

   signal rj45TimingClkP  : slv(5 downto 0);
   signal rj45TimingClkN  : slv(5 downto 0);
   signal rj45TimingDataP : slv(5 downto 0);
   signal rj45TimingDataN : slv(5 downto 0);
   signal rj45TimingMgtP  : slv(5 downto 0);
   signal rj45TimingMgtN  : slv(5 downto 0);
   signal rj45PgpP        : slv(5 downto 0);
   signal rj45PgpN        : slv(5 downto 0);

begin

   U_ColumnModuleBoard_Coordinator : entity warm_tdm.ColumnModuleBoard
      generic map (
         TPD_G                   => TPD_G,
         RING_ADDR_0_G           => true,
         SIM_PGP_PORT_NUM_G      => 7000,
         SIM_ETH_SRP_PORT_NUM_G  => 10000,
         SIM_ETH_DATA_PORT_NUM_G => 20000)
      port map (
         rj45TimingRxClkP  => rj45TimingClkP(5),   -- [in]
         rj45TimingRxClkN  => rj45TimingClkN(5),   -- [in]
         rj45TimingRxDataP => rj45TimingDataP(5),  -- [in]
         rj45TimingRxDataN => rj45TimingDataN(5),  -- [in]
         rj45TimingRxMgtP  => rj45TimingRxMgtP(5)  -- [in]
         rj45TimingRxMgtP  => rj45TimingRxMgtN(5)  -- [in]
         rj45PgpRxP        => rj45PgpP(5),         -- [in]
         rj45PgpRxN        => rj45PgpN(5),         -- [in]
         rj45TimingTxClkP  => rj45TimingClkP(0),   -- [out]
         rj45TimingTxClkN  => rj45TimingClkN(0),   -- [out]
         rj45TimingTxDataP => rj45TimingDataP(0),  -- [out]
         rj45TimingTxDataN => rj45TimingDataN(0),  -- [out]
         rj45TimingTxMgtP  => rj45TimingMgtP(0),   -- [out]
         rj45TimingTxMgtN  => rj45TimingMgtN(0),   -- [out]
         rj45PgpTxP        => rj45PgpP(0),         -- [out]
         rj45PgpTxN        => rj45PgpN(0));        -- [out]


   U_ColumnModuleBoard_1 : entity warm_tdm.ColumnModuleBoard
      generic map (
         TPD_G                   => TPD_G,
         RING_ADDR_0_G           => false,
         SIM_PGP_PORT_NUM_G      => 7000 + 10,
         SIM_ETH_SRP_PORT_NUM_G  => 10000 + 1000,  -- Not used
         SIM_ETH_DATA_PORT_NUM_G => 20000 + 1000)  -- Not used
      port map (
         rj45TimingRxClkP  => rj45TimingClkP(0),   -- [in]
         rj45TimingRxClkN  => rj45TimingClkN(0),   -- [in]
         rj45TimingRxDataP => rj45TimingDataP(0),  -- [in]
         rj45TimingRxDataN => rj45TimingDataN(0),  -- [in]
         rj45TimingRxMgtP  => rj45TimingMgtP(0),   -- [in]
         rj45TimingRxMgtN  => rj45TimingMgtN(0),   -- [in]
         rj45PgpRxP        => rj45PgpP(0),         -- [in]
         rj45PgpRxN        => rj45PgpN(0),         -- [in]
         rj45TimingTxClkP  => rj45TimingClkP(1),   -- [out]
         rj45TimingTxClkN  => rj45TimingClkN(1),   -- [out]
         rj45TimingTxDataP => rj45TimingDataP(1),  -- [out]
         rj45TimingTxDataN => rj45TimingDataN(1),  -- [out]
         rj45TimingTxMgtP  => rj45TimingMgtP(1),   -- [out]
         rj45TimingTxMgtN  => rj45TimingMgtN(1),   -- [out]
         rj45PgpTxP        => rj45PgpP(1),         -- [out]
         rj45PgpTxN        => rj45PgpN(1));        -- [out]

   U_ColumnModuleBoard_2 : entity warm_tdm.ColumnModuleBoard
      generic map (
         TPD_G                   => TPD_G,
         RING_ADDR_0_G           => false,
         SIM_PGP_PORT_NUM_G      => 7000 + 20,
         SIM_ETH_SRP_PORT_NUM_G  => 10000 + 2000,  -- Not used
         SIM_ETH_DATA_PORT_NUM_G => 20000 + 2000)  -- Not used
      port map (
         rj45TimingRxClkP  => rj45TimingClkP(1),   -- [in]
         rj45TimingRxClkN  => rj45TimingClkN(1),   -- [in]
         rj45TimingRxDataP => rj45TimingDataP(1),  -- [in]
         rj45TimingRxDataN => rj45TimingDataN(1),  -- [in]
         rj45TimingRxMgtP  => rj45TimingMgtP(1),   -- [in]
         rj45TimingRxMgtN  => rj45TimingMgtN(1),   -- [in]
         rj45PgpRxP        => rj45PgpP(1),         -- [in]
         rj45PgpRxN        => rj45PgpN(1),         -- [in]
         rj45TimingTxClkP  => rj45TimingClkP(2),   -- [out]
         rj45TimingTxClkN  => rj45TimingClkN(2),   -- [out]
         rj45TimingTxDataP => rj45TimingDataP(2),  -- [out]
         rj45TimingTxDataN => rj45TimingDataN(2),  -- [out]
         rj45TimingTxMgtP  => rj45TimingMgtP(2),   -- [out]
         rj45TimingTxMgtN  => rj45TimingMgtN(2),   -- [out]
         rj45PgpTxP        => rj45PgpP(2),         -- [out]
         rj45PgpTxN        => rj45PgpN(2));        -- [out]

   U_ColumnModuleBoard_3 : entity warm_tdm.ColumnModuleBoard
      generic map (
         TPD_G                   => TPD_G,
         RING_ADDR_0_G           => false,
         SIM_PGP_PORT_NUM_G      => 7000 + 30,
         SIM_ETH_SRP_PORT_NUM_G  => 10000 + 3000,  -- Not used
         SIM_ETH_DATA_PORT_NUM_G => 20000 + 3000)  -- Not used
      port map (
         rj45TimingRxClkP  => rj45TimingClkP(2),   -- [in]
         rj45TimingRxClkN  => rj45TimingClkN(2),   -- [in]
         rj45TimingRxDataP => rj45TimingDataP(2),  -- [in]
         rj45TimingRxDataN => rj45TimingDataN(2),  -- [in]
         rj45TimingRxMgtP  => rj45TimingMgtP(2),   -- [in]
         rj45TimingRxMgtN  => rj45TimingMgtN(2),   -- [in]
         rj45PgpRxP        => rj45PgpP(2),         -- [in]
         rj45PgpRxN        => rj45PgpN(2),         -- [in]
         rj45TimingTxClkP  => rj45TimingClkP(3),   -- [out]
         rj45TimingTxClkN  => rj45TimingClkN(3),   -- [out]
         rj45TimingTxDataP => rj45TimingDataP(3),  -- [out]
         rj45TimingTxDataN => rj45TimingDataN(3),  -- [out]
         rj45TimingTxMgtP  => rj45TimingMgtP(3),   -- [out]
         rj45TimingTxMgtN  => rj45TimingMgtN(3),   -- [out]
         rj45PgpTxP        => rj45PgpP(3),         -- [out]
         rj45PgpTxN        => rj45PgpN(3));        -- [out]

   U_RowModuleBoard_4 : entity warm_tdm.RowModuleBoard
      generic map (
         TPD_G                   => TPD_G,
         RING_ADDR_0_G           => false,
         SIM_PGP_PORT_NUM_G      => 7000 + 40,
         SIM_ETH_SRP_PORT_NUM_G  => 10000 + 4000,  -- Not used
         SIM_ETH_DATA_PORT_NUM_G => 20000 + 4000)  -- Not used
      port map (
         rj45TimingRxClkP  => rj45TimingClkP(3),   -- [in]
         rj45TimingRxClkN  => rj45TimingClkN(3),   -- [in]
         rj45TimingRxDataP => rj45TimingDataP(3),  -- [in]
         rj45TimingRxDataN => rj45TimingDataN(3),  -- [in]
         rj45TimingRxMgtP  => rj45TimingMgtP(3),   -- [in]
         rj45TimingRxMgtN  => rj45TimingMgtN(3),   -- [in]
         rj45PgpRxP        => rj45PgpP(3),         -- [in]
         rj45PgpRxN        => rj45PgpN(3),         -- [in]
         rj45TimingTxClkP  => rj45TimingClkP(4),   -- [out]
         rj45TimingTxClkN  => rj45TimingClkN(4),   -- [out]
         rj45TimingTxDataP => rj45TimingDataP(4),  -- [out]
         rj45TimingTxDataN => rj45TimingDataN(4),  -- [out]
         rj45TimingTxMgtP  => rj45TimingMgtP(4),   -- [out]
         rj45TimingTxMgtN  => rj45TimingMgtN(4),   -- [out]
         rj45PgpTxP        => rj45PgpP(4),         -- [out]
         rj45PgpTxN        => rj45PgpN(4));        -- [out]

   U_RowModuleBoard_5 : entity warm_tdm.RowModuleBoard
      generic map (
         TPD_G                   => TPD_G,
         RING_ADDR_0_G           => false,
         SIM_PGP_PORT_NUM_G      => 7000 + 50,
         SIM_ETH_SRP_PORT_NUM_G  => 10000 + 5000,  -- Not used
         SIM_ETH_DATA_PORT_NUM_G => 20000 + 5000)  -- Not used
      port map (
         rj45TimingRxClkP  => rj45TimingClkP(4),   -- [in]
         rj45TimingRxClkN  => rj45TimingClkN(4),   -- [in]
         rj45TimingRxDataP => rj45TimingDataP(4),  -- [in]
         rj45TimingRxDataN => rj45TimingDataN(4),  -- [in]
         rj45TimingRxMgtP  => rj45TimingMgtP(4),   -- [in]
         rj45TimingRxMgtN  => rj45TimingMgtN(4),   -- [in]
         rj45PgpRxP        => rj45PgpP(4),         -- [in]
         rj45PgpRxN        => rj45PgpN(4),         -- [in]
         rj45TimingTxClkP  => rj45TimingClkP(5),   -- [out]
         rj45TimingTxClkN  => rj45TimingClkN(5),   -- [out]
         rj45TimingTxDataP => rj45TimingDataP(5),  -- [out]
         rj45TimingTxDataN => rj45TimingDataN(5),  -- [out]
         rj45TimingTxMgtP  => rj45TimingMgtP(5),   -- [out]
         rj45TimingTxMgtN  => rj45TimingMgtN(5),   -- [out]
         rj45PgpTxP        => rj45PgpP(5),         -- [out]
         rj45PgpTxN        => rj45PgpN(5));        -- [out]


end sim;
