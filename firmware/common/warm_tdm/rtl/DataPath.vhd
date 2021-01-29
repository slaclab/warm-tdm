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

entity DataPath is

   generic (
      TPD_G            : time             := 1 ns;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := (others => '0');
      IODELAY_GROUP_G  : string           := "DEFAULT_GROUP");

   port (
      -- ADC Serial Interface
      adc : in Ad9681SerialType;

      -- Timing interface
      timingClk125 : in sl;
      timingRst125 : in sl;
      timingData   : in LocalTimingType;

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
      TDEST_BITS_C  => 0,
      TID_BITS_C    => 0,
      TKEEP_MODE_C  => TKEEP_FIXED_C,
      TUSER_BITS_C  => 0,
      TUSER_MODE_C  => TUSER_NORMAL_C);

   type RegType is record
      firstSample : slv(7 downto 0);
      lastSample  : slv(7 downto 0);
      windowStart : slv7Array(7 downto 0);
      windowEnd   : slv7Array(7 downto 0);
      inWindow    : slv(7 downto 0);
      average     : slv32Array(7 downto 0);
      axisMaster  : AxiStreamMasterType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      firstSample => (others => '0'),
      lastSample  => (others => '0'),
      windowStart => (others => toSlv(150, 7)),
      windowEnd   => (others => toSlv(250, 7)),
      inWindow    => (others => '0'),
      average     => (others => (others => '0')),
      axisMaster  => axiStreamMasterInit(INT_AXIS_CONFIG_C));

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   constant FILTER_COEFFICIENTS_C : IntegerArray(0 to 20) := (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21);
   signal adcStreams         : AxiStreamMasterArray(7 downto 0) := (others => axiStreamMasterInit(AD9681_AXIS_CFG_G));
   signal filteredAdcStreams : AxiStreamMasterArray(7 downto 0) := (others => axiStreamMasterInit(AD9681_AXIS_CFG_G));

   signal fifoAxisSlave : AxiStreamSlaveType;


   constant NUM_AXIL_MASTERS_C : integer := 9;

   constant XBAR_COFNIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_MASTERS_C, AXIL_BASE_ADDR_G, 12, 8);

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
         IODELAY_GROUP_G => IODELAY_GROUP_G)
--         IDELAYCTRL_FREQ_G => 200.0,
--         DEFAULT_DELAY_G   => DEFAULT_DELAY_G
      port map (
         axilClk         => axilClk,                 -- [in]
         axilRst         => axilRst,                 -- [in]
         axilWriteMaster => locAxilWriteMasters(0),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(0),   -- [out]
         axilReadMaster  => locAxilReadMasters(0),   -- [in]
         axilReadSlave   => locAxilReadSlaves(0),    -- [out]
         adcClkRst       => '0',                     -- [in]
         adcSerial       => adc,                     -- [in]
         adcStreamClk    => timingClk125,            -- [in]
         adcStreams      => adcStreams);             -- [out]

   FIR_FILTER_GEN : for i in 7 downto 0 generate
      U_FirFilterSingleChannel_1 : entity surf.FirFilterSingleChannel
         generic map (
            TPD_G          => TPD_G,
            PIPE_STAGES_G  => 0,
            COMMON_CLK_G   => false,
            TAP_SIZE_G     => 21,
            WIDTH_G        => 16,
            COEFFICIENTS_G => FILTER_COEFFICIENTS_C)
         port map (
            clk             => timingClk125,                              -- [in]
            rst             => timingRst125,                              -- [in]
            ibValid         => adcStreams(i).tvalid,                      -- [in]
            din             => adcStreams(i).tData(15 downto 0),          -- [in]
            obValid         => filteredAdcStreams(i).tvalid,              -- [out]
            dout            => filteredAdcStreams(i).tData(15 downto 0),  -- [out]
            axilClk         => axilClk,                                   -- [in]
            axilRst         => axilRst,                                   -- [in]
            axilReadMaster  => locAxilReadMasters(i+1),                   -- [in]
            axilReadSlave   => locAxilReadSlaves(i+1),                    -- [out]
            axilWriteMaster => locAxilWriteMasters(i+1),                  -- [in]
            axilWriteSlave  => locAxilWriteSlaves(i+1));                  -- [out]
