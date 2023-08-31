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
      TPD_G            : time             := 1 ns;
      SIMULATION_G     : boolean          := false;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := (others => '0');
      SQ1FB_RAM_ADDR_G : slv(31 downto 0) := (others => '0');
      IODELAY_GROUP_G  : string           := "DEFAULT_GROUP");

   port (
      -- ADC Serial Interface
      adc : in Ad9681SerialType;

      -- Timing interface
      timingRxClk125 : in sl;
      timingRxRst125 : in sl;
      timingRxData   : in LocalTimingType;
      sq1FbDacs      : in Slv14Array(7 downto 0);

      -- Formatted data
      axisClk    : in  sl;
      axisRst    : in  sl;
      axisMaster : out AxiStreamMasterType;
      axisSlave  : in  AxiStreamSlaveType;

      -- Local register access
      axilClk          : in  sl;
      axilRst          : in  sl;
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

   constant FILTER_COEFFICIENTS_C : IntegerArray(0 to 40) := (20 => 2**24-1, others => 0);

   constant NUM_AXIL_MASTERS_C : integer                                                         := 11;
   constant XBAR_COFNIG_C      : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_MASTERS_C, AXIL_BASE_ADDR_G, 20, 16);

   constant FILTER_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(7 downto 0) := genAxiLiteConfig(8, XBAR_COFNIG_C(10).baseAddr, 16, 12);

   signal syncAxilReadMaster  : AxiLiteReadMasterType;
   signal syncAxilReadSlave   : AxiLiteReadSlaveType;
   signal syncAxilWriteMaster : AxiLiteWriteMasterType;
   signal syncAxilWriteSlave  : AxiLiteWriteSlaveType;

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);

   signal filterAxilWriteMasters : AxiLiteWriteMasterArray(7 downto 0);
   signal filterAxilWriteSlaves  : AxiLiteWriteSlaveArray(7 downto 0);
   signal filterAxilReadMasters  : AxiLiteReadMasterArray(7 downto 0);
   signal filterAxilReadSlaves   : AxiLiteReadSlaveArray(7 downto 0);


   signal adcStreams         : AxiStreamMasterArray(7 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);
   signal filteredAdcStreams : AxiStreamMasterArray(7 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);

   signal sq1FbAxilWriteMasters : AxiLiteWriteMasterArray(7 downto 0);
   signal sq1FbAxilWriteSlaves  : AxiLiteWriteSlaveArray(7 downto 0);
   signal sq1FbAxilReadMasters  : AxiLiteReadMasterArray(7 downto 0);
   signal sq1FbAxilReadSlaves   : AxiLiteReadSlaveArray(7 downto 0);

   signal sq1FbAxilReadMaster  : AxiLiteReadMasterType;
   signal sq1FbAxilReadSlave   : AxiLiteReadSlaveType;
   signal sq1FbAxilWriteMaster : AxiLiteWriteMasterType;
   signal sq1FbAxilWriteSlave  : AxiLiteWriteSlaveType;

   signal waveformMaster : AxiStreamMasterType;
   signal waveformSlave  : AxiStreamSlaveType;

   signal pidDebugMasters : AxiStreamMasterArray(7 downto 0);
   signal pidDebugSlaves  : AxiStreamSlaveArray(7 downto 0);

   signal pidDebugMaster : AxiStreamMasterType;
   signal pidDebugSlave  : AxiStreamSlaveType;

   signal dataAxisMaster : AxiStreamMasterType;
   signal dataAxisSlave  : AxiStreamSlaveType;

