-------------------------------------------------------------------------------
-- Title      : Floating Point PID ADC DSP
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   :
-- Standard   : VHDL'08
-------------------------------------------------------------------------------
-- Description: Floating point PI servo loop for TES SQUID readout.
-- Port-compatible with AdcDsp.vhd. Uses Xilinx FpMac, Int2Fp, and Fp2Int
-- IP cores for IEEE 754 single-precision arithmetic.
-- Outputs float32 on pidStreamMaster for downstream BiquadFilter.
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

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;
use surf.SsiPkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;
use warm_tdm.WarmTdmPkg.all;
use warm_tdm.FrameHeaderPkg.all;

entity AdcDspFp is

   generic (
      TPD_G            : time                 := 1 ns;
      SIMULATION_G     : boolean              := false;
      INVERT_SQ1FB_G   : boolean              := true;
      COLUMN_NUM_G     : integer range 0 to 7 := 0;
      ROW_ADDR_BITS_G  : integer range 3 to 8 := 7;
      GEN_PID_DEBUG_G  : boolean              := true;
      AXIL_BASE_ADDR_G : slv(31 downto 0)     := (others => '0');
      SQ1FB_RAM_ADDR_G : slv(31 downto 0)     := (others => '0'));

   port (
      timingRxClk125   : in  sl;
      timingRxRst125   : in  sl;
      timingRxData     : in  LocalTimingType;
      config           : in  WarmTdmConfigType := WARM_TDM_CONFIG_INIT_C;  -- board/group id (synchronized) for frame header
      accumIn          : in  AdcAccumResultType;
      accumValid       : in  sl;
      sAxilReadMaster  : in  AxiLiteReadMasterType;
      sAxilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      sAxilWriteMaster : in  AxiLiteWriteMasterType;
      sAxilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      mAxilReadMaster  : out AxiLiteReadMasterType;
      mAxilReadSlave   : in  AxiLiteReadSlaveType;
      mAxilWriteMaster : out AxiLiteWriteMasterType;
      mAxilWriteSlave  : in  AxiLiteWriteSlaveType;
      pidStreamMaster  : out AxiStreamMasterType;
      pidStreamSlave   : in  AxiStreamSlaveType;
      axisClk          : in  sl;
      axisRst          : in  sl;
      pidDebugMaster   : out AxiStreamMasterType;
      pidDebugSlave    : in  AxiStreamSlaveType);

end entity;

