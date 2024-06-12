-------------------------------------------------------------------------------
-- File       : RceSimTb.vhd
-- Company    : SLAC National Accelerator Laboratory
-- Created    : 2018-06-23
-- Last update: 2024-05-08
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

   constant SIM_PGP_GT_C : boolean := true;

   constant COLUMN_BOARDS_C : integer := 1;
   constant ROW_BOARDS_C    : integer := 1;

   constant GROUP_SIZE_C : integer := COLUMN_BOARDS_C + ROW_BOARDS_C;
   constant TPD_G        : time    := 1 ns;

   -------------------------------------------------------------------------------------------------
   -- Ring network
   -- Pgp carried on rj45TimingMgt for compatibility with older Column Module
   -------------------------------------------------------------------------------------------------
   signal rj45TimingClkP  : slv(GROUP_SIZE_C-1 downto 0);
   signal rj45TimingClkN  : slv(GROUP_SIZE_C-1 downto 0);
   signal rj45TimingDataP : slv(GROUP_SIZE_C-1 downto 0);
   signal rj45TimingDataN : slv(GROUP_SIZE_C-1 downto 0);
   signal rj45TimingMgtP  : slv(GROUP_SIZE_C-1 downto 0);
   signal rj45TimingMgtN  : slv(GROUP_SIZE_C-1 downto 0);
   signal rj45PgpMgtP     : slv(GROUP_SIZE_C-1 downto 0);
   signal rj45PgpMgtN     : slv(GROUP_SIZE_C-1 downto 0);

begin

   GEN_COL_BOARDS : for i in 0 to COLUMN_BOARDS_C-1 generate
      U_ColumnModuleBoard : entity warm_tdm.ColumnModuleBoard
         generic map (
            TPD_G                   => TPD_G,
            RING_ADDR_0_G           => (i = 0),
            SIM_PGP_PORT_NUM_G      => 7000 + (40 *i),  --ite(SIM_PGP_GT_C, 0, 7000),
            SIM_ETH_SRP_PORT_NUM_G  => 10000 + (i * 1000),
            SIM_ETH_DATA_PORT_NUM_G => 20000 + (i * 1000))
         port map (
            -- Incomming connections from last in loop
            rj45TimingRxClkP  => rj45TimingClkP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
            rj45TimingRxClkN  => rj45TimingClkN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
            rj45TimingRxDataP => rj45TimingDataP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),  -- [in]
            rj45TimingRxDataN => rj45TimingDataN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),  -- [in]
            rj45TimingRxMgtP  => rj45TimingMgtP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
            rj45TimingRxMgtN  => rj45TimingMgtN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
            rj45PgpRxMgtP     => rj45PgpMgtP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),      -- [in]
            rj45PgpRxMgtN     => rj45PgpMgtN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),      -- [in]
            -- Outgoing connections
            rj45TimingTxClkP  => rj45TimingClkP(i),     -- [out]
            rj45TimingTxClkN  => rj45TimingClkN(i),     -- [out]
            rj45TimingTxDataP => rj45TimingDataP(i),    -- [out]
            rj45TimingTxDataN => rj45TimingDataN(i),    -- [out]
            rj45TimingTxMgtP  => rj45TimingMgtP(i),     -- [out]
            rj45TimingTxMgtN  => rj45TimingMgtN(i),     -- [out]
            rj45PgpTxMgtP     => rj45PgpMgtP(i),        -- [out]
            rj45PgpTxMgtN     => rj45PgpMgtN(i));       -- [out]

   end generate GEN_COL_BOARDS;

   GEN_ROW_BOARDS : for i in COLUMN_BOARDS_C to GROUP_SIZE_C-1 generate
      U_RowModuleBoard : entity warm_tdm.RowModuleBoard
         generic map (
            TPD_G                   => TPD_G,
            RING_ADDR_0_G           => false,
            SIM_PGP_PORT_NUM_G      => 70000 + (40*i),                                  --7000 + 40,
            SIM_ETH_SRP_PORT_NUM_G  => 10000 + (i * 1000),                              -- Not used
            SIM_ETH_DATA_PORT_NUM_G => 20000 + (i * 1000))                              -- Not used
         port map (
            rj45TimingRxClkP  => rj45TimingClkP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
            rj45TimingRxClkN  => rj45TimingClkN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
            rj45TimingRxDataP => rj45TimingDataP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),  -- [in]
            rj45TimingRxDataN => rj45TimingDataN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),  -- [in]
            rj45TimingRxMgtP  => rj45TimingMgtP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
            rj45TimingRxMgtN  => rj45TimingMgtN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
            rj45PgpRxMgtP     => rj45PgpMgtP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),      -- [in]
            rj45PgpRxMgtN     => rj45PgpMgtN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),      -- [in]
            rj45TimingTxClkP  => rj45TimingClkP(i),                                     -- [out]
            rj45TimingTxClkN  => rj45TimingClkN(i),                                     -- [out]
            rj45TimingTxDataP => rj45TimingDataP(i),                                    -- [out]
            rj45TimingTxDataN => rj45TimingDataN(i),                                    -- [out]
            rj45TimingTxMgtP  => rj45TimingMgtP(i),                                     -- [out]
            rj45TimingTxMgtN  => rj45TimingMgtN(i),                                     -- [out]
            rj45PgpTxMgtP     => rj45PgpMgtP(i),                                        -- [out]
            rj45PgpTxMgtN     => rj45PgpMgtN(i));                                       -- [out]

   end generate GEN_ROW_BOARDS;

end sim;