begin

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
   U_Ad9681Readout_1 : entity surf.Ad9681Readout
      generic map (
         TPD_G           => TPD_G,
         SIMULATION_G    => SIMULATION_G,
         DEFAULT_DELAY_G => 12,
         IODELAY_GROUP_G => IODELAY_GROUP_G,
         NEGATE_G        => true)
      port map (
         axilClk         => timingRxClk125,          -- [in]
         axilRst         => timingRxRst125,          -- [in]
         axilWriteMaster => locAxilWriteMasters(0),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(0),   -- [out]
         axilReadMaster  => locAxilReadMasters(0),   -- [in]
         axilReadSlave   => locAxilReadSlaves(0),    -- [out]
         adcClkRst       => timingRxRst125,          -- [in]
         adcSerial       => adc,                     -- [in]
         adcStreamClk    => timingRxClk125,          -- [in]
         adcStreams      => adcStreams);             -- [out]

   -------------------------------------------------------------------------------------------------
   -- Crossbar for filters
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_FILTER : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 8,
         MASTERS_CONFIG_G   => FILTER_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => timingRxClk125,           -- [in]
         axiClkRst           => timingRxRst125,           -- [in]
         sAxiWriteMasters(0) => locAxilWriteMasters(10),  -- [in]
         sAxiWriteSlaves(0)  => locAxilWriteSlaves(10),   -- [out]
         sAxiReadMasters(0)  => locAxilReadMasters(10),   -- [in]
         sAxiReadSlaves(0)   => locAxilReadSlaves(10),    -- [out]
         mAxiWriteMasters    => filterAxilWriteMasters,   -- [out]
         mAxiWriteSlaves     => filterAxilWriteSlaves,    -- [in]
         mAxiReadMasters     => filterAxilReadMasters,    -- [out]
         mAxiReadSlaves      => filterAxilReadSlaves);    -- [in]


   FIR_FILTER_GEN : for i in 7 downto 0 generate
--       U_FirFilterSingleChannel_1 : entity surf.FirFilterSingleChannel
--          generic map (
--             TPD_G            => TPD_G,
--             COMMON_CLK_G     => true,
--             NUM_TAPS_G       => 41,
--             SIDEBAND_WIDTH_G => 11+14,
--             DATA_WIDTH_G     => 16,
--             COEFF_WIDTH_G    => 26,
--             COEFFICIENTS_G   => FILTER_COEFFICIENTS_C)
--          port map (
--             clk                 => timingRxClk125,                             -- [in]
--             rst                 => timingRxRst125,                             -- [in]
--             ibValid             => adcStreams(i).tvalid,                       -- [in]
--             din                 => adcStreams(i).tData(15 downto 0),           -- [in]
--             sbIn(7 downto 0)    => timingRxData.rowIndex,                      -- [in]
--             sbIn(8)             => timingRxData.firstSample,                   -- [in]
--             sbIn(9)             => timingRxData.lastSample,                    -- [in]
--             sbIn(10)            => timingRxData.rowStrobe,                     -- [in]
--             sbIn(24 downto 11)  => sq1FbDacs(i),                               -- [in]
--             obValid             => filteredAdcStreams(i).tvalid,               -- [out]
--             dout                => filteredAdcStreams(i).tData(15 downto 0),   -- [out]
--             sbOut(7 downto 0)   => filteredAdcStreams(i).tid(7 downto 0),      -- [out]
--             sbOut(8)            => filteredAdcStreams(i).tUser(0),             -- [out]
--             sbOut(9)            => filteredAdcStreams(i).tUser(1),             -- [out]
--             sbOut(10)           => filteredAdcStreams(i).tUser(2),             -- [out]
--             sbOut(24 downto 11) => filteredAdcStreams(i).tData(29 downto 16),  -- [out]
--             axilClk             => timingRxClk125,                             -- [in]
--             axilRst             => timingRxRst125,                             -- [in]
--             axilReadMaster      => filterAxilReadMasters(i),                   -- [in]
--             axilReadSlave       => filterAxilReadSlaves(i),                    -- [out]
--             axilWriteMaster     => filterAxilWriteMasters(i),                  -- [in]
--             axilWriteSlave      => filterAxilWriteSlaves(i));                  -- [out]

      filteredAdcStreams(i).tValid              <= adcStreams(i).tValid;
      filteredAdcStreams(i).tData(15 downto 0)  <= adcStreams(i).tData(15 downto 0);
      filteredAdcStreams(i).tid(7 downto 0)     <= timingRxData.rowIndex;
      filteredAdcStreams(i).tuser(0)            <= timingRxData.firstSample;
      filteredAdcStreams(i).tuser(1)            <= timingRxData.lastSample;
      filteredAdcStreams(i).tuser(2)            <= timingRxData.rowStrobe;
      filteredAdcStreams(i).tData(29 downto 16) <= sq1FbDacs(i);

   end generate FIR_FILTER_GEN;




   U_WaveformCapture_1 : entity warm_tdm.WaveformCapture
      generic map (
         TPD_G => TPD_G)
      port map (
         timingRxClk125  => timingRxClk125,          -- [in]
         timingRxRst125  => timingRxRst125,          -- [in]
         timingRxData    => timingRxData,            -- [in]
         adcStreams      => filteredAdcStreams,      -- [in]
         axilReadMaster  => locAxilReadMasters(9),   -- [in]
         axilReadSlave   => locAxilReadSlaves(9),    -- [out]
         axilWriteMaster => locAxilWriteMasters(9),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(9),   -- [out]
         axisClk         => axisClk,                 -- [in]
         axisRst         => axisRst,                 -- [in]
         axisMaster      => waveformMaster,          -- [out]
         axisSlave       => waveformSlave);          -- [in]


   GEN_ADC_DSP : for i in 7 downto 0 generate
      U_AdcDsp_1 : entity warm_tdm.AdcDsp
         generic map (
            TPD_G            => TPD_G,
            COLUMN_NUM_G     => i,
            AXIL_BASE_ADDR_G => XBAR_COFNIG_C(i+1).baseAddr,
            SQ1FB_RAM_ADDR_G => SQ1FB_RAM_ADDR_G(31 downto 16) & toslv(i, 4) & X"000")
         port map (
            timingRxClk125   => timingRxClk125,            -- [in]
            timingRxRst125   => timingRxRst125,            -- [in]
            timingRxData     => timingRxData,              -- [in]
            adcAxisMaster    => filteredAdcStreams(i),     -- [in]
--             axilClk         => timingRxClk125,            -- [in]
--             axilRst         => timingRxRst125,            -- [in]
            sAxilReadMaster  => locAxilReadMasters(i+1),   -- [in]
            sAxilReadSlave   => locAxilReadSlaves(i+1),    -- [out]
            sAxilWriteMaster => locAxilWriteMasters(i+1),  -- [in]
            sAxilWriteSlave  => locAxilWriteSlaves(i+1),   -- [out]
            mAxilReadMaster  => sq1fbAxilReadMasters(i),   -- [out]
            mAxilReadSlave   => sq1fbAxilReadSlaves(i),    -- [in]
            mAxilWriteMaster => sq1fbAxilWriteMasters(i),  -- [out]
            mAxilWriteSlave  => sq1fbAxilWriteSlaves(i),   -- [in]
            axisClk          => axisClk,                   -- [in]
            axisRst          => axisRst,                   -- [in]
            pidDebugMaster   => pidDebugMasters(i),        -- [out]
            pidDebugSlave    => pidDebugSlaves(i));        -- [in]            
   end generate;

