-------------------------------------------------------------------------------
-- Title      : 
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

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;
use surf.SsiPkg.all;


library warm_tdm;
use warm_tdm.TimingPkg.all;
use warm_tdm.WarmTdmPkg.all;

entity EventBuilder is

   generic (
      TPD_G : time := 1 ns);

   port (
      timingRxClk125   : in  sl;
      timingRxRst125   : in  sl;
      timingRxData     : in  LocalTimingType;
      pidStreamMasters : in  AxiStreamMasterArray(7 downto 0);
      pidStreamSlaves  : out AxiStreamSlaveArray(7 downto 0);

      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;

      axisClk         : in  sl;
      axisRst         : in  sl;
      eventAxisMaster : out AxiStreamMasterType;
      eventAxisSlave  : in  AxiStreamSlaveType
      );

end entity EventBuilder;

architecture rtl of EventBuilder is

   constant EVENT_AXIS_CFG_C : AxiStreamConfigType := ssiAxiStreamConfig(dataBytes => 4, tDestBits => 0);

   type StateType is (
      WAIT_RSS_S,
      DO_HEADER_0_S,
      DO_HEADER_1_S,
      DO_HEADER_2_S,
      DO_HEADER_3_S,
      DO_HEADER_4_S,
      DO_HEADER_5_S,
      DO_DATA_S);

   type RegType is record
      state           : StateType;
      burn            : sl;
      fifoRdEn        : sl;
      doneCols        : slv(7 downto 0);
      burnCount       : slv(31 downto 0);
      rssCount        : slv(31 downto 0);
      daqReadoutCount : slv(31 downto 0);
      timingRxData    : LocalTimingType;
      muxAxisSlave    : AxiStreamSlaveType;
      eventAxisMaster : AxiStreamMasterType;
      axilReadSlave   : AxiLiteReadSlaveType;
      axilWriteSlave  : AxiLiteWriteSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      state           => WAIT_RSS_S,
      burn            => '0',
      fifoRdEn        => '0',
      doneCols        => (others => '0'),
      burnCount       => (others => '0'),
      rssCount        => (others => '0'),
      daqReadoutCount => (others => '0'),
      timingRxData    => LOCAL_TIMING_INIT_C,
      muxAxisSlave    => AXI_STREAM_SLAVE_INIT_C,
      eventAxisMaster => axiStreamMasterInit(EVENT_AXIS_CFG_C),
      axilReadSlave   => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C,
      axilWriteSlave  => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal muxAxisMaster       : AxiStreamMasterType;
   signal fifoAxisCtrl        : AxiStreamCtrlType;
   signal readoutFifoValid    : sl;
   signal fifoDaqReadoutCount : slv(63 downto 0);
   signal fifoRowSeqCount     : slv(63 downto 0);
   signal fifoRunTime         : slv(63 downto 0);
   signal fifoDaqReadoutStart : sl;

