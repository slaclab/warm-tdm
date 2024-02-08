-------------------------------------------------------------------------------
-- Title      : Row Module Timing
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Timing receiver logic for row module
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

entity TimingRx is

   generic (
      TPD_G             : time                  := 1 ns;
      SIMULATION_G      : boolean               := false;
      AXIL_CLK_FREQ_G   : real                  := 156.25E6;
      IODELAY_GROUP_G   : string                := "DEFAULT_GROUP";
      IDELAYCTRL_FREQ_G : real                  := 200.0;
      DEFAULT_DELAY_G   : integer range 0 to 31 := 0;
      AXIL_BASE_ADDR_G  : slv(31 downto 0)      := (others => '0'));

   port (
      timingRxClkP  : in sl;
      timingRxClkN  : in sl;
      timingRxDataP : in sl;
      timingRxDataN : in sl;

      timingRxClkOut  : out sl;
      timingRxRstOut  : out sl;
      timingRxDataOut : out LocalTimingType;

      timingRxLocked : out sl;

      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);

end entity TimingRx;

architecture rtl of TimingRx is

   signal timingRxClk : sl;
   signal timingRxRst : sl;
   signal bitClk      : sl;
   signal bitClkInv   : sl;
   signal bitRst      : sl;
   signal wordClk     : sl;
   signal wordRst     : sl;

   signal slip : sl;

   signal dlyLoad        : sl;
   signal dlyCfg         : slv(8 downto 0);
   signal enUsrDlyCfg    : sl;
   signal usrDlyCfg      : slv(8 downto 0) := (others => '0');
   signal errorDet       : sl;
   signal locked         : sl;
   signal realignGearbox : sl;

   signal timingRxCodeWord : slv(9 downto 0);
   signal timingRxValid    : sl;
   signal timingRxData     : slv(7 downto 0);
   signal timingRxDataK    : sl;
   signal codeErr          : sl;
   signal dispErr          : sl;

   signal rxClkFreq : slv(31 downto 0);

   type RegType is record
      timingRxData : LocalTimingType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      timingRxData => LOCAL_TIMING_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;


   -------------------------------------------------------------------------------------------------
   -- AXI Lite
   -------------------------------------------------------------------------------------------------

   constant NUM_AXIL_C : integer := 1;

   constant XBAR_COFNIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_C, AXIL_BASE_ADDR_G, 16, 12);

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_C-1 downto 0) := (others => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_C-1 downto 0)  := (others => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);

   type AxilRegType is record
      realignGearbox : sl;
      resetPll       : sl;
      delay          : slv(4 downto 0);
      set            : sl;
      minEyeWidth    : slv(7 downto 0);
      counterReset   : sl;
      readoutDebug0  : slv(9 downto 0);
      readoutDebug1  : slv(9 downto 0);
      readoutDebug2  : slv(9 downto 0);
      axilWriteSlave : AxiLiteWriteSlaveType;
      axilReadSlave  : AxiLiteReadSlaveType;
   end record AxilRegType;

   constant AXIL_REG_INIT_C : AxilRegType := (
      realignGearbox => '0',
      resetPll       => '0',
      delay          => toSlv(DEFAULT_DELAY_G, 5),
      set            => '0',
      minEyeWidth    => toSlv(ite(SIMULATION_G, 2, 64), 8),
      counterReset   => '0',
      readoutDebug0  => (others => '0'),
      readoutDebug1  => (others => '0'),
      readoutDebug2  => (others => '0'),
      axilWriteSlave => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave  => AXI_LITE_READ_SLAVE_INIT_C);

   signal axilR   : AxilRegType := AXIL_REG_INIT_C;
   signal axilRin : AxilRegType;

   signal curDelay        : slv(4 downto 0);
   signal lockedFallCount : slv(15 downto 0);
   signal errorDetCount   : slv(15 downto 0);
   signal lockedSync      : sl;
   signal debugDataValid  : sl;
   signal debugDataOut    : slv(9 downto 0);

   signal minEyeWidthSync : slv(7 downto 0);
   signal lockingCntCfg   : slv(23 downto 0) := ite(SIMULATION_G, X"000008", X"00FFFF");
   signal counterVector   : SlVectorArray(7 downto 0, 15 downto 0);
   signal statusVector    : slv(7 downto 0);



