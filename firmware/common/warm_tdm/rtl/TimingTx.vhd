-------------------------------------------------------------------------------
-- Title      : Timing Rx
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
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity TimingTx is

   generic (
      TPD_G            : time             := 1 ns;
      RING_ADDR_0_G    : boolean          := false;
      SIMULATION_G     : boolean          := false;
      AXIL_CLK_FREQ_G  : real             := 125.0E+6;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := (others => '0'));

   port (
      timingRefClk : in sl;
      timingRefRst : in sl;

      xbarDataSel   : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarClkSel    : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarMgtSel    : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");
      xbarTimingSel : out slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");

      timingTxClkP  : out sl;
      timingTxClkN  : out sl;
      timingTxDataP : out sl;
      timingTxDataN : out sl;
      pwrSyncA      : out sl := '0';
      pwrSyncB      : out sl := '0';
      pwrSyncC      : out sl := '1';

      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);

end entity TimingTx;

architecture rtl of TimingTx is

   constant SOFTWARE_C : sl := '0';
   constant HARDWARE_C : sl := '1';
   constant PWR_SYNC_LOW_C  : slv(1 downto 0) := "00";
   constant PWR_SYNC_HIGH_C : slv(1 downto 0) := "01";
   constant PWR_SYNC_OSC_C  : slv(1 downto 0) := "10";

   -- Control words and row-index bytes are sent on separate cycles.
   -- START_RUN is followed by one prime byte for the first pending row.
   type TxStateType is (
      CONTROL_S,
      ROW_INDEX_S,
      END_RUN_S);

   signal bitClk  : sl;
   signal bitRst  : sl;
   signal wordClk : sl;
   signal wordRst : sl;

   signal timingTxCodeWord : slv(9 downto 0);

   type RegType is record
      -- XBAR
      xbarDataSel   : slv(1 downto 0);
      xbarClkSel    : slv(1 downto 0);
      xbarMgtSel    : slv(1 downto 0);
      xbarTimingSel : slv(1 downto 0);

      -- Config
      runMode                 : sl;
      pwrSyncEn               : sl;
      softwareRowStrobe       : sl;
      rowPeriod               : slv(31 downto 0);
      numRows                 : slv(15 downto 0);
      sampleStartTime         : slv(31 downto 0);
      sampleEndTime           : slv(31 downto 0);
      stageNextRowLead        : slv(31 downto 0);
      endRunPending          : sl;
      waveformCaptureTime     : slv(31 downto 0);
      daqReadoutPeriod        : slv(31 downto 0);
      daqReadoutPeriodCounter : slv(31 downto 0);
      pwrSyncACfg             : slv(1 downto 0);
      pwrSyncBCfg             : slv(1 downto 0);
      pwrSyncCCfg             : slv(1 downto 0);
      syncPeriodDiv2          : slv(31 downto 0);
      syncClkCount            : slv(31 downto 0);
      syncReset               : sl;
      pwrSyncA                : sl;
      pwrSyncB                : sl;
      pwrSyncC                : sl;
      -- Row-order RAM drives the startup prime byte and the pending row byte after each boundary.
      rowOrderAddr            : slv(7 downto 0);
      -- Hold the first boundary after START_RUN so it becomes the initial row-sequence start.
      startupBoundaryPending  : sl;
      -- Hold state for power-sync gating at the next row-sequence boundary.
      pwrSyncWait             : sl;
      txState                 : TxStateType;
      -- State
      timingData              : LocalTimingType;
      timingTx                : slv(7 downto 0);
      timingTxK               : slv(0 downto 0);
      -- AXIL
      axilWriteSlave          : AxiLiteWriteSlaveType;
      axilReadSlave           : AxiLiteReadSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      xbarDataSel             => ite(RING_ADDR_0_G, "11", "00"),  -- Temporary loopback only
      xbarClkSel              => ite(RING_ADDR_0_G, "11", "00"),
      xbarMgtSel              => "01",
      xbarTimingSel           => "01",
      runMode                 => SOFTWARE_C,
      pwrSyncEn               => '0',
      softwareRowStrobe       => '0',
      rowPeriod               => toSlv(250, 32),                  -- 125 MHz / 256 = 488 kHz
      numRows                 => toSlv(256, 16),
      sampleStartTime         => toSlv(32, 32),
      sampleEndTime           => toSlv(160, 32),                  -- Could be corner case here?
      stageNextRowLead        => toSlv(32, 32),
      endRunPending          => '0',
      waveformCaptureTime     => toSlv(2, 32),
      daqReadoutPeriod        => toSlv(40, 32),  -- Readout once every 40 rowSequences
      daqReadoutPeriodCounter => (others => '0'),
      pwrSyncACfg             => PWR_SYNC_LOW_C,
      pwrSyncBCfg             => PWR_SYNC_LOW_C,
      pwrSyncCCfg             => PWR_SYNC_HIGH_C,
      syncPeriodDiv2          => toSlv(integer(AXIL_CLK_FREQ_G / (2.0*2000000.0))+1, 32),
      syncClkCount            => (others => '0'),
      syncReset               => '0',
      pwrSyncA                => '0',
      pwrSyncB                => '0',
      pwrSyncC                => '1',
      rowOrderAddr            => (others => '0'),
      startupBoundaryPending  => '0',
      pwrSyncWait             => '0',
      txState                 => CONTROL_S,
      timingTx                => IDLE_C,
      timingTxK               => "1",
      timingData              => LOCAL_TIMING_INIT_C,
      axilWriteSlave          => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave           => AXI_LITE_READ_SLAVE_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal refClkFreq  : slv(31 downto 0);
   signal wordClkFreq : slv(31 downto 0);

   signal timingAxilWriteMaster : AxiLiteWriteMasterType;
   signal timingAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal timingAxilReadMaster  : AxiLiteReadMasterType;
   signal timingAxilReadSlave   : AxiLiteReadSlaveType;

   signal rowOrderRamOut : slv(7 downto 0);

   constant NUM_AXIL_C : integer := 2;

   constant XBAR_COFNIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_C, AXIL_BASE_ADDR_G, 16, 12);

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_C-1 downto 0) := (others => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_C-1 downto 0)  := (others => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);


