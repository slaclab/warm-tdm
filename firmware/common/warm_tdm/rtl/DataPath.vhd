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
use surf.AxiLitePkg.all;
use surf.AxiStreamPacketizer2Pkg.all;
use surf.Ad9681Pkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity DataPath is

   generic (
      TPD_G : time := 1 ns);

   port (
      -- ADC Serial Interface
      adc : in Ad9681SerialType;

      -- Timing interface
      timingClk125 : in sl;
      timingRst125 : in sl;
      timingData     : in LocalTimingType;

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

   type RegType is record
      firstSample : slv(7 downto 0);
      lastSample  : slv(7 downto 0);
      inWindow    : slv(7 downto 0);
      average     : slv32Array(7 downto 0);
      axisMaster  : AxiStreamMasterType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      firstSample => (others => '0'),
      lastSample  => (others => '0'),
      inWindow    => (others => '0'),
      average     => (others => (others => '0')),
      axisMaster  => AXI_STREAM_MASTER_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal adcStreams         : AxiStreamMasterArray(7 downto 0);
   signal filteredAdcStreams : AxiStreamMasterArray(7 downto 0);

   signal fifoAxisSlave : AxiStreamSlaveType;

begin

   U_Ad9681Readout_1 : entity surf.Ad9681Readout
      generic map (
         TPD_G             => TPD_G,
         IODELAY_GROUP_G   => IODELAY_GROUP_G,
         IDELAYCTRL_FREQ_G => IDELAYCTRL_FREQ_G,
         DEFAULT_DELAY_G   => DEFAULT_DELAY_G,
         ADC_INVERT_CH_G   => "00000000")
      port map (
         axilClk         => axilClk,          -- [in]
         axilRst         => axilRst,          -- [in]
         axilWriteMaster => axilWriteMaster,  -- [in]
         axilWriteSlave  => axilWriteSlave,   -- [out]
         axilReadMaster  => axilReadMaster,   -- [in]
         axilReadSlave   => axilReadSlave,    -- [out]
         adcClkRst       => '0',              -- [in]
         adcSerial       => adc,              -- [in]
         adcStreamClk    => timingClk125,     -- [in]
         adcStreams      => adcStreams);      -- [out]

   FIR_FILTER_GEN : for i in 7 downto 0 generate
      U_FirFilterWrapper_1 : entity warm_tdm.FirFilterWrapper
         generic map (
            TPD_G => TPD_G)
         port map (
            dataClk         => timingClk125,            -- [in]
            dataRst         => timingRst125,            -- [in]
            sDataAxisMaster => adcStreams(i),           -- [in]
            mDataAxisMaster => filteredAdcStreams(i));  -- [out]
   end generate FIR_FILTER_GEN;

   comb : process (fifoAxisSlave, filteredAdcStreams, r, timingData) is
      variable v : RegType;
   begin
      v := r;

      v.firstSample := (others => '0');
      for i in 7 downto 0 loop

         -- Determine sample windows
         if (timingData.rowTime = r.windowStart(i)) then
            v.inWindow(i)    := '1';
            v.firstSample(i) := '1';
         elsif (timingData.rowTime = r.windowEnd(i)) then
            v.inWindow      := '0';
            v.lastSample(i) := '1';
         end if;

         -- Leaky integrator
         -- Prime the average with the value of the first sample
         -- On subsequent samples
         -- Subtract a small fraction of the current average
         -- Add a small fraction of the current sample
         if (filteredAdcStreams(i).tValid = '1' and r.inWindow(i) = '1') then
            if (r.firstSample(i) = '1') then
               v.average(i) := shift_left(signed(filteredAdcStreams(i).tData(15 downto 0)), 16);
            else
               v.average(i) := r.average(i) - shift_right(r.average(i), 7) + shift_left(signed(filteredAdcStreams(i).tdata(15 downto 0)), 16-7);
            end if;
         end if;

      end loop;

      -- When all channels are done
      -- Output a wide word
      if (axisSlave.tReady = '1') then
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

      if (dataRst) then
         v := REG_INIT_C;
      end if;

      rin <= v;

   end process comb;

   seq : process (timingClk125) is
   begin
      if (rising_edge(timningClk125)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

   U_AxiStreamFifoV2_1 : entity work.AxiStreamFifoV2
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