begin


   -------------------------
   -- 125 Mhz Timing RX clock
   -------------------------
   TIMING_RX_CLK_BUFF : IBUFGDS
      port map (
         i  => timingRxClkP,
         ib => timingRxClkN,
         o  => timingRxClk);

--    U_PwrUpRst_1 : entity surf.PwrUpRst
--       generic map (
--          TPD_G => TPD_G)
-- --         SIM_SPEEDUP_G  => SIMULATION_G,
-- --         DURATION_G     => DURATION_G)
--       port map (
--          arst   => '0',                 -- [in]
--          clk    => timingRxClk,         -- [in]
--          rstOut => timingRxRst);        -- [out]

   U_RstSync_1 : entity surf.RstSync
      generic map (
         TPD_G           => TPD_G,
         RELEASE_DELAY_G => 10,
         OUT_REG_RST_G   => false)
      port map (
         clk      => timingRxClk,       -- [in]
         asyncRst => axilR.resetPll,    -- [in]
         syncRst  => timingRxRst);      -- [out]

   timingRxClkOut <= wordClk;           --timingRxClk;
   timingRxRstOut <= wordRst;           --timingRxRst;


   -------------------------------------------------------------------------------------------------
   -- Create serial clock for deserializer
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
         BANDWIDTH_G      => "OPTIMIZED",
         CLKIN_PERIOD_G   => 8.0,
         DIVCLK_DIVIDE_G  => 1,
         CLKFBOUT_MULT_G  => 10,
         CLKOUT0_DIVIDE_G => 2,
         CLKOUT1_DIVIDE_G => 10)
      port map (
         clkIn     => timingRxClk,      -- [in]
         rstIn     => timingRxRst,      -- [in]
         clkOut(0) => bitClk,           -- [out]
         clkOut(1) => wordClk,          -- [out]         
         rstOut(0) => bitRst,           -- [out]
         rstOut(1) => wordRst);         -- [out]

