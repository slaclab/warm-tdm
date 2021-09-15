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
use ieee.numeric_std.all;

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
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

   constant INT_AXIS_CONFIG_C : AxiStreamConfigType := (
      TSTRB_EN_C    => false,
      TDATA_BYTES_C => 16,
      TDEST_BITS_C  => 8,
      TID_BITS_C    => 0,
      TKEEP_MODE_C  => TKEEP_FIXED_C,
      TUSER_BITS_C  => 0,
      TUSER_MODE_C  => TUSER_NORMAL_C);

   type RegType is record
      doRawAdc     : sl;
      rawAdcMaster : AxiStreamMasterType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      doRawAdc     => '0',
      rawAdcMaster => axiStreamMasterInit(INT_AXIS_CONFIG_C));

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal rawAdcCtrl : AxiStreamCtrlType;

   constant FILTER_COEFFICIENTS_C : IntegerArray(0 to 20)            := (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21);
   signal adcStreams              : AxiStreamMasterArray(7 downto 0) := (others => axiStreamMasterInit(AD9681_AXIS_CFG_G));
   signal filteredAdcStreams      : AxiStreamMasterArray(7 downto 0) := (others => axiStreamMasterInit(AD9681_AXIS_CFG_G));

   signal fifoAxisSlave : AxiStreamSlaveType;


   constant NUM_AXIL_MASTERS_C : integer := 9;

   constant XBAR_COFNIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_MASTERS_C, AXIL_BASE_ADDR_G, 20, 16);

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);


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

   comb : process (adcStreams, r, rawAdcCtrl, timingRxData, timingRxRst125) is
      variable v : RegType;
   begin
      v := r;

--      v.rawAdcMaster.tDest := "00001000";

      if (timingRxData.rawAdc = '1') then
         v.doRawAdc := '1';
      end if;

      if (r.doRawAdc = '1') then
         for i in 7 downto 0 loop
            v.rawAdcMaster.tData(i*16+15 downto i*16) := adcStreams(i).tData(15 downto 0);
         end loop;
         v.rawAdcMaster.tValid := '1';

         if (rawAdcCtrl.pause = '1') then
            v.rawAdcMaster.tLast := '1';
         end if;

         if (r.rawAdcMaster.tLast = '1') then
            v.doRawAdc            := '0';
            v.rawAdcMaster.tValid := '0';
            v.rawAdcMaster.tLast  := '0';
         end if;
      end if;

      if (timingRxRst125 = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

   end process;

   seq : process (timingRxClk125) is
   begin
      if (rising_edge(timingRxClk125)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

   U_AxiStreamFifoV2_1 : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         VALID_THOLD_G       => 0,
         SLAVE_READY_EN_G    => false,
         GEN_SYNC_FIFO_G     => false,
         FIFO_ADDR_WIDTH_G   => 11,
         FIFO_PAUSE_THRESH_G => 2**11-8,
--           SYNTH_MODE_G           => SYNTH_MODE_G,
--           MEMORY_TYPE_G          => MEMORY_TYPE_G,
--           INT_WIDTH_SELECT_G     => INT_WIDTH_SELECT_G,
--           INT_DATA_WIDTH_G       => INT_DATA_WIDTH_G,
         SLAVE_AXI_CONFIG_G  => INT_AXIS_CONFIG_C,
         MASTER_AXI_CONFIG_G => DATA_AXIS_CONFIG_C)
      port map (
         sAxisClk    => timingRxClk125,  -- [in]
         sAxisRst    => timingRxRst125,  -- [in]
         sAxisMaster => r.rawAdcMaster,  -- [in]
--       sAxisSlave  => fifoAxisSlave,  -- [out]
         sAxisCtrl   => rawAdcCtrl,      -- [out]
         mAxisClk    => axisClk,         -- [in]
         mAxisRst    => axisRst,         -- [in]
         mAxisMaster => axisMaster,      -- [out]
         mAxisSlave  => axisSlave);      -- [in]


end architecture rtl;
