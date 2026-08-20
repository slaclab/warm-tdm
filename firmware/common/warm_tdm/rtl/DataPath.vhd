-------------------------------------------------------------------------------
-- Title      : Column Module ADC Data Pipeline
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Data pipeline for ADC data
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
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;


library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
use surf.AxiLitePkg.all;
use surf.AxiStreamPacketizer2Pkg.all;
use surf.Ad9681Pkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;
use warm_tdm.WarmTdmPkg.all;

entity DataPath is

   generic (
      TPD_G            : time                 := 1 ns;
      SIMULATION_G     : boolean              := false;
      GEN_ADC_FILTER_G : boolean              := true;
      USE_FLOAT_PID_G  : boolean              := false;
      GEN_PID_DEBUG_G  : boolean              := true;
      ROW_ADDR_BITS_G  : integer range 3 to 8 := 7;
      NEGATE_ADC_G     : boolean              := true;
      INVERT_SQ1FB_G   : boolean              := true;
      AXIL_BASE_ADDR_G : slv(31 downto 0)     := (others => '0');
      SQ1FB_RAM_ADDR_G : slv(31 downto 0)     := (others => '0');
      IODELAY_GROUP_G  : string               := "DEFAULT_GROUP");

   port (
      -- ADC Serial Interface
      adc : in Ad9681SerialType;

      -- Timing interface
      timingRxClk125 : in sl;
      timingRxRst125 : in sl;
      timingRxData   : in LocalTimingType;
      sq1FbDacs      : in Slv14Array(7 downto 0);

      -- Frame-header identity sources. boardId is the PGP ring address (comms
      -- clock domain); groupId is a WarmTdmConfig register value (axilClk). Both
      -- are async on entry, synchronized to timingRxClk125 internally, assembled
      -- into a FrameIdentityType, and fed to the frame builders.
      boardId        : in slv(2 downto 0) := "000";
      groupId        : in slv(7 downto 0) := (others => '0');

      -- Formatted data
      axisClk    : in  sl;
      axisRst    : in  sl;
      axisMaster : out AxiStreamMasterType;
      axisSlave  : in  AxiStreamSlaveType;

      -- Local register access
      axilClk          : in  sl;
      axilRst          : in  sl;
      adcFilterEn      : in  slv(7 downto 0);
      sAxilReadMaster  : in  AxiLiteReadMasterType;
      sAxilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      sAxilWriteMaster : in  AxiLiteWriteMasterType;
      sAxilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      mAxilReadMaster  : out AxiLiteReadMasterType;
      mAxilReadSlave   : in  AxiLiteReadSlaveType;
      mAxilWriteMaster : out AxiLiteWriteMasterType;
      mAxilWriteSlave  : in  AxiLiteWriteSlaveType);

end entity DataPath;

