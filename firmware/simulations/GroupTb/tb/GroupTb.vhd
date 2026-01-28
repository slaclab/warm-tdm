-------------------------------------------------------------------------------
-- File       : RceSimTb.vhd
-- Company    : SLAC National Accelerator Laboratory
-- Created    : 2018-06-23
-- Last update: 2026-01-28
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
use warm_tdm.SimPkg.all;

entity GroupTb is
end GroupTb;

architecture sim of GroupTb is

   constant LOAD_C : string := "WAFER";
   constant SIM_PGP_GT_C : boolean := true;

   constant COLUMN_BOARDS_C : integer := 1;
   constant ROW_BOARDS_C    : integer := 1;

   constant AWAXE_G : boolean := false;

   constant NUM_WAFERS_G       : integer range 1 to 2  := 1;
   constant NUM_ROW_SELECTS_G  : integer range 1 to 32 := 32;
   constant NUM_CHIP_SELECTS_G : integer range 0 to 8  := 0;

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

   signal tesBiasP   : RealArray(7 downto 0);
   signal tesBiasN   : RealArray(7 downto 0);
   signal saBiasOutP : CurrentArray(7 downto 0);
   signal saBiasOutN : CurrentArray(7 downto 0);
   signal saBiasInP  : RealArray(7 downto 0);
   signal saBiasInN  : RealArray(7 downto 0);
   signal saFbP      : CurrentArray(7 downto 0);
   signal saFbN      : CurrentArray(7 downto 0);
   signal sq1BiasP   : CurrentArray(7 downto 0);
   signal sq1BiasN   : CurrentArray(7 downto 0);
   signal sq1FbP     : CurrentArray(7 downto 0);
   signal sq1FbN     : CurrentArray(7 downto 0);

   signal rsP : CurrentArray(31 downto 0);
   signal rsN : CurrentArray(31 downto 0);


begin

   GEN_COL_BOARDS : for i in 0 to COLUMN_BOARDS_C-1 generate
      U_ColumnFpgaBoardSim : entity warm_tdm.ColumnFpgaBoardSim
         generic map (
            TPD_G                   => TPD_G,
            RING_ADDR_0_G           => (i = 0),
            AWAXE_G                 => AWAXE_G,
            SIM_PGP_PORT_NUM_G      => 7000 + (40 *i),  --ite(SIM_PGP_GT_C, 0, 7000),
            SIM_ETH_SRP_PORT_NUM_G  => 10000 + (i * 1000),
            SIM_ETH_DATA_PORT_NUM_G => 20000 + (i * 1000))
         port map (
            tesBiasP   => tesBiasP,
            tesBiasN   => tesBiasN,
            saBiasOutP => saBiasOutP,
            saBiasOutN => saBiasOutN,
            saBiasInP  => saBiasInP,
            saBiasInN  => saBiasInN,
            saFbP      => saFbP,
            saFbN      => saFbN,
            sq1BiasP   => sq1BiasP,
            sq1BiasN   => sq1BiasN,
            sq1FbP     => sq1FbP,
            sq1FbN     => sq1FbN,

            -- Incomming connections from last in loop
            rj45TimingRxClkP  => rj45TimingClkP(ite(i = 0, GROUP_SIZE_C-1, i-1)),   -- [in]
            rj45TimingRxClkN  => rj45TimingClkN(ite(i = 0, GROUP_SIZE_C-1, i-1)),   -- [in]
            rj45TimingRxDataP => rj45TimingDataP(ite(i = 0, GROUP_SIZE_C-1, i-1)),  -- [in]
            rj45TimingRxDataN => rj45TimingDataN(ite(i = 0, GROUP_SIZE_C-1, i-1)),  -- [in]
--            rj45TimingRxMgtP  => rj45TimingMgtP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
--            rj45TimingRxMgtN  => rj45TimingMgtN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
--            rj45PgpRxMgtP     => rj45PgpMgtP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),      -- [in]
--            rj45PgpRxMgtN     => rj45PgpMgtN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),      -- [in]
            -- Outgoing connections
            rj45TimingTxClkP  => rj45TimingClkP(i),                                 -- [out]
            rj45TimingTxClkN  => rj45TimingClkN(i),                                 -- [out]
            rj45TimingTxDataP => rj45TimingDataP(i),                                -- [out]
            rj45TimingTxDataN => rj45TimingDataN(i));                               -- [out]
