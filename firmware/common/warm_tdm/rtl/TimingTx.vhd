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
      runMode             : sl;
      softwareRowStrobe   : sl;
      rowPeriod           : slv(31 downto 0);
      numRows             : slv(15 downto 0);
      sampleStartTime     : slv(31 downto 0);
      sampleEndTime       : slv(31 downto 0);
      loadDacsTime        : slv(31 downto 0);
      waveformCaptureTime : slv(31 downto 0);
      -- State
      timingData          : LocalTimingType;
      timingTx            : slv(7 downto 0);
      timingTxK           : slv(0 downto 0);
      -- AXIL
      axilWriteSlave      : AxiLiteWriteSlaveType;
      axilReadSlave       : AxiLiteReadSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      xbarDataSel         => ite(RING_ADDR_0_G, "11", "00"),  -- Temporary loopback only
      xbarClkSel          => ite(RING_ADDR_0_G, "11", "00"),
      xbarMgtSel          => "01",
      xbarTimingSel       => "01",
      runMode             => SOFTWARE_C,
      softwareRowStrobe   => '0',
      rowPeriod           => toSlv(250, 32),                  -- 125 MHz / 256 = 488 kHz
      numRows             => toSlv(256, 16),                  -- Default of 64 rows
      sampleStartTime     => toSlv(32, 32),
      sampleEndTime       => toSlv(160, 32),                  -- Could be corner case here?
      loadDacsTime        => toSlv(200, 32),
      waveformCaptureTime => toSlv(1, 32),
      timingTx            => IDLE_C,
      timingTxK           => "1",
      timingData          => LOCAL_TIMING_INIT_C,
      axilWriteSlave      => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave       => AXI_LITE_READ_SLAVE_INIT_C);

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
         addr           => r.timingData.rowSeq,     -- [in]
         dout           => rowOrderRamOut);         -- [out]   

   comb : process (r, refClkFreq, rowOrderRamOut, timingAxilReadMaster, timingAxilWriteMaster,
                   wordClkFreq, wordRst) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndpointType;
   begin
      v := r;

      --------------------
      -- AXI Lite
      --------------------
      axiSlaveWaitTxn(axilEp, timingAxilWriteMaster, timingAxilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      -- Strobed signals
      v.softwareRowStrobe := '0';

      -- Configuration
      axiSlaveRegister(axilEp, X"00", 0, v.timingData.startRun);
      axiSlaveRegister(axilEp, X"04", 0, v.timingData.endRun);
      axiSlaveRegister(axilEp, X"08", 0, v.rowPeriod);
      axiSlaveRegister(axilEp, X"0C", 0, v.numRows);
      axiSlaveRegister(axilEp, X"10", 0, v.sampleStartTime);
      axiSlaveRegister(axilEp, X"14", 0, v.sampleEndTime);
      axiSlaveRegister(axilEp, X"18", 0, v.runMode);
      axiSlaveRegister(axilEp, X"1C", 0, v.softwareRowStrobe);

      axiSlaveRegister(axilEp, X"20", 0, v.timingData.waveformCapture);
      axiSlaveRegister(axilEp, X"24", 0, v.loadDacsTime);
      axiSlaveRegister(axilEp, X"28", 0, v.waveformCaptureTime);

      -- Status
      axiSlaveRegisterR(axilEp, X"30", 0, r.timingData.running);
      axiSlaveRegisterR(axilEp, X"30", 1, r.timingData.sample);
      axiSlaveRegisterR(axilEp, X"34", 0, r.timingData.rowSeq);
      axiSlaveRegisterR(axilEp, X"34", 16, r.timingData.rowIndex);
      axiSlaveRegisterR(axilEp, X"34", 24, r.timingData.rowIndexNext);
      axiSlaveRegisterR(axilEp, X"38", 0, r.timingData.rowTime);
      axiSlaveRegisterR(axilEp, X"40", 0, r.timingData.runTime);
      axiSlaveRegisterR(axilEp, X"48", 0, r.timingData.readoutCount);

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
      v.timingData.loadDacs    := '0';

      v.timingData.rowStrobe := '0';

      if (r.timingData.waveformCapture = '1' and r.waveformCaptureTime = r.timingData.rowTime) then
         v.timingTx                   := WAVEFORM_CAPTURE_C;
         v.timingData.waveformCapture := '0';
      end if;

      -- Start run
      if (r.timingData.startRun = '1' and r.timingData.running = '0') then
         v.timingData.running      := '1';
         v.timingData.runTime      := (others => '0');
         v.timingData.rowSeq       := (others => '0');
         v.timingData.rowTime      := (others => '0');
         v.timingData.readoutCount := (others => '0');

         v.timingTx := START_RUN_C;
      end if;


      if (r.timingData.running = '1') then
         v.timingData.startRun := '0';
         -- Count the things
         v.timingData.runTime  := r.timingData.runTime + 1;
         v.timingData.rowTime  := r.timingData.rowTime + 1;

         if ((r.runMode = HARDWARE_C and r.timingData.rowTime = r.rowPeriod-1) or
             (r.runMode = SOFTWARE_C and r.softwareRowStrobe = '1')) then

            v.timingData.rowTime := (others => '0');
            v.timingData.rowSeq  := r.timingData.rowSeq + 1;

            if (r.timingData.rowSeq = r.numRows-1) then
               v.timingData.rowSeq       := (others => '0');
               v.timingData.readoutCount := r.timingData.readoutCount + 1;
            end if;
         end if;

         -- Send codes
         if (r.runMode = HARDWARE_C and r.timingData.rowTime = 0 and r.timingData.startRun = '0') or
            (r.runMode = SOFTWARE_C and r.softwareRowStrobe = '1') then
            v.timingTx             := ROW_STROBE_C;
            v.timingData.rowStrobe := '1';

         elsif (r.timingTxK = "1" and (r.timingTx = ROW_STROBE_C or r.timingTx = START_RUN_C)) then
            v.timingTxK := "0";
            v.timingTx  := rowOrderRamOut;

         elsif (r.timingData.rowTime = r.sampleStartTime) then
            v.timingData.sample      := '1';
            v.timingData.firstSample := '1';
            v.timingTx               := SAMPLE_START_C;

         elsif (r.timingData.rowTime = r.sampleEndTime) then
            v.timingData.sample     := '0';
            v.timingData.lastSample := '1';
            v.timingTx              := SAMPLE_END_C;

         elsif (r.timingData.rowTime = r.loadDacsTime) then
            v.timingData.loadDacs := '1';
            v.timingTx            := LOAD_DACS_C;

         end if;

         -- Need to end run more cleanly than this
         if (r.timingData.endRun = '1') then
            v.timingData.running := '0';
            v.timingData.sample  := '0';
            v.timingData.endRun  := '0';
            v.timingTx           := END_RUN_C;
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
         locClk      => axilClk,        -- [in]
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
         locClk      => axilClk,        -- [in]
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