architecture rtl of AdcDspFp is

   constant NUM_AXIL_MASTERS_C : integer := 5;
   constant LOCAL_C            : integer := 0;
   constant ACCUM_ERROR_C      : integer := 1;
   constant SUM_ACCUM_C        : integer := 2;
   constant SQ1FB_FULL_C       : integer := 3;
   constant FLUX_JUMP_C        : integer := 4;

   constant XBAR_CONFIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) :=
      genAxiLiteConfig(NUM_AXIL_MASTERS_C, AXIL_BASE_ADDR_G, 16, 12);

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);

   signal timingAxilWriteMaster : AxiLiteWriteMasterType;
   signal timingAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal timingAxilReadMaster  : AxiLiteReadMasterType;
   signal timingAxilReadSlave   : AxiLiteReadSlaveType;

   -- ADC accumulation is still integer (14-bit ADC + up to 256 samples = 22 bits)
   constant ACCUM_BITS_C : integer := 22;

   constant SQ1FB_MAX_C : integer := 2**13-1;
   constant SQ1FB_MIN_C : integer := -(2**13);
   constant CLEAR_LAST_ADDR_C : slv(ROW_ADDR_BITS_G-1 downto 0) := toSlv((2**ROW_ADDR_BITS_G)-1, ROW_ADDR_BITS_G);

   -- FP constants
   constant FP_ONE_C     : slv(31 downto 0) := X"3F800000";  -- 1.0
   constant FP_ZERO_C    : slv(31 downto 0) := X"00000000";  -- 0.0
   constant FP_DAC_MAX_C : slv(31 downto 0) := X"45FFF800";  -- +8191.0
   constant FP_DAC_MIN_C : slv(31 downto 0) := X"C6000000";  -- -8192.0

   -- "Unseeded" marker written into the SQ1FB_FULL RAM by the clear, so the first
   -- visit of each row after StartRun/clearPidState initializes sq1FbFull from the
   -- seeded DAC value (accumIn.sq1FbDac) instead of the cleared 0 -- otherwise the
   -- servo starts from feedback 0 (SQ1 V-Phi extremum) and cannot lock at the
   -- tuned mid-slope operating point. This marker is reserved for initialization;
   -- configured gains and valid operating state must remain finite.
   constant SEED_SENTINEL_C : slv(31 downto 0) := X"7FC00000";  -- NaN = "unseeded"

   constant AXIS_DEBUG_CFG_C : AxiStreamConfigType := ssiAxiStreamConfig(
      dataBytes => 8,
      tKeepMode => TKEEP_COMP_C,
      tDestBits => 4);

   -- Select inferred RAM/FIFOs for portable control-logic simulation. The FP
   -- cores still need generated vendor models or explicit test-only stand-ins.
   constant MEMORY_SYNTH_MODE_C : string := ite(SIMULATION_G, "inferred", "xpm");

   type StateType is (
      IDLE_S,
      DEBUG_HDR1_S,
      DEBUG_BODY_S,
      WAIT_INT2FP_S,
      SEED_CONVERT_S,
      INTEGRATOR_S,
      PID_P_S,
      PID_I_S,
      FLUX_DIVIDE_S,
      FLUX_ROUND_S,
      FLUX_INT2FP_S,
      WRAP_S,
      DAC_CONVERT_S,
      CLIP_FEEDBACK_S,
      RAM_WRITE_S,
      DATA_STREAM_S);

   type RegType is record
      -- Software configuration
      fllEnable            : sl;
      rowEnableMask        : slv(255 downto 0);
      outputMode           : slv(1 downto 0);
      pCoef                : slv(31 downto 0);
      iCoef                : slv(31 downto 0);
      fluxQuantumFp        : slv(31 downto 0);
      invFluxQuantumFp     : slv(31 downto 0);
      axilPidDebugEnable   : sl;
      -- Accepted visit and its coefficient snapshot
      state                : StateType;
      logicalRow           : slv(ROW_ADDR_BITS_G-1 downto 0);
      rowEnabled           : sl;
      accumSamples         : unsigned(7 downto 0);
      accumError           : signed(ACCUM_BITS_C-1 downto 0);
      sq1FbDacSeed         : slv(13 downto 0);
      activePCoef          : slv(31 downto 0);
      activeICoef          : slv(31 downto 0);
      activeQuantum        : slv(31 downto 0);
      activeInvQuantum     : slv(31 downto 0);
      pidDebugEnable       : sl;
      waitCount            : unsigned(2 downto 0);
      -- Working PI/feedback values
      accumErrorFp         : slv(31 downto 0);
      sumAccumFp           : slv(31 downto 0);
      newSumAccum          : slv(31 downto 0);
      sq1FbFullFp          : slv(31 downto 0);
      sq1FbNewFp           : slv(31 downto 0);
      numFluxJumps         : signed(31 downto 0);
      numFluxJumpsFp       : slv(31 downto 0);
      sq1FbInt             : signed(31 downto 0);
      sq1FbValid           : sl;
      saturatedHigh        : sl;
      saturatedLow         : sl;
      -- State clearing and per-row RAM interface
      clearPidState        : sl;
      clearPidStateBusy    : sl;
      clearSumPending      : sl;
      clearSumBusy         : sl;
      pidStateRamAddr      : slv(ROW_ADDR_BITS_G-1 downto 0);
      ramWriteEnable       : slv(FLUX_JUMP_C downto ACCUM_ERROR_C);
      ramWriteData         : Slv32Array(FLUX_JUMP_C downto ACCUM_ERROR_C);
      -- Shared arithmetic core requests
      int2FpInValid        : sl;
      int2FpInData         : slv(31 downto 0);
      fpMacInValid         : sl;
      fpMacA               : slv(31 downto 0);
      fpMacB               : slv(31 downto 0);
      fpMacC               : slv(31 downto 0);
      fp2IntInValid        : sl;
      fp2IntInData         : slv(31 downto 0);
      -- Stream and register-bus outputs
      pidDebugMaster       : AxiStreamMasterType;
      pidStreamMaster      : AxiStreamMasterType;
      axilWriteSlave       : AxiLiteWriteSlaveType;
      axilReadSlave        : AxiLiteReadSlaveType;
      -- Diagnostics and outstanding DAC writes
      resetCounters        : sl;
      missedVisitCount     : unsigned(31 downto 0);
      discardedVisitCount  : unsigned(31 downto 0);
      dacOverflowCount     : unsigned(31 downto 0);
      dacErrorCount        : unsigned(31 downto 0);
      pendingDacWrites     : unsigned(5 downto 0);
      dropCount            : unsigned(31 downto 0);
   end record;

   constant REG_INIT_C : RegType := (
      fllEnable            => '0',
      rowEnableMask        => (others => '1'),
      rowEnabled           => '0',
      outputMode           => (others => '0'),
      state                => IDLE_S,
      logicalRow           => (others => '0'),
      accumSamples         => (others => '0'),
      accumError           => (others => '0'),
      sq1FbDacSeed         => (others => '0'),
      accumErrorFp         => (others => '0'),
      sumAccumFp           => (others => '0'),
      sq1FbFullFp          => (others => '0'),
      sq1FbNewFp           => (others => '0'),
      newSumAccum          => (others => '0'),
      numFluxJumps         => (others => '0'),
      pCoef                => (others => '0'),
      iCoef                => (others => '0'),
      fluxQuantumFp        => (others => '0'),
      invFluxQuantumFp     => (others => '0'),
      activePCoef          => (others => '0'),
      activeICoef          => (others => '0'),
      activeQuantum        => (others => '0'),
      activeInvQuantum     => (others => '0'),
      numFluxJumpsFp       => (others => '0'),
      clearSumPending      => '0',
      clearSumBusy         => '0',
      resetCounters        => '0',
      missedVisitCount     => (others => '0'),
      discardedVisitCount  => (others => '0'),
      dacOverflowCount     => (others => '0'),
      dacErrorCount        => (others => '0'),
      pendingDacWrites     => (others => '0'),
      sq1FbInt             => (others => '0'),
      sq1FbValid           => '0',
      clearPidState        => '0',
      clearPidStateBusy    => '0',
      pidStateRamAddr      => (others => '0'),
      waitCount            => (others => '0'),
      saturatedHigh        => '0',
      saturatedLow         => '0',
      ramWriteEnable       => (others => '0'),
      ramWriteData         => (others => (others => '0')),
      int2FpInValid        => '0',
      int2FpInData         => (others => '0'),
      fpMacInValid         => '0',
      fpMacA               => (others => '0'),
      fpMacB               => (others => '0'),
      fpMacC               => (others => '0'),
      fp2IntInValid        => '0',
      fp2IntInData         => (others => '0'),
      dropCount            => (others => '0'),
      axilPidDebugEnable   => '0',
      pidDebugEnable       => '0',
      pidDebugMaster       => axiStreamMasterInit(AXIS_DEBUG_CFG_C),
      pidStreamMaster      => axiStreamMasterInit(PID_DATA_FP_AXIS_CFG_C),
      axilWriteSlave       => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave        => AXI_LITE_READ_SLAVE_INIT_C);

   -- These procedures only assign next-cycle register values. The calling
   -- state still selects the operation and its completion/transition cycle.
   procedure launchMac (
      variable v : inout RegType;
      constant a, b, c : in slv(31 downto 0)) is
   begin
      v.fpMacInValid := '1';
      v.fpMacA := a;
      v.fpMacB := b;
      v.fpMacC := c;
   end procedure;

   procedure emitDebugPair (
      variable v : inout RegType;
      constant lowWord, highWord : in slv(31 downto 0)) is
   begin
      v.pidDebugMaster.tValid := v.pidDebugEnable;
      v.pidDebugMaster.tData(31 downto 0) := lowWord;
      v.pidDebugMaster.tData(63 downto 32) := highWord;
   end procedure;

   procedure clearRowState (
      variable v : inout RegType;
      constant allState : in boolean) is
   begin
      v.ramWriteEnable(SUM_ACCUM_C) := '1';
      v.ramWriteData(SUM_ACCUM_C) := FP_ZERO_C;
      if allState then
         v.ramWriteEnable := (others => '1');
         v.ramWriteData := (others => FP_ZERO_C);
         v.ramWriteData(SQ1FB_FULL_C) := SEED_SENTINEL_C;
      end if;
   end procedure;

   procedure completeFeedback (
      variable v : inout RegType;
      constant feedback : in slv(31 downto 0)) is
   begin
      v.sq1FbNewFp := feedback;
      v.sq1FbValid := v.rowEnabled;
      v.waitCount := (others => '0');
      v.state := RAM_WRITE_S;
   end procedure;

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal ramReadData : Slv32Array(FLUX_JUMP_C downto ACCUM_ERROR_C);

   signal int2FpOutValid : sl;
   signal int2FpOutData  : slv(31 downto 0);
   signal fpMacOutValid  : sl;
   signal fpMacOutData   : slv(31 downto 0);
   signal fp2IntOutValid : sl;
   signal fp2IntOutData  : slv(31 downto 0);

   signal pidDebugCtrl : AxiStreamCtrlType := AXI_STREAM_CTRL_UNUSED_C;

   -------------------------------------------------------------------------------------------------
   -- AXIL Signals for SQ1FB DAC writes
   -------------------------------------------------------------------------------------------------
   type AxilRegType is record
      fifoRd : sl;
      req    : AxiLiteReqType;
   end record AxilRegType;

   constant AXIL_REG_INIT_C : AxilRegType := (
      fifoRd => '0',
      req    => AXI_LITE_REQ_INIT_C);

   signal axilR   : AxilRegType := AXIL_REG_INIT_C;
   signal axilRin : AxilRegType;

   signal logicalRow8 : slv(7 downto 0);
   signal fifoDout  : slv(21 downto 0);
   signal fifoValid : sl;
   signal ack       : AxiLiteAckType;
   signal dacOverflow : sl;
   signal controlBusy : sl;
   signal dacWriteBusy : sl;

   -------------------------------------------------------------------------------------------------
   -- Convert DAC format to 2s complement and back
   -------------------------------------------------------------------------------------------------
   function convOffsetBin (
      vec : slv(13 downto 0))
      return slv is
      variable ret : slv(13 downto 0);
   begin
      if (INVERT_SQ1FB_G) then
         ret(13)          := vec(13);
         ret(12 downto 0) := not vec(12 downto 0);
      else
         ret(13)          := not vec(13);
         ret(12 downto 0) := vec(12 downto 0);
      end if;
      return ret;
   end function convOffsetBin;

   signal sq1fbOffsetBin : slv(13 downto 0);

   -------------------------------------------------------------------------------------------------
   -- FP IP Core component declarations
   -------------------------------------------------------------------------------------------------
   component FpMac
      port (
         aclk                 : in  std_logic;
         s_axis_a_tvalid      : in  std_logic;
         s_axis_a_tdata       : in  std_logic_vector(31 downto 0);
         s_axis_b_tvalid      : in  std_logic;
         s_axis_b_tdata       : in  std_logic_vector(31 downto 0);
         s_axis_c_tvalid      : in  std_logic;
         s_axis_c_tdata       : in  std_logic_vector(31 downto 0);
         m_axis_result_tvalid : out std_logic;
         m_axis_result_tdata  : out std_logic_vector(31 downto 0));
   end component;

   component Int2Fp
      port (
         aclk                 : in  std_logic;
         s_axis_a_tvalid      : in  std_logic;
         s_axis_a_tdata       : in  std_logic_vector(31 downto 0);
         m_axis_result_tvalid : out std_logic;
         m_axis_result_tdata  : out std_logic_vector(31 downto 0));
   end component;

   component Fp2Int
      port (
         aclk                 : in  std_logic;
         s_axis_a_tvalid      : in  std_logic;
         s_axis_a_tdata       : in  std_logic_vector(31 downto 0);
         m_axis_result_tvalid : out std_logic;
         m_axis_result_tdata  : out std_logic_vector(31 downto 0));
   end component;

