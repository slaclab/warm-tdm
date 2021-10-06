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

   constant FILTER_COEFFICIENTS_C : IntegerArray(0 to 20) := (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21);

   constant NUM_AXIL_MASTERS_C : integer                                                         := 10;
   constant XBAR_COFNIG_C      : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_MASTERS_C, AXIL_BASE_ADDR_G, 20, 16);

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);

   signal adcStreams : AxiStreamMasterArray(7 downto 0);


begin

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
         axiClk              => axilClk,              -- [in]
         axiClkRst           => axilRst,              -- [in]
         sAxiWriteMasters(0) => axilWriteMaster,      -- [in]
         sAxiWriteSlaves(0)  => axilWriteSlave,       -- [out]
         sAxiReadMasters(0)  => axilReadMaster,       -- [in]
         sAxiReadSlaves(0)   => axilReadSlave,        -- [out]
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
         axilClk         => axilClk,                 -- [in]
         axilRst         => axilRst,                 -- [in]
         axilWriteMaster => locAxilWriteMasters(0),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(0),   -- [out]
         axilReadMaster  => locAxilReadMasters(0),   -- [in]
         axilReadSlave   => locAxilReadSlaves(0),    -- [out]
         adcClkRst       => timingRxRst125,          -- [in]
         adcSerial       => adc,                     -- [in]
         adcStreamClk    => timingRxClk125,          -- [in]
         adcStreams      => adcStreams);             -- [out]

   U_WaveformCapture_1 : entity warm_tdm.WaveformCapture
      generic map (
         TPD_G => TPD_G)
      port map (
         timingRxClk125  => timingRxClk125,          -- [in]
         timingRxRst125  => timingRxRst125,          -- [in]
         timingRxData    => timingRxData,            -- [in]
         adcStreams      => adcStreams,              -- [in]
         axisClk         => axisClk,                 -- [in]
         axisRst         => axisRst,                 -- [in]
         axisMaster      => axisMaster,              -- [out]
         axisSlave       => axisSlave,               -- [in]
         axilClk         => axilClk,                 -- [in]
         axilRst         => axilRst,                 -- [in]
         axilReadMaster  => locAxilReadMasters(9),   -- [in]
         axilReadSlave   => locAxilReadSlaves(9),    -- [out]
         axilWriteMaster => locAxilWriteMasters(9),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(9));  -- [out]

--    FIR_FILTER_GEN : for i in 7 downto 0 generate
--       U_FirFilterSingleChannel_1 : entity surf.FirFilterSingleChannel
--          generic map (
--             TPD_G          => TPD_G,
--             PIPE_STAGES_G  => 0,
--             COMMON_CLK_G   => false,
--             TAP_SIZE_G     => 21,
--             WIDTH_G        => 16,
--             COEFFICIENTS_G => FILTER_COEFFICIENTS_C)
--          port map (
--             clk             => timingClk125,                              -- [in]
--             rst             => timingRst125,                              -- [in]
--             ibValid         => adcStreams(i).tvalid,                      -- [in]
--             din             => adcStreams(i).tData(15 downto 0),          -- [in]
--             obValid         => filteredAdcStreams(i).tvalid,              -- [out]
--             dout            => filteredAdcStreams(i).tData(15 downto 0),  -- [out]
--             axilClk         => axilClk,                                   -- [in]
--             axilRst         => axilRst,                                   -- [in]
--             axilReadMaster  => locAxilReadMasters(i+1),                   -- [in]
--             axilReadSlave   => locAxilReadSlaves(i+1),                    -- [out]
--             axilWriteMaster => locAxilWriteMasters(i+1),                  -- [in]
--             axilWriteSlave  => locAxilWriteSlaves(i+1));                  -- [out]
--    end generate FIR_FILTER_GEN;

   GEN_ADC_DSP : for i in 7 downto 0 generate
      U_AdcDsp_1 : entity warm_tdm.AdcDsp
         generic map (
            TPD_G            => TPD_G,
            AXIL_BASE_ADDR_G => XBAR_COFNIG_C(i+1).baseAddr)
         port map (
            timingRxClk125  => timingRxClk125,            -- [in]
            timingRxRst125  => timingRxRst125,            -- [in]
            timingRxData    => timingRxData,              -- [in]
            adcAxisMaster   => adcStreams(i),             -- [in]
            axilClk         => axilClk,                   -- [in]
            axilRst         => axilRst,                   -- [in]
            axilReadMaster  => locAxilReadMasters(i+1),   -- [in]
            axilReadSlave   => locAxilReadSlaves(i+1),    -- [out]
            axilWriteMaster => locAxilWriteMasters(i+1),  -- [in]
            axilWriteSlave  => locAxilWriteSlaves(i+1));  -- [out]


   end generate;

end architecture rtl;