architecture rtl of DataPath is

   constant FILTER_COEFF_WIDTH_C  : integer                                := 25;
   constant FILTER_NUM_TAPS_C     : integer                                := 61;
   constant FILTER_COEFFICIENTS_C : IntegerArray(0 to FILTER_NUM_TAPS_C-1) := ((FILTER_NUM_TAPS_C-1)/2 => (2**FILTER_COEFF_WIDTH_C)-1, others => 0);

   -- Main crossbar config
   constant NUM_AXIL_MASTERS_C   : integer := 8;
   constant ADC_READOUT_AXIL_C   : integer := 0;
   constant WAVEFORM_AXIL_C      : integer := 1;
   constant EVENT_BUILDER_AXIL_C : integer := 2;
   constant ADC_FILTER_AXIL_C    : integer := 3;
   constant ADC_DSP_AXIL_C       : integer := 4;
   constant PID_FILTER_AXIL_C    : integer := 5;
   constant DELAY_AXIL_C         : integer := 6;
   constant ACCUM_AXIL_C         : integer := 7;

   constant XBAR_COFNIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_MASTERS_C, AXIL_BASE_ADDR_G, 24, 20);

   constant ADC_FILTER_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(7 downto 0) := genAxiLiteConfig(8, XBAR_COFNIG_C(ADC_FILTER_AXIL_C).baseAddr, 16, 12);
   constant PID_FILTER_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(7 downto 0) := genAxiLiteConfig(8, XBAR_COFNIG_C(PID_FILTER_AXIL_C).baseAddr, 16, 12);
   constant ADC_DSP_XBAR_CFG_C    : AxiLiteCrossbarMasterConfigArray(7 downto 0) := genAxiLiteConfig(8, XBAR_COFNIG_C(ADC_DSP_AXIL_C).baseAddr, 20, 16);
   constant ACCUM_XBAR_CFG_C      : AxiLiteCrossbarMasterConfigArray(7 downto 0) := genAxiLiteConfig(8, XBAR_COFNIG_C(ACCUM_AXIL_C).baseAddr, 16, 12);

   signal syncAxilReadMaster  : AxiLiteReadMasterType;
   signal syncAxilReadSlave   : AxiLiteReadSlaveType;
   signal syncAxilWriteMaster : AxiLiteWriteMasterType;
   signal syncAxilWriteSlave  : AxiLiteWriteSlaveType;

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);

   signal adcFilterAxilWriteMasters : AxiLiteWriteMasterArray(7 downto 0);
   signal adcFilterAxilWriteSlaves  : AxiLiteWriteSlaveArray(7 downto 0);
   signal adcFilterAxilReadMasters  : AxiLiteReadMasterArray(7 downto 0);
   signal adcFilterAxilReadSlaves   : AxiLiteReadSlaveArray(7 downto 0);

   signal adcDspAxilWriteMasters : AxiLiteWriteMasterArray(7 downto 0);
   signal adcDspAxilWriteSlaves  : AxiLiteWriteSlaveArray(7 downto 0);
   signal adcDspAxilReadMasters  : AxiLiteReadMasterArray(7 downto 0);
   signal adcDspAxilReadSlaves   : AxiLiteReadSlaveArray(7 downto 0);

   signal pidFilterAxilWriteMasters : AxiLiteWriteMasterArray(7 downto 0);
   signal pidFilterAxilWriteSlaves  : AxiLiteWriteSlaveArray(7 downto 0);
   signal pidFilterAxilReadMasters  : AxiLiteReadMasterArray(7 downto 0);
   signal pidFilterAxilReadSlaves   : AxiLiteReadSlaveArray(7 downto 0);

   signal accumAxilWriteMasters : AxiLiteWriteMasterArray(7 downto 0);
   signal accumAxilWriteSlaves  : AxiLiteWriteSlaveArray(7 downto 0);
   signal accumAxilReadMasters  : AxiLiteReadMasterArray(7 downto 0);
   signal accumAxilReadSlaves   : AxiLiteReadSlaveArray(7 downto 0);


   signal adcStreams         : AxiStreamMasterArray(7 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);
   signal filteredAdcStreams : AxiStreamMasterArray(7 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);
   signal selectedAdcStreams : AxiStreamMasterArray(7 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);
   signal adcFilterEnSync    : slv(7 downto 0);

   signal sq1FbAxilWriteMasters : AxiLiteWriteMasterArray(7 downto 0);
   signal sq1FbAxilWriteSlaves  : AxiLiteWriteSlaveArray(7 downto 0);
   signal sq1FbAxilReadMasters  : AxiLiteReadMasterArray(7 downto 0);
   signal sq1FbAxilReadSlaves   : AxiLiteReadSlaveArray(7 downto 0);

   signal sq1FbAxilReadMaster  : AxiLiteReadMasterType;
   signal sq1FbAxilReadSlave   : AxiLiteReadSlaveType;
   signal sq1FbAxilWriteMaster : AxiLiteWriteMasterType;
   signal sq1FbAxilWriteSlave  : AxiLiteWriteSlaveType;

   signal pidStreamMasters       : AxiStreamMasterArray(7 downto 0);
   signal pidStreamSlaves        : AxiStreamSlaveArray(7 downto 0);
   signal pidFilterStreamMasters : AxiStreamMasterArray(7 downto 0);
   signal pidFilterStreamSlaves  : AxiStreamSlaveArray(7 downto 0);


   signal waveformMaster : AxiStreamMasterType;
   signal waveformSlave  : AxiStreamSlaveType;

   signal pidDebugMasters : AxiStreamMasterArray(7 downto 0);
   signal pidDebugSlaves  : AxiStreamSlaveArray(7 downto 0);

   signal pidDebugMaster : AxiStreamMasterType;
   signal pidDebugSlave  : AxiStreamSlaveType;

   signal eventAxisMaster : AxiStreamMasterType;
   signal eventAxisSlave  : AxiStreamSlaveType;

   signal dataAxisMaster : AxiStreamMasterType;
   signal dataAxisSlave  : AxiStreamSlaveType;

   signal timingRxDataDelayed : LocalTimingType;
   signal timingDelayValue    : slv(6 downto 0);
   signal sq1FbDacsDelayed    : Slv14Array(7 downto 0);
   signal selectedSq1FbDacs   : Slv14Array(7 downto 0);

   type AdcAccumResultArray is array (natural range <>) of AdcAccumResultType;
   signal accumResults : AdcAccumResultArray(7 downto 0);
   signal accumValids  : slv(7 downto 0);

   type LocalTimingTypeArray is array (natural range <>) of LocalTimingType;
   signal selectedTimingRxData : LocalTimingTypeArray(7 downto 0);

   -- boardId+groupId synchronized into the timingRxClk125 domain and assembled
   -- into the frame-identity record fed to the builders.
   signal frameIdSyncVec : slv(10 downto 0);
   signal frameId        : FrameIdentityType;

