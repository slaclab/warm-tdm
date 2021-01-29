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
use surf.I2cPkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity TimingRx is

   generic (
      TPD_G             : time                  := 1 ns;
      SIMULATION_G      : boolean               := false;
      IODELAY_GROUP_G   : string                := "DEFAULT_GROUP";
      IDELAYCTRL_FREQ_G : real                  := 200.0;
      DEFAULT_DELAY_G   : integer range 0 to 31 := 0);

   port (
      timingRefClkP : in sl;
      timingRefClkN : in sl;

      timingRxClkP  : in sl;
      timingRxClkN  : in sl;
      timingRxDataP : in sl;
      timingRxDataN : in sl;

      timingClkOut : out sl;
      timingRstOut : out sl;
      timingData   : out LocalTimingType;

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
   signal wordClk     : sl;
   signal wordRst     : sl;

   signal slip : sl;

   signal dlyLoad     : sl;
   signal dlyCfg      : slv(8 downto 0);
   signal enUsrDlyCfg : sl;
   signal usrDlyCfg   : slv(8 downto 0) := (others => '0');
   signal errorDet    : sl;
   signal locked      : sl;

   signal timingRxCodeWord : slv(9 downto 0);
   signal timingRxValid    : sl;
   signal timingRxData     : slv(7 downto 0);
   signal timingRxDataK    : sl;
   signal codeErr          : sl;
   signal dispErr          : sl;

   signal timingRefClk  : sl;
   signal timingRefClkG : sl;

   signal idelayClk : sl;
   signal idelayRst : sl;

   type RegType is record
      timingData : LocalTimingType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      timingData => LOCAL_TIMING_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;


   attribute IODELAY_GROUP                 : string;
   attribute IODELAY_GROUP of IDELAYCTRL_0 : label is IODELAY_GROUP_G;

   -------------------------------------------------------------------------------------------------
   -- AXI Lite
   -------------------------------------------------------------------------------------------------
   type AxilRegType is record
      delay          : slv(4 downto 0);
      set            : sl;
      lockedCountRst : sl;
      readoutDebug0  : slv(9 downto 0);
      readoutDebug1  : slv(9 downto 0);
      readoutDebug2  : slv(9 downto 0);
      axilWriteSlave : AxiLiteWriteSlaveType;
      axilReadSlave  : AxiLiteReadSlaveType;
   end record AxilRegType;

   constant AXIL_REG_INIT_C : AxilRegType := (
      delay          => toSlv(DEFAULT_DELAY_G, 5),
      set            => '0',
      lockedCountRst => '0',
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

begin

   -------------------------------------------------------------------------------------------------
   -- USE Timing Refclk to create 200 MHz IODELAY CLK
   -------------------------------------------------------------------------------------------------
   U_IBUFDS_GTE2 : IBUFDS_GTE2
      port map (
         I     => timingRefClkP,
         IB    => timingRefClkN,
         CEB   => '0',
         ODIV2 => open,
         O     => timingRefClk);

   U_BUFG : BUFG
      port map (
         I => timingRefClk,
         O => timingRefClkG);

   U_MMCM_IDELAY : entity surf.ClockManager7
      generic map(
         TPD_G              => TPD_G,
         TYPE_G             => "MMCM",
         INPUT_BUFG_G       => false,
         FB_BUFG_G          => true,    -- Without this, will never lock in simulation
         RST_IN_POLARITY_G  => '1',
         NUM_CLOCKS_G       => 1,
         -- MMCM attributes
         BANDWIDTH_G        => "OPTIMIZED",
         CLKIN_PERIOD_G     => 4.0,     -- 250 MHz
         DIVCLK_DIVIDE_G    => 1,       -- 250 MHz
         CLKFBOUT_MULT_F_G  => 4.0,     -- 1.0GHz =  x 250 MHz
         CLKOUT0_DIVIDE_F_G => 5.0)     --  = 200 MHz = 1.0GHz/5
      port map(
         clkIn     => timingRefClkG,
         rstIn     => '0',
         clkOut(0) => idelayClk,
         rstOut(0) => idelayRst,
         locked    => open);


   -------------
   -- IDELAYCTRL
   -------------
   IDELAYCTRL_0 : IDELAYCTRL
      port map (
         RDY    => open,
         REFCLK => idelayClk,
         RST    => idelayRst);

   -------------------------
   -- 125 Mhz Timing clock
   -------------------------
   TIMING_RX_CLK_BUFF : IBUFGDS
      port map (
         i  => timingRxClkP,
         ib => timingRxClkN,
         o  => timingRxClk);

   U_PwrUpRst_1 : entity surf.PwrUpRst
      generic map (
         TPD_G => TPD_G)
--         SIM_SPEEDUP_G  => SIMULATION_G,
--         DURATION_G     => DURATION_G)
      port map (
         arst   => '0',                 -- [in]
         clk    => timingRxClk,         -- [in]
         rstOut => timingRxRst);        -- [out]

   timingClkOut <= timingRxClk;
   timingRstOut <= timingRxRst;


   -------------------------------------------------------------------------------------------------
   -- Create serial clock for deserializer
   -------------------------------------------------------------------------------------------------
   U_TimingMmcm_1 : entity warm_tdm.TimingMmcm
      generic map (
         TPD_G => TPD_G)
      port map (
         timingRxClk => timingRxClk,    -- [in]
         timingRxRst => timingRxRst,    -- [in]
         bitClk      => bitClk,         -- [out]
         wordClk     => wordClk,        -- [out]
         wordRst     => wordRst);       -- [out]

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
         rst           => '0',                 -- [in]
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
         TPD_G        => TPD_G,
         CODE_TYPE_G  => "LINE_CODE",
         SIMULATION_G => SIMULATION_G)
      port map (
         clk             => wordClk,          -- [in]
         rst             => wordRst,          -- [in]
         lineCodeValid   => timingRxValid,    -- [in]
         lineCodeErr     => codeErr,          -- [in]
         lineCodeDispErr => dispErr,          -- [in]
         linkOutOfSync   => '0',              -- [in]
         rxHeaderValid   => '0',              -- [in]
         rxHeader        => (others => '0'),  -- [in]
         bitSlip         => slip,             -- [out]
         dlyLoad         => dlyLoad,          -- [out]
         dlyCfg          => dlyCfg,           -- [out]
         enUsrDlyCfg     => enUsrDlyCfg,      -- [in]
         usrDlyCfg       => usrDlyCfg,        -- [in]
         bypFirstBerDet  => '1',              -- [in]
         minEyeWidth     => toSlv(8, 8),      -- [in]
--         lockingCntCfg   => lockingCntCfg,    -- [in]
         errorDet        => errorDet,         -- [out]
         locked          => locked);          -- [out]

   Synchronizer_1 : entity surf.Synchronizer
      generic map (
         TPD_G    => TPD_G,
         STAGES_G => 3)
      port map (
         clk     => wordClk,
         rst     => wordRst,
         dataIn  => axilR.set,
         dataOut => enUsrDlyCfg);

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


   SynchronizerOneShotCnt_1 : entity surf.SynchronizerOneShotCnt
      generic map (
         TPD_G          => TPD_G,
         IN_POLARITY_G  => '0',
         OUT_POLARITY_G => '0',
         CNT_RST_EDGE_G => true,
         CNT_WIDTH_G    => 16)
      port map (
         dataIn     => locked,
         rollOverEn => '0',
         cntRst     => axilR.lockedCountRst,
         dataOut    => open,
         cntOut     => lockedFallCount,
         wrClk      => wordClk,
         wrRst      => '0',
         rdClk      => axilClk,
         rdRst      => axilRst);

   SynchronizerOneShotCnt_2 : entity surf.SynchronizerOneShotCnt
      generic map (
         TPD_G          => TPD_G,
         IN_POLARITY_G  => '1',
         OUT_POLARITY_G => '1',
         CNT_RST_EDGE_G => true,
         CNT_WIDTH_G    => 16)
      port map (
         dataIn     => errorDet,
         rollOverEn => '0',
         cntRst     => axilR.lockedCountRst,
         dataOut    => open,
         cntOut     => errorDetCount,
         wrClk      => wordClk,
         wrRst      => '0',
         rdClk      => axilClk,
         rdRst      => axilRst);


   Synchronizer_2 : entity surf.Synchronizer
      generic map (
         TPD_G    => TPD_G,
         STAGES_G => 2)
      port map (
         clk     => axilClk,
         rst     => axilRst,
         dataIn  => locked,
         dataOut => lockedSync);


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


   -------------------------------------------------------------------------------------------------
   -- Transition to timingRxClk here from wordClk
   -- Is this ok?
   -------------------------------------------------------------------------------------------------
   comb : process (r, timingRxData, timingRxDataK, timingRxRst, timingRxValid) is
      variable v : RegType;
   begin
      v := r;

      if (v.timingData.running = '1') then
         v.timingData.runTime := r.timingData.runTime + 1;
         v.timingData.rowTime := r.timingData.rowTime + 1;
      end if;

      v.timingData.startRun  := '0';
      v.timingData.endRun    := '0';
      v.timingData.rowStrobe := '0';

      if (timingRxValid = '1' and timingRxDataK = '1') then
         case timingRxData is
            when START_RUN_C =>
               v.timingData.startRun := '1';
               v.timingData.runTime  := (others => '0');
               v.timingData.running  := '1';
            when END_RUN_C =>
               v.timingData.endRun  := '1';
               v.timingData.running := '0';
            when FIRST_ROW_C =>
               v.timingData.rowStrobe := '1';
               v.timingData.rowNum    := (others => '0');
               v.timingData.rowTime   := (others => '0');
            when ROW_STROBE_C =>
               v.timingData.rowStrobe := '1';
               v.timingData.rowNum    := r.timingData.rowNum + 1;
               v.timingData.rowTime   := (others => '0');
            when others => null;
         end case;
      end if;

      if (timingRxRst = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      timingData <= r.timingData;

   end process comb;

   seq : process (timingRxClk) is
   begin
      if (rising_edge(timingRxClk)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

   -------------------------------------------------------------------------------------------------
   -- AXI-Lite interface
   -------------------------------------------------------------------------------------------------
   axilComb : process (axilR, axilReadMaster, axilRst, axilWriteMaster, curDelay, debugDataOut,
                       debugDataValid, errorDetCount, lockedFallCount, lockedSync) is
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

      axiSlaveWaitTxn(axilEp, axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      -- Up to 8 delay registers
      -- Write delay values to IDELAY primatives
      -- All writes go to same r.delay register,
      -- dataDelaySet(ch) or frameDelaySet enables the primative write
      axiSlaveRegister(axilEp, X"00", 0, v.delay);
      axiSlaveRegister(axilEp, X"00", 5, v.set, '1');
      axiSlaveRegisterR(axilEp, X"00", 0, curDelay);

      -- Debug output to see how many times the shift has needed a relock
      axiSlaveRegisterR(axilEp, X"10", 0, lockedFallCount);
      axiSlaveRegisterR(axilEp, X"10", 16, lockedSync);
      axiSlaveRegisterR(axilEp, X"14", 0, errorDetCount);

      axiSlaveRegister(axilEp, X"1C", 0, v.lockedCountRst);

      axiSlaveRegisterR(axilEp, X"20", 0, axilR.readoutDebug0);
      axiSlaveRegisterR(axilEp, X"20", 10, axilR.readoutDebug1);
      axiSlaveRegisterR(axilEp, X"20", 20, axilR.readoutDebug2);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      if (axilRst = '1') then
         v := AXIL_REG_INIT_C;
      end if;

      axilRin        <= v;
      axilWriteSlave <= axilR.axilWriteSlave;
      axilReadSlave  <= axilR.axilReadSlave;

   end process;

   axilSeq : process (axilClk) is
   begin
      if (rising_edge(axilClk)) then
         axilR <= axilRin after TPD_G;
      end if;
   end process axilSeq;

end architecture rtl;
