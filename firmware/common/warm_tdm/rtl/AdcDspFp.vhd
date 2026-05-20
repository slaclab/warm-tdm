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

   constant NUM_AXIL_MASTERS_C : integer := 6;
   constant LOCAL_C            : integer := 0;
   constant ACCUM_ERROR_C      : integer := 1;
   constant SUM_ACCUM_C        : integer := 2;
   constant SQ1FB_FULL_C       : integer := 3;
   constant FLUX_OFFSET_C      : integer := 4;
   constant FLUX_JUMP_C        : integer := 5;

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
      IDLE_S,
      WAIT_INT2FP_S,
      PID_COMPUTE_S,
      PID_I_S,
      PID_D_S,
      SQ1FB_ADD_S,
      WRAP_S,
      FLUX_RECIPROCAL_S,
      FLUX_TRUNCATE_S,
      OFFSET_UPDATE_S,
      DAC_WRAP_S,
      DAC_CONVERT_S,
      RAM_WRITE_S,
      DATA_STREAM_S,
      CLEAR_STATE_S);

   type RegType is record
      fllEnable          : sl;
      rowEnableMask      : slv(255 downto 0);
      rowEnabled         : sl;
      outputMode         : slv(1 downto 0);
      state              : StateType;
      rowIndex           : slv(ROW_ADDR_BITS_G-1 downto 0);
      -- Integer accumulation
      accumSamples       : unsigned(7 downto 0);
      accumError         : signed(ACCUM_BITS_C-1 downto 0);
      -- FP PID state
      accumErrorFp       : slv(31 downto 0);
      lastAccumErrorFp   : slv(31 downto 0);
      sumAccumFp         : slv(31 downto 0);
      sq1FbFullFp        : slv(31 downto 0);
      fluxOffsetFp       : slv(31 downto 0);
      pidResultFp        : slv(31 downto 0);
      dErr               : slv(31 downto 0);
      newSumAccum        : slv(31 downto 0);
      wrappedFp          : slv(31 downto 0);
      dacValueFp         : slv(31 downto 0);
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
      additionalJumps    : signed(31 downto 0);
      fluxQuantumInt     : slv(13 downto 0);
      -- Control
      clearPidState      : sl;
      clearPidStateBusy  : sl;
      pidStateRamAddr    : slv(ROW_ADDR_BITS_G-1 downto 0);
      waitCount          : unsigned(2 downto 0);
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
      fpAddInValid       : sl;
      fpAddA             : slv(31 downto 0);
      fpAddB             : slv(31 downto 0);
      fpAddSub           : sl;
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
      state              => IDLE_S,
      rowIndex           => (others => '0'),
      accumSamples       => (others => '0'),
      accumError         => (others => '0'),
      accumErrorFp       => (others => '0'),
      lastAccumErrorFp   => (others => '0'),
      sumAccumFp         => (others => '0'),
      sq1FbFullFp        => (others => '0'),
      fluxOffsetFp       => (others => '0'),
      pidResultFp        => (others => '0'),
      dErr               => (others => '0'),
      newSumAccum        => (others => '0'),
      wrappedFp          => (others => '0'),
      dacValueFp         => (others => '0'),
      pCoef              => (others => '0'),
      iCoef              => (others => '0'),
      dCoef              => (others => '0'),
      fluxQuantumFp      => (others => '0'),
      invFluxQuantumFp   => (others => '0'),
      sq1FbInt           => (others => '0'),
      sq1FbValid         => '0',
      numFluxJumps       => (others => '0'),
      additionalJumps    => (others => '0'),
      fluxQuantumInt     => (others => '0'),
      clearPidState      => '0',
      clearPidStateBusy  => '0',
      pidStateRamAddr    => (others => '0'),
      waitCount          => (others => '0'),
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
      fpAddInValid       => '0',
      fpAddA             => (others => '0'),
      fpAddB             => (others => '0'),
      fpAddSub           => '0',
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

   signal accumErrorRamOut   : slv(31 downto 0);
   signal sumAccumRamOut     : slv(31 downto 0);
   signal sq1FbFullRamOut    : slv(31 downto 0);
   signal fluxOffsetRamOut   : slv(31 downto 0);
   signal fluxJumpRamOut     : slv(15 downto 0);

   signal int2FpOutValid : sl;
   signal int2FpOutData  : slv(31 downto 0);
   signal fpMacOutValid  : sl;
   signal fpMacOutData   : slv(31 downto 0);
   signal fpAddOutValid  : sl;
   signal fpAddOutData   : slv(31 downto 0);
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
   -- LUT: Convert small integer jump count to IEEE 754 single-precision float
   -- Saturates at +/- 4.0 for values outside [-4, +4]
   -------------------------------------------------------------------------------------------------
   function jumpCountToFloat (jumps : signed(31 downto 0)) return slv is
      variable ret : slv(31 downto 0);
   begin
      case to_integer(jumps) is
         when -4     => ret := X"C0800000";  -- -4.0
         when -3     => ret := X"C0400000";  -- -3.0
         when -2     => ret := X"C0000000";  -- -2.0
         when -1     => ret := X"BF800000";  -- -1.0
         when  0     => ret := X"00000000";  --  0.0
         when  1     => ret := X"3F800000";  --  1.0
         when  2     => ret := X"40000000";  --  2.0
         when  3     => ret := X"40400000";  --  3.0
         when  4     => ret := X"40800000";  --  4.0
         when others =>
            if (jumps > 0) then
               ret := X"40800000";  -- saturate at +4.0
            else
               ret := X"C0800000";  -- saturate at -4.0
            end if;
      end case;
      return ret;
   end function jumpCountToFloat;

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

   component FpAdd
      port (
         aclk                    : in  std_logic;
         s_axis_a_tvalid         : in  std_logic;
         s_axis_a_tdata          : in  std_logic_vector(31 downto 0);
         s_axis_b_tvalid         : in  std_logic;
         s_axis_b_tdata          : in  std_logic_vector(31 downto 0);
         s_axis_operation_tvalid : in  std_logic;
         s_axis_operation_tdata  : in  std_logic_vector(7 downto 0);
         m_axis_result_tvalid    : out std_logic;
         m_axis_result_tdata     : out std_logic_vector(31 downto 0));
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

   U_FpAdd_1 : FpAdd
      port map (
         aclk                    => timingRxClk125,
         s_axis_a_tvalid         => r.fpAddInValid,
         s_axis_a_tdata          => r.fpAddA,
         s_axis_b_tvalid         => r.fpAddInValid,
         s_axis_b_tdata          => r.fpAddB,
         s_axis_operation_tvalid => r.fpAddInValid,
         s_axis_operation_tdata  => "0000000" & r.fpAddSub,
         m_axis_result_tvalid    => fpAddOutValid,
         m_axis_result_tdata     => fpAddOutData);

   -------------------------------------------------------------------------------------------------
   -- Main combinatorial process
   -------------------------------------------------------------------------------------------------
   comb : process (accumErrorRamOut, accumIn, accumValid, fluxJumpRamOut,
                   fluxOffsetRamOut, fp2IntOutData, fp2IntOutValid, fpAddOutData, fpAddOutValid,
                   fpMacOutData, fpMacOutValid, int2FpOutData, int2FpOutValid, pidDebugCtrl, r,
                   sq1FbFullRamOut, sumAccumRamOut, timingAxilReadMaster, timingAxilWriteMaster,
                   timingRxData, timingRxRst125) is
      variable v              : RegType;
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
      v.fpAddInValid       := '0';
      v.fp2IntInValid      := '0';

      v.pidStreamMaster  := axiStreamMasterInit(PID_DATA_FP_AXIS_CFG_C);
      v.pidDebugMaster   := axiStreamMasterInit(AXIS_DEBUG_CFG_C);
      v.pidDebugMaster.tDest := toSlv(8, 8);


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
         v.state             := IDLE_S;
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
         v.state := IDLE_S;
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

      elsif (r.fllEnable = '0' and accumValid = '1' and accumIn.seqStart = '1') then
         v.pidStreamMaster.tValid := '1';
         v.pidStreamMaster.tKeep  := (others => '0');
         v.pidStreamMaster.tLast  := '1';

      elsif (r.fllEnable = '1') then
         case r.state is
            -------------------------------------------------------------------
            -- IDLE_S (Cycle 0)
            -- Wait for new accumulation result. Capture inputs, launch Int2Fp,
            -- emit debug SOF header, handle seqStart frame marker.
            -------------------------------------------------------------------
            when IDLE_S =>
               v.pidDebugEnable := not pidDebugCtrl.pause and r.axilPidDebugEnable;
               if (r.axilPidDebugEnable = '1' and pidDebugCtrl.pause = '1') then
                  v.dropCount := r.dropCount + 1;
               end if;

               if (accumValid = '1') then
                  -- Capture accumulation inputs
                  v.rowIndex     := accumIn.rowIndex(ROW_ADDR_BITS_G-1 downto 0);
                  v.accumError   := resize(accumIn.accumError, ACCUM_BITS_C);
                  v.accumSamples := accumIn.numSamples;
                  v.rowEnabled   := r.rowEnableMask(to_integer(unsigned(accumIn.rowIndex)));

                  -- pidStateRamAddr tracks rowIndex via assignment after case
                  -- RAM outputs will be valid next cycle (1-cycle BRAM latency)

                  -- Launch Int2Fp(accumError) -- result ready in 2 cycles
                  v.int2FpInValid := '1';
                  v.int2FpInData  := std_logic_vector(resize(accumIn.accumError, 32));

                  -- Handle sequence start frame marker
                  if (accumIn.seqStart = '1') then
                     v.pidStreamMaster.tValid := '1';
                     v.pidStreamMaster.tKeep  := (others => '0');
                     v.pidStreamMaster.tLast  := '1';
                  end if;

                  -- Debug SOF header packet
                  ssiSetUserSof(AXIS_DEBUG_CFG_C, v.pidDebugMaster, '1');
                  v.pidDebugMaster.tValid              := v.pidDebugEnable;
                  v.pidDebugMaster.tData(3 downto 0)   := toSlv(COLUMN_NUM_G, 4);
                  v.pidDebugMaster.tData(15 downto 8)  := resize(v.rowIndex, 8);
                  v.pidDebugMaster.tData(63 downto 16) := timingRxData.runTime(47 downto 0);

                  v.waitCount := (others => '0');
                  v.state     := WAIT_INT2FP_S;
               end if;

            -------------------------------------------------------------------
            -- WAIT_INT2FP_S (Cycles 1-4)
            -- Wait for RAM read latency (READ_LATENCY_G=3) and Int2Fp
            -- (C_Latency=2). Poll int2FpOutValid each cycle to capture the
            -- one-cycle result pulse. At wc=3 RAM outputs are valid; launch
            -- D-diff (FpAdd) and P-term (FpMac) in parallel.
            -------------------------------------------------------------------
            when WAIT_INT2FP_S =>
               if (int2FpOutValid = '1') then
                  v.accumErrorFp := int2FpOutData;
               end if;

               if (r.waitCount = 3) then
                  v.lastAccumErrorFp := accumErrorRamOut;
                  v.sumAccumFp       := sumAccumRamOut;
                  v.sq1FbFullFp      := sq1FbFullRamOut;
                  v.fluxOffsetFp     := fluxOffsetRamOut;
                  v.numFluxJumps     := signed(fluxJumpRamOut);

                  -- Write accumErrorFp to RAM for next iteration's D-term
                  v.accumErrorRamWrEn   := '1';
                  v.accumErrorRamWrData := r.accumErrorFp;

                  -- Launch FpAdd: lastAccumErrorFp - accumErrorFp (D-diff)
                  v.fpAddInValid := '1';
                  v.fpAddA       := accumErrorRamOut;
                  v.fpAddB       := r.accumErrorFp;
                  v.fpAddSub     := '1';  -- subtract

                  -- Launch FpMac: P * accumErrorFp + 0.0 (P-term)
                  v.fpMacInValid := '1';
                  v.fpMacA       := r.accumErrorFp;
                  v.fpMacB       := r.pCoef;
                  v.fpMacC       := X"00000000";

                  v.waitCount := (others => '0');
                  v.state     := PID_COMPUTE_S;
               else
                  v.waitCount := r.waitCount + 1;
               end if;

            -------------------------------------------------------------------
            -- PID_COMPUTE_S (Cycles 3-6)
            -- Parallel FpAdd (D-diff, 2-cycle) and FpMac (P-term, 4-cycle).
            -- After D-diff arrives, launch speculative integrator on FpAdd.
            -- Both FpAdd (integrator) and FpMac (P-term) complete at wc=3.
            -------------------------------------------------------------------
            when PID_COMPUTE_S =>
               case to_integer(r.waitCount) is
                  when 0 =>
                     -- Cycle 3: FpAdd computing D-diff, FpMac computing P
                     v.waitCount := r.waitCount + 1;

                  when 1 =>
                     -- Cycle 4: FpAdd result ready (D-diff = last - current)
                     if (fpAddOutValid = '1') then
                        v.dErr := fpAddOutData;

                        -- Launch FpAdd: accumErrorFp + sumAccumFp (speculative integrator)
                        v.fpAddInValid := '1';
                        v.fpAddA       := r.accumErrorFp;
                        v.fpAddB       := r.sumAccumFp;
                        v.fpAddSub     := '0';  -- add

                        v.waitCount := r.waitCount + 1;
                     end if;

                  when 2 =>
                     -- Cycle 5: FpAdd computing integrator, FpMac computing P
                     v.waitCount := r.waitCount + 1;

                  when 3 =>
                     -- Cycle 6: FpAdd integrator result + FpMac P-term result
                     if (fpAddOutValid = '1' and fpMacOutValid = '1') then
                        v.newSumAccum := fpAddOutData;
                        v.pidResultFp := fpMacOutData;

                        -- Launch FpMac: I * sumAccumFp + pidResultFp (I-term)
                        v.fpMacInValid := '1';
                        v.fpMacA       := r.sumAccumFp;
                        v.fpMacB       := r.iCoef;
                        v.fpMacC       := fpMacOutData;

                        v.waitCount := (others => '0');
                        v.state     := PID_I_S;
                     end if;

                  when others =>
                     null;
               end case;

            -------------------------------------------------------------------
            -- PID_I_S (Cycles 7-10)
            -- Wait for I-term FpMac result (4-cycle latency), then launch
            -- D-term computation.
            -------------------------------------------------------------------
            when PID_I_S =>
               if (fpMacOutValid = '1') then
                  v.pidResultFp := fpMacOutData;

                  -- Launch FpMac: D * dErr + pidResultFp (D-term)
                  v.fpMacInValid := '1';
                  v.fpMacA       := r.dErr;
                  v.fpMacB       := r.dCoef;
                  v.fpMacC       := fpMacOutData;

                  v.state := PID_D_S;
               end if;

            -------------------------------------------------------------------
            -- PID_D_S (Cycles 11-14)
            -- Wait for D-term FpMac result (full PID output), then launch
            -- SQ1FB update addition.
            -------------------------------------------------------------------
            when PID_D_S =>
               if (fpMacOutValid = '1') then
                  v.pidResultFp := fpMacOutData;

                  -- Launch FpAdd: pidResultFp + sq1FbFullFp (SQ1FB update)
                  v.fpAddInValid := '1';
                  v.fpAddA       := fpMacOutData;
                  v.fpAddB       := r.sq1FbFullFp;
                  v.fpAddSub     := '0';  -- add

                  v.state := SQ1FB_ADD_S;
               end if;

            -------------------------------------------------------------------
            -- SQ1FB_ADD_S (Cycles 15-16)
            -- Wait for FpAdd result (new unwrapped SQ1FB value), then launch
            -- wrapping subtraction.
            -------------------------------------------------------------------
            when SQ1FB_ADD_S =>
               if (fpAddOutValid = '1') then
                  v.sq1FbFullFp := fpAddOutData;

                  -- Launch FpAdd: sq1FbFullFp - fluxOffsetFp (wrapping)
                  v.fpAddInValid := '1';
                  v.fpAddA       := fpAddOutData;
                  v.fpAddB       := r.fluxOffsetFp;
                  v.fpAddSub     := '1';  -- subtract

                  v.state := WRAP_S;
               end if;

            -------------------------------------------------------------------
            -- WRAP_S (Cycles 17-18)
            -- Wait for wrapped value, launch reciprocal multiply to determine
            -- number of flux jumps.
            -------------------------------------------------------------------
            when WRAP_S =>
               if (fpAddOutValid = '1') then
                  v.wrappedFp := fpAddOutData;

                  -- Launch FpMac: wrappedFp * invFluxQuantumFp + 0.0
                  v.fpMacInValid := '1';
                  v.fpMacA       := fpAddOutData;
                  v.fpMacB       := r.invFluxQuantumFp;
                  v.fpMacC       := X"00000000";

                  v.state := FLUX_RECIPROCAL_S;
               end if;

            -------------------------------------------------------------------
            -- FLUX_RECIPROCAL_S (Cycles 19-22)
            -- Wait for FpMac result (jumps as float), launch Fp2Int truncation
            -- to get integer jump count.
            -------------------------------------------------------------------
            when FLUX_RECIPROCAL_S =>
               if (fpMacOutValid = '1') then
                  -- Convert jumpsFp to integer (truncate toward zero)
                  v.fp2IntInValid := '1';
                  v.fp2IntInData  := fpMacOutData;

                  v.state := FLUX_TRUNCATE_S;
               end if;

            -------------------------------------------------------------------
            -- FLUX_TRUNCATE_S (Cycles 23-24)
            -- Wait for Fp2Int result. Update numFluxJumps, look up float via
            -- LUT, launch FpMac for flux offset update. Emit debug pkt 0.
            -------------------------------------------------------------------
            when FLUX_TRUNCATE_S =>
               if (fp2IntOutValid = '1') then
                  v.additionalJumps := signed(fp2IntOutData);
                  v.numFluxJumps    := r.numFluxJumps + resize(signed(fp2IntOutData), 16);

                  -- Launch FpMac: additionalJumpsFp * fluxQuantumFp + fluxOffsetFp
                  -- (incremental offset update)
                  v.fpMacInValid := '1';
                  v.fpMacA       := jumpCountToFloat(signed(fp2IntOutData));
                  v.fpMacB       := r.fluxQuantumFp;
                  v.fpMacC       := r.fluxOffsetFp;

                  -- Emit debug packet 0: sq1FbFullFp & pidResultFp
                  v.pidDebugMaster.tValid              := r.pidDebugEnable;
                  v.pidDebugMaster.tData(31 downto 0)  := r.pidResultFp;
                  v.pidDebugMaster.tData(63 downto 32) := r.sq1FbFullFp;

                  v.waitCount := (others => '0');
                  v.state     := OFFSET_UPDATE_S;
               end if;

            -------------------------------------------------------------------
            -- OFFSET_UPDATE_S (Cycles 25-28)
            -- Emit debug packets while waiting for FpMac flux offset result.
            -- On wc=3, capture new fluxOffsetFp and launch DAC value subtract.
            -------------------------------------------------------------------
            when OFFSET_UPDATE_S =>
               case to_integer(r.waitCount) is
                  when 0 =>
                     -- Cycle 25: Emit debug packet 1
                     v.pidDebugMaster.tValid              := r.pidDebugEnable;
                     v.pidDebugMaster.tData(15 downto 0)  := std_logic_vector(r.numFluxJumps);
                     v.pidDebugMaster.tData(23 downto 16) := slv(r.accumSamples);
                     v.pidDebugMaster.tData(31 downto 24) := (others => '0');
                     v.pidDebugMaster.tData(63 downto 32) := std_logic_vector(r.additionalJumps);
                     v.waitCount := r.waitCount + 1;

                  when 1 =>
                     -- Cycle 26: Emit debug packet 2 (last)
                     v.pidDebugMaster.tValid              := r.pidDebugEnable;
                     v.pidDebugMaster.tData(31 downto 0)  := slv(r.dropCount);
                     v.pidDebugMaster.tData(63 downto 32) := timingRxData.rowSeqCount(31 downto 0);
                     v.pidDebugMaster.tLast               := '1';
                     v.waitCount := r.waitCount + 1;

                  when 2 =>
                     -- Cycle 27: Wait for FpMac
                     v.waitCount := r.waitCount + 1;

                  when 3 =>
                     -- Cycle 28: FpMac result ready (new flux offset)
                     if (fpMacOutValid = '1') then
                        v.fluxOffsetFp := fpMacOutData;

                        -- Launch FpAdd: sq1FbFullFp - newFluxOffset (DAC value)
                        v.fpAddInValid := '1';
                        v.fpAddA       := r.sq1FbFullFp;
                        v.fpAddB       := fpMacOutData;
                        v.fpAddSub     := '1';  -- subtract

                        v.state := DAC_WRAP_S;
                     end if;

                  when others =>
                     null;
               end case;

            -------------------------------------------------------------------
            -- DAC_WRAP_S (Cycles 29-30)
            -- Wait for FpAdd result (DAC value as float), launch Fp2Int for
            -- final integer conversion.
            -------------------------------------------------------------------
            when DAC_WRAP_S =>
               if (fpAddOutValid = '1') then
                  v.dacValueFp := fpAddOutData;

                  -- Launch Fp2Int for final DAC conversion
                  v.fp2IntInValid := '1';
                  v.fp2IntInData  := fpAddOutData;

                  v.state := DAC_CONVERT_S;
               end if;

            -------------------------------------------------------------------
            -- DAC_CONVERT_S (Cycles 31-32)
            -- Wait for Fp2Int result, clip to DAC range [SQ1FB_MIN_C,
            -- SQ1FB_MAX_C], set saturation flags.
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
                     v.sq1FbInt     := to_signed(SQ1FB_MIN_C, 32);
                     v.saturatedLow := '1';
                  end if;

                  v.sq1FbValid := r.rowEnabled;
                  v.state      := RAM_WRITE_S;
               end if;

            -------------------------------------------------------------------
            -- RAM_WRITE_S (Cycle 33)
            -- Anti-windup mux: decide whether to commit speculative integrator.
            -- Write all PID state RAMs.
            -------------------------------------------------------------------
            when RAM_WRITE_S =>
               -- Anti-windup: determine sign of I-contribution
               iContribSign := r.iCoef(31) xor r.accumErrorFp(31);

               if (r.iCoef = X"00000000") or
                  (r.saturatedHigh = '1' and iContribSign = '0') or
                  (r.saturatedLow = '1' and iContribSign = '1') then
                  -- Discard integrator update (anti-windup active)
                  v.sumAccumRamWrData := r.sumAccumFp;
               else
                  -- Commit speculative integrator
                  v.sumAccumRamWrData := r.newSumAccum;
               end if;

               -- Write all state RAMs (accumError already written in WAIT_INT2FP_S)
               v.sumAccumRamWrEn     := '1';
               v.sq1FbFullRamWrEn    := '1';
               v.sq1FbFullRamWrData  := r.sq1FbFullFp;
               v.fluxOffsetRamWrEn   := '1';
               v.fluxOffsetRamWrData := r.fluxOffsetFp;
               v.fluxJumpRamWrEn     := '1';
               v.fluxJumpRamWrData   := std_logic_vector(r.numFluxJumps);

               v.state := DATA_STREAM_S;

            -------------------------------------------------------------------
            -- DATA_STREAM_S (Cycle 34)
            -- Emit PID stream output based on outputMode selection.
            -------------------------------------------------------------------
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
               v.state := IDLE_S;

            -------------------------------------------------------------------
            -- CLEAR_STATE_S
            -- Unused placeholder state
            -------------------------------------------------------------------
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