--    axisMaster        <= pidDebugMasters(0);
--    pidDebugSlaves(0) <= axisSlave;

   -- Multiplex debug streams
   U_AxiStreamMux_1 : entity surf.AxiStreamMux
      generic map (
         TPD_G         => TPD_G,
         PIPE_STAGES_G => 0,
         NUM_SLAVES_G  => 8,
         MODE_G        => "INDEXED")
      port map (
         axisClk      => axisClk,          -- [in]
         axisRst      => axisRst,          -- [in]
         sAxisMasters => pidDebugMasters,  -- [in]
         sAxisSlaves  => pidDebugSlaves,   -- [out]
         mAxisMaster  => pidDebugMaster,   -- [out]
         mAxisSlave   => pidDebugSlave);   -- [in]

   -- Multiplex waveform stream into debug streams
   U_AxiStreamMux_2 : entity surf.AxiStreamMux
      generic map (
         TPD_G          => TPD_G,
         PIPE_STAGES_G  => 0,
         NUM_SLAVES_G   => 2,
         MODE_G         => "ROUTED",
         TDEST_ROUTES_G => (
            0           => "00000---",  -- pid debug
            1           => "00001000"))      -- waveform
      port map (
         axisClk         => axisClk,         -- [in]
         axisRst         => axisRst,         -- [in]
         sAxisMasters(0) => pidDebugMaster,  -- [in]
         sAxisMasters(1) => waveformMaster,  -- [in]         
         sAxisSlaves(0)  => pidDebugSlave,   -- [out]
         sAxisSlaves(1)  => waveformSlave,   -- [out]
         mAxisMaster     => dataAxisMaster,  -- [out]
         mAxisSlave      => dataAxisSlave);  -- [in]

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
         INPUT_PIPE_STAGES_G  => 0,
         OUTPUT_PIPE_STAGES_G => 0)
      port map (
         axisClk     => axisClk,         -- [in]
         axisRst     => axisRst,         -- [in]
         sAxisMaster => dataAxisMaster,  -- [in]
         sAxisSlave  => dataAxisSlave,   -- [out]
         mAxisMaster => axisMaster,      -- [out]
         mAxisSlave  => axisSlave);      -- [in]   


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
