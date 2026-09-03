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
use warm_tdm.WaferSimPkg.all;

entity GroupTb is
   generic (
      LOAD_G          : string               := "WAFER";
      COLUMN_BOARDS_G : integer range 1 to 3 := 1;
      NUM_DETECTORS_G : integer range 1 to 2 := 1);
end GroupTb;

architecture sim of GroupTb is

   function simulatedColumnsPerDetector (
      physicalColumns : positive;
      warmColumns     : positive;
      numDetectors    : positive)
      return positive is
      variable available : natural;
   begin
      available := warmColumns / numDetectors;
      if available = 0 then
         return 1;
      elsif available < physicalColumns then
         return available;
      else
         return physicalColumns;
      end if;
   end function simulatedColumnsPerDetector;

   constant SIM_PGP_GT_C : boolean := true;

   constant COLUMN_BOARDS_C : integer := COLUMN_BOARDS_G;
   constant ROW_BOARDS_C    : integer := 1;

   constant AWAXE_G : boolean := false;

   constant WAFER_PROFILE_C : WaferProfileType := waferProfile(LOAD_G);

   constant NUM_ROW_SELECTS_G  : integer range 1 to 32 :=
      WAFER_PROFILE_C.topology.rowsPerBank;
   constant NUM_CHIP_SELECTS_G : integer range 0 to 8  :=
      ite(WAFER_PROFILE_C.topology.twoLevel,
          WAFER_PROFILE_C.topology.numBanks, 0);

   constant GROUP_SIZE_C : integer := COLUMN_BOARDS_C + ROW_BOARDS_C;
   constant TPD_G        : time    := 1 ns;
   constant NUM_WARM_COLUMNS_C : positive := COLUMN_BOARDS_C*8;
   constant NUM_WARM_ROW_LINES_C : positive := ROW_BOARDS_C*32;
   constant COLUMNS_PER_DETECTOR_C : positive :=
      simulatedColumnsPerDetector(
         WAFER_PROFILE_C.topology.physicalColumns,
         NUM_WARM_COLUMNS_C,
         NUM_DETECTORS_G);
   constant WARM_DETECTOR_MAP_C : IntegerVector(0 to NUM_WARM_COLUMNS_C-1) :=
      presetWarmDetectorMap(
         LOAD_G, NUM_WARM_COLUMNS_C, NUM_DETECTORS_G,
         COLUMNS_PER_DETECTOR_C);
   constant WARM_COLUMN_MAP_C : IntegerVector(0 to NUM_WARM_COLUMNS_C-1) :=
      presetWarmColumnMap(
         LOAD_G, NUM_WARM_COLUMNS_C, NUM_DETECTORS_G,
         COLUMNS_PER_DETECTOR_C);
   constant RS_LINE_MAP_C : IntegerVector(
      0 to NUM_DETECTORS_G*WAFER_PROFILE_C.topology.rowsPerBank-1) :=
      presetRsLineMap(
         LOAD_G, NUM_DETECTORS_G,
         WAFER_PROFILE_C.topology.rowsPerBank,
         WAFER_PROFILE_C.topology.numBanks,
         WAFER_PROFILE_C.topology.twoLevel);
   constant CS_LINE_MAP_C : IntegerVector(
      0 to NUM_DETECTORS_G*WAFER_PROFILE_C.topology.numBanks-1) :=
      presetCsLineMap(
         LOAD_G, NUM_DETECTORS_G,
         WAFER_PROFILE_C.topology.rowsPerBank,
         WAFER_PROFILE_C.topology.numBanks,
         WAFER_PROFILE_C.topology.twoLevel);

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

   signal columnDrive : ColumnCryoDriveArray(0 to NUM_WARM_COLUMNS_C-1) :=
      (others => ZERO_COLUMN_CRYO_DRIVE_C);
   signal columnSense : ColumnCryoSenseArray(0 to NUM_WARM_COLUMNS_C-1) :=
      (others => ZERO_COLUMN_CRYO_SENSE_C);
   signal rowSelectDrive : DifferentialSourceArray(
      0 to NUM_WARM_ROW_LINES_C-1) :=
      (others => ZERO_DIFFERENTIAL_SOURCE_C);


