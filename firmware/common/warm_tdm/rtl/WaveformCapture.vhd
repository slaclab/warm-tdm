-------------------------------------------------------------------------------
-- Title      : WaveformCapture 
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: 
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
use surf.Ad9681Pkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;
use warm_tdm.WarmTdmPkg.all;

entity WaveformCapture is

   generic (
      TPD_G : time := 1 ns);
   port (
      -- Timing interface
      timingRxClk125 : in sl;
      timingRxRst125 : in sl;
      timingRxData   : in LocalTimingType;

      -- Adc Streams
      adcStreams : in AxiStreamMasterArray(7 downto 0);

      -- Captured Waveform Stream
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
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);

end entity WaveformCapture;

architecture rtl of WaveformCapture is

   constant RESIZE_SLAVE_CFG_C : AxiStreamConfigType := (
      TSTRB_EN_C    => false,
      TDATA_BYTES_C => 2,
      TDEST_BITS_C  => 3,
      TID_BITS_C    => 0,
      TKEEP_MODE_C  => TKEEP_FIXED_C,
      TUSER_BITS_C  => 0,
      TUSER_MODE_C  => TUSER_NONE_C);

   constant RESIZE_MASTER_CFG_C : AxiStreamConfigType := (
      TSTRB_EN_C    => false,
      TDATA_BYTES_C => 16,
      TDEST_BITS_C  => 3,
      TID_BITS_C    => 0,
      TKEEP_MODE_C  => TKEEP_FIXED_C,
      TUSER_BITS_C  => 0,
      TUSER_MODE_C  => TUSER_NONE_C);

   constant INT_AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(
      dataBytes => 16,
      tKeepMode => TKEEP_FIXED_C,
      tUserMode => TUSER_FIRST_LAST_C,
      tUserBits => 2,
      tDestBits => 4);

   type RegType is record
      waveformTrigger  : sl;
      doWaveform       : sl;
      decimation       : slv(15 downto 0);
      decCnt           : slv(15 downto 0);
      selectedChannel  : slv(2 downto 0);
      allChannels      : sl;
      decimatedStreams : AxiStreamMasterArray(7 downto 0);
      selectedStream   : AxiStreamMasterType;
      combinedStream   : AxiStreamMasterType;
      bufferStream     : AxiStreamMasterType;
      axilWriteSlave   : AxiLiteWriteSlaveType;
      axilReadSlave    : AxiLiteReadSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      waveformTrigger  => '0',
      doWaveform       => '0',
      decimation       => (others => '0'),
      decCnt           => (others => '0'),
      selectedChannel  => (others => '0'),
      allChannels      => '1',
      decimatedStreams => (others => axiStreamMasterInit(RESIZE_SLAVE_CFG_C)),
      selectedStream   => axiStreamMasterInit(RESIZE_SLAVE_CFG_C),
      combinedStream   => axiStreamMasterInit(RESIZE_MASTER_CFG_C),
      bufferStream     => axiStreamMasterInit(INT_AXIS_CONFIG_C),
      axilWriteSlave   => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave    => AXI_LITE_READ_SLAVE_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal bufferCtrl    : AxiStreamCtrlType;
   signal resizedStream : AxiStreamMasterType := axiStreamMasterInit(RESIZE_MASTER_CFG_C);

   signal syncAxilReadMaster  : AxiLiteReadMasterType;
   signal syncAxilReadSlave   : AxiLiteReadSlaveType;
   signal syncAxilWriteMaster : AxiLiteWriteMasterType;
   signal syncAxilWriteSlave  : AxiLiteWriteSlaveType;