begin

   U_Fifo_1 : entity surf.Fifo
      generic map (
         TPD_G           => TPD_G,
         GEN_SYNC_FIFO_G => true,
         FWFT_EN_G       => true,
         SYNTH_MODE_G    => "inferred",
         MEMORY_TYPE_G   => "distributed",
         DATA_WIDTH_G    => 64*3+1,
         ADDR_WIDTH_G    => 4)
      port map (
         rst                  => timingRxRst125,                -- [in]
         wr_clk               => timingRxClk125,                -- [in]
         wr_en                => timingRxData.rowSeqStart,      -- [in]
         din(63 downto 0)     => timingRxData.daqReadoutCount,  -- [in]
         din(127 downto 64)   => timingRxData.rowSeqCount,      -- [in]
         din(191 downto 128)  => timingRxData.runTime,          -- [in]
         din(192)             => timingRxData.daqReadoutStart,  -- [in]
         rd_clk               => timingRxClk125,                -- [in]
         rd_en                => r.fifoRdEn,                    -- [in]
         dout(63 downto 0)    => fifoDaqReadoutCount,           -- [out]
         dout(127 downto 64)  => fifoRowSeqCount,               -- [out]
         dout(191 downto 128) => fifoRunTime,                   -- [out]
         dout(192)            => fifoDaqReadoutStart,           -- [in]
         valid                => readoutFifoValid);             -- [out]

   U_AxiStreamMux_1 : entity surf.AxiStreamMux
      generic map (
         TPD_G                => TPD_G,
         PIPE_STAGES_G        => 0,
         NUM_SLAVES_G         => 8,
         MODE_G               => "INDEXED",
         TID_MODE_G           => "PASSTHROUGH",
         ILEAVE_EN_G          => true,
         ILEAVE_ON_NOTVALID_G => true,
         ILEAVE_REARB_G       => 0,          -- unlimited (for now)
         REARB_DELAY_G        => true,
         FORCED_REARB_HOLD_G  => true)
      port map (
         axisClk      => timingRxClk125,     -- [in]
         axisRst      => timingRxRst125,     -- [in]
         rearbitrate  => '0',                -- [in]
         disableSel   => rin.doneCols,
--         ileaveRearb  => ileaveRearb,   -- [in]
         sAxisMasters => pidStreamMasters,   -- [in]
         sAxisSlaves  => pidStreamSlaves,    -- [out]
         mAxisMaster  => muxAxisMaster,      -- [out]
         mAxisSlave   => rin.muxAxisSlave);  -- [in]

   comb : process (axilReadMaster, axilWriteMaster, fifoAxisCtrl, fifoDaqReadoutCount,
                   fifoDaqReadoutStart, fifoRowSeqCount, fifoRunTime, muxAxisMaster, r,
                   readoutFifoValid, timingRxData, timingRxRst125) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndpointType;
   begin

      v := r;

      if (timingRxData.startRun = '1') then
         v.burnCount       := (others => '0');
         v.rssCount        := (others => '0');
         v.daqReadoutCount := (others => '0');
      end if;

      axiSlaveWaitTxn(axilEp, axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegisterR(axilEp, X"00", 0, r.daqReadoutCount);
      axiSlaveRegisterR(axilEp, X"04", 0, r.rssCount);
      axiSlaveRegisterR(axilEp, X"08", 0, r.burnCount);
      axiSlaveRegisterR(axilEp, X"0c", 0, r.doneCols);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);


      v.muxAxisSlave.tReady := '0';
      v.fifoRdEn            := '0';
      v.eventAxisMaster     := axiStreamMasterInit(EVENT_AXIS_CFG_C);

      case r.state is
         when WAIT_RSS_S =>
            v.doneCols := (others => '0');
            v.burn     := '0';
            if (readoutFifoValid = '1') then
               if (fifoDaqReadoutStart = '1') then
                  -- Capture timing data for event header