begin

   assert validLoadName(LOAD_G)
      report "GroupTb: LOAD_G must be LOAD_BOARD, WAFER, WAFER_32, " &
             "BICEP3, NIST_50R, or BA4"
      severity failure;
   assert NUM_WARM_COLUMNS_C >= NUM_DETECTORS_G
      report "GroupTb: each detector needs at least one warm column"
      severity failure;
   assert NUM_DETECTORS_G*topologySelectLines(WAFER_PROFILE_C.topology) <=
          NUM_WARM_ROW_LINES_C
      report "GroupTb: detector assembly needs more physical select lines"
      severity failure;

   GEN_COL_BOARDS : for i in 0 to COLUMN_BOARDS_C-1 generate
      signal localTesBiasP   : RealArray(7 downto 0);
      signal localTesBiasN   : RealArray(7 downto 0);
      signal localSaBiasOutP : CurrentArray(7 downto 0);
      signal localSaBiasOutN : CurrentArray(7 downto 0);
      signal localSaBiasInP  : RealArray(7 downto 0);
      signal localSaBiasInN  : RealArray(7 downto 0);
      signal localSaFbP      : CurrentArray(7 downto 0);
      signal localSaFbN      : CurrentArray(7 downto 0);
      signal localSq1BiasP   : CurrentArray(7 downto 0);
      signal localSq1BiasN   : CurrentArray(7 downto 0);
      signal localSq1FbP     : CurrentArray(7 downto 0);
      signal localSq1FbN     : CurrentArray(7 downto 0);
   begin
      U_ColumnFpgaBoardSim : entity warm_tdm.ColumnFpgaBoardSim
         generic map (
            TPD_G                   => TPD_G,
            RING_ADDR_0_G           => (i = 0),
            AWAXE_G                 => AWAXE_G,
            SIM_PGP_PORT_NUM_G      => 7000 + (40 *i),  --ite(SIM_PGP_GT_C, 0, 7000),
            SIM_ETH_SRP_PORT_NUM_G  => 10000 + (i * 1000),
            SIM_ETH_DATA_PORT_NUM_G => 20000 + (i * 1000))
         port map (
            tesBiasP   => localTesBiasP,
            tesBiasN   => localTesBiasN,
            saBiasOutP => localSaBiasOutP,
            saBiasOutN => localSaBiasOutN,
            saBiasInP  => localSaBiasInP,
            saBiasInN  => localSaBiasInN,
            saFbP      => localSaFbP,
            saFbN      => localSaFbN,
            sq1BiasP   => localSq1BiasP,
            sq1BiasN   => localSq1BiasN,
            sq1FbP     => localSq1FbP,
            sq1FbN     => localSq1FbN,

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

      WAFER_CONNECTION : if LOAD_G /= "LOAD_BOARD" generate
         GEN_CHANNELS : for channel in 0 to 7 generate
            constant WARM_COLUMN_C : natural := i*8 + channel;
         begin
            columnDrive(WARM_COLUMN_C).tesBias.p <= localTesBiasP(channel);
            columnDrive(WARM_COLUMN_C).tesBias.n <= localTesBiasN(channel);
            columnDrive(WARM_COLUMN_C).ssaBias.p <= localSaBiasOutP(channel);
            columnDrive(WARM_COLUMN_C).ssaBias.n <= localSaBiasOutN(channel);
            columnDrive(WARM_COLUMN_C).ssaFeedback.p <= localSaFbP(channel);
            columnDrive(WARM_COLUMN_C).ssaFeedback.n <= localSaFbN(channel);
            columnDrive(WARM_COLUMN_C).sq1Bias.p <= localSq1BiasP(channel);
            columnDrive(WARM_COLUMN_C).sq1Bias.n <= localSq1BiasN(channel);
            columnDrive(WARM_COLUMN_C).sq1Feedback.p <= localSq1FbP(channel);
            columnDrive(WARM_COLUMN_C).sq1Feedback.n <= localSq1FbN(channel);
            localSaBiasInP(channel) <=
               columnSense(WARM_COLUMN_C).ssaVoltage.p;
            localSaBiasInN(channel) <=
               columnSense(WARM_COLUMN_C).ssaVoltage.n;
         end generate GEN_CHANNELS;
      end generate WAFER_CONNECTION;

      LOAD_BOARD_CONNECTION : if LOAD_G = "LOAD_BOARD" generate
         U_ColumnLoadBoard : entity warm_tdm.ColumnLoadBoard
            port map (
               tesBiasP   => localTesBiasP,
               tesBiasN   => localTesBiasN,
               saBiasOutP => localSaBiasOutP,
               saBiasOutN => localSaBiasOutN,
               saBiasInP  => localSaBiasInP,
               saBiasInN  => localSaBiasInN,
               saFbP      => localSaFbP,
               saFbN      => localSaFbN,
               sq1BiasP   => localSq1BiasP,
               sq1BiasN   => localSq1BiasN,
               sq1FbP     => localSq1FbP,
               sq1FbN     => localSq1FbN);
      end generate LOAD_BOARD_CONNECTION;

   end generate GEN_COL_BOARDS;

   GEN_ROW_BOARDS : for i in COLUMN_BOARDS_C to GROUP_SIZE_C-1 generate
      constant ROW_BOARD_C : natural := i-COLUMN_BOARDS_C;
      signal localRsP : CurrentArray(31 downto 0);
      signal localRsN : CurrentArray(31 downto 0);
   begin
      U_RowFpgaBoardSim : entity warm_tdm.RowFpgaBoardSim
         generic map (
            TPD_G                   => TPD_G,
            RING_ADDR_0_G           => (i = 0),
            SIM_PGP_PORT_NUM_G      => 70000 + (40*i),  --7000 + 40,
            SIM_ETH_SRP_PORT_NUM_G  => 10000 + (i * 1000),
            SIM_ETH_DATA_PORT_NUM_G => 20000 + (i * 1000),
            NUM_WAFERS_G            => NUM_DETECTORS_G,
            NUM_ROW_SELECTS_G       => NUM_ROW_SELECTS_G,
            NUM_CHIP_SELECTS_G      => NUM_CHIP_SELECTS_G)
         port map (
            rsP => localRsP,                            -- [out]
            rsN => localRsN,                            -- [out]

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

      WAFER_CONNECTION : if LOAD_G /= "LOAD_BOARD" generate
         GEN_LINES : for line in 0 to 31 generate
            constant WARM_LINE_C : natural := ROW_BOARD_C*32 + line;
         begin
            rowSelectDrive(WARM_LINE_C).p <= localRsP(line);
            rowSelectDrive(WARM_LINE_C).n <= localRsN(line);
         end generate GEN_LINES;
      end generate WAFER_CONNECTION;

      LOAD_BOARD_CONNECTION : if LOAD_G = "LOAD_BOARD" generate
         U_RowLoadBoard : entity warm_tdm.RowLoadBoard
            port map (
               rsP => localRsP,
               rsN => localRsN);
      end generate LOAD_BOARD_CONNECTION;

   end generate GEN_ROW_BOARDS;

   WAFER_GEN : if (LOAD_G /= "LOAD_BOARD") generate
      U_GroupDetectorHarness : entity warm_tdm.GroupDetectorHarnessSim
         generic map (
            NUM_WARM_COLUMNS_G     => NUM_WARM_COLUMNS_C,
            NUM_WARM_ROW_LINES_G   => NUM_WARM_ROW_LINES_C,
            NUM_DETECTORS_G        => NUM_DETECTORS_G,
            COLUMNS_PER_DETECTOR_G => COLUMNS_PER_DETECTOR_C,
            NUM_BANKS_G            => WAFER_PROFILE_C.topology.numBanks,
            ROWS_PER_BANK_G        => WAFER_PROFILE_C.topology.rowsPerBank,
            TWO_LEVEL_G            => WAFER_PROFILE_C.topology.twoLevel,
            WARM_DETECTOR_MAP_G    => WARM_DETECTOR_MAP_C,
            WARM_COLUMN_MAP_G      => WARM_COLUMN_MAP_C,
            RS_LINE_MAP_G          => RS_LINE_MAP_C,
            CS_LINE_MAP_G          => CS_LINE_MAP_C,
            SSA_PARAMS_G           => WAFER_PROFILE_C.ssa,
            SQ1_PARAMS_G           => WAFER_PROFILE_C.sq1,
            ROW_FAS_PARAMS_G       => WAFER_PROFILE_C.rowFas,
            CHIP_FAS_PARAMS_G      => WAFER_PROFILE_C.chipFas,
            COLUMN_PARAMS_G        => WAFER_PROFILE_C.muxColumn)
         port map (
            columnDrive    => columnDrive,
            columnSense    => columnSense,
            rowSelectDrive => rowSelectDrive);
   end generate WAFER_GEN;



end sim;