--    U_TimingMmcm_1 : entity warm_tdm.TimingMmcm
--       generic map (
--          TPD_G              => TPD_G,
--          USE_HPC_G          => false,
--          CLKIN1_PERIOD_G    => 8.0,
--          DIVCLK_DIVIDE_G    => 1,
--          CLKFBOUT_MULT_F_G  => 5.0,
--          CLKOUT0_DIVIDE_F_G => 1.0,
--          CLKOUT1_DIVIDE_G   => 5)
--       port map (
--          timingRxClk => timingRxClk,    -- [in]
--          timingRxRst => timingRxRst,    -- [in]
--          bitClk      => bitClk,         -- [out]
--          wordClk     => wordClk,        -- [out]
--          wordRst     => wordRst);       -- [out]

   -------------------------------------------------------------------------------------------------
   -- Deserialize the incomming data
   -------------------------------------------------------------------------------------------------
   bitClkInv <= not bitClk;

   U_TimingDeserializer_1 : entity warm_tdm.TimingDeserializer
      generic map (
         TPD_G             => TPD_G,
         IODELAY_GROUP_G   => IODELAY_GROUP_G,
         DEFAULT_DELAY_G   => DEFAULT_DELAY_G,
         IDELAYCTRL_FREQ_G => IDELAYCTRL_FREQ_G)
      port map (
         rst           => wordRst,             -- [in]
         bitClk        => bitClk,              -- [in]
         bitClkInv     => bitClkInv,           -- [in]
         timingRxDataP => timingRxDataP,       -- [in]
         timingRxDataN => timingRxDataN,       -- [in]
         wordClk       => wordClk,             -- [in]
         wordRst       => wordRst,             -- [in]
         dataOut       => timingRxCodeWord,    -- [out]
         slip          => slip,                -- [in]
         sysClk        => wordClk,             -- [in]
         curDelay      => open,                -- [out]
         setDelay      => dlyCfg(8 downto 4),  -- [in]
         setValid      => dlyLoad);            -- [in]

   -------------------------------------------------------------------------------------------------
   -- 8B10B decode
   -------------------------------------------------------------------------------------------------
   U_Decoder8b10b_1 : entity surf.Decoder8b10b
      generic map (
         TPD_G       => TPD_G,
         NUM_BYTES_G => 1)
      port map (
         clk         => wordClk,           -- [in]
         rst         => wordRst,           -- [in]
         dataIn      => timingRxCodeWord,  -- [in]
         dataOut     => timingRxData,      -- [out]
         dataKOut(0) => timingRxDataK,     -- [out]
         validOut    => timingRxValid,     -- [out]
         codeErr(0)  => codeErr,           -- [out]
         dispErr(0)  => dispErr);          -- [out]

   -------------------------------------------------------------------------------------------------
   -- Aligner
   -------------------------------------------------------------------------------------------------
   U_SelectIoRxGearboxAligner_1 : entity surf.SelectIoRxGearboxAligner
      generic map (
         TPD_G           => TPD_G,
         SIMULATION_G    => SIMULATION_G,
         CODE_TYPE_G     => "LINE_CODE",
         DLY_STEP_SIZE_G => 16)
      port map (
         clk             => wordClk,          -- [in]
         rst             => wordRst,          -- [in]
         lineCodeValid   => timingRxValid,    -- [in]
         lineCodeErr     => codeErr,          -- [in]
         lineCodeDispErr => dispErr,          -- [in]
         linkOutOfSync   => realignGearbox,   -- [in]
         rxHeaderValid   => '0',              -- [in]
         rxHeader        => (others => '0'),  -- [in]
         bitSlip         => slip,             -- [out]
         dlyLoad         => dlyLoad,          -- [out]
         dlyCfg          => dlyCfg,           -- [out]
         enUsrDlyCfg     => enUsrDlyCfg,      -- [in]
         usrDlyCfg       => usrDlyCfg,        -- [in]
         bypFirstBerDet  => '1',              -- [in]
         minEyeWidth     => minEyeWidthSync,  -- [in]
         lockingCntCfg   => lockingCntCfg,    -- [in]
         errorDet        => errorDet,         -- [out]
         locked          => locked);          -- [out]

   timingRxLocked <= locked;

   -------------------------------------------------------------------------------------------------
   -- AXIL clock to word clock
   -------------------------------------------------------------------------------------------------
   Synchronizer_1 : entity surf.Synchronizer
      generic map (
         TPD_G    => TPD_G,
         STAGES_G => 3)
      port map (
         clk     => wordClk,
         rst     => wordRst,
         dataIn  => axilR.set,
         dataOut => enUsrDlyCfg);

   Synchronizer_2 : entity surf.Synchronizer
      generic map (
         TPD_G    => TPD_G,
         STAGES_G => 3)
      port map (
         clk     => wordClk,
         rst     => wordRst,
         dataIn  => axilR.realignGearbox,
         dataOut => realignGearbox);


   U_SynchronizerVector_1 : entity surf.SynchronizerVector
      generic map (
         TPD_G    => TPD_G,
         STAGES_G => 2,
         WIDTH_G  => 5)
      port map (
         clk     => wordClk,                 -- [in]
         rst     => wordRst,                 -- [in]
         dataIn  => axilR.delay,             -- [in]
         dataOut => usrDlyCfg(8 downto 4));  -- [out]

   U_SynchronizerVector_2 : entity surf.SynchronizerVector
      generic map (
         TPD_G    => TPD_G,
         STAGES_G => 2,
         WIDTH_G  => 5)
      port map (
         clk     => wordClk,             -- [in]
         rst     => wordRst,             -- [in]
         dataIn  => dlyCfg(8 downto 4),  -- [in]
         dataOut => curDelay);           -- [out]

   U_SynchronizerVector_3 : entity surf.SynchronizerVector
      generic map (
         TPD_G    => TPD_G,
         STAGES_G => 2,
         WIDTH_G  => 8)
      port map (
         clk     => wordClk,            -- [in]
         rst     => wordRst,            -- [in]
         dataIn  => axilR.minEyeWidth,  -- [in]
         dataOut => minEyeWidthSync);   -- [out]


   -------------------------------------------------------------------------------------------------
   -- Word clock to AXIL clock
   -------------------------------------------------------------------------------------------------