--               v.timingRxData. := timingRxData;
                  v.state := DO_HEADER_0_S;
                  if (fifoAxisCtrl.pause = '1') then
                     v.burn      := '1';
                     v.burnCount := r.burnCount + 1;
                  end if;
               else
                  v.burn     := '1';
                  v.fifoRdEn := '1';
                  v.state    := DO_DATA_S;
               end if;
            end if;

         when DO_HEADER_0_S =>
            v.eventAxisMaster.tValid             := '1';
            ssiSetUserSof(EVENT_AXIS_CFG_C, v.eventAxisMaster, '1');
            v.eventAxisMaster.tData(31 downto 0) := fifoDaqReadoutCount(31 downto 0);  -- r.timingRxData.daqReadoutCount(31 downto 0);
            v.state                              := DO_HEADER_1_S;

         when DO_HEADER_1_S =>
            v.eventAxisMaster.tValid             := '1';
            v.eventAxisMaster.tData(31 downto 0) := fifoDaqReadoutCount(63 downto 32);  -- r.timingRxData.daqReadoutCount(63 downto 32);
            v.state                              := DO_HEADER_2_S;

         when DO_HEADER_2_S =>
            v.eventAxisMaster.tValid             := '1';
            v.eventAxisMaster.tData(31 downto 0) := fifoRowSeqCount(31 downto 0);  -- r.timingRxData.rowSeqCount(31 downto 0);
            v.state                              := DO_HEADER_3_S;

         when DO_HEADER_3_S =>
            v.eventAxisMaster.tValid             := '1';
            v.eventAxisMaster.tData(31 downto 0) := fifoRowSeqCount(63 downto 32);  -- r.timingRxData.rowSeqCount(63 downto 32);
            v.state                              := DO_HEADER_4_S;

         when DO_HEADER_4_S =>
            v.eventAxisMaster.tValid             := '1';
            v.eventAxisMaster.tData(31 downto 0) := fifoRunTime(31 downto 0);  --r.timingRxData.runTime(31 downto 0);
            v.state                              := DO_HEADER_5_S;

         when DO_HEADER_5_S =>
            v.eventAxisMaster.tValid             := '1';
            v.eventAxisMaster.tData(31 downto 0) := fifoRunTime(63 downto 32);  --r.timingRxData.runTime(63 downto 32);
            v.fifoRdEn                           := '1';
            v.state                              := DO_DATA_S;


         when DO_DATA_S =>
            if (muxAxisMaster.tValid = '1') then
               v.muxAxisSlave.tReady := '1';
               if (muxAxisMaster.tLast = '1') then
                  v.doneCols(conv_integer(muxAxisMaster.tDest(2 downto 0))) := '1';
                  -- TLASTS have empty data
                  v.eventAxisMaster.tValid                                  := '0';
               else
                  v.eventAxisMaster.tValid              := not r.burn;
                  v.eventAxisMaster.tData(15 downto 0)  := muxAxisMaster.tData(15 downto 0);
                  v.eventAxisMaster.tData(23 downto 16) := muxAxisMaster.tID(7 downto 0);
                  v.eventAxisMaster.tData(26 downto 24) := muxAxisMaster.tDest(2 downto 0);
               end if;
            end if;

            if (r.doneCols = "11111111") then
               v.eventAxisMaster.tValid             := not r.burn;
               v.eventAxisMaster.tData(31 downto 0) := r.burnCount;
               v.eventAxisMaster.tLast              := '1';
               v.state                              := WAIT_RSS_S;
            end if;

         when others => null;
      end case;

      if (timingRxRst125 = '1') then
         v := REG_INIT_C;
      end if;

      axilReadSlave  <= r.axilReadSlave;
      axilWriteSlave <= r.axilWriteSlave;

      rin <= v;

   end process comb;

   seq : process (timingRxClk125) is
   begin
      if (rising_edge(timingRxClk125)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

   U_AxiStreamFifoV2_DATA : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 0,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => false,
         VALID_THOLD_G       => 0,
         VALID_BURST_MODE_G  => true,
         FIFO_PAUSE_THRESH_G => 15,
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => 9,
         SYNTH_MODE_G        => "xpm",
         MEMORY_TYPE_G       => "bram",
         INT_WIDTH_SELECT_G  => "WIDE",
         SLAVE_AXI_CONFIG_G  => EVENT_AXIS_CFG_C,
         MASTER_AXI_CONFIG_G => DATA_AXIS_CONFIG_C)
      port map (
         sAxisClk    => timingRxClk125,     -- [in]
         sAxisRst    => timingRxRst125,     -- [in]
         sAxisMaster => r.eventAxisMaster,  -- [in]
         sAxisSlave  => open,               -- [out]
         sAxisCtrl   => fifoAxisCtrl,       -- [out]
         mAxisClk    => axisClk,            -- [in]
         mAxisRst    => axisRst,            -- [in]
         mAxisMaster => eventAxisMaster,    -- [out]
         mAxisSlave  => eventAxisSlave);    -- [in]   

end architecture rtl;