begin

   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_C,
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

   U_AxiLiteAsync_1 : entity surf.AxiLiteAsync
      generic map (
         TPD_G         => TPD_G,
         PIPE_STAGES_G => 0)
      port map (
         sAxiClk         => axilClk,                 -- [in]
         sAxiClkRst      => axilRst,                 -- [in]
         sAxiReadMaster  => locAxilReadMasters(0),   -- [in]
         sAxiReadSlave   => locAxilReadSlaves(0),    -- [out]
         sAxiWriteMaster => locAxilWriteMasters(0),  -- [in]
         sAxiWriteSlave  => locAxilWriteSlaves(0),   -- [out]
         mAxiClk         => wordClk,                 -- [in]
         mAxiClkRst      => wordRst,                 -- [in]
         mAxiReadMaster  => timingAxilReadMaster,    -- [out]
         mAxiReadSlave   => timingAxilReadSlave,     -- [in]
         mAxiWriteMaster => timingAxilWriteMaster,   -- [out]
         mAxiWriteSlave  => timingAxilWriteSlave);   -- [in]

   -- RAM for Row Index Order
   U_AxiDualPortRam_ROW_ORDER : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => 8,                     -- 256 rows max
         DATA_WIDTH_G     => 8)
      port map (
         axiClk         => axilClk,                 -- [in]
         axiRst         => axilRst,                 -- [in]
         axiReadMaster  => locAxilReadMasters(1),   -- [in]
         axiReadSlave   => locAxilReadSlaves(1),    -- [out]
         axiWriteMaster => locAxilWriteMasters(1),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(1),   -- [out]
         clk            => wordClk,                 -- [in]
         rst            => wordRst,                 -- [in]
         addr           => r.rowOrderAddr,          -- [in]
         dout           => rowOrderRamOut);         -- [out]   

   comb : process (r, refClkFreq, rowOrderRamOut, timingAxilReadMaster, timingAxilWriteMaster,
                   wordClkFreq, wordRst) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndpointType;
      variable rowAdvanceReq      : boolean;
      variable rowAdvanceFire     : boolean;
      variable rowSeqStartReq     : boolean;
      variable daqReadoutStartReq : boolean;
      variable stageNextRowTime   : slv(31 downto 0);
      variable initialNextRowSeq  : slv(7 downto 0);
      variable nextRowSeq         : slv(7 downto 0);
      variable prefetchRowSeq     : slv(7 downto 0);
      variable syncPulse          : sl;
   begin
      v := r;

      --------------------
      -- AXI Lite
      --------------------
      axiSlaveWaitTxn(axilEp, timingAxilWriteMaster, timingAxilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      -- Strobed signals
      v.softwareRowStrobe := '0';
      v.syncReset         := '0';

      -- Configuration
      axiSlaveRegister(axilEp, X"00", 0, v.timingData.startRun);
      axiSlaveRegister(axilEp, X"04", 0, v.endRunPending);
      axiSlaveRegister(axilEp, X"08", 0, v.rowPeriod);
      axiSlaveRegister(axilEp, X"0C", 0, v.numRows);
      axiSlaveRegister(axilEp, X"10", 0, v.sampleStartTime);
      axiSlaveRegister(axilEp, X"14", 0, v.sampleEndTime);
      axiSlaveRegister(axilEp, X"18", 0, v.runMode);
      axiSlaveRegister(axilEp, X"1C", 0, v.softwareRowStrobe);
      axiSlaveRegister(axilEp, X"1C", 1, v.pwrSyncEn);
      axiSlaveRegister(axilEp, X"2C", 0, v.daqReadoutPeriod);

      axiSlaveRegister(axilEp, X"20", 0, v.timingData.waveformCapture);
      axiSlaveRegister(axilEp, X"24", 0, v.stageNextRowLead);
      axiSlaveRegister(axilEp, X"28", 0, v.waveformCaptureTime);
      axiSlaveRegister(axilEp, X"80", 0, v.pwrSyncACfg);
      axiSlaveRegister(axilEp, X"80", 2, v.pwrSyncBCfg);
      axiSlaveRegister(axilEp, X"80", 4, v.pwrSyncCCfg);
      axiSlaveRegister(axilEp, X"84", 0, v.syncPeriodDiv2);
      axiWrDetect(axilEp, X"84", v.syncReset);

      -- Status
      axiSlaveRegisterR(axilEp, X"30", 0, r.timingData.running);
      axiSlaveRegisterR(axilEp, X"30", 1, r.timingData.sample);
      axiSlaveRegisterR(axilEp, X"34", 0, r.timingData.rowSeq);
      axiSlaveRegisterR(axilEp, X"34", 16, r.timingData.rowIndex);
      axiSlaveRegisterR(axilEp, X"34", 24, r.timingData.rowIndexNext);
      axiSlaveRegisterR(axilEp, X"38", 0, r.timingData.rowTime);
      axiSlaveRegisterR(axilEp, X"40", 0, r.timingData.runTime);
      axiSlaveRegisterR(axilEp, X"70", 0, r.timingData.rowSeqCount);
      axiSlaveRegisterR(axilEp, X"78", 0, r.timingData.daqReadoutCount);

      axiSlaveRegister(axilEp, X"50", 0, v.xbarClkSel);
      axiSlaveRegister(axilEp, X"50", 4, v.xbarDataSel);
      axiSlaveRegister(axilEp, X"50", 8, v.xbarMgtSel);
      axiSlaveRegister(axilEp, X"50", 12, v.xbarTimingSel);

      axiSlaveRegisterR(axilEp, X"60", 0, refClkFreq);
      axiSlaveRegisterR(axilEp, X"64", 0, wordClkFreq);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      ----------------------
      -- Timing Gen
      ----------------------
      v.timingTx  := IDLE_C;
      v.timingTxK := "1";

      v.timingData.firstSample := '0';
      v.timingData.lastSample  := '0';
      v.timingData.endRun      := '0';
      v.timingData.stageNextRow := '0';

      v.timingData.rowStrobe       := '0';
      v.timingData.rowSeqStart     := '0';
      v.timingData.daqReadoutStart := '0';

      syncPulse := '0';

      -- Generate the power-sync outputs in the same clock domain as the row-sequencer.
      v.syncClkCount := r.syncClkCount + 1;
      if (r.syncClkCount = r.syncPeriodDiv2 - 1 or r.syncReset = '1') then
         v.syncClkCount := (others => '0');
         syncPulse      := '1';
      end if;

      if (r.pwrSyncACfg = PWR_SYNC_HIGH_C) then
         v.pwrSyncA := '0';  -- Do not allow pwrSyncA to drive high.
      elsif (r.pwrSyncACfg = PWR_SYNC_LOW_C) then
         v.pwrSyncA := '0';
      elsif (r.pwrSyncACfg = PWR_SYNC_OSC_C and syncPulse = '1') then
         v.pwrSyncA := not r.pwrSyncA;
      end if;

      if (r.pwrSyncBCfg = PWR_SYNC_HIGH_C) then
         v.pwrSyncB := '1';
      elsif (r.pwrSyncBCfg = PWR_SYNC_LOW_C) then
         v.pwrSyncB := '0';
      elsif (r.pwrSyncBCfg = PWR_SYNC_OSC_C and syncPulse = '1') then
         v.pwrSyncB := not r.pwrSyncB;
      end if;

      if (r.pwrSyncCCfg = PWR_SYNC_HIGH_C) then
         v.pwrSyncC := '1';
      elsif (r.pwrSyncCCfg = PWR_SYNC_LOW_C) then
         v.pwrSyncC := '0';
      elsif (r.pwrSyncCCfg = PWR_SYNC_OSC_C and syncPulse = '1') then
         v.pwrSyncC := not r.pwrSyncC;
      end if;

      -- Row advancement is driven either by the hardware row-period timer or a software strobe.
      -- Boundary events are suppressed while START_RUN is still priming the initial active/pending rows.
      rowAdvanceReq := (r.txState = CONTROL_S and
                        ((r.runMode = HARDWARE_C and r.timingData.rowTime >= r.rowPeriod-1) or
                         (r.runMode = SOFTWARE_C and r.softwareRowStrobe = '1')));

      -- Emit stageNextRow a programmable number of timing clocks ahead of the next row boundary.
      -- If the row period is shorter than the requested lead, emit it on the earliest cycle after
      -- the pending-row byte has been sent.
      stageNextRowTime := toSlv(1, 32);
      if (r.rowPeriod > r.stageNextRowLead + 1) then
         stageNextRowTime := r.rowPeriod - r.stageNextRowLead - 1;
      end if;

      initialNextRowSeq := toSlv(1, 8);
      if (r.numRows = 1) then
         initialNextRowSeq := (others => '0');
      end if;

      nextRowSeq := r.timingData.rowSeq + 1;
      if (r.startupBoundaryPending = '1') then
         nextRowSeq := (others => '0');
      elsif (r.timingData.rowSeq = r.numRows-1) then
         nextRowSeq := (others => '0');
      end if;

      prefetchRowSeq := nextRowSeq + 1;
      if (r.startupBoundaryPending = '1') then
         prefetchRowSeq := initialNextRowSeq;
      elsif (nextRowSeq = r.numRows-1) then
         prefetchRowSeq := (others => '0');
      end if;

      -- A sequence-start boundary is the wrap from the final row back to row zero.
      rowSeqStartReq := ((r.startupBoundaryPending = '1') or (r.timingData.rowSeq = r.numRows-1));
      daqReadoutStartReq := (rowSeqStartReq and (r.daqReadoutPeriodCounter = 0));
      rowAdvanceFire := false;

      -- In power-sync mode, sequence-start boundaries can only advance when pwrSync is seen.
      -- All related counters remain frozen while pwrSyncWait is asserted.
      if (r.pwrSyncWait = '1') then
         rowAdvanceFire := (syncPulse = '1');
      elsif (rowAdvanceReq) then
         if (rowSeqStartReq and r.pwrSyncEn = '1') then
            rowAdvanceFire := (syncPulse = '1');
         else
            rowAdvanceFire := true;
         end if;
      end if;

      if (r.startupBoundaryPending = '0' and r.timingData.waveformCapture = '1' and
          r.waveformCaptureTime = r.timingData.rowTime and r.timingData.rowSeq = 0) then
         v.timingTx                   := WAVEFORM_CAPTURE_C;
         v.timingData.waveformCapture := '0';
      end if;

      -- Start run
      if (r.timingData.startRun = '1' and r.timingData.running = '0') then
         v.timingData.running                 := '1';
         v.timingData.runTime                 := (others => '0');
         -- START_RUN primes the first pending row; the first real row entry happens on rowStrobe.
         v.timingData.rowSeq                  := (others => '0');
         v.timingData.rowTime                 := (others => '0');
         v.timingData.rowSeqCount             := (others => '0');
         v.timingData.daqReadoutCount         := (others => '0');
         v.timingData.rowIndex                := (others => '0');
         v.timingData.rowIndexNext            := (others => '0');
         v.daqReadoutPeriodCounter            := (others => '0');
         v.endRunPending                      := '0';
         -- The byte after START_RUN primes the first pending row to be committed on rowStrobe.
         v.rowOrderAddr                       := (others => '0');
         v.startupBoundaryPending             := '1';
         v.pwrSyncWait                        := '0';
         v.txState                            := ROW_INDEX_S;

         v.timingTx := START_RUN_C;
      end if;


      if (r.timingData.running = '1') then
         v.timingData.startRun := '0';

         -- Normal free-running timebase. This is suppressed when waiting on pwrSync or when a row
         -- boundary is being consumed on the current cycle.
         if (r.pwrSyncWait = '0' and rowAdvanceReq = false) then
            v.timingData.runTime := r.timingData.runTime + 1;
            v.timingData.rowTime := r.timingData.rowTime + 1;
         end if;

         -- Once a sequence-start boundary is due, hold here until pwrSync arrives.
         if (rowAdvanceReq and rowSeqStartReq and r.pwrSyncEn = '1' and syncPulse = '0' and r.pwrSyncWait = '0') then
            v.pwrSyncWait := '1';

         elsif (rowAdvanceFire) then
            -- Commit the row transition on the same cycle that the boundary control word is emitted.
            v.timingData.runTime      := r.timingData.runTime + 1;
            v.timingData.rowTime      := (others => '0');
            v.timingData.rowSeq       := nextRowSeq;
            v.timingData.rowIndex     := r.timingData.rowIndexNext;
            v.timingData.rowStrobe    := '1';
            v.startupBoundaryPending  := '0';
            v.pwrSyncWait             := '0';

            if (r.endRunPending = '1') then
               -- Finish the current row transition cleanly, then emit END_RUN on the next cycle
               -- instead of sending another pending-row byte.
               v.txState := END_RUN_S;
            else
               -- Prefetch the row index that will be consumed on the following boundary.
               v.rowOrderAddr := prefetchRowSeq;
               v.txState      := ROW_INDEX_S;
            end if;

            v.timingTx := ROW_STROBE_C;
            if (rowSeqStartReq) then
               v.timingData.rowSeqStart := '1';
               v.timingData.rowSeqCount := r.timingData.rowSeqCount + 1;
               v.timingTx               := ROW_SEQ_START_C;

               if (daqReadoutStartReq) then
                  v.timingData.daqReadoutStart := '1';
                  v.timingData.daqReadoutCount := r.timingData.daqReadoutCount + 1;
                  v.timingTx                   := DAQ_READOUT_START_C;
               end if;

               v.daqReadoutPeriodCounter := r.daqReadoutPeriodCounter + 1;
               if (r.daqReadoutPeriodCounter = r.daqReadoutPeriod - 1) then
                  v.daqReadoutPeriodCounter := (others => '0');
               end if;
            end if;

         elsif (r.pwrSyncWait = '1') then
            -- Advertise the hold so TimingRx can freeze its counters too.
            v.timingTx := PWR_SYNC_WAIT_C;

         -- START_RUN is followed by one prime byte, and row-boundary control words normally carry
         -- the pending row index on the next cycle unless END_RUN has been armed.
         elsif (r.txState = ROW_INDEX_S) then
            v.timingTxK               := "0";
            v.timingTx                := rowOrderRamOut;
            v.timingData.rowIndexNext := rowOrderRamOut;
            v.txState                 := CONTROL_S;

         elsif (r.txState = END_RUN_S) then
            v.timingData.rowTime := (others => '0');
            v.timingData.running := '0';
            v.timingData.sample  := '0';
            v.timingData.endRun  := '1';
            v.endRunPending      := '0';
            v.txState            := CONTROL_S;
            v.timingTx           := END_RUN_C;

         elsif (r.pwrSyncWait = '0' and r.timingData.rowTime = stageNextRowTime) then
            v.timingData.stageNextRow := '1';
            v.timingTx                := STAGE_NEXT_ROW_C;

         elsif (r.startupBoundaryPending = '0' and r.pwrSyncWait = '0' and
                r.timingData.rowTime = r.sampleStartTime) then
            v.timingData.sample      := '1';
            v.timingData.firstSample := '1';
            v.timingTx               := SAMPLE_START_C;

         elsif (r.startupBoundaryPending = '0' and r.pwrSyncWait = '0' and
                r.timingData.rowTime = r.sampleEndTime) then
            v.timingData.sample     := '0';
            v.timingData.lastSample := '1';
            v.timingTx              := SAMPLE_END_C;

         end if;

      end if;


      if (wordRst = '1') then
         v := REG_INIT_C;
      end if;

      rin                  <= v;
      timingAxilWriteSlave <= r.axilWriteSlave;
      timingAxilReadSlave  <= r.axilReadSlave;

      xbarClkSel    <= r.xbarClkSel;
      xbarDataSel   <= r.xbarDataSel;
      xbarMgtSel    <= r.xbarMgtSel;
      xbarTimingSel <= r.xbarTimingSel;
      pwrSyncA      <= r.pwrSyncA;
      pwrSyncB      <= r.pwrSyncB;
      pwrSyncC      <= r.pwrSyncC;


   end process;

   seq : process (wordClk) is
   begin
      if (rising_edge(wordClk)) then
         r <= rin after TPD_G;
      end if;
   end process;

   --------------------------------------
   -- Output Timing Clock
   -------------------------------------
   U_ClkOutBufDiff_1 : entity surf.ClkOutBufDiff
      generic map (
         TPD_G => TPD_G)
      port map (
         clkIn   => wordClk,            --timingClk125,       -- [in]
         clkOutP => timingTxClkP,       -- [out]
         clkOutN => timingTxClkN);      -- [out]

   -------------------------------------------------------------------------------------------------
   -- Create serial clock for serializer
   -------------------------------------------------------------------------------------------------
   U_ClockManager7_1 : entity surf.ClockManager7
      generic map (
         TPD_G            => TPD_G,
         SIMULATION_G     => false,
         TYPE_G           => "PLL",
         INPUT_BUFG_G     => false,
         FB_BUFG_G        => true,
         OUTPUT_BUFG_G    => true,
         NUM_CLOCKS_G     => 2,
         BANDWIDTH_G      => "HIGH",
         CLKIN_PERIOD_G   => 8.0,
         DIVCLK_DIVIDE_G  => 1,
         CLKFBOUT_MULT_G  => 10,
         CLKOUT0_DIVIDE_G => 2,
         CLKOUT1_DIVIDE_G => 10)
      port map (
         clkIn     => timingRefClk,     -- [in]
         rstIn     => timingRefRst,     -- [in]
         clkOut(0) => bitClk,           -- [out]
         clkOut(1) => wordClk,          -- [out]         
         rstOut(0) => bitRst,           -- [out]
         rstOut(1) => wordRst);         -- [out]

   U_SyncClockFreq_REF : entity surf.SyncClockFreq
      generic map (
         TPD_G             => TPD_G,
--         USE_DSP_G         => USE_DSP_G,
         REF_CLK_FREQ_G    => AXIL_CLK_FREQ_G,
         REFRESH_RATE_G    => 100.0,
         CLK_LOWER_LIMIT_G => 124.0E6,
         CLK_UPPER_LIMIT_G => 126.0E6,
         COMMON_CLK_G      => true,
         CNT_WIDTH_G       => 32)
      port map (
         freqOut     => refClkFreq,     -- [out]
         freqUpdated => open,           -- [out]
         locked      => open,           -- [out]
         tooFast     => open,           -- [out]
         tooSlow     => open,           -- [out]
         clkIn       => timingRefClk,   -- [in]
         locClk      => wordClk,        -- [in]
         refClk      => axilClk);       -- [in]

   U_SyncClockFreq_WORD : entity surf.SyncClockFreq
      generic map (
         TPD_G             => TPD_G,
--         USE_DSP_G         => USE_DSP_G,
         REF_CLK_FREQ_G    => AXIL_CLK_FREQ_G,
         REFRESH_RATE_G    => 100.0,
         CLK_LOWER_LIMIT_G => 124.0E6,
         CLK_UPPER_LIMIT_G => 126.0E6,
         COMMON_CLK_G      => true,
         CNT_WIDTH_G       => 32)
      port map (
         freqOut     => wordClkFreq,    -- [out]
         freqUpdated => open,           -- [out]
         locked      => open,           -- [out]
         tooFast     => open,           -- [out]
         tooSlow     => open,           -- [out]
         clkIn       => wordClk,        -- [in]
         locClk      => wordClk,        -- [in]
         refClk      => axilClk);       -- [in]


   -- 
--    U_TimingMmcm_1 : entity warm_tdm.TimingMmcm
--       generic map (
--          TPD_G     => TPD_G,
--          USE_HPC_G => false,
--          CLKIN1_PERIOD_G    => 8.0,
--          DIVCLK_DIVIDE_G    => 1,
--          CLKFBOUT_MULT_F_G  => 5.0,
--          CLKOUT0_DIVIDE_F_G => 1.0,
--          CLKOUT1_DIVIDE_G   => 5)
--       port map (
--          timingRxClk => timingClk125,   -- [in]
--          timingRxRst => timingRst125,   -- [in]
--          bitClk      => bitClk,         -- [out]
--          bitRst      => bitRst,         -- [out]
--          wordClk     => wordClk,        -- [out]
--          wordRst     => wordRst);       -- [out]

   -------------------------------------------------------------------------------------------------
   -- 8B10B encode
   -------------------------------------------------------------------------------------------------
   U_Encoder8b10b_1 : entity surf.Encoder8b10b
      generic map (
         TPD_G          => TPD_G,
         RST_POLARITY_G => '1',
         NUM_BYTES_G    => 1)
      port map (
         clk     => wordClk,            -- [in]
         rst     => wordRst,            -- [in]
         dataIn  => r.timingTx,         -- [in]
         dataKIn => r.timingTxK,        -- [in]
         dataOut => timingTxCodeWord);  -- [out]


   -------------------------------------------------------------------------------------------------
   -- Serialize the data stream
   -------------------------------------------------------------------------------------------------
   U_TimingSerializer_1 : entity warm_tdm.TimingSerializer
      generic map (
         TPD_G => TPD_G)
      port map (
         rst           => wordRst,            -- [in]
         enable        => '1',                --r.enable,           -- [in]
         bitClk        => bitClk,             -- [in]
         timingTxDataP => timingTxDataP,      -- [in]
         timingTxDataN => timingTxDataN,      -- [in]
         wordClk       => wordClk,            -- [in]
         wordRst       => wordRst,            -- [in]
         dataIn        => timingTxCodeWord);  -- [out]


end architecture rtl;