--    SynchronizerOneShotCnt_1 : entity surf.SynchronizerOneShotCnt
--       generic map (
--          TPD_G          => TPD_G,
--          IN_POLARITY_G  => '0',
--          OUT_POLARITY_G => '0',
--          CNT_RST_EDGE_G => true,
--          CNT_WIDTH_G    => 16)
--       port map (
--          dataIn     => locked,
--          rollOverEn => '0',
--          cntRst     => axilR.counterReset,
--          dataOut    => open,
--          cntOut     => lockedFallCount,
--          wrClk      => wordClk,
--          wrRst      => '0',
--          rdClk      => axilClk,
--          rdRst      => axilRst);

--    SynchronizerOneShotCnt_2 : entity surf.SynchronizerOneShotCnt
--       generic map (
--          TPD_G          => TPD_G,
--          IN_POLARITY_G  => '1',
--          OUT_POLARITY_G => '1',
--          CNT_RST_EDGE_G => false,
--          CNT_WIDTH_G    => 16)
--       port map (
--          dataIn     => errorDet,
--          rollOverEn => '0',
--          cntRst     => axilR.counterReset,
--          dataOut    => open,
--          cntOut     => errorDetCount,
--          wrClk      => wordClk,
--          wrRst      => '0',
--          rdClk      => axilClk,
--          rdRst      => axilRst);