--             rj45TimingTxMgtP  => rj45TimingMgtP(i),     -- [out]
--             rj45TimingTxMgtN  => rj45TimingMgtN(i),     -- [out]
--             rj45PgpTxMgtP     => rj45PgpMgtP(i),        -- [out]
--             rj45PgpTxMgtN     => rj45PgpMgtN(i));       -- [out]

   end generate GEN_COL_BOARDS;

   GEN_ROW_BOARDS : for i in COLUMN_BOARDS_C to GROUP_SIZE_C-1 generate
      U_RowFpgaBoardSim : entity warm_tdm.RowFpgaBoardSim
         generic map (
            TPD_G                   => TPD_G,
            RING_ADDR_0_G           => (i = 0),
            SIM_PGP_PORT_NUM_G      => 70000 + (40*i),  --7000 + 40,
            SIM_ETH_SRP_PORT_NUM_G  => 10000 + (i * 1000),
            SIM_ETH_DATA_PORT_NUM_G => 20000 + (i * 1000),
            NUM_WAFERS_G            => NUM_WAFERS_G,
            NUM_ROW_SELECTS_G       => NUM_ROW_SELECTS_G,
            NUM_CHIP_SELECTS_G      => NUM_CHIP_SELECTS_G)
         port map (
            rsP => rsP,                                 -- [out]
            rsN => rsN,                                 -- [out]

            rj45TimingRxClkP  => rj45TimingClkP(ite(i = 0, GROUP_SIZE_C-1, i-1)),   -- [in]
            rj45TimingRxClkN  => rj45TimingClkN(ite(i = 0, GROUP_SIZE_C-1, i-1)),   -- [in]
            rj45TimingRxDataP => rj45TimingDataP(ite(i = 0, GROUP_SIZE_C-1, i-1)),  -- [in]
            rj45TimingRxDataN => rj45TimingDataN(ite(i = 0, GROUP_SIZE_C-1, i-1)),  -- [in]
--             rj45TimingRxMgtP  => rj45TimingMgtP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
--             rj45TimingRxMgtN  => rj45TimingMgtN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),   -- [in]
--             rj45PgpRxMgtP     => rj45PgpMgtP((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),      -- [in]
--             rj45PgpRxMgtN     => rj45PgpMgtN((i+GROUP_SIZE_C-1) mod GROUP_SIZE_C),      -- [in]
            rj45TimingTxClkP  => rj45TimingClkP(i),                                 -- [out]
            rj45TimingTxClkN  => rj45TimingClkN(i),                                 -- [out]
            rj45TimingTxDataP => rj45TimingDataP(i),                                -- [out]
            rj45TimingTxDataN => rj45TimingDataN(i));                               -- [out]
--             rj45TimingTxMgtP  => rj45TimingMgtP(i),                                     -- [out]
--             rj45TimingTxMgtN  => rj45TimingMgtN(i),                                     -- [out]
--             rj45PgpTxMgtP     => rj45PgpMgtP(i),                                        -- [out]
--             rj45PgpTxMgtN     => rj45PgpMgtN(i));                                       -- [out]

   end generate GEN_ROW_BOARDS;

   LOAD_BOARD : if (LOAD_C = "LOAD_BOARD") generate
      U_ColumnLoadBoard_1 : entity warm_tdm.ColumnLoadBoard
--         generic map (
--             SA_BIAS_LOADS_G  => SA_BIAS_LOADS_G,
--             SA_FB_LOADS_G    => SA_FB_LOADS_G,
--             SQ1_BIAS_LOADS_G => SQ1_BIAS_LOADS_G,
--             SQ1_FB_LOADS_G   => SQ1_FB_LOADS_G)
         port map (
            tesBiasP   => tesBiasP,     -- [in]
            tesBiasN   => tesBiasN,     -- [in]
            saBiasOutP => saBiasOutP,   -- [in]
            saBiasOutN => saBiasOutN,   -- [in]
            saBiasInP  => saBiasInP,    -- [out]
            saBiasInN  => saBiasInN,    -- [out]
            saFbP      => saFbP,        -- [in]
            saFbN      => saFbN,        -- [in]
            sq1BiasP   => sq1BiasP,     -- [in]
            sq1BiasN   => sq1BiasN,     -- [in]
            sq1FbP     => sq1FbP,       -- [in]
            sq1FbN     => sq1FbN);      -- [in]

      U_RowLoadBoard_1 : entity warm_tdm.RowLoadBoard
--         generic map (
--             SA_BIAS_LOADS_G  => SA_BIAS_LOADS_G,
--             SA_FB_LOADS_G    => SA_FB_LOADS_G,
--             SQ1_BIAS_LOADS_G => SQ1_BIAS_LOADS_G,
--             SQ1_FB_LOADS_G   => SQ1_FB_LOADS_G)
         port map (
            rsP => rsP,                 -- [in]
            rsN => rsN);                -- [in]

   end generate;

   WAFTER_GEN: if (LOAD_C = "WAFER") generate
      U_WaferSim_1: entity warm_tdm.WaferSim
         generic map (
--             SA_BIAS_LOADS_G  => SA_BIAS_LOADS_G,
--             SA_FB_LOADS_G    => SA_FB_LOADS_G,
--             SQ1_BIAS_LOADS_G => SQ1_BIAS_LOADS_G,
--             SQ1_FB_LOADS_G   => SQ1_FB_LOADS_G,
--             RS_LOADS_G       => RS_LOADS_G,
            NUM_ROWS_G       => 32)
--             R_SHUNT_G        => R_SHUNT_G,
--             SSA_RN_G         => SSA_RN_G,
--             SSA_IC0_G        => SSA_IC0_G,
--             SSA_PHINOT_G     => SSA_PHINOT_G,
--             SQ1_RN_G         => SQ1_RN_G,
--             SQ1_IC0_G        => SQ1_IC0_G,
--             SQ1_PHINOT_G     => SQ1_PHINOT_G,
--             RS_RN_G          => RS_RN_G,
--             RS_IC0_G         => RS_IC0_G,
--             RS_PHINOT_G      => RS_PHINOT_G)
         port map (
            tesBiasP   => tesBiasP,     -- [in]
            tesBiasN   => tesBiasN,     -- [in]
            saBiasOutP => saBiasOutP,   -- [in]
            saBiasOutN => saBiasOutN,   -- [in]
            saBiasInP  => saBiasInP,    -- [out]
            saBiasInN  => saBiasInN,    -- [out]
            saFbP      => saFbP,        -- [in]
            saFbN      => saFbN,        -- [in]
            sq1BiasP   => sq1BiasP,     -- [in]
            sq1BiasN   => sq1BiasN,     -- [in]
            sq1FbP     => sq1FbP,       -- [in]
            sq1FbN     => sq1FbN,       -- [in]
            rsP        => rsP,          -- [in]
            rsN        => rsN);         -- [in]
   end generate WAFTER_GEN;



end sim;