--       U_FirFilterWrapper_1 : entity warm_tdm.FirFilterWrapper
--          generic map (
--             TPD_G => TPD_G)
--          port map (
--             dataClk         => timingClk125,                              -- [in]
--             dataRst         => timingRst125,                              -- [in]
--             sDataAxisMaster => adcStreams(i),                             -- [in]
--             mDataAxisMaster => filteredAdcStreams(i));                    -- [out]
   end generate FIR_FILTER_GEN;

   comb : process (fifoAxisSlave, filteredAdcStreams, r, timingData, timingRst125) is
      variable v : RegType;
      variable average : signed(31 downto 0);
      variable sample : signed(15 downto 0);
      variable avgDiv : signed(31 downto 0);
   begin
      v := r;

      v.firstSample := (others => '0');
      for i in 7 downto 0 loop

         -- Determine sample windows
         if (timingData.rowTime = r.windowStart(i)) then
            v.inWindow(i)    := '1';
            v.firstSample(i) := '1';
         elsif (timingData.rowTime = r.windowEnd(i)) then
            v.inWindow(i)   := '0';
            v.lastSample(i) := '1';
         end if;

         -- Leaky integrator
         -- Prime the average with the value of the first sample
         -- On subsequent samples
         -- Subtract a small fraction of the current average
         -- Add a small fraction of the current sample
         if (filteredAdcStreams(i).tValid = '1' and r.inWindow(i) = '1') then
            if (r.firstSample(i) = '1') then
               v.average(i) := filteredAdcStreams(i).tData(15 downto 0) & X"0000";
            else
               average := signed(r.average(i));
               avgDiv := shift_right(average, 7);
               sample := signed(filteredAdcStreams(i).tData(15 downto 0));
               sample := shift_left(sample, 16-7);
               average := average - avgDiv + sample;
               v.average(i) := slv(average);
--               v.average(i) := slv(signed(r.average(i)) - shift_right(signed(r.average(i)), 7) + shift_left(signed(resize(filteredAdcStreams(i).tdata(15 downto 0), 32)), 16-7));
            end if;
         end if;

      end loop;

      -- When all channels are done
      -- Output a wide word
      if (fifoAxisSlave.tReady = '1') then
         v.axisMaster.tValid := '0';
      end if;

      v.axisMaster.tLast := '0';
      if (uAnd(r.lastSample) = '1' and v.axisMaster.tValid = '0') then
         v.lastSample := (others => '0');
         for i in 7 downto 0 loop
            v.axisMaster.tData(i*16+15 downto i*16) := slv(r.average(i)(31 downto 16));
            v.axisMaster.tValid                     := '1';
            v.axisMaster.tLast                      := '1';
         end loop;
      end if;

      if (timingRst125 = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

   end process comb;

   seq : process (timingClk125) is
   begin
      if (rising_edge(timingClk125)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

   U_AxiStreamFifoV2_1 : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 1,
         SLAVE_READY_EN_G    => true,
         GEN_SYNC_FIFO_G     => false,
--          FIFO_ADDR_WIDTH_G      => FIFO_ADDR_WIDTH_G,
--          FIFO_PAUSE_THRESH_G    => FIFO_PAUSE_THRESH_G,
--          SYNTH_MODE_G           => SYNTH_MODE_G,
--          MEMORY_TYPE_G          => MEMORY_TYPE_G,
--          INT_WIDTH_SELECT_G     => INT_WIDTH_SELECT_G,
--          INT_DATA_WIDTH_G       => INT_DATA_WIDTH_G,
         SLAVE_AXI_CONFIG_G  => INT_AXIS_CONFIG_C,
         MASTER_AXI_CONFIG_G => PACKETIZER2_AXIS_CFG_C)
      port map (
         sAxisClk    => timingClk125,   -- [in]
         sAxisRst    => timingRst125,   -- [in]
         sAxisMaster => r.axisMaster,   -- [in]
         sAxisSlave  => fifoAxisSlave,  -- [out]
--         sAxisCtrl       => sAxisCtrl,        -- [out]
         mAxisClk    => axisClk,        -- [in]
         mAxisRst    => axisRst,        -- [in]
         mAxisMaster => axisMaster,     -- [out]
         mAxisSlave  => axisSlave);     -- [in]


end architecture rtl;
