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
      IODELAY_GROUP_G  : string           := "DEFAULT_GROUP");

   port (
      -- ADC Serial Interface
      adc : in Ad9681SerialType;

      -- Timing interface
      timingRxClk125 : in sl;
      timingRxRst125 : in sl;
      timingRxData   : in LocalTimingType;

      -- Formatted data
      axisClk    : in  sl;
      axisRst    : in  sl;
      axisMaster : out AxiStreamMasterType;
      axisSlave  : in  AxiStreamSlaveType;

      -- Local register access
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C

      );

end entity DataPath;

architecture rtl of DataPath is

   constant FILTER_COEFFICIENTS_C : IntegerArray(0 to 41) := (others => 0);

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


   signal adcStreams         : AxiStreamMasterArray(7 downto 0);
   signal filteredAdcStreams : AxiStreamMasterArray(7 downto 0);


begin

   U_AxiLiteAsync : entity surf.AxiLiteAsync
      generic map (
         TPD_G => TPD_G)
      port map (
         -- Slave Interface
         sAxiClk         => axilClk,
         sAxiClkRst      => axilRst,
         sAxiReadMaster  => axilReadMaster,
         sAxiReadSlave   => axilReadSlave,
         sAxiWriteMaster => axilWriteMaster,
         sAxiWriteSlave  => axilWriteSlave,
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
--         SIMULATION_G    => SIMULATION_G,
         DEFAULT_DELAY_G => 12,
         IODELAY_GROUP_G => IODELAY_GROUP_G)
      port map (
         axilClk         => timingRxClk125,                 -- [in]
         axilRst         => timingRxRst125,                 -- [in]
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
      U_FirFilterSingleChannel_1 : entity surf.FirFilterSingleChannel
         generic map (
            TPD_G          => TPD_G,
            PIPE_STAGES_G  => 0,
            COMMON_CLK_G   => true,
            TAP_SIZE_G     => 41,
            WIDTH_G        => 16,
            COEFFICIENTS_G => FILTER_COEFFICIENTS_C)
         port map (
            clk             => timingRxClk125,                            -- [in]
            rst             => timingRxRst125,                            -- [in]
            ibValid         => adcStreams(i).tvalid,                      -- [in]
            din             => adcStreams(i).tData(15 downto 0),          -- [in]
            obValid         => filteredAdcStreams(i).tvalid,              -- [out]
            dout            => filteredAdcStreams(i).tData(15 downto 0),  -- [out]
            axilClk         => timingRxClk125,                            -- [in]
            axilRst         => timingRxRst125,                            -- [in]
            axilReadMaster  => filterAxilReadMasters(i),                  -- [in]
            axilReadSlave   => filterAxilReadSlaves(i),                   -- [out]
            axilWriteMaster => filterAxilWriteMasters(i),                 -- [in]
            axilWriteSlave  => filterAxilWriteSlaves(i));                 -- [out]
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
         axisMaster      => axisMaster,              -- [out]
         axisSlave       => axisSlave);              -- [in]


   GEN_ADC_DSP : for i in 7 downto 0 generate
      U_AdcDsp_1 : entity warm_tdm.AdcDsp
         generic map (
            TPD_G            => TPD_G,
            AXIL_BASE_ADDR_G => XBAR_COFNIG_C(i+1).baseAddr)
         port map (
            timingRxClk125  => timingRxClk125,            -- [in]
            timingRxRst125  => timingRxRst125,            -- [in]
            timingRxData    => timingRxData,              -- [in]
            adcAxisMaster   => filteredAdcStreams(i),     -- [in]
            axilClk         => timingRxClk125,            -- [in]
            axilRst         => timingRxRst125,            -- [in]
            axilReadMaster  => locAxilReadMasters(i+1),   -- [in]
            axilReadSlave   => locAxilReadSlaves(i+1),    -- [out]
            axilWriteMaster => locAxilWriteMasters(i+1),  -- [in]
            axilWriteSlave  => locAxilWriteSlaves(i+1));  -- [out]


   end generate;

end architecture rtl;