--    Synchronizer_3 : entity surf.Synchronizer
--       generic map (
--          TPD_G    => TPD_G,
--          STAGES_G => 2)
--       port map (
--          clk     => axilClk,
--          rst     => axilRst,
--          dataIn  => locked,
--          dataOut => lockedSync);


   U_DataFifoDebug : entity surf.SynchronizerFifo
      generic map (
         TPD_G         => TPD_G,
         MEMORY_TYPE_G => "distributed",
         DATA_WIDTH_G  => 10,
         ADDR_WIDTH_G  => 4,
         INIT_G        => "0")
      port map (
         rst    => wordRst,
         wr_clk => wordClk,
         wr_en  => '1',                 --Always write data,
         din    => timingRxCodeWord,
         rd_clk => axilClk,
         rd_en  => debugDataValid,
         valid  => debugDataValid,
         dout   => debugDataOut);

   ----------------------------------------------------
   -- Monitor clock frequency
   ----------------------------------------------------
   U_SyncClockFreq_1 : entity surf.SyncClockFreq
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
         freqOut     => rxClkFreq,      -- [out]
         freqUpdated => open,           -- [out]
         locked      => open,           -- [out]
         tooFast     => open,           -- [out]
         tooSlow     => open,           -- [out]
         clkIn       => timingRxClk,    -- [in]
         locClk      => axilClk,        -- [in]
         refClk      => axilClk);       -- [in]

   U_SyncStatusVector_1 : entity surf.SyncStatusVector
      generic map (
         TPD_G          => TPD_G,
         COMMON_CLK_G   => false,
         USE_DSP_G      => "yes",
         SYNTH_CNT_G    => "11111111",
         CNT_RST_EDGE_G => true,
         CNT_WIDTH_G    => 16,
         WIDTH_G        => 8)
      port map (
         statusIn(0)  => locked,                      -- [in]
         statusIn(1)  => errorDet,                    -- [in]
         statusIn(2)  => r.timingRxData.startRun,     -- [in]
         statusIn(3)  => r.timingRxData.endRun,       -- [in]
         statusIn(4)  => r.timingRxData.rowStrobe,    -- [in]
         statusIn(5)  => r.timingRxData.firstSample,  -- [in]
         statusIn(6)  => r.timingRxData.lastSample,   -- [in]
         statusIn(7)  => r.timingRxData.rawAdc,       -- [in]
         statusOut    => statusVector,                -- [out]
         cntRstIn     => axilR.counterReset,          -- [in]
         rollOverEnIn => "01110000",                  -- [in]
         cntOut       => counterVector,               -- [out]
         wrClk        => wordClk,                     -- [in]
         wrRst        => wordRst,                     -- [in]
         rdClk        => axilClk,                     -- [in]
         rdRst        => axilRst);                    -- [in]

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







   -------------------------------------------------------------------------------------------------
   -- Transition to timingRxClk here from wordClk
   -- Is this ok?
   -------------------------------------------------------------------------------------------------
   comb : process (locked, r, timingRxData, timingRxDataK, timingRxValid, wordRst) is
      variable v : RegType;
   begin
      v := r;

      if (v.timingRxData.running = '1') then
         v.timingRxData.runTime := r.timingRxData.runTime + 1;
         v.timingRxData.rowTime := r.timingRxData.rowTime + 1;
      end if;

      v.timingRxData.startRun    := '0';
      v.timingRxData.endRun      := '0';
      v.timingRxData.rowStrobe   := '0';
      v.timingRxData.firstSample := '0';
      v.timingRxData.lastSample  := '0';
      v.timingRxData.loadDacs    := '0';
      v.timingRxData.rawAdc      := '0';

--      v.nextRowSeq := r.timingRxData.rowSeq + 1;

      if (timingRxValid = '1' and timingRxDataK = '1' and locked = '1') then

         case timingRxData is
            when START_RUN_C =>
               v.timingRxData.startRun     := '1';
               v.timingRxData.runTime      := (others => '0');
               v.timingRxData.readoutCount := (others => '0');
               v.timingRxData.running      := '1';
               v.timingRxData.sample       := '0';
               v.timingRxData.rowSeq       := (others => '1');
            when END_RUN_C =>
               v.timingRxData.endRun  := '1';
               v.timingRxData.running := '0';
               v.timingRxData.sample  := '0';