begin

   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => XBAR_CONFIG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => timingRxClk125,
         axiClkRst           => timingRxRst125,
         sAxiWriteMasters(0) => sAxilWriteMaster,
         sAxiWriteSlaves(0)  => sAxilWriteSlave,
         sAxiReadMasters(0)  => sAxilReadMaster,
         sAxiReadSlaves(0)   => sAxilReadSlave,
         mAxiWriteMasters    => locAxilWriteMasters,
         mAxiWriteSlaves     => locAxilWriteSlaves,
         mAxiReadMasters     => locAxilReadMasters,
         mAxiReadSlaves      => locAxilReadSlaves);

   timingAxilReadMaster        <= locAxilReadMasters(LOCAL_C);
   locAxilReadSlaves(LOCAL_C)  <= timingAxilReadSlave;
   timingAxilWriteMaster       <= locAxilWriteMasters(LOCAL_C);
   locAxilWriteSlaves(LOCAL_C) <= timingAxilWriteSlave;

   -- Four independent per-row RAMs with the same port timing and geometry:
   -- error telemetry, integral history, unwrapped feedback, and wrap quotient.
   GEN_STATE_RAM : for bank in ACCUM_ERROR_C to FLUX_JUMP_C generate
      U_StateRam : entity surf.AxiDualPortRam
         generic map (
            TPD_G            => TPD_G,
            SYNTH_MODE_G     => MEMORY_SYNTH_MODE_C,
            MEMORY_TYPE_G    => "block",
            READ_LATENCY_G   => 3,
            AXI_WR_EN_G      => true,
            SYS_WR_EN_G      => true,
            SYS_BYTE_WR_EN_G => false,
            COMMON_CLK_G     => false,
            ADDR_WIDTH_G     => ROW_ADDR_BITS_G,
            DATA_WIDTH_G     => 32)
         port map (
            axiClk         => timingRxClk125,
            axiRst         => timingRxRst125,
            axiReadMaster  => locAxilReadMasters(bank),
            axiReadSlave   => locAxilReadSlaves(bank),
            axiWriteMaster => locAxilWriteMasters(bank),
            axiWriteSlave  => locAxilWriteSlaves(bank),
            clk            => timingRxClk125,
            rst            => timingRxRst125,
            addr           => r.pidStateRamAddr,
            we             => r.ramWriteEnable(bank),
            din            => r.ramWriteData(bank),
            dout           => ramReadData(bank));
   end generate GEN_STATE_RAM;

   -------------------------------------------------------------------------------------------------
   -- FP IP Core instances
   -------------------------------------------------------------------------------------------------
   U_Int2Fp_1 : Int2Fp
      port map (
         aclk                 => timingRxClk125,
         s_axis_a_tvalid      => r.int2FpInValid,
         s_axis_a_tdata       => r.int2FpInData,
         m_axis_result_tvalid => int2FpOutValid,
         m_axis_result_tdata  => int2FpOutData);

   U_FpMac_1 : FpMac
      port map (
         aclk                 => timingRxClk125,
         s_axis_a_tvalid      => r.fpMacInValid,
         s_axis_a_tdata       => r.fpMacA,
         s_axis_b_tvalid      => r.fpMacInValid,
         s_axis_b_tdata       => r.fpMacB,
         s_axis_c_tvalid      => r.fpMacInValid,
         s_axis_c_tdata       => r.fpMacC,
         m_axis_result_tvalid => fpMacOutValid,
         m_axis_result_tdata  => fpMacOutData);

   U_Fp2Int_1 : Fp2Int
      port map (
         aclk                 => timingRxClk125,
         s_axis_a_tvalid      => r.fp2IntInValid,
         s_axis_a_tdata       => r.fp2IntInData,
         m_axis_result_tvalid => fp2IntOutValid,
         m_axis_result_tdata  => fp2IntOutData);

   controlBusy <= '1' when r.state /= IDLE_S or r.clearPidStateBusy = '1' or
                           r.clearSumBusy = '1' or r.clearSumPending = '1' else '0';
   -- Track queued writes across the asynchronous FIFO pointer latency as well.
   dacWriteBusy <= '1' when r.pendingDacWrites /= 0 or r.sq1FbValid = '1' or
                            fifoValid = '1' or axilR.req.request = '1' or ack.done = '1' else '0';

   -------------------------------------------------------------------------------------------------
   -- Main combinatorial process
   -------------------------------------------------------------------------------------------------
   comb : process (all) is
      variable v              : RegType;
      variable requestClear   : boolean;
      variable iContribSign   : sl;
      variable negFluxQuantum : slv(31 downto 0);
      variable wrapReciprocal : slv(31 downto 0);
      variable clippedFeedback : slv(31 downto 0);
      variable axilEp         : AxiLiteEndpointType;
   begin
      v := r;

      v.clearPidState := '0';
      v.resetCounters := '0';

      ----------------------------------------------------------------------------------------------
      -- AXI Lite Registers
      ----------------------------------------------------------------------------------------------
      axiSlaveWaitTxn(axilEp, timingAxilWriteMaster, timingAxilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.fllEnable);
      axiSlaveRegister(axilEp, X"00", 8, v.outputMode);

      axiSlaveRegister(axilEp, X"04", 0, v.pCoef);
      axiSlaveRegister(axilEp, X"08", 0, v.iCoef);

      axiSlaveRegisterR(axilEp, X"10", 0, std_logic_vector(resize(r.accumError, 32)));
      axiSlaveRegisterR(axilEp, X"18", 0, r.sumAccumFp);
      axiSlaveRegisterR(axilEp, X"20", 0, r.sq1FbNewFp);
      axiSlaveRegisterR(axilEp, X"28", 0, r.sq1FbFullFp);
      axiSlaveRegisterR(axilEp, X"2C", 0, std_logic_vector(r.sq1FbInt));

      axiSlaveRegister(axilEp, X"30", 0, v.clearPidState);
      axiSlaveRegisterR(axilEp, X"34", 0, controlBusy);
      axiSlaveRegisterR(axilEp, X"34", 1, dacWriteBusy);
      axiSlaveRegister(axilEp, X"38", 0, v.resetCounters);
      axiSlaveRegisterR(axilEp, X"80", 0, std_logic_vector(r.missedVisitCount));
      axiSlaveRegisterR(axilEp, X"84", 0, std_logic_vector(r.discardedVisitCount));
      axiSlaveRegisterR(axilEp, X"88", 0, std_logic_vector(r.dacOverflowCount));
      axiSlaveRegisterR(axilEp, X"8C", 0, std_logic_vector(r.dacErrorCount));

      axiSlaveRegister(axilEp, X"40", 0, v.fluxQuantumFp);
      axiSlaveRegister(axilEp, X"44", 0, v.invFluxQuantumFp);

      axiSlaveRegister(axilEp, X"50", 0, v.axilPidDebugEnable);
      axiSlaveRegister(axilEp, X"60", 0, v.rowEnableMask);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      ----------------------------------------------------------------------------------------------
      -- Default assignments
      ----------------------------------------------------------------------------------------------
      v.sq1FbValid         := '0';
      v.pidStateRamAddr    := r.logicalRow;
      v.ramWriteEnable     := (others => '0');
      v.int2FpInValid      := '0';
      v.fpMacInValid       := '0';
      v.fp2IntInValid      := '0';

      v.pidStreamMaster  := axiStreamMasterInit(PID_DATA_FP_AXIS_CFG_C);
      v.pidDebugMaster   := axiStreamMasterInit(AXIS_DEBUG_CFG_C);
      v.pidDebugMaster.tDest := toSlv(1, 8);  -- Board-local PID-debug stream (DataPath U_AxiStreamMux_1 ROUTED re-stamps this anyway).

      -- Canonicalize signed zero; both +0 and -0 disable integral history.
      if (v.iCoef(30 downto 0) = (30 downto 0 => '0')) then
         v.iCoef := FP_ZERO_C;
      end if;
      if (v.iCoef /= r.iCoef) then
         v.clearSumPending := '1';
      end if;

      negFluxQuantum := (not r.activeQuantum(31)) & r.activeQuantum(30 downto 0);

      requestClear := false;

      if (timingRxData.startRun = '1') then
         v.dropCount  := (others => '0');
         requestClear := true;
      end if;

      if (v.clearPidState = '1') then
         requestClear := true;
      end if;

      if (r.fllEnable = '0' and v.fllEnable = '1') then
         requestClear := true;
      end if;

      ----------------------------------------------------------------------------------------------
      -- Visit-loss and DAC-delivery accounting (independent of arithmetic state)
      ----------------------------------------------------------------------------------------------
      -- Count only actual visits. Clear/disable discards are intentional;
      -- enabled arrivals while computing indicate an unsupported row schedule.
      if (accumValid = '1') then
         if (requestClear or r.clearPidStateBusy = '1' or r.clearSumBusy = '1' or
             (r.state = IDLE_S and v.clearSumPending = '1') or r.fllEnable = '0') then
            v.discardedVisitCount := r.discardedVisitCount + 1;
         elsif (r.state /= IDLE_S) then
            v.missedVisitCount := r.missedVisitCount + 1;
         end if;
      end if;
      if (dacOverflow = '1') then
         v.dacOverflowCount := r.dacOverflowCount + 1;
      end if;
      if (r.sq1FbValid = '1') then
         v.pendingDacWrites := v.pendingDacWrites + 1;
      end if;
      if (dacOverflow = '1') then
         v.pendingDacWrites := v.pendingDacWrites - 1;
      end if;
      if (axilR.req.request = '1' and ack.done = '1') then
         v.pendingDacWrites := v.pendingDacWrites - 1;
      end if;
      if (axilR.req.request = '1' and ack.done = '1' and ack.resp /= AXI_RESP_OK_C) then
         v.dacErrorCount := r.dacErrorCount + 1;
      end if;
      if (v.resetCounters = '1' or timingRxData.startRun = '1') then
         v.missedVisitCount := (others => '0');
         v.discardedVisitCount := (others => '0');
         v.dacOverflowCount := (others => '0');
         v.dacErrorCount := (others => '0');
      end if;

      ----------------------------------------------------------------------------------------------
      -- Clearing has priority over accepting/continuing a visit.
      ----------------------------------------------------------------------------------------------
      if (requestClear) then
         v.clearSumPending := '0';
         v.clearSumBusy := '0';
         v.clearPidStateBusy := '1';
         v.state             := IDLE_S;
         v.rowEnabled        := '0';
         v.accumSamples      := (others => '0');
         v.accumError        := (others => '0');
         v.accumErrorFp      := (others => '0');
         v.sumAccumFp        := (others => '0');
         v.sq1FbFullFp       := (others => '0');
         v.sq1FbNewFp        := (others => '0');
         v.newSumAccum       := (others => '0');
         v.numFluxJumps      := (others => '0');
         v.sq1FbInt          := (others => '0');
         v.sq1FbValid        := '0';
         v.pidDebugEnable    := '0';
         v.pidStateRamAddr   := (others => '0');
         clearRowState(v, true);
      elsif (r.clearPidStateBusy = '1' or r.clearSumBusy = '1') then
         -- Both sweeps walk the same address sequence; integral-only clearing
         -- leaves feedback, quotient and unseeded markers untouched.
         v.state := IDLE_S;
         clearRowState(v, r.clearPidStateBusy = '1');
         if (r.pidStateRamAddr = CLEAR_LAST_ADDR_C) then
            v.clearPidStateBusy := '0';
            v.clearSumBusy := '0';
         else
            v.pidStateRamAddr := slv(unsigned(r.pidStateRamAddr) + 1);
         end if;

      elsif (r.state = IDLE_S and v.clearSumPending = '1') then
         v.clearSumPending := '0';
         v.clearSumBusy := '1';
         v.pidStateRamAddr := (others => '0');
         clearRowState(v, false);
         v.sumAccumFp := FP_ZERO_C;
         v.newSumAccum := FP_ZERO_C;
      elsif (r.state = IDLE_S and r.fllEnable = '0' and accumValid = '1' and accumIn.seqStart = '1') then
         v.pidStreamMaster.tValid := '1';
         v.pidStreamMaster.tKeep  := (others => '0');
         v.pidStreamMaster.tLast  := '1';

      -- Disabling prevents new visits but drains the accepted visit and DAC
      -- queue. ControlBusy/DacWriteBusy expose when configuration is quiescent.
      elsif (r.fllEnable = '1' or r.state /= IDLE_S) then
         case r.state is
            -------------------------------------------------------------------
            -- IDLE_S
            -- Wait for new accumulation result. Capture inputs, launch Int2Fp,
            -- present logicalRow to RAMs, emit debug SOF header.
            -------------------------------------------------------------------
            when IDLE_S =>
               v.pidDebugEnable := not pidDebugCtrl.pause and r.axilPidDebugEnable;
               if (accumValid = '1' and r.axilPidDebugEnable = '1' and pidDebugCtrl.pause = '1') then
                  v.dropCount := r.dropCount + 1;
               end if;

               if (accumValid = '1') then
                  -- Capture accumulation inputs
                  v.logicalRow   := accumIn.logicalRow(ROW_ADDR_BITS_G-1 downto 0);
                  v.accumError   := resize(accumIn.accumError, ACCUM_BITS_C);
                  v.accumSamples := accumIn.numSamples;
                  v.rowEnabled   := r.rowEnableMask(to_integer(unsigned(accumIn.logicalRow)));
                  -- Capture the seeded DAC feedback; used to initialize sq1FbFull
                  -- on this row's first visit after a clear (SEED_CONVERT_S).
                  v.sq1FbDacSeed := accumIn.sq1FbDac;
                  v.activePCoef := v.pCoef;
                  v.activeICoef := v.iCoef;
                  v.activeQuantum := v.fluxQuantumFp;
                  v.activeInvQuantum := v.invFluxQuantumFp;

                  -- Launch Int2Fp(accumError) -- result ready in 2 cycles
                  v.int2FpInValid := '1';
                  v.int2FpInData  := std_logic_vector(resize(accumIn.accumError, 32));

                  -- Handle sequence start frame marker
                  if (accumIn.seqStart = '1') then
                     v.pidStreamMaster.tValid := '1';
                     v.pidStreamMaster.tKeep  := (others => '0');
                     v.pidStreamMaster.tLast  := '1';
                  end if;

                  -- Frame word 0: shared identity header (SOF here). The old
                  -- col/row/runTime word is demoted to a body word (DEBUG_BODY_S).
                  emitFrameHeaderWord0(
                     axisConfig => AXIS_DEBUG_CFG_C,
                     axisMaster => v.pidDebugMaster,
                     formatType => FRAME_FORMAT_PID_FLOAT_C,
                     boardId    => "00000" & config.boardId,
                     groupId    => config.groupId,
                     valid      => v.pidDebugEnable);

                  v.waitCount := (others => '0');
                  v.state     := DEBUG_HDR1_S;
               end if;

            -- Frame word 1: 64-bit absolute-ns timestamp.
            when DEBUG_HDR1_S =>
               emitFrameHeaderWord1(
                  axisMaster  => v.pidDebugMaster,
                  timestampNs => timingRxData.runTimeNs,
                  valid       => r.pidDebugEnable);
               v.state := DEBUG_BODY_S;

            -- Frame body word 0 (was word 0 pre-header): column + row index. The
            -- runTime bits it used to carry are superseded by the header timestamp.
            when DEBUG_BODY_S =>
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(3 downto 0)  := toSlv(COLUMN_NUM_G, 4);
               v.pidDebugMaster.tData(15 downto 8) := resize(r.logicalRow, 8);
               v.state                             := WAIT_INT2FP_S;

            -------------------------------------------------------------------
            -- WAIT_INT2FP_S (4 cycles: wc=0..3)
            -- Wait for RAM read latency (READ_LATENCY_G=3) and Int2Fp
            -- (C_Latency=2). Poll int2FpOutValid to capture accumErrorFp.
            -- At wc=3: capture RAM outputs, launch integrator FpMac.
            -------------------------------------------------------------------
            when WAIT_INT2FP_S =>
               -- Capture the pipelined error conversion when valid.
               if (int2FpOutValid = '1') then
                  v.accumErrorFp := int2FpOutData;
               end if;

               if (r.waitCount = 3) then
                  -- RAM outputs are valid after READ_LATENCY_G=3 cycles
                  v.sumAccumFp   := ramReadData(SUM_ACCUM_C);
                  v.numFluxJumps := signed(ramReadData(FLUX_JUMP_C));
                  v.waitCount    := (others => '0');

                  if (ramReadData(SQ1FB_FULL_C) = SEED_SENTINEL_C) then
                     -- First visit for this row since the clear: convert the
                     -- seeded DAC feedback to float (Int2Fp is free now that
                     -- accumError is captured) and finish the integrator launch in
                     -- SEED_CONVERT_S once sq1FbFull is established.
                     v.int2FpInValid := '1';
                     v.int2FpInData  := std_logic_vector(resize(signed(convOffsetBin(r.sq1FbDacSeed)), 32));
                     v.state         := SEED_CONVERT_S;
                  else
                     v.sq1FbFullFp  := ramReadData(SQ1FB_FULL_C);

                     -- Launch FpMac: integrator = 1.0 * accumErrorFp + sumAccumFp
                     launchMac(v, FP_ONE_C, v.accumErrorFp, ramReadData(SUM_ACCUM_C));

                     v.state        := INTEGRATOR_S;
                  end if;
               else
                  v.waitCount := r.waitCount + 1;
               end if;

            -------------------------------------------------------------------
            -- SEED_CONVERT_S (first visit per row after a clear)
            -- Wait for Int2Fp(seed DAC) -> establish sq1FbFull from the seeded
            -- operating point, then launch the integrator FpMac (same as the
            -- WAIT_INT2FP_S seeded==false path) so the servo starts locked at the
            -- tuned point instead of feedback 0 (V-Phi extremum).
            -------------------------------------------------------------------
            when SEED_CONVERT_S =>
               if (int2FpOutValid = '1') then
                  v.sq1FbFullFp  := int2FpOutData;

                  -- Launch FpMac: integrator = 1.0 * accumErrorFp + sumAccumFp
                  launchMac(v, FP_ONE_C, r.accumErrorFp, r.sumAccumFp);

                  v.waitCount    := (others => '0');
                  v.state        := INTEGRATOR_S;
               end if;

            -------------------------------------------------------------------
            -- INTEGRATOR_S
            -- Wait for FpMac result (newSumAccum = accumError + sumAccum).
            -- Emit debug Word 1. Launch P-term FpMac.
            -------------------------------------------------------------------
            when INTEGRATOR_S =>
               -- Debug Word 1 (first cycle only): accumErrorFp | sq1FbFullFp
               if (r.waitCount = 0) then
                  emitDebugPair(v, r.accumErrorFp, r.sq1FbFullFp);
                  v.waitCount := to_unsigned(1, 3);
               end if;

               if (fpMacOutValid = '1') then
                  v.newSumAccum := fpMacOutData;

                  -- Launch FpMac: P-term = pCoef * accumErrorFp + sq1FbFullFp
                  launchMac(v, r.activePCoef, r.accumErrorFp, r.sq1FbFullFp);

                  v.waitCount := (others => '0');
                  v.state     := PID_P_S;
               end if;

            -------------------------------------------------------------------
            -- PID_P_S
            -- Wait for P-term FpMac result. Emit debug Word 2.
            -- Launch I-term FpMac.
            -------------------------------------------------------------------
            when PID_P_S =>
               -- Debug Word 2 (first cycle only): sumAccumFp | newSumAccum
               if (r.waitCount = 0) then
                  emitDebugPair(v, r.sumAccumFp, r.newSumAccum);
                  v.waitCount := to_unsigned(1, 3);
               end if;

               if (fpMacOutValid = '1') then
                  -- Capture P-term intermediate, launch I-term
                  -- I-term = iCoef * sumAccumFp + P-term result
                  launchMac(v, r.activeICoef, r.sumAccumFp, fpMacOutData);

                  v.waitCount := (others => '0');
                  v.state     := PID_I_S;
               end if;

            -------------------------------------------------------------------
            -- PID_I_S
            -- Wait for I-term FpMac result (sq1FbNewFp = full PI output).
            -- Launch flux divide FpMac.
            -------------------------------------------------------------------
            when PID_I_S =>
               if (fpMacOutValid = '1') then
                  v.sq1FbNewFp := fpMacOutData;

                  -- R=0 disables wrapping even if the raw inverse is stale.
                  wrapReciprocal := r.activeInvQuantum;
                  if (r.activeQuantum(30 downto 0) = (30 downto 0 => '0')) then
                     wrapReciprocal := FP_ZERO_C;
                  end if;
                  launchMac(v, wrapReciprocal, fpMacOutData, FP_ZERO_C);

                  v.waitCount := (others => '0');
                  v.state     := FLUX_DIVIDE_S;
               end if;

            -------------------------------------------------------------------
            -- FLUX_DIVIDE_S
            -- Wait for FpMac result (jumpsFp). Launch nearest-even Fp2Int conversion.
            -------------------------------------------------------------------
            when FLUX_DIVIDE_S =>
               if (fpMacOutValid = '1') then
                  -- Convert jumpsFp to integer (round to nearest, ties to even)
                  v.fp2IntInValid := '1';
                  v.fp2IntInData  := fpMacOutData;

                  v.waitCount := (others => '0');
                  v.state     := FLUX_ROUND_S;
               end if;

            -------------------------------------------------------------------
            -- FLUX_ROUND_S
            -- Wait for Fp2Int result (numFluxJumps integer).
            -- Launch Int2Fp(numFluxJumps) for wrap calculation.
            -------------------------------------------------------------------
            when FLUX_ROUND_S =>
               if (fp2IntOutValid = '1') then
                  v.numFluxJumps := signed(fp2IntOutData);

                  -- Launch Int2Fp(numFluxJumps) for wrap computation
                  v.int2FpInValid := '1';
                  v.int2FpInData  := fp2IntOutData;

                  v.waitCount := (others => '0');
                  v.state     := FLUX_INT2FP_S;
               end if;

            -------------------------------------------------------------------
            -- FLUX_INT2FP_S
            -- Wait for Int2Fp result (numFluxJumpsFp).
            -- Launch FpMac: numFluxJumpsFp * negFluxQuantum + sq1FbNewFp
            -- (wraps feedback by subtracting numFluxJumps * fluxQuantum)
            -------------------------------------------------------------------
            when FLUX_INT2FP_S =>
               if (int2FpOutValid = '1') then
                  v.numFluxJumpsFp := int2FpOutData;
                  -- Launch FpMac: numFluxJumpsFp * (-fluxQuantum) + sq1FbNewFp
                  launchMac(v, int2FpOutData, negFluxQuantum, r.sq1FbNewFp);

                  v.waitCount := (others => '0');
                  v.state     := WRAP_S;
               end if;

            -------------------------------------------------------------------
            -- WRAP_S
            -- Wait for wrapped feedback from FpMac.
            -- Launch Fp2Int for DAC conversion.
            -------------------------------------------------------------------
            when WRAP_S =>
               if (fpMacOutValid = '1') then
                  -- Launch Fp2Int for DAC conversion
                  v.fp2IntInValid := '1';
                  v.fp2IntInData  := fpMacOutData;

                  v.waitCount := (others => '0');
                  v.state     := DAC_CONVERT_S;
               end if;

            -------------------------------------------------------------------
            -- DAC_CONVERT_S
            -- Wait for Fp2Int result. Clip to DAC range, set saturation flags.
            -- Emit debug Word 3 after any clipped-feedback back-calculation.
            -------------------------------------------------------------------
            when DAC_CONVERT_S =>
               if (fp2IntOutValid = '1') then
                  v.sq1FbInt      := signed(fp2IntOutData);
                  v.saturatedHigh := '0';
                  v.saturatedLow  := '0';

                  -- Clip to DAC range
                  if (signed(fp2IntOutData) > SQ1FB_MAX_C) then
                     v.sq1FbInt      := to_signed(SQ1FB_MAX_C, 32);
                     v.saturatedHigh := '1';
                  elsif (signed(fp2IntOutData) < SQ1FB_MIN_C) then
                     v.sq1FbInt      := to_signed(SQ1FB_MIN_C, 32);
                     v.saturatedLow  := '1';
                  end if;

                  if (v.saturatedHigh = '1' or v.saturatedLow = '1') then
                     -- Back-calculate accepted unwrapped feedback only on clipping.
                     -- Reuse FpMac: J*R + clipped local DAC, preserving flux history.
                     if (v.saturatedHigh = '1') then
                        clippedFeedback := FP_DAC_MAX_C;
                     else
                        clippedFeedback := FP_DAC_MIN_C;
                     end if;
                     launchMac(v, r.numFluxJumpsFp, r.activeQuantum, clippedFeedback);
                     v.state := CLIP_FEEDBACK_S;
                  else
                     completeFeedback(v, r.sq1FbNewFp);
                     emitDebugPair(v, r.sq1FbNewFp, std_logic_vector(r.numFluxJumps));
                  end if;
               end if;

            when CLIP_FEEDBACK_S =>
               if (fpMacOutValid = '1') then
                  completeFeedback(v, fpMacOutData);
                  emitDebugPair(v, fpMacOutData, std_logic_vector(r.numFluxJumps));
               end if;

            -------------------------------------------------------------------
            -- RAM_WRITE_S (2 cycles)
            -- Anti-windup decision. Write SUM_ACCUM, SQ1FB_FULL, FLUX_JUMP
            -- RAMs. Emit debug Word 4 (EOF).
            -------------------------------------------------------------------
            when RAM_WRITE_S =>
               if (r.waitCount = 0) then
                  -- Debug Word 4 (EOF):
                  -- sq1FbInt[13:0] | pad[15:14] | accumSamples[23:16] | pad[31:24] | dropCount[63:32]
                  v.pidDebugMaster.tValid              := r.pidDebugEnable;
                  v.pidDebugMaster.tLast               := '1';
                  v.pidDebugMaster.tData(13 downto 0)  := std_logic_vector(r.sq1FbInt(13 downto 0));
                  v.pidDebugMaster.tData(15 downto 14) := "00";
                  v.pidDebugMaster.tData(23 downto 16) := std_logic_vector(r.accumSamples);
                  v.pidDebugMaster.tData(31 downto 24) := (others => '0');
                  v.pidDebugMaster.tData(63 downto 32) := std_logic_vector(r.dropCount);

                  -- Anti-windup: determine sign of I-contribution
                  iContribSign := r.activeICoef(31) xor r.accumErrorFp(31);

                  if (r.activeICoef(30 downto 0) = (30 downto 0 => '0')) then
                     v.ramWriteData(SUM_ACCUM_C) := FP_ZERO_C;
                  elsif (r.saturatedHigh = '1' and iContribSign = '0') or
                     (r.saturatedLow = '1' and iContribSign = '1') then
                     -- Discard integrator update (anti-windup active)
                     v.ramWriteData(SUM_ACCUM_C) := r.sumAccumFp;
                  else
                     -- Commit integrator
                     v.ramWriteData(SUM_ACCUM_C) := r.newSumAccum;
                  end if;

                  -- Error telemetry always updates; masked control state holds.
                  v.ramWriteEnable(ACCUM_ERROR_C) := '1';
                  v.ramWriteData(ACCUM_ERROR_C)   := r.accumErrorFp;
                  v.ramWriteEnable(SUM_ACCUM_C)   := r.rowEnabled;
                  v.ramWriteEnable(SQ1FB_FULL_C)  := r.rowEnabled;
                  v.ramWriteData(SQ1FB_FULL_C)    := r.sq1FbNewFp;
                  v.ramWriteEnable(FLUX_JUMP_C)   := r.rowEnabled;
                  v.ramWriteData(FLUX_JUMP_C)     := std_logic_vector(r.numFluxJumps);

                  v.waitCount := to_unsigned(1, 3);
               else
                  v.state := DATA_STREAM_S;
               end if;

            -------------------------------------------------------------------
            -- DATA_STREAM_S
            -- Emit PID stream output based on outputMode selection.
            -------------------------------------------------------------------
            when DATA_STREAM_S =>
               v.pidStreamMaster.tValid := r.rowEnabled;
               if (r.outputMode = "00") then
                  -- Output unwrapped sq1FbNew as float (primary mode)
                  v.pidStreamMaster.tData(31 downto 0) := r.sq1FbNewFp;
               elsif (r.outputMode = "01") then
                  -- Output accumError as float
                  v.pidStreamMaster.tData(31 downto 0) := r.accumErrorFp;
               elsif (r.outputMode = "10") then
                  -- Output row sequence count (for diagnostics)
                  v.pidStreamMaster.tData(31 downto 0) := timingRxData.rowSeqCount(31 downto 0);
               elsif (r.outputMode = "11") then
                  -- Output newSumAccum as float
                  v.pidStreamMaster.tData(31 downto 0) := r.newSumAccum;
               end if;

               v.pidStreamMaster.tId(ROW_ADDR_BITS_G-1 downto 0) := r.logicalRow;
               v.state := IDLE_S;

         end case;
      end if;

      if (v.clearPidStateBusy = '0' and v.clearSumBusy = '0') then
         v.pidStateRamAddr := v.logicalRow;
      end if;

      if (timingRxRst125 = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      timingAxilWriteSlave <= r.axilWriteSlave;
      timingAxilReadSlave  <= r.axilReadSlave;

   end process;

   seq : process (timingRxClk125) is
   begin
      if (rising_edge(timingRxClk125)) then
         r <= rin after TPD_G;
      end if;
   end process;

   -------------------------------------------------------------------------------------------------
   -- Debug stream to axisClk domain
   -------------------------------------------------------------------------------------------------
   GEN_PID_DEBUG : if (GEN_PID_DEBUG_G) generate
      U_AxiStreamFifoV2_PID_DEBUG : entity surf.AxiStreamFifoV2
         generic map (
            TPD_G               => TPD_G,
            INT_PIPE_STAGES_G   => 1,
            PIPE_STAGES_G       => 1,
            SLAVE_READY_EN_G    => false,
            VALID_THOLD_G       => 0,
            VALID_BURST_MODE_G  => true,
            FIFO_PAUSE_THRESH_G => 15,
            GEN_SYNC_FIFO_G     => false,
            FIFO_ADDR_WIDTH_G   => 9,
            SYNTH_MODE_G        => MEMORY_SYNTH_MODE_C,
            MEMORY_TYPE_G       => "bram",
            INT_WIDTH_SELECT_G  => "WIDE",
            SLAVE_AXI_CONFIG_G  => AXIS_DEBUG_CFG_C,
            MASTER_AXI_CONFIG_G => DATA_AXIS_CONFIG_C)
         port map (
            sAxisClk    => timingRxClk125,
            sAxisRst    => timingRxRst125,
            sAxisMaster => r.pidDebugMaster,
            sAxisSlave  => open,
            sAxisCtrl   => pidDebugCtrl,
            mAxisClk    => axisClk,
            mAxisRst    => axisRst,
            mAxisMaster => pidDebugMaster,
            mAxisSlave  => pidDebugSlave);
   end generate GEN_PID_DEBUG;

   NO_GEN_PID_DEBUG : if (not GEN_PID_DEBUG_G) generate
      pidDebugMaster <= AXI_STREAM_MASTER_INIT_C;
   end generate NO_GEN_PID_DEBUG;

   U_AxiStreamFifoV2_DATA : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 1,
         SLAVE_READY_EN_G    => false,
         VALID_THOLD_G       => 1,
         VALID_BURST_MODE_G  => true,
         FIFO_PAUSE_THRESH_G => 15,
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => 5,
         SYNTH_MODE_G        => MEMORY_SYNTH_MODE_C,
         MEMORY_TYPE_G       => "distributed",
         INT_WIDTH_SELECT_G  => "WIDE",
         SLAVE_AXI_CONFIG_G  => PID_DATA_FP_AXIS_CFG_C,
         MASTER_AXI_CONFIG_G => PID_DATA_FP_AXIS_CFG_C)
      port map (
         sAxisClk    => timingRxClk125,
         sAxisRst    => timingRxRst125,
         sAxisMaster => r.pidStreamMaster,
         sAxisSlave  => open,
         sAxisCtrl   => open,
         mAxisClk    => timingRxClk125,
         mAxisRst    => timingRxRst125,
         mAxisMaster => pidStreamMaster,
         mAxisSlave  => pidStreamSlave);

   -------------------------------------------------------------------------------------------------
   -- SQ1FB DAC writes via AXIL
   -------------------------------------------------------------------------------------------------
   sq1fbOffsetBin <= convOffsetBin(std_logic_vector(r.sq1FbInt(13 downto 0)));
   logicalRow8      <= resize(r.logicalRow, 8);

   U_Fifo_1 : entity surf.Fifo
      generic map (
         TPD_G           => TPD_G,
         GEN_SYNC_FIFO_G => false,
         FWFT_EN_G       => true,
         SYNTH_MODE_G    => MEMORY_SYNTH_MODE_C,
         MEMORY_TYPE_G   => "distributed",
         PIPE_STAGES_G   => 0,
         DATA_WIDTH_G    => 22,
         ADDR_WIDTH_G    => 4)
      port map (
         rst               => timingRxRst125,
         wr_clk            => timingRxClk125,
         wr_en             => r.sq1FbValid,
         din(13 downto 0)  => sq1fbOffsetBin,
         din(21 downto 14) => logicalRow8,
         overflow          => dacOverflow,
         rd_clk            => timingRxClk125,
         rd_en             => axilR.fifoRd,
         dout              => fifoDout,
         valid             => fifoValid);

   U_AxiLiteMaster_1 : entity surf.AxiLiteMaster
      generic map (
         TPD_G       => TPD_G,
         RST_ASYNC_G => false)
      port map (
         axilClk         => timingRxClk125,
         axilRst         => timingRxRst125,
         req             => axilR.req,
         ack             => ack,
         axilWriteMaster => mAxilWriteMaster,
         axilWriteSlave  => mAxilWriteSlave,
         axilReadMaster  => mAxilReadMaster,
         axilReadSlave   => mAxilReadSlave);

   axilComb : process (ack, axilR, fifoDout, fifoValid, timingRxRst125) is
      variable v : AxilRegType := AXIL_REG_INIT_C;
   begin
      v := axilR;

      v.req.rnw := '0';
      v.fifoRd  := '0';

      if (fifoValid = '1' and axilR.req.request = '0' and ack.done = '0') then
         v.req.request             := '1';
         v.req.address             := SQ1FB_RAM_ADDR_G(31 downto 12) & "00" & fifoDout(21 downto 14) & "00";
         v.req.wrData              := (others => '0');
         v.req.wrData(13 downto 0) := fifoDout(13 downto 0);
         v.fifoRd                  := '1';
      end if;

      if (axilR.req.request = '1' and ack.done = '1') then
         v.req.request := '0';
      end if;

      if (timingRxRst125 = '1') then
         v := AXIL_REG_INIT_C;
      end if;

      axilRin <= v;
   end process axilComb;

   axilSeq : process (timingRxClk125) is
   begin
      if (rising_edge(timingRxClk125)) then
         axilR <= axilRin after TPD_G;
      end if;
   end process axilSeq;

end rtl;
