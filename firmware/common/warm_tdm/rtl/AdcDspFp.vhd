-------------------------------------------------------------------------------
-- Title      : Floating Point PID ADC DSP
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   :
-- Standard   : VHDL'08
-------------------------------------------------------------------------------
-- Description: Floating point PID servo loop for TES SQUID readout.
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

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;
use surf.SsiPkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;
use warm_tdm.WarmTdmPkg.all;

entity AdcDspFp is

   generic (
      TPD_G            : time                 := 1 ns;
      INVERT_SQ1FB_G   : boolean              := true;
      COLUMN_NUM_G     : integer range 0 to 7 := 0;
      ROW_ADDR_BITS_G  : integer range 3 to 8 := 8;
      AXIL_BASE_ADDR_G : slv(31 downto 0)     := (others => '0');
      SQ1FB_RAM_ADDR_G : slv(31 downto 0)     := (others => '0'));

   port (
      timingRxClk125   : in  sl;
      timingRxRst125   : in  sl;
      timingRxData     : in  LocalTimingType;
      adcAxisMaster    : in  AxiStreamMasterType;
      sq1FbDac         : in  slv(13 downto 0);
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

   constant NUM_AXIL_MASTERS_C : integer := 7;
   constant LOCAL_C            : integer := 0;
   constant ADC_BASELINE_C     : integer := 1;
   constant ACCUM_ERROR_C      : integer := 2;
   constant SUM_ACCUM_C        : integer := 3;
   constant SQ1FB_FULL_C       : integer := 4;
   constant FLUX_OFFSET_C      : integer := 5;
   constant FLUX_JUMP_C        : integer := 6;

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
   constant FLUX_JUMP_THRESHOLD_C : integer := 7862;
   constant CLEAR_LAST_ADDR_C : slv(ROW_ADDR_BITS_G-1 downto 0) := toSlv((2**ROW_ADDR_BITS_G)-1, ROW_ADDR_BITS_G);

   constant AXIS_DEBUG_CFG_C : AxiStreamConfigType := ssiAxiStreamConfig(
      dataBytes => 8,
      tKeepMode => TKEEP_COMP_C,
      tDestBits => 4);

   type StateType is (
      WAIT_ROW_STROBE_S,
      WAIT_FIRST_SAMPLE_S,
      ACCUMULATE_S,
      PREP_PID_S,
      WAIT_INT2FP_S,
      PID_P_S,
      PID_I_S,
      PID_D_DIFF_S,
      PID_D_S,
      SQ1FB_ADD_S,
      DERIVE_WRAPPED_S,
      FP2INT_S,
      FLUX_JUMP_CHECK_S,
      ANTI_WINDUP_S,
      SUM_UPDATE_S,
      FLUX_OFFSET_UPDATE_INT2FP_S,
      FLUX_OFFSET_UPDATE_FMA_S,
      RAM_WRITE_S,
      DATA_STREAM_S,
      DEBUG_0_S,
      DEBUG_1_S,
      LOOP_DONE_S,
      CLEAR_STATE_S);

   type RegType is record
      fllEnable          : sl;
      rowEnableMask      : slv(255 downto 0);
      rowEnabled         : sl;
      outputMode         : slv(1 downto 0);
      state              : StateType;
      rowIndex           : slv(ROW_ADDR_BITS_G-1 downto 0);
      -- Integer accumulation
      accumSamples       : unsigned(31 downto 0);
      accumError         : signed(ACCUM_BITS_C-1 downto 0);
      -- FP PID state
      accumErrorFp       : slv(31 downto 0);
      lastAccumErrorFp   : slv(31 downto 0);
      sumAccumFp         : slv(31 downto 0);
      sq1FbFullFp        : slv(31 downto 0);
      fluxOffsetFp       : slv(31 downto 0);
      pidResultFp        : slv(31 downto 0);
      -- FP coefficients (IEEE 754)
      pCoef              : slv(31 downto 0);
      iCoef              : slv(31 downto 0);
      dCoef              : slv(31 downto 0);
      fluxQuantumFp      : slv(31 downto 0);
      invFluxQuantumFp   : slv(31 downto 0);
      -- Integer DAC output
      sq1FbInt           : signed(31 downto 0);
      sq1FbValid         : sl;
      numFluxJumps       : signed(15 downto 0);
      fluxQuantumInt     : slv(13 downto 0);
      -- Control
      clearPidState      : sl;
      clearPidStateBusy  : sl;
      pidStateRamAddr    : slv(ROW_ADDR_BITS_G-1 downto 0);
      fluxJumpOccurred   : sl;
      saturatedHigh      : sl;
      saturatedLow       : sl;
      -- RAM write signals
      accumErrorRamWrEn  : sl;
      accumErrorRamWrData : slv(31 downto 0);
      sumAccumRamWrEn    : sl;
      sumAccumRamWrData  : slv(31 downto 0);
      sq1FbFullRamWrEn   : sl;
      sq1FbFullRamWrData : slv(31 downto 0);
      fluxOffsetRamWrEn  : sl;
      fluxOffsetRamWrData : slv(31 downto 0);
      fluxJumpRamWrEn    : sl;
      fluxJumpRamWrData  : slv(15 downto 0);
      -- FP IP core interfaces
      int2FpInValid      : sl;
      int2FpInData       : slv(31 downto 0);
      fpMacInValid       : sl;
      fpMacA             : slv(31 downto 0);
      fpMacB             : slv(31 downto 0);
      fpMacC             : slv(31 downto 0);
      fp2IntInValid      : sl;
      fp2IntInData       : slv(31 downto 0);
      -- Debug
      dropCount          : unsigned(31 downto 0);
      axilPidDebugEnable : sl;
      pidDebugEnable     : sl;
      pidDebugMaster     : AxiStreamMasterType;
      pidStreamMaster    : AxiStreamMasterType;
      axilWriteSlave     : AxiLiteWriteSlaveType;
      axilReadSlave      : AxiLiteReadSlaveType;
   end record;

   constant REG_INIT_C : RegType := (
      fllEnable          => '0',
      rowEnableMask      => (others => '1'),
      rowEnabled         => '0',
      outputMode         => (others => '0'),
      state              => WAIT_ROW_STROBE_S,
      rowIndex           => (others => '0'),
      accumSamples       => (others => '0'),
      accumError         => (others => '0'),
      accumErrorFp       => (others => '0'),
      lastAccumErrorFp   => (others => '0'),
      sumAccumFp         => (others => '0'),
      sq1FbFullFp        => (others => '0'),
      fluxOffsetFp       => (others => '0'),
      pidResultFp        => (others => '0'),
      pCoef              => (others => '0'),
      iCoef              => (others => '0'),
      dCoef              => (others => '0'),
      fluxQuantumFp      => (others => '0'),
      invFluxQuantumFp   => (others => '0'),
      sq1FbInt           => (others => '0'),
      sq1FbValid         => '0',
      numFluxJumps       => (others => '0'),
      fluxQuantumInt     => (others => '0'),
      clearPidState      => '0',
      clearPidStateBusy  => '0',
      pidStateRamAddr    => (others => '0'),
      fluxJumpOccurred   => '0',
      saturatedHigh      => '0',
      saturatedLow       => '0',
      accumErrorRamWrEn  => '0',
      accumErrorRamWrData => (others => '0'),
      sumAccumRamWrEn    => '0',
      sumAccumRamWrData  => (others => '0'),
      sq1FbFullRamWrEn   => '0',
      sq1FbFullRamWrData => (others => '0'),
      fluxOffsetRamWrEn  => '0',
      fluxOffsetRamWrData => (others => '0'),
      fluxJumpRamWrEn    => '0',
      fluxJumpRamWrData  => (others => '0'),
      int2FpInValid      => '0',
      int2FpInData       => (others => '0'),
      fpMacInValid       => '0',
      fpMacA             => (others => '0'),
      fpMacB             => (others => '0'),
      fpMacC             => (others => '0'),
      fp2IntInValid      => '0',
      fp2IntInData       => (others => '0'),
      dropCount          => (others => '0'),
      axilPidDebugEnable => '0',
      pidDebugEnable     => '0',
      pidDebugMaster     => axiStreamMasterInit(AXIS_DEBUG_CFG_C),
      pidStreamMaster    => axiStreamMasterInit(PID_DATA_FP_AXIS_CFG_C),
      axilWriteSlave     => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave      => AXI_LITE_READ_SLAVE_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal adcBaselineRamOut  : slv(15 downto 0);
   signal accumErrorRamOut   : slv(31 downto 0);
   signal sumAccumRamOut     : slv(31 downto 0);
   signal sq1FbFullRamOut    : slv(31 downto 0);
   signal fluxOffsetRamOut   : slv(31 downto 0);
   signal fluxJumpRamOut     : slv(15 downto 0);

   signal int2FpOutValid : sl;
   signal int2FpOutData  : slv(31 downto 0);
   signal fpMacOutValid  : sl;
   signal fpMacOutData   : slv(31 downto 0);
   signal fp2IntOutValid : sl;
   signal fp2IntOutData  : slv(31 downto 0);

   signal pidDebugCtrl : AxiStreamCtrlType;

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

   signal rowIndex8 : slv(7 downto 0);
   signal fifoDout  : slv(21 downto 0);
   signal fifoValid : sl;
   signal ack       : AxiLiteAckType;

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

   -- ADC Baseline RAM (16-bit integer, unchanged)
   U_AxiDualPortRam_ADC_BASELINE : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 1,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => ROW_ADDR_BITS_G,
         DATA_WIDTH_G     => 16)
      port map (
         axiClk         => timingRxClk125,
         axiRst         => timingRxRst125,
         axiReadMaster  => locAxilReadMasters(ADC_BASELINE_C),
         axiReadSlave   => locAxilReadSlaves(ADC_BASELINE_C),
         axiWriteMaster => locAxilWriteMasters(ADC_BASELINE_C),
         axiWriteSlave  => locAxilWriteSlaves(ADC_BASELINE_C),
         clk            => timingRxClk125,
         rst            => timingRxRst125,
         addr           => r.rowIndex,
         dout           => adcBaselineRamOut);

   -- AccumError RAM (32-bit float)
   U_AxiDualPortRam_ACCUM_ERROR : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
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
         axiReadMaster  => locAxilReadMasters(ACCUM_ERROR_C),
         axiReadSlave   => locAxilReadSlaves(ACCUM_ERROR_C),
         axiWriteMaster => locAxilWriteMasters(ACCUM_ERROR_C),
         axiWriteSlave  => locAxilWriteSlaves(ACCUM_ERROR_C),
         clk            => timingRxClk125,
         rst            => timingRxRst125,
         addr           => r.pidStateRamAddr,
         we             => r.accumErrorRamWrEn,
         din            => r.accumErrorRamWrData,
         dout           => accumErrorRamOut);

   -- SumAccum RAM (32-bit float)
   U_AxiDualPortRam_SUM_ACCUM : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
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
         axiReadMaster  => locAxilReadMasters(SUM_ACCUM_C),
         axiReadSlave   => locAxilReadSlaves(SUM_ACCUM_C),
         axiWriteMaster => locAxilWriteMasters(SUM_ACCUM_C),
         axiWriteSlave  => locAxilWriteSlaves(SUM_ACCUM_C),
         clk            => timingRxClk125,
         rst            => timingRxRst125,
         addr           => r.pidStateRamAddr,
         we             => r.sumAccumRamWrEn,
         din            => r.sumAccumRamWrData,
         dout           => sumAccumRamOut);

   -- SQ1FB Full (unwrapped) RAM (32-bit float)
   U_AxiDualPortRam_SQ1FB_FULL : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
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
         axiReadMaster  => locAxilReadMasters(SQ1FB_FULL_C),
         axiReadSlave   => locAxilReadSlaves(SQ1FB_FULL_C),
         axiWriteMaster => locAxilWriteMasters(SQ1FB_FULL_C),
         axiWriteSlave  => locAxilWriteSlaves(SQ1FB_FULL_C),
         clk            => timingRxClk125,
         rst            => timingRxRst125,
         addr           => r.pidStateRamAddr,
         we             => r.sq1FbFullRamWrEn,
         din            => r.sq1FbFullRamWrData,
         dout           => sq1FbFullRamOut);

   -- Flux Offset RAM (32-bit float: numFluxJumps * fluxQuantum, cached)
   U_AxiDualPortRam_FLUX_OFFSET : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
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
         axiReadMaster  => locAxilReadMasters(FLUX_OFFSET_C),
         axiReadSlave   => locAxilReadSlaves(FLUX_OFFSET_C),
         axiWriteMaster => locAxilWriteMasters(FLUX_OFFSET_C),
         axiWriteSlave  => locAxilWriteSlaves(FLUX_OFFSET_C),
         clk            => timingRxClk125,
         rst            => timingRxRst125,
         addr           => r.pidStateRamAddr,
         we             => r.fluxOffsetRamWrEn,
         din            => r.fluxOffsetRamWrData,
         dout           => fluxOffsetRamOut);

   -- Flux Jump counter RAM (16-bit signed integer)
   U_AxiDualPortRam_FLUX_JUMP : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "block",
         READ_LATENCY_G   => 3,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => true,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => ROW_ADDR_BITS_G,
         DATA_WIDTH_G     => 16)
      port map (
         axiClk         => timingRxClk125,
         axiRst         => timingRxRst125,
         axiReadMaster  => locAxilReadMasters(FLUX_JUMP_C),
         axiReadSlave   => locAxilReadSlaves(FLUX_JUMP_C),
         axiWriteMaster => locAxilWriteMasters(FLUX_JUMP_C),
         axiWriteSlave  => locAxilWriteSlaves(FLUX_JUMP_C),
         clk            => timingRxClk125,
         rst            => timingRxRst125,
         addr           => r.pidStateRamAddr,
         dout           => fluxJumpRamOut,
         we             => r.fluxJumpRamWrEn,
         din            => r.fluxJumpRamWrData);

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

   -------------------------------------------------------------------------------------------------
   -- Main combinatorial process
   -------------------------------------------------------------------------------------------------
   comb : process (accumErrorRamOut, adcAxisMaster, adcBaselineRamOut, fluxJumpRamOut,
                   fluxOffsetRamOut, fp2IntOutData, fp2IntOutValid, fpMacOutData, fpMacOutValid,
                   int2FpOutData, int2FpOutValid, pidDebugCtrl, r, sq1FbFullRamOut,
                   sumAccumRamOut, timingAxilReadMaster, timingAxilWriteMaster, timingRxData,
                   timingRxRst125) is
      variable v              : RegType;
      variable adcValue       : signed(13 downto 0);
      variable adcBaseline    : signed(13 downto 0);
      variable requestClear   : boolean;
      variable iContribSign   : sl;
      variable axilEp         : AxiLiteEndpointType;
   begin
      v := r;

      v.clearPidState := '0';

      ----------------------------------------------------------------------------------------------
      -- AXI Lite Registers
      ----------------------------------------------------------------------------------------------
      axiSlaveWaitTxn(axilEp, timingAxilWriteMaster, timingAxilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.fllEnable);
      axiSlaveRegister(axilEp, X"00", 8, v.outputMode);

      axiSlaveRegister(axilEp, X"04", 0, v.pCoef);
      axiSlaveRegister(axilEp, X"08", 0, v.iCoef);
      axiSlaveRegister(axilEp, X"0C", 0, v.dCoef);

      axiSlaveRegisterR(axilEp, X"10", 0, std_logic_vector(resize(r.accumError, 32)));
      axiSlaveRegisterR(axilEp, X"14", 0, r.lastAccumErrorFp);
      axiSlaveRegisterR(axilEp, X"18", 0, r.sumAccumFp);
      axiSlaveRegisterR(axilEp, X"20", 0, r.pidResultFp);
      axiSlaveRegisterR(axilEp, X"28", 0, r.sq1FbFullFp);
      axiSlaveRegisterR(axilEp, X"2C", 0, std_logic_vector(r.sq1FbInt));

      axiSlaveRegister(axilEp, X"30", 0, v.clearPidState);

      axiSlaveRegister(axilEp, X"40", 0, v.fluxQuantumFp);
      axiSlaveRegister(axilEp, X"44", 0, v.invFluxQuantumFp);
      axiSlaveRegisterR(axilEp, X"48", 0, std_logic_vector(resize(r.numFluxJumps, 32)));
      axiSlaveRegister(axilEp, X"4C", 0, v.fluxQuantumInt);

      axiSlaveRegister(axilEp, X"50", 0, v.axilPidDebugEnable);
      axiSlaveRegister(axilEp, X"60", 0, v.rowEnableMask);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      ----------------------------------------------------------------------------------------------
      -- Default assignments
      ----------------------------------------------------------------------------------------------
      v.sq1FbValid       := '0';
      v.pidStateRamAddr  := r.rowIndex;
      v.accumErrorRamWrEn  := '0';
      v.sumAccumRamWrEn    := '0';
      v.sq1FbFullRamWrEn   := '0';
      v.fluxOffsetRamWrEn  := '0';
      v.fluxJumpRamWrEn    := '0';
      v.int2FpInValid      := '0';
      v.fpMacInValid       := '0';
      v.fp2IntInValid      := '0';

      v.pidStreamMaster  := axiStreamMasterInit(PID_DATA_FP_AXIS_CFG_C);
      v.pidDebugMaster   := axiStreamMasterInit(AXIS_DEBUG_CFG_C);
      v.pidDebugMaster.tDest := toSlv(8, 8);

      adcValue    := signed(adcAxisMaster.tData(15 downto 2));
      adcBaseline := signed(adcBaselineRamOut(15 downto 2));

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

      if (requestClear) then
         v.clearPidStateBusy := '1';
         v.state             := WAIT_ROW_STROBE_S;
         v.rowEnabled        := '0';
         v.accumSamples      := (others => '0');
         v.accumError        := (others => '0');
         v.accumErrorFp      := (others => '0');
         v.lastAccumErrorFp  := (others => '0');
         v.sumAccumFp        := (others => '0');
         v.sq1FbFullFp       := (others => '0');
         v.fluxOffsetFp      := (others => '0');
         v.pidResultFp       := (others => '0');
         v.sq1FbInt          := (others => '0');
         v.numFluxJumps      := (others => '0');
         v.sq1FbValid        := '0';
         v.pidDebugEnable    := '0';
         v.pidStateRamAddr   := (others => '0');
         v.accumErrorRamWrEn   := '1';
         v.accumErrorRamWrData := (others => '0');
         v.sumAccumRamWrEn     := '1';
         v.sumAccumRamWrData   := (others => '0');
         v.sq1FbFullRamWrEn    := '1';
         v.sq1FbFullRamWrData  := (others => '0');
         v.fluxOffsetRamWrEn   := '1';
         v.fluxOffsetRamWrData := (others => '0');
         v.fluxJumpRamWrEn     := '1';
         v.fluxJumpRamWrData   := (others => '0');
      elsif (r.clearPidStateBusy = '1') then
         v.state := WAIT_ROW_STROBE_S;
         v.accumErrorRamWrEn   := '1';
         v.accumErrorRamWrData := (others => '0');
         v.sumAccumRamWrEn     := '1';
         v.sumAccumRamWrData   := (others => '0');
         v.sq1FbFullRamWrEn    := '1';
         v.sq1FbFullRamWrData  := (others => '0');
         v.fluxOffsetRamWrEn   := '1';
         v.fluxOffsetRamWrData := (others => '0');
         v.fluxJumpRamWrEn     := '1';
         v.fluxJumpRamWrData   := (others => '0');

         if (r.pidStateRamAddr = CLEAR_LAST_ADDR_C) then
            v.clearPidStateBusy := '0';
         else
            v.pidStateRamAddr := slv(unsigned(r.pidStateRamAddr) + 1);
         end if;

      elsif (r.fllEnable = '0' and timingRxData.rowSeqStart = '1') then
         v.pidStreamMaster.tValid := '1';
         v.pidStreamMaster.tKeep  := (others => '0');
         v.pidStreamMaster.tLast  := '1';

      elsif (r.fllEnable = '1') then
         case r.state is
            when WAIT_ROW_STROBE_S =>
               v.pidDebugEnable := not pidDebugCtrl.pause and r.axilPidDebugEnable;
               if (r.axilPidDebugEnable = '1' and pidDebugCtrl.pause = '1') then
                  v.dropCount := r.dropCount + 1;
               end if;

               if (timingRxData.rowStrobe = '1') then
                  v.rowIndex   := timingRxData.rowIndex(ROW_ADDR_BITS_G-1 downto 0);
                  v.accumError := (others => '0');
                  v.rowEnabled := r.rowEnableMask(to_integer(unsigned(v.rowIndex)));

                  ssiSetUserSof(AXIS_DEBUG_CFG_C, v.pidDebugMaster, '1');
                  v.pidDebugMaster.tValid              := v.pidDebugEnable;
                  v.pidDebugMaster.tData(3 downto 0)   := toSlv(COLUMN_NUM_G, 4);
                  v.pidDebugMaster.tData(15 downto 8)  := resize(v.rowIndex, 8);
                  v.pidDebugMaster.tData(63 downto 16) := timingRxData.runTime(47 downto 0);

                  if (timingRxData.rowSeqStart = '1') then
                     v.pidStreamMaster.tValid := '1';
                     v.pidStreamMaster.tKeep  := (others => '0');
                     v.pidStreamMaster.tLast  := '1';
                  end if;

                  v.state := WAIT_FIRST_SAMPLE_S;
               end if;

            when WAIT_FIRST_SAMPLE_S =>
               if (timingRxData.firstSample = '1') then
                  v.pidDebugMaster.tValid             := r.pidDebugEnable;
                  v.pidDebugMaster.tData(31 downto 0) := resize(adcBaselineRamOut, 32);
                  v.accumSamples := (others => '0');
                  v.state        := ACCUMULATE_S;
               end if;

            when ACCUMULATE_S =>
               v.accumError   := resize(r.accumError + (adcValue - adcBaseline), ACCUM_BITS_C);
               v.accumSamples := r.accumSamples + 1;
               if (timingRxData.lastSample = '1') then
                  v.state := PREP_PID_S;
               end if;

            when PREP_PID_S =>
               -- RAM values are available (3+ cycles since rowIndex was set)
               v.lastAccumErrorFp := accumErrorRamOut;
               v.sumAccumFp       := sumAccumRamOut;
               v.sq1FbFullFp      := sq1FbFullRamOut;
               v.fluxOffsetFp     := fluxOffsetRamOut;
               v.numFluxJumps     := signed(fluxJumpRamOut);
               -- Convert integer accumError to float
               v.int2FpInValid    := '1';
               v.int2FpInData     := std_logic_vector(resize(r.accumError, 32));
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0) := std_logic_vector(resize(r.accumError, 32));
               v.state := WAIT_INT2FP_S;

            when WAIT_INT2FP_S =>
               if (int2FpOutValid = '1') then
                  v.accumErrorFp := int2FpOutData;
                  -- Write accumError float to RAM for next cycle's D-term
                  v.accumErrorRamWrEn   := '1';
                  v.accumErrorRamWrData := int2FpOutData;
                  -- Start P term: result = P * accumError + 0.0
                  v.fpMacInValid := '1';
                  v.fpMacA       := int2FpOutData;
                  v.fpMacB       := r.pCoef;
                  v.fpMacC       := X"00000000";
                  v.state        := PID_P_S;
               end if;

            when PID_P_S =>
               if (fpMacOutValid = '1') then
                  v.pidResultFp := fpMacOutData;
                  -- I term: result += I * sumAccum
                  v.fpMacInValid := '1';
                  v.fpMacA       := r.sumAccumFp;
                  v.fpMacB       := r.iCoef;
                  v.fpMacC       := fpMacOutData;
                  v.state        := PID_I_S;
               end if;

            when PID_I_S =>
               if (fpMacOutValid = '1') then
                  v.pidResultFp := fpMacOutData;
                  -- Compute dError = lastAccumError - accumError
                  -- FMA: (-1.0) * accumError + lastAccumError
                  v.fpMacInValid := '1';
                  v.fpMacA       := r.accumErrorFp;
                  v.fpMacB       := X"BF800000";
                  v.fpMacC       := r.lastAccumErrorFp;
                  v.pidDebugMaster.tValid             := r.pidDebugEnable;
                  v.pidDebugMaster.tData(31 downto 0) := r.sumAccumFp;
                  v.state        := PID_D_DIFF_S;
               end if;

            when PID_D_DIFF_S =>
               if (fpMacOutValid = '1') then
                  -- fpMacOutData = dError (lastAccumError - accumError)
                  -- D term: result += D * dError
                  v.fpMacInValid := '1';
                  v.fpMacA       := fpMacOutData;
                  v.fpMacB       := r.dCoef;
                  v.fpMacC       := r.pidResultFp;
                  v.state        := PID_D_S;
               end if;

            when PID_D_S =>
               if (fpMacOutValid = '1') then
                  v.pidResultFp := fpMacOutData;
                  -- Add pidResult to sq1FbFull: sq1FbFull += pidResult
                  -- FMA: pidResult * 1.0 + sq1FbFull
                  v.fpMacInValid := '1';
                  v.fpMacA       := fpMacOutData;
                  v.fpMacB       := X"3F800000";
                  v.fpMacC       := r.sq1FbFullFp;
                  v.pidDebugMaster.tValid             := r.pidDebugEnable;
                  v.pidDebugMaster.tData(31 downto 0) := fpMacOutData;
                  v.state        := SQ1FB_ADD_S;
               end if;

            when SQ1FB_ADD_S =>
               if (fpMacOutValid = '1') then
                  v.sq1FbFullFp := fpMacOutData;
                  -- Derive wrapped value: wrapped = sq1FbFull - fluxOffset
                  -- FMA: fluxOffset * (-1.0) + sq1FbFull
                  v.fpMacInValid := '1';
                  v.fpMacA       := r.fluxOffsetFp;
                  v.fpMacB       := X"BF800000";
                  v.fpMacC       := fpMacOutData;
                  v.state        := DERIVE_WRAPPED_S;
               end if;

            when DERIVE_WRAPPED_S =>
               if (fpMacOutValid = '1') then
                  -- Convert wrapped float to integer for threshold check
                  v.fp2IntInValid := '1';
                  v.fp2IntInData  := fpMacOutData;
                  v.state         := FP2INT_S;
               end if;

            when FP2INT_S =>
               if (fp2IntOutValid = '1') then
                  v.sq1FbInt         := signed(fp2IntOutData);
                  v.fluxJumpOccurred := '0';
                  v.saturatedHigh    := '0';
                  v.saturatedLow     := '0';
                  v.state            := FLUX_JUMP_CHECK_S;
               end if;

            when FLUX_JUMP_CHECK_S =>
               -- Iterative flux jump check (supports multi-quantum jumps)
               if (r.sq1FbInt > FLUX_JUMP_THRESHOLD_C) then
                  v.sq1FbInt         := r.sq1FbInt - signed(resize(unsigned(r.fluxQuantumInt), 32));
                  v.numFluxJumps     := r.numFluxJumps + 1;
                  v.fluxJumpOccurred := '1';
                  -- Stay in this state for another iteration
               elsif (r.sq1FbInt < -FLUX_JUMP_THRESHOLD_C) then
                  v.sq1FbInt         := r.sq1FbInt + signed(resize(unsigned(r.fluxQuantumInt), 32));
                  v.numFluxJumps     := r.numFluxJumps - 1;
                  v.fluxJumpOccurred := '1';
                  -- Stay in this state for another iteration
               else
                  -- Check DAC saturation for anti-windup
                  if (r.sq1FbInt > SQ1FB_MAX_C) then
                     v.sq1FbInt      := to_signed(SQ1FB_MAX_C, 32);
                     v.saturatedHigh := '1';
                  elsif (r.sq1FbInt < SQ1FB_MIN_C) then
                     v.sq1FbInt     := to_signed(SQ1FB_MIN_C, 32);
                     v.saturatedLow := '1';
                  end if;
                  v.sq1FbValid := r.rowEnabled;
                  v.state      := ANTI_WINDUP_S;
               end if;

            when ANTI_WINDUP_S =>
               -- Determine sign of I-contribution: sign(I * accumError)
               -- Positive if signs of iCoef and accumError match
               iContribSign := r.iCoef(31) xor r.accumErrorFp(31);

               if (r.iCoef = x"00000000") then
                  -- I coef is zero: clear integrator
                  v.sumAccumFp := X"00000000";
                  v.state      := RAM_WRITE_S;
               elsif (r.saturatedHigh = '1' and iContribSign = '0') then
                  -- Saturated high and I would push higher: don't integrate
                  v.state := RAM_WRITE_S;
               elsif (r.saturatedLow = '1' and iContribSign = '1') then
                  -- Saturated low and I would push lower: don't integrate
                  v.state := RAM_WRITE_S;
               else
                  -- Allow integration: sumAccum += accumError
                  -- FMA: accumError * 1.0 + sumAccum
                  v.fpMacInValid := '1';
                  v.fpMacA       := r.accumErrorFp;
                  v.fpMacB       := X"3F800000";
                  v.fpMacC       := r.sumAccumFp;
                  v.state        := SUM_UPDATE_S;
               end if;

            when SUM_UPDATE_S =>
               if (fpMacOutValid = '1') then
                  v.sumAccumFp := fpMacOutData;
                  v.state      := RAM_WRITE_S;
               end if;

            when RAM_WRITE_S =>
               -- Write updated state to RAMs
               v.sumAccumRamWrEn    := '1';
               v.sumAccumRamWrData  := r.sumAccumFp;
               v.sq1FbFullRamWrEn   := '1';
               v.sq1FbFullRamWrData := r.sq1FbFullFp;
               v.fluxJumpRamWrEn    := '1';
               v.fluxJumpRamWrData  := std_logic_vector(r.numFluxJumps);

               if (r.fluxJumpOccurred = '1') then
                  -- Need to recompute fluxOffset = numFluxJumps * fluxQuantum
                  -- First convert numFluxJumps to float
                  v.int2FpInValid := '1';
                  v.int2FpInData  := std_logic_vector(resize(r.numFluxJumps, 32));
                  v.state         := FLUX_OFFSET_UPDATE_INT2FP_S;
               else
                  v.fluxOffsetRamWrEn   := '1';
                  v.fluxOffsetRamWrData := r.fluxOffsetFp;
                  v.state               := DATA_STREAM_S;
               end if;

            when FLUX_OFFSET_UPDATE_INT2FP_S =>
               if (int2FpOutValid = '1') then
                  -- Compute fluxOffset = numFluxJumpsFp * fluxQuantumFp
                  v.fpMacInValid := '1';
                  v.fpMacA       := int2FpOutData;
                  v.fpMacB       := r.fluxQuantumFp;
                  v.fpMacC       := X"00000000";
                  v.state        := FLUX_OFFSET_UPDATE_FMA_S;
               end if;

            when FLUX_OFFSET_UPDATE_FMA_S =>
               if (fpMacOutValid = '1') then
                  v.fluxOffsetFp        := fpMacOutData;
                  v.fluxOffsetRamWrEn   := '1';
                  v.fluxOffsetRamWrData := fpMacOutData;
                  v.state               := DATA_STREAM_S;
               end if;

            when DATA_STREAM_S =>
               v.pidStreamMaster.tValid := r.rowEnabled;
               if (r.outputMode = "00") then
                  -- Output unwrapped sq1FbFull as float (primary mode)
                  v.pidStreamMaster.tData(31 downto 0) := r.sq1FbFullFp;
               elsif (r.outputMode = "01") then
                  -- Output accumError as float
                  v.pidStreamMaster.tData(31 downto 0) := r.accumErrorFp;
               elsif (r.outputMode = "10") then
                  -- Output row sequence count (for diagnostics)
                  v.pidStreamMaster.tData(31 downto 0) := timingRxData.rowSeqCount(31 downto 0);
               elsif (r.outputMode = "11") then
                  -- Output pidResult as float
                  v.pidStreamMaster.tData(31 downto 0) := r.pidResultFp;
               end if;

               v.pidStreamMaster.tId(ROW_ADDR_BITS_G-1 downto 0) := r.rowIndex;
               v.state := DEBUG_0_S;

            when DEBUG_0_S =>
               v.pidDebugMaster.tValid              := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0)  := r.sq1FbFullFp;
               v.pidDebugMaster.tData(63 downto 32) := std_logic_vector(r.sq1FbInt);
               v.state := DEBUG_1_S;

            when DEBUG_1_S =>
               v.pidDebugMaster.tValid              := r.pidDebugEnable;
               v.pidDebugMaster.tData(15 downto 0)  := std_logic_vector(r.numFluxJumps);
               v.pidDebugMaster.tData(31 downto 16) := (others => '0');
               v.pidDebugMaster.tData(63 downto 32) := slv(r.accumSamples);
               v.state := LOOP_DONE_S;

            when LOOP_DONE_S =>
               v.pidDebugMaster.tValid              := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0)  := slv(r.dropCount);
               v.pidDebugMaster.tData(63 downto 32) := timingRxData.rowSeqCount(31 downto 0);
               v.pidDebugMaster.tLast               := '1';
               v.state := WAIT_ROW_STROBE_S;

            when CLEAR_STATE_S =>
               null;

         end case;
      end if;

      if (v.clearPidStateBusy = '0') then
         v.pidStateRamAddr := v.rowIndex;
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
         SYNTH_MODE_G        => "xpm",
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
         SYNTH_MODE_G        => "xpm",
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
   rowIndex8      <= resize(r.rowIndex, 8);

   U_Fifo_1 : entity surf.Fifo
      generic map (
         TPD_G           => TPD_G,
         GEN_SYNC_FIFO_G => false,
         FWFT_EN_G       => true,
         SYNTH_MODE_G    => "xpm",
         MEMORY_TYPE_G   => "distributed",
         PIPE_STAGES_G   => 0,
         DATA_WIDTH_G    => 22,
         ADDR_WIDTH_G    => 4)
      port map (
         rst               => timingRxRst125,
         wr_clk            => timingRxClk125,
         wr_en             => r.sq1FbValid,
         din(13 downto 0)  => sq1fbOffsetBin,
         din(21 downto 14) => rowIndex8,
         overflow          => open,
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

      if (fifoValid = '1') then
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