begin

   -------------------------------------------------------------------------------------------------
   -- Synchronize AXI-Lite bus to timing clock
   -------------------------------------------------------------------------------------------------
   U_AxiLiteAsync_1 : entity surf.AxiLiteAsync
      generic map (
         TPD_G => TPD_G)
      port map (
         sAxiClk         => axilClk,              -- [in]
         sAxiClkRst      => axilRst,              -- [in]
         sAxiReadMaster  => axilReadMaster,       -- [in]
         sAxiReadSlave   => axilReadSlave,        -- [out]
         sAxiWriteMaster => axilWriteMaster,      -- [in]
         sAxiWriteSlave  => axilWriteSlave,       -- [out]
         mAxiClk         => timingRxClk125,       -- [in]
         mAxiClkRst      => timingRxRst125,       -- [in]
         mAxiReadMaster  => syncAxilReadMaster,   -- [out]
         mAxiReadSlave   => syncAxilReadSlave,    -- [in]
         mAxiWriteMaster => syncAxilWriteMaster,  -- [out]
         mAxiWriteSlave  => syncAxilWriteSlave);  -- [in]

   -------------------------------------------------------------------------------------------------
   -- Resize channel ADC stream to 8 samples wide (16 bytes)
   -------------------------------------------------------------------------------------------------
   U_AxiStreamResize_1 : entity surf.AxiStreamResize
      generic map (
         TPD_G               => TPD_G,
         READY_EN_G          => false,
         PIPE_STAGES_G       => 0,
         SLAVE_AXI_CONFIG_G  => RESIZE_SLAVE_CFG_C,
         MASTER_AXI_CONFIG_G => RESIZE_MASTER_CFG_C)
      port map (
         axisClk     => timingRxClk125,             -- [in]
         axisRst     => timingRxRst125,             -- [in]
         sAxisMaster => r.selectedStream,           -- [in]
         sAxisSlave  => open,                       -- [out]
         mAxisMaster => resizedStream,              -- [out]
         mAxisSlave  => AXI_STREAM_SLAVE_FORCE_C);  -- [in]

   -------------------------------------------------------------------------------------------------
   -- Main Logic
   -------------------------------------------------------------------------------------------------
   comb : process (adcStreams, bufferCtrl, r, resizedStream, syncAxilReadMaster,
                   syncAxilWriteMaster, timingRxData, timingRxRst125) is
      variable v               : RegType;
      variable selectedChannel : integer;
      variable axilEp          : AxiLiteEndpointType;
   begin
      v := r;

      v.waveformTrigger := '0';

      ----------------------------------------------------------------------------------------------
      -- AXI-Lite Registers
      ----------------------------------------------------------------------------------------------
      axiSlaveWaitTxn(axilEp, syncAxilWriteMaster, syncAxilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.selectedChannel);
      axiSlaveRegister(axilEp, X"00", 3, v.allChannels);
      axiSlaveRegister(axilEp, X"04", 0, v.waveformTrigger);
      axiSlaveRegister(axilEp, X"08", 0, v.decimation);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      ----------------------------------------------------------------------------------------------
      -- Decimator
      ----------------------------------------------------------------------------------------------
      if (adcStreams(0).tValid = '1') then
         v.decCnt := r.decCnt + 1;

         for i in 7 downto 0 loop
            v.decimatedStreams(i).tValid := '0';
            if (adcStreams(i).tValid = '1' and (r.decCnt = r.decimation-1 or r.decimation = 0)) then
               v.decimatedStreams(i).tValid             := '1';
               v.decimatedStreams(i).tData(15 downto 0) := adcStreams(i).tData(15 downto 0);
               v.decCnt                                 := (others => '0');
            end if;
         end loop;
      end if;

      ----------------------------------------------------------------------------------------------
      -- Multiplex decimated stream to resizer
      ----------------------------------------------------------------------------------------------
      selectedChannel        := conv_integer(r.selectedChannel);
      v.selectedStream       := r.decimatedStreams(selectedChannel);
      v.selectedStream.tDest := resize(r.selectedChannel, 8);

      ----------------------------------------------------------------------------------------------
      -- Create a combined stream of all channels
      ----------------------------------------------------------------------------------------------
      v.combinedStream.tValid := r.decimatedStreams(0).tValid;
      for i in 7 downto 0 loop
         v.combinedStream.tData(i*16+15 downto i*16) := r.decimatedStreams(i).tData(15 downto 0);
      end loop;
      v.combinedStream.tDest := toSlv(8, 8);

      ----------------------------------------------------------------------------------------------
      -- Dump data info FIFO when triggered
      -- Multiplex combined or resized channel streams
      ----------------------------------------------------------------------------------------------
      if (timingRxData.rawAdc = '1' or r.waveformTrigger = '1') then
         v.doWaveform := '1';
         ssiSetUserSof(INT_AXIS_CONFIG_C, v.bufferStream, '1');
      end if;

      if (r.doWaveform = '1') then
         if (r.allChannels = '1') then
            v.bufferStream := r.combinedStream;
         else
            v.bufferStream := resizedStream;
         end if;
      end if;

      if (r.bufferStream.tvalid = '1') then
         ssiSetUserSof(INT_AXIS_CONFIG_C, v.bufferStream, '0');
      end if;

      if (bufferCtrl.pause = '1' and v.bufferStream.tvalid = '1') then
         v.bufferStream.tLast := '1';
      end if;

      if (r.bufferStream.tLast = '1') then
         v.doWaveform          := '0';
         v.bufferStream.tValid := '0';
         v.bufferStream.tLast  := '0';
      end if;


      if (timingRxRst125 = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      syncAxilReadSlave  <= r.axilReadSlave;
      syncAxilWriteSlave <= r.axilWriteSlave;

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
         FIFO_ADDR_WIDTH_G   => 14,
         FIFO_PAUSE_THRESH_G => 2**14-8,
--           SYNTH_MODE_G           => SYNTH_MODE_G,
--           MEMORY_TYPE_G          => MEMORY_TYPE_G,
--           INT_WIDTH_SELECT_G     => INT_WIDTH_SELECT_G,
--           INT_DATA_WIDTH_G       => INT_DATA_WIDTH_G,
         SLAVE_AXI_CONFIG_G  => INT_AXIS_CONFIG_C,
         MASTER_AXI_CONFIG_G => DATA_AXIS_CONFIG_C)
      port map (
         sAxisClk    => timingRxClk125,  -- [in]
         sAxisRst    => timingRxRst125,  -- [in]
         sAxisMaster => r.bufferStream,  -- [in]
         sAxisCtrl   => bufferCtrl,      -- [out]
         mAxisClk    => axisClk,         -- [in]
         mAxisRst    => axisRst,         -- [in]
         mAxisMaster => axisMaster,      -- [out]
         mAxisSlave  => axisSlave);      -- [in]
end architecture rtl;