--             when FIRST_ROW_C =>
--                v.timingRxData.rowStrobe    := '1';
--                v.timingRxData.rowNum       := (others => '0');
--                v.timingRxData.rowTime      := (others => '0');
--                v.timingRxData.readoutCount := r.timingRxData.readoutCount + 1;
            when ROW_STROBE_C =>
               v.timingRxData.rowStrobe := '1';
               v.timingRxData.rowSeq    := r.timingRxData.rowSeq + 1;
               v.timingRxData.rowIndex  := r.timingRxData.rowIndexNext;
               v.timingRxData.rowTime   := (others => '0');
            when SAMPLE_START_C =>
               v.timingRxData.sample      := '1';
               v.timingRxData.firstSample := '1';
            when SAMPLE_END_C =>
               v.timingRxData.sample     := '0';
               v.timingRxData.lastSample := '1';
            when LOAD_DACS_C =>
               v.timingRxData.loadDacs := '1';
            when RAW_ADC_C =>
               v.timingRxData.rawAdc := '1';
            when others => null;
         end case;
      end if;

      -- First word after row strobe or start run is rowIndex for next strobe
      if (r.timingRxData.startRun = '1' or r.timingRxData.rowStrobe = '1') then
         v.timingRxData.rowIndexNext := timingRxData;
      end if;

      if (wordRst = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      timingRxDataOut <= r.timingRxData;

   end process comb;

   seq : process (wordClk) is
   begin
      if (rising_edge(wordClk)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

   -------------------------------------------------------------------------------------------------
   -- AXI-Lite interface
   -------------------------------------------------------------------------------------------------
   axilComb : process (axilR, axilRst, counterVector, curDelay, debugDataOut, debugDataValid,
                       locAxilReadMasters, locAxilWriteMasters, rxClkFreq, statusVector) is
      variable v      : AxilRegType;
      variable axilEp : AxiLiteEndpointType;
   begin
      v := axilR;

      v.set := '0';

      --v.curDelay := curDelay;

      -- Store last two samples read from ADC
      if (debugDataValid = '1') then
         v.readoutDebug0 := debugDataOut;
         v.readoutDebug1 := axilR.readoutDebug0;
         v.readoutDebug2 := axilR.readoutDebug1;
      end if;

      axiSlaveWaitTxn(axilEp, locAxilWriteMasters(0), locAxilReadMasters(0), v.axilWriteSlave, v.axilReadSlave);

      -- Up to 8 delay registers
      -- Write delay values to IDELAY primatives
      -- All writes go to same r.delay register,
      -- dataDelaySet(ch) or frameDelaySet enables the primative write
      axiSlaveRegister(axilEp, X"00", 0, v.delay);
      axiSlaveRegister(axilEp, X"00", 5, v.set, '1');
      axiSlaveRegisterR(axilEp, X"00", 8, curDelay);

      axiSlaveRegister(axilEp, X"04", 0, v.realignGearbox);
      axiSlaveRegister(axilEp, X"04", 1, v.resetPll);

      axiSlaveRegisterR(axilEp, X"08", 0, statusVector(0));  -- locked      

      -- Debug output to see how many times the shift has needed a relock
      axiSlaveRegisterR(axilEp, X"10", 0, muxSlVectorArray(counterVector, 0));  -- lock count
      axiSlaveRegisterR(axilEp, X"14", 0, muxSlVectorArray(counterVector, 1));  -- Error Det Count

      axiSlaveRegister(axilEp, X"1C", 0, v.counterReset);

      axiSlaveRegisterR(axilEp, X"20", 0, axilR.readoutDebug0);
      axiSlaveRegisterR(axilEp, X"20", 10, axilR.readoutDebug1);
      axiSlaveRegisterR(axilEp, X"20", 20, axilR.readoutDebug2);

      axiSlaveRegisterR(axilEp, X"30", 0, rxClkFreq);

      axiSlaveRegister(axilEp, X"40", 0, v.minEyeWidth);

      axiSlaveRegisterR(axilEp, X"50", 0, muxSlVectorArray(counterVector, 2));  -- start count
      axiSlaveRegisterR(axilEp, X"54", 0, muxSlVectorArray(counterVector, 3));  -- end count
      axiSlaveRegisterR(axilEp, X"58", 0, muxSlVectorArray(counterVector, 4));  -- row strobe count
      axiSlaveRegisterR(axilEp, X"5C", 0, muxSlVectorArray(counterVector, 5));  -- first sample count
      axiSlaveRegisterR(axilEp, X"60", 0, muxSlVectorArray(counterVector, 6));  -- last sample count
      axiSlaveRegisterR(axilEp, X"64", 0, muxSlVectorArray(counterVector, 7));  -- raw adc count

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      if (axilRst = '1') then
         v := AXIL_REG_INIT_C;
      end if;

      axilRin               <= v;
      locAxilWriteSlaves(0) <= axilR.axilWriteSlave;
      locAxilReadSlaves(0)  <= axilR.axilReadSlave;

   end process;

   axilSeq : process (axilClk) is
   begin
      if (rising_edge(axilClk)) then
         axilR <= axilRin after TPD_G;
      end if;
   end process axilSeq;

end architecture rtl;