begin

   -- Synchronize the (quasi-static, cross-domain) identity sources into the
   -- builder clock domain before they are packed into the frame-identity header.
   -- boardId (3b, comms domain) and groupId (8b, axilClk) are crossed together.
   U_Synchronizer_FrameId : entity surf.SynchronizerVector
      generic map (
         TPD_G   => TPD_G,
         WIDTH_G => 11)
      port map (
         clk     => timingRxClk125,        -- [in]
         rst     => timingRxRst125,        -- [in]
         dataIn  => groupId & boardId,     -- [in]
         dataOut => frameIdSyncVec);       -- [out]

   frameId.boardId <= frameIdSyncVec(2 downto 0);
   frameId.groupId <= frameIdSyncVec(10 downto 3);

   U_AxiLiteAsync_SRP : entity surf.AxiLiteAsync
      generic map (
         TPD_G => TPD_G)
      port map (
         -- Slave Interface
         sAxiClk         => axilClk,
         sAxiClkRst      => axilRst,
         sAxiReadMaster  => sAxilReadMaster,
         sAxiReadSlave   => sAxilReadSlave,
         sAxiWriteMaster => sAxilWriteMaster,
         sAxiWriteSlave  => sAxilWriteSlave,
         -- Master Interface
         mAxiClk         => timingRxClk125,
         mAxiClkRst      => timingRxRst125,
         mAxiReadMaster  => syncAxilReadMaster,
         mAxiReadSlave   => syncAxilReadSlave,
         mAxiWriteMaster => syncAxilWriteMaster,
         mAxiWriteSlave  => syncAxilWriteSlave);

   -------------------------------------------------------------------------------------------------
   -- AXIL Crossbar
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => XBAR_COFNIG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => timingRxClk125,       -- [in]
         axiClkRst           => timingRxRst125,       -- [in]
         sAxiWriteMasters(0) => syncAxilWriteMaster,  -- [in]
         sAxiWriteSlaves(0)  => syncAxilWriteSlave,   -- [out]
         sAxiReadMasters(0)  => syncAxilReadMaster,   -- [in]
         sAxiReadSlaves(0)   => syncAxilReadSlave,    -- [out]
         mAxiWriteMasters    => locAxilWriteMasters,  -- [out]
         mAxiWriteSlaves     => locAxilWriteSlaves,   -- [in]
         mAxiReadMasters     => locAxilReadMasters,   -- [out]
         mAxiReadSlaves      => locAxilReadSlaves);   -- [in]


   -------------------------------------------------------------------------------------------------
   -- ADC Deserializers
   -------------------------------------------------------------------------------------------------
   U_Ad9681Readout_1 : entity surf.Ad9681Readout2
      generic map (
         TPD_G           => TPD_G,
         IODELAY_GROUP_G => IODELAY_GROUP_G,
         DELAY_BITS_G    => 5,
         DEVICE_FAMILY_G => "7SERIES",
         LEFT_JUSTIFY_G  => true,
         NEGATE_G        => NEGATE_ADC_G)
      port map (
         axilClk         => timingRxClk125,                           -- [in]
         axilRst         => timingRxRst125,                           -- [in]
         axilWriteMaster => locAxilWriteMasters(ADC_READOUT_AXIL_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(ADC_READOUT_AXIL_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(ADC_READOUT_AXIL_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(ADC_READOUT_AXIL_C),    -- [out]
         adcClkRst       => timingRxRst125,                           -- [in]
         idelayCtrlRdy   => '1',                                      -- [in]
         adcSerial       => adc,                                      -- [in]
         adcStreamClk    => timingRxClk125,                           -- [in]
         adcStreamRst    => timingRxRst125,                           -- [in]
         adcStreams      => adcStreams);                              -- [out]

   -------------------------------------------------------------------------------------------------
   -- Crossbar for filters
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_ADC_FILTER : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 8,
         MASTERS_CONFIG_G   => ADC_FILTER_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => timingRxClk125,                          -- [in]
         axiClkRst           => timingRxRst125,                          -- [in]
         sAxiWriteMasters(0) => locAxilWriteMasters(ADC_FILTER_AXIL_C),  -- [in]
         sAxiWriteSlaves(0)  => locAxilWriteSlaves(ADC_FILTER_AXIL_C),   -- [out]
         sAxiReadMasters(0)  => locAxilReadMasters(ADC_FILTER_AXIL_C),   -- [in]
         sAxiReadSlaves(0)   => locAxilReadSlaves(ADC_FILTER_AXIL_C),    -- [out]
         mAxiWriteMasters    => adcFilterAxilWriteMasters,               -- [out]
         mAxiWriteSlaves     => adcFilterAxilWriteSlaves,                -- [in]
         mAxiReadMasters     => adcFilterAxilReadMasters,                -- [out]
         mAxiReadSlaves      => adcFilterAxilReadSlaves);                -- [in]

   -------------------------------------------------------------------------------------------------
   -- Crossbar for ADC_DSP
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_DSP : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 8,
         MASTERS_CONFIG_G   => ADC_DSP_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => timingRxClk125,                       -- [in]
         axiClkRst           => timingRxRst125,                       -- [in]
         sAxiWriteMasters(0) => locAxilWriteMasters(ADC_DSP_AXIL_C),  -- [in]
         sAxiWriteSlaves(0)  => locAxilWriteSlaves(ADC_DSP_AXIL_C),   -- [out]
         sAxiReadMasters(0)  => locAxilReadMasters(ADC_DSP_AXIL_C),   -- [in]
         sAxiReadSlaves(0)   => locAxilReadSlaves(ADC_DSP_AXIL_C),    -- [out]
         mAxiWriteMasters    => adcDspAxilWriteMasters,               -- [out]
         mAxiWriteSlaves     => adcDspAxilWriteSlaves,                -- [in]
         mAxiReadMasters     => adcDspAxilReadMasters,                -- [out]
         mAxiReadSlaves      => adcDspAxilReadSlaves);                -- [in]

   U_AxiLiteCrossbar_PID_FILTER : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 8,
         MASTERS_CONFIG_G   => PID_FILTER_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => timingRxClk125,                          -- [in]
         axiClkRst           => timingRxRst125,                          -- [in]
         sAxiWriteMasters(0) => locAxilWriteMasters(PID_FILTER_AXIL_C),  -- [in]
         sAxiWriteSlaves(0)  => locAxilWriteSlaves(PID_FILTER_AXIL_C),   -- [out]
         sAxiReadMasters(0)  => locAxilReadMasters(PID_FILTER_AXIL_C),   -- [in]
         sAxiReadSlaves(0)   => locAxilReadSlaves(PID_FILTER_AXIL_C),    -- [out]
         mAxiWriteMasters    => pidFilterAxilWriteMasters,               -- [out]
         mAxiWriteSlaves     => pidFilterAxilWriteSlaves,                -- [in]
         mAxiReadMasters     => pidFilterAxilReadMasters,                -- [out]
         mAxiReadSlaves      => pidFilterAxilReadSlaves);                -- [in]

   U_AxiLiteCrossbar_ACCUM : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 8,
         MASTERS_CONFIG_G   => ACCUM_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => timingRxClk125,                      -- [in]
         axiClkRst           => timingRxRst125,                      -- [in]
         sAxiWriteMasters(0) => locAxilWriteMasters(ACCUM_AXIL_C),   -- [in]
         sAxiWriteSlaves(0)  => locAxilWriteSlaves(ACCUM_AXIL_C),    -- [out]
         sAxiReadMasters(0)  => locAxilReadMasters(ACCUM_AXIL_C),    -- [in]
         sAxiReadSlaves(0)   => locAxilReadSlaves(ACCUM_AXIL_C),     -- [out]
         mAxiWriteMasters    => accumAxilWriteMasters,               -- [out]
         mAxiWriteSlaves     => accumAxilWriteSlaves,                -- [in]
         mAxiReadMasters     => accumAxilReadMasters,                -- [out]
         mAxiReadSlaves      => accumAxilReadSlaves);                -- [in]

   -------------------------------------------------------------------------------------------------
   -- Delay timing by 20 cycles to account for ADC Latency
   -------------------------------------------------------------------------------------------------
   U_TimingDelay_1 : entity warm_tdm.TimingDelay
      generic map (
         TPD_G   => TPD_G,
         DELAY_G => 55)
      port map (
         clk             => timingRxClk125,                     -- [in]
         rst             => timingRxRst125,                     -- [in]
         timingIn        => timingRxData,                       -- [in]
         timingOut       => timingRxDataDelayed,                -- [out]
         delayOut        => timingDelayValue,                   -- [out]
         axilWriteMaster => locAxilWriteMasters(DELAY_AXIL_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(DELAY_AXIL_C),   -- [out]
         axilReadMaster  => locAxilReadMasters(DELAY_AXIL_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(DELAY_AXIL_C));   -- [out]

   SQ1FB_DELAY_GEN : for i in 7 downto 0 generate
      U_SlvDelay_Sq1FbDacs : entity surf.SlvDelay
         generic map (
            TPD_G        => TPD_G,
            SRL_EN_G     => true,
            DELAY_G      => 128,
            REG_OUTPUT_G => true,
            WIDTH_G      => 14)
         port map (
            clk   => timingRxClk125,       -- [in]
            en    => '1',                  -- [in]
            delay => timingDelayValue,     -- [in]
            din   => sq1FbDacs(i),         -- [in]
            dout  => sq1FbDacsDelayed(i)); -- [out]
   end generate SQ1FB_DELAY_GEN;


   FIR_FILTER_GEN : for i in 7 downto 0 generate
      signal filterTimingSbOut    : slv(14 downto 0);
      signal filteredSq1FbDac     : slv(13 downto 0);
      signal filteredTimingRxData : LocalTimingType;
   begin

      GEN_ADC_FILTER : if (GEN_ADC_FILTER_G) generate
         U_FirFilterSingleChannel_1 : entity surf.FirFilterSingleChannel
            generic map (
               TPD_G            => TPD_G,
               COMMON_CLK_G     => true,
               NUM_TAPS_G       => FILTER_NUM_TAPS_C,
               SIDEBAND_WIDTH_G => 15+14,
               DATA_WIDTH_G     => 14,
               COEFF_WIDTH_G    => FILTER_COEFF_WIDTH_C,
               COEFFICIENTS_G   => FILTER_COEFFICIENTS_C)
            port map (
               clk                 => timingRxClk125,                  -- [in]
               rst                 => timingRxRst125,                  -- [in]
               ibValid             => adcStreams(i).tvalid,            -- [in]
               din                 => adcStreams(i).tData(15 downto 2),           -- [in]
               sbIn(7 downto 0)    => timingRxDataDelayed.rowIndex,    -- [in]
               sbIn(8)             => timingRxDataDelayed.firstSample,            -- [in]
               sbIn(9)             => timingRxDataDelayed.lastSample,  -- [in]
               sbIn(10)            => timingRxDataDelayed.rowStrobe,   -- [in]
               sbIn(11)            => timingRxDataDelayed.waveformCapture,        -- [in]
               sbIn(12)            => timingRxDataDelayed.sample,      -- [in]
               sbIn(13)            => timingRxDataDelayed.rowSeqStart,            -- [in]
               sbIn(14)            => timingRxDataDelayed.daqReadoutStart,        -- [in]
               sbIn(28 downto 15)  => sq1FbDacsDelayed(i),             -- [in]
               obValid             => filteredAdcStreams(i).tvalid,    -- [out]
               dout                => filteredAdcStreams(i).tData(15 downto 2),   -- [out]
               sbOut(7 downto 0)   => filterTimingSbOut(7 downto 0),  -- [out]
               sbOut(8)            => filterTimingSbOut(8),            -- [out]
               sbOut(9)            => filterTimingSbOut(9),            -- [out]
               sbOut(10)           => filterTimingSbOut(10),           -- [out]
               sbOut(11)           => filterTimingSbOut(11),           -- [out]
               sbOut(12)           => filterTimingSbOut(12),           -- [out]
               sbOut(13)           => filterTimingSbOut(13),           -- [out]
               sbOut(14)           => filterTimingSbOut(14),           -- [out]
               sbOut(28 downto 15) => filteredSq1FbDac,               -- [out]
               axilClk             => timingRxClk125,                  -- [in]
               axilRst             => timingRxRst125,                  -- [in]
               axilReadMaster      => adcFilterAxilReadMasters(i),     -- [in]
               axilReadSlave       => adcFilterAxilReadSlaves(i),      -- [out]
               axilWriteMaster     => adcFilterAxilWriteMasters(i),    -- [in]
               axilWriteSlave      => adcFilterAxilWriteSlaves(i));    -- [out]

         filteredAdcStreams(i).tData(1 downto 0) <= "00";

         filteredTimingRxData.startRun        <= timingRxDataDelayed.startRun;
         filteredTimingRxData.endRun          <= timingRxDataDelayed.endRun;
         filteredTimingRxData.running         <= timingRxDataDelayed.running;
         filteredTimingRxData.runTime         <= timingRxDataDelayed.runTime;
         filteredTimingRxData.stageNextRow    <= timingRxDataDelayed.stageNextRow;
         filteredTimingRxData.rowSeq          <= timingRxDataDelayed.rowSeq;
         filteredTimingRxData.rowIndexNext    <= timingRxDataDelayed.rowIndexNext;
         filteredTimingRxData.rowTime         <= timingRxDataDelayed.rowTime;
         filteredTimingRxData.rowSeqCount     <= timingRxDataDelayed.rowSeqCount;
         filteredTimingRxData.daqReadoutCount <= timingRxDataDelayed.daqReadoutCount;
         filteredTimingRxData.rowIndex        <= filterTimingSbOut(7 downto 0);
         filteredTimingRxData.firstSample     <= filterTimingSbOut(8);
         filteredTimingRxData.lastSample      <= filterTimingSbOut(9);
         filteredTimingRxData.rowStrobe       <= filterTimingSbOut(10);
         filteredTimingRxData.waveformCapture <= filterTimingSbOut(11);
         filteredTimingRxData.sample          <= filterTimingSbOut(12);
         filteredTimingRxData.rowSeqStart     <= filterTimingSbOut(13);
         filteredTimingRxData.daqReadoutStart <= filterTimingSbOut(14);

         U_Synchronizer_1 : entity surf.Synchronizer
            generic map (
               TPD_G => TPD_G)
            port map (
               clk     => timingRxClk125,       -- [in]
               rst     => timingRxRst125,       -- [in]
               dataIn  => adcFilterEn(i),       -- [in]
               dataOut => adcFilterEnSync(i));  -- [out]

         selectedAdcStreams(i)   <= filteredAdcStreams(i) when adcFilterEnSync(i) = '1' else adcStreams(i);
         selectedTimingRxData(i) <= filteredTimingRxData when adcFilterEnSync(i) = '1' else timingRxDataDelayed;
         selectedSq1FbDacs(i)    <= filteredSq1FbDac when adcFilterEnSync(i) = '1' else sq1FbDacsDelayed(i);
      end generate GEN_ADC_FILTER;

      NO_GEN_ADC_FILTER : if (GEN_ADC_FILTER_G = false) generate
         selectedAdcStreams(i)   <= adcStreams(i);
         selectedTimingRxData(i) <= timingRxDataDelayed;
         selectedSq1FbDacs(i)    <= sq1FbDacsDelayed(i);
      end generate NO_GEN_ADC_FILTER;

   end generate FIR_FILTER_GEN;


   U_WaveformCapture_1 : entity warm_tdm.WaveformCapture
      generic map (
         TPD_G => TPD_G)
      port map (
         timingRxClk125  => timingRxClk125,                        -- [in]
         timingRxRst125  => timingRxRst125,                        -- [in]
         timingRxData    => selectedTimingRxData(0),               -- [in]
         frameId         => frameId,                               -- [in]
         adcStreams      => selectedAdcStreams,                    -- [in]
         axilReadMaster  => locAxilReadMasters(WAVEFORM_AXIL_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(WAVEFORM_AXIL_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(WAVEFORM_AXIL_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(WAVEFORM_AXIL_C),   -- [out]
         axisClk         => axisClk,                               -- [in]
         axisRst         => axisRst,                               -- [in]
         axisMaster      => waveformMaster,                        -- [out]
         axisSlave       => waveformSlave);                        -- [in]


   GEN_ADC_DSP : for i in 7 downto 0 generate

      U_AdcAccumulator_1 : entity warm_tdm.AdcAccumulator
         generic map (
            TPD_G           => TPD_G,
            ROW_ADDR_BITS_G => ROW_ADDR_BITS_G)
         port map (
            clk             => timingRxClk125,              -- [in]
            rst             => timingRxRst125,              -- [in]
            timingRxData    => selectedTimingRxData(i),     -- [in]
            adcValid        => selectedAdcStreams(i).tValid, -- [in]
            adcData         => selectedAdcStreams(i).tData(15 downto 0), -- [in]
            sq1FbDac        => selectedSq1FbDacs(i),        -- [in]
            accumOut        => accumResults(i),             -- [out]
            accumValid      => accumValids(i),             -- [out]
            axilReadMaster  => accumAxilReadMasters(i),     -- [in]
            axilReadSlave   => accumAxilReadSlaves(i),      -- [out]
            axilWriteMaster => accumAxilWriteMasters(i),    -- [in]
            axilWriteSlave  => accumAxilWriteSlaves(i));    -- [out]

      GEN_FIXED_PID : if (not USE_FLOAT_PID_G) generate
         U_AdcDsp_1 : entity warm_tdm.AdcDsp
            generic map (
               TPD_G            => TPD_G,
               SIMULATION_G     => SIMULATION_G,
               COLUMN_NUM_G     => i,
               INVERT_SQ1FB_G   => INVERT_SQ1FB_G,
               ROW_ADDR_BITS_G  => ROW_ADDR_BITS_G,
               GEN_PID_DEBUG_G  => GEN_PID_DEBUG_G,
               AXIL_BASE_ADDR_G => ADC_DSP_XBAR_CFG_C(i).baseAddr,
               SQ1FB_RAM_ADDR_G => SQ1FB_RAM_ADDR_G(31 downto 16) & toslv(i, 4) & X"000")
            port map (
               timingRxClk125   => timingRxClk125,
               timingRxRst125   => timingRxRst125,
               timingRxData     => selectedTimingRxData(i),
               frameId          => frameId,
               accumIn          => accumResults(i),
               accumValid       => accumValids(i),
               sAxilReadMaster  => adcDspAxilReadMasters(i),
               sAxilReadSlave   => adcDspAxilReadSlaves(i),
               sAxilWriteMaster => adcDspAxilWriteMasters(i),
               sAxilWriteSlave  => adcDspAxilWriteSlaves(i),
               mAxilReadMaster  => sq1fbAxilReadMasters(i),
               mAxilReadSlave   => sq1fbAxilReadSlaves(i),
               mAxilWriteMaster => sq1fbAxilWriteMasters(i),
               mAxilWriteSlave  => sq1fbAxilWriteSlaves(i),
               pidStreamMaster  => pidStreamMasters(i),
               pidStreamSlave   => pidStreamSlaves(i),
               axisClk          => axisClk,
               axisRst          => axisRst,
               pidDebugMaster   => pidDebugMasters(i),
               pidDebugSlave    => pidDebugSlaves(i));
      end generate GEN_FIXED_PID;

      GEN_FLOAT_PID : if (USE_FLOAT_PID_G) generate
         U_AdcDspFp_1 : entity warm_tdm.AdcDspFp
            generic map (
               TPD_G            => TPD_G,
               SIMULATION_G     => SIMULATION_G,
               COLUMN_NUM_G     => i,
               INVERT_SQ1FB_G   => INVERT_SQ1FB_G,
               ROW_ADDR_BITS_G  => ROW_ADDR_BITS_G,
               GEN_PID_DEBUG_G  => GEN_PID_DEBUG_G,
               AXIL_BASE_ADDR_G => ADC_DSP_XBAR_CFG_C(i).baseAddr,
               SQ1FB_RAM_ADDR_G => SQ1FB_RAM_ADDR_G(31 downto 16) & toslv(i, 4) & X"000")
            port map (
               timingRxClk125   => timingRxClk125,
               timingRxRst125   => timingRxRst125,
               timingRxData     => selectedTimingRxData(i),
               frameId          => frameId,
               accumIn          => accumResults(i),
               accumValid       => accumValids(i),
               sAxilReadMaster  => adcDspAxilReadMasters(i),
               sAxilReadSlave   => adcDspAxilReadSlaves(i),
               sAxilWriteMaster => adcDspAxilWriteMasters(i),
               sAxilWriteSlave  => adcDspAxilWriteSlaves(i),
               mAxilReadMaster  => sq1fbAxilReadMasters(i),
               mAxilReadSlave   => sq1fbAxilReadSlaves(i),
               mAxilWriteMaster => sq1fbAxilWriteMasters(i),
               mAxilWriteSlave  => sq1fbAxilWriteSlaves(i),
               pidStreamMaster  => pidStreamMasters(i),
               pidStreamSlave   => pidStreamSlaves(i),
               axisClk          => axisClk,
               axisRst          => axisRst,
               pidDebugMaster   => pidDebugMasters(i),
               pidDebugSlave    => pidDebugSlaves(i));
      end generate GEN_FLOAT_PID;

      U_BiquadFilter_1 : entity warm_tdm.BiquadFilter
         generic map (
            TPD_G                => TPD_G,
            CASCADE_SIZE_G       => 2,
            CHANNEL_ADDR_WIDTH_G => ROW_ADDR_BITS_G,
            INPUT_IS_FLOAT_G     => USE_FLOAT_PID_G)
         port map (
            axisClk         => timingRxClk125,
            axisRst         => timingRxRst125,
            sAxisMaster     => pidStreamMasters(i),
            sAxisSlave      => pidStreamSlaves(i),
            mAxisMaster     => pidFilterStreamMasters(i),
            mAxisSlave      => pidFilterStreamSlaves(i),
            axilReadMaster  => pidFilterAxilReadMasters(i),
            axilReadSlave   => pidFilterAxilReadSlaves(i),
            axilWriteMaster => pidFilterAxilWriteMasters(i),
            axilWriteSlave  => pidFilterAxilWriteSlaves(i));
   end generate;

   U_EventBuilder_1 : entity warm_tdm.EventBuilder
      generic map (
         TPD_G => TPD_G)
      port map (
         timingRxClk125   => timingRxClk125,                             -- [in]
         timingRxRst125   => timingRxRst125,                             -- [in]
         frameId          => frameId,                                    -- [in]
         timingRxData     => timingRxDataDelayed,                        -- [in]
         pidStreamMasters => pidFilterStreamMasters,                     -- [out]
         pidStreamSlaves  => pidFilterStreamSlaves,                      -- [in]
         axilReadMaster   => locAxilReadMasters(EVENT_BUILDER_AXIL_C),   -- [in]
         axilReadSlave    => locAxilReadSlaves(EVENT_BUILDER_AXIL_C),    -- [out]
         axilWriteMaster  => locAxilWriteMasters(EVENT_BUILDER_AXIL_C),  -- [in]
         axilWriteSlave   => locAxilWriteSlaves(EVENT_BUILDER_AXIL_C),   -- [out]
         axisClk          => axisClk,                                    -- [in]
         axisRst          => axisRst,                                    -- [in]
         eventAxisMaster  => eventAxisMaster,                            -- [out]
         eventAxisSlave   => eventAxisSlave);                            -- [in]


   -- Multiplex debug streams
   U_AxiStreamMux_1 : entity surf.AxiStreamMux
      generic map (
         TPD_G         => TPD_G,
         PIPE_STAGES_G => 1,
         NUM_SLAVES_G  => 8,
         MODE_G        => "INDEXED")
      port map (
         axisClk      => axisClk,          -- [in]
         axisRst      => axisRst,          -- [in]
         sAxisMasters => pidDebugMasters,  -- [in]
         sAxisSlaves  => pidDebugSlaves,   -- [out]
         mAxisMaster  => pidDebugMaster,   -- [out]
         mAxisSlave   => pidDebugSlave);   -- [in]

   -- Multiplex all streams together
   -- Investigate interleaving here
   U_AxiStreamMux_2 : entity surf.AxiStreamMux
      generic map (
         TPD_G          => TPD_G,
         PIPE_STAGES_G  => 1,
         NUM_SLAVES_G   => 3,
         MODE_G         => "ROUTED",
         TDEST_ROUTES_G => (
            0           => "00000---",  -- pid debug
            1           => "00001000",        -- waveform
            2           => "00001001"))       -- data
      port map (
         axisClk         => axisClk,          -- [in]
         axisRst         => axisRst,          -- [in]
         sAxisMasters(0) => pidDebugMaster,   -- [in]
         sAxisMasters(1) => waveformMaster,   -- [in]
         sAxisMasters(2) => eventAxisMaster,  -- [in]
         sAxisSlaves(0)  => pidDebugSlave,    -- [out]
         sAxisSlaves(1)  => waveformSlave,    -- [out]
         sAxisSlaves(2)  => eventAxisSlave,   -- [out]
         mAxisMaster     => dataAxisMaster,   -- [out]
         mAxisSlave      => dataAxisSlave);   -- [in]

   -- Packetize everything
   U_AxiStreamPacketizer2_1 : entity surf.AxiStreamPacketizer2
      generic map (
         TPD_G                => TPD_G,
         MEMORY_TYPE_G        => "distributed",
         REG_EN_G             => false,
         CRC_MODE_G           => "NONE",
         MAX_PACKET_BYTES_G   => 256,
         TDEST_BITS_G         => 8,
         OUTPUT_TDEST_G       => "00001000",  -- Direct stream to eth on ring addr 0
         INPUT_PIPE_STAGES_G  => 1,
         OUTPUT_PIPE_STAGES_G => 1)
      port map (
         axisClk     => axisClk,              -- [in]
         axisRst     => axisRst,              -- [in]
         sAxisMaster => dataAxisMaster,       -- [in]
         sAxisSlave  => dataAxisSlave,        -- [out]
         mAxisMaster => axisMaster,           -- [out]
         mAxisSlave  => axisSlave);           -- [in]   


   -- Combine Sq1 masters into single bus
   U_AxiLiteCrossbar_SQ1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 8,
         NUM_MASTER_SLOTS_G => 1,
         MASTERS_CONFIG_G   => (
            0               => (
               baseAddr     => (others => '0'),
               addrBits     => 32,
               connectivity => X"FFFF")))
      port map (
         axiClk              => timingRxClk125,         -- [in]
         axiClkRst           => timingRxRst125,         -- [in]
         sAxiWriteMasters    => sq1fbAxilWriteMasters,  -- [in]
         sAxiWriteSlaves     => sq1fbAxilWriteSlaves,   -- [out]
         sAxiReadMasters     => sq1fbAxilReadMasters,   -- [in]
         sAxiReadSlaves      => sq1fbAxilReadSlaves,    -- [out]
         mAxiWriteMasters(0) => sq1FbAxilWriteMaster,   -- [out]
         mAxiWriteSlaves(0)  => sq1FbAxilWriteSlave,    -- [in]
         mAxiReadMasters(0)  => sq1FbAxilReadMaster,    -- [out]
         mAxiReadSlaves(0)   => sq1FbAxilReadSlave);    -- [in]

   -- Synchronize bus to axil clock
   U_AxiLiteAsync_SQ1 : entity surf.AxiLiteAsync
      generic map (
         TPD_G => TPD_G)
      port map (
         sAxiClk         => timingRxClk125,
         sAxiClkRst      => timingRxRst125,
         sAxiReadMaster  => sq1FbAxilReadMaster,
         sAxiReadSlave   => sq1FbAxilReadSlave,
         sAxiWriteMaster => sq1FbAxilWriteMaster,
         sAxiWriteSlave  => sq1FbAxilWriteSlave,
         mAxiClk         => axilClk,
         mAxiClkRst      => axilRst,
         mAxiReadMaster  => mAxilReadMaster,
         mAxiReadSlave   => mAxilReadSlave,
         mAxiWriteMaster => mAxilWriteMaster,
         mAxiWriteSlave  => mAxilWriteSlave);

end architecture rtl;
