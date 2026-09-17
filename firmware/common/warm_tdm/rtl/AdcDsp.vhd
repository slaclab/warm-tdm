


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
use warm_tdm.FixedPkg.all;
use warm_tdm.FrameHeaderPkg.all;

entity AdcDsp is

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
      -- Timing interface
      timingRxClk125   : in  sl;
      timingRxRst125   : in  sl;
      timingRxData     : in  LocalTimingType;
      config           : in  WarmTdmConfigType := WARM_TDM_CONFIG_INIT_C;  -- board/group id (synchronized) for frame header
      -- Accumulated ADC result from AdcAccumulator
      accumIn          : in  AdcAccumResultType;
      accumValid       : in  sl;
      -- AXI-Lite
      -- Local register access
      sAxilReadMaster  : in  AxiLiteReadMasterType;
      sAxilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      sAxilWriteMaster : in  AxiLiteWriteMasterType;
      sAxilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      -- DAC RAM updates
      mAxilReadMaster  : out AxiLiteReadMasterType;
      mAxilReadSlave   : in  AxiLiteReadSlaveType;
      mAxilWriteMaster : out AxiLiteWriteMasterType;
      mAxilWriteSlave  : in  AxiLiteWriteSlaveType;
      -- PID output stream to filter/downsample/eventbuilder
      pidStreamMaster  : out AxiStreamMasterType;
      pidStreamSlave   : in  AxiStreamSlaveType;

      axisClk        : in  sl;
      axisRst        : in  sl;
      pidDebugMaster : out AxiStreamMasterType;
      pidDebugSlave  : in  AxiStreamSlaveType);

end entity;

architecture rtl of AdcDsp is

   constant NUM_AXIL_MASTERS_C : integer := 8;
   constant LOCAL_C            : integer := 0;
   constant ACCUM_ERROR_C      : integer := 1;
   constant SUM_ACCUM_C        : integer := 2;
   constant PID_RESULTS_C      : integer := 3;
   constant FILTER_RESULTS_C   : integer := 4;
   constant FILTER_COEF_C      : integer := 5;
   constant FLUX_JUMP_C        : integer := 6;
   constant SQ1FB_FULL_C       : integer := 7;

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


   -- Max of 256 accumulations adds 8 bits to 14 bit ADC
   constant ACCUM_BITS_C : integer := 18;
   constant COEF_HIGH_C  : integer := 0;
   constant COEF_LOW_C   : integer := -23;
   constant COEF_BITS_C  : integer := COEF_HIGH_C - COEF_LOW_C + 1;

   constant SUM_BITS_C    : integer := ACCUM_BITS_C;
   constant RESULT_HIGH_C : integer := sfixed_high(COEF_HIGH_C, COEF_LOW_C, '*', ACCUM_BITS_C-1, 0);  --26;
   constant RESULT_LOW_C  : integer := sfixed_low(COEF_HIGH_C, COEF_LOW_C, '*', ACCUM_BITS_C-1, 0);  --8;
   constant RESULT_BITS_C : integer := RESULT_HIGH_C - RESULT_LOW_C + 1;
   -- Full feedback: 38 bits (sign + 14 integer magnitude + 23 fractional).
   -- The guard integer bit lets a command exceed the DAC range before one
   -- flux wrap (e.g. 8500.25 - 2000 = 6500.25). A larger overflow cannot be
   -- recovered by one signed 14-bit quantum, so saturation here is harmless:
   -- it will still reach the final DAC clamp after the wrap.
   constant SQ1FB_FULL_HIGH_C : integer := 14;
   constant SQ1FB_FULL_BITS_C : integer := SQ1FB_FULL_HIGH_C - RESULT_LOW_C + 1;
   constant SQ1FB_FULL_RAM_BITS_C : integer := SQ1FB_FULL_BITS_C + 1;  -- MSB = valid
   constant ZERO_COEF_C   : slv(COEF_BITS_C-1 downto 0) := (others => '0');
   constant SQ1FB_MAX_C   : integer := 2**13-1;
   constant SQ1FB_MIN_C   : integer := -(2**13);
   constant FLUX_JUMP_THRESHOLD_C : integer := 7862;
   constant CLEAR_LAST_ADDR_C : slv(ROW_ADDR_BITS_G-1 downto 0) := toSlv((2**ROW_ADDR_BITS_G)-1, ROW_ADDR_BITS_G);

   constant FILTER_COEFFICIENTS_C : IntegerArray(0 to 10) := (5 => 2**7-1, others => 0);

   constant AXIS_DEBUG_CFG_C : AxiStreamConfigType := ssiAxiStreamConfig(
      dataBytes => 8,
      tKeepMode => TKEEP_COMP_C,
      tDestBits => 4);

   -- GHDL/cocotb cannot elaborate the XPM-backed FIFO primitives. Select the
   -- vendor XPM path for hardware builds and inferred FIFOs/RAMs for simulation.
   constant STREAM_FIFO_SYNTH_MODE_C : string := ite(SIMULATION_G, "inferred", "xpm");


   type StateType is (
      IDLE_S,
      DEBUG_HDR1_S,
      DEBUG_BODY_S,
      -- Holds pidStateRamAddr on the incoming row long enough for the
      -- READ_LATENCY_G=3 per-row state RAMs to present that row's stored state
      -- before PREP_PID_S latches it. Needed post accumulator-split: the row is
      -- now known only at accumValid (via accumIn.logicalRow), losing the long
      -- address setup the pre-split core had across its accumulate window.
      PREP_WAIT_S,
      PREP_PID_S,
      PID_P_S,
      PID_I_S,
      PID_D_S,
      SQ1FB_ADJUST_S,
      FLUX_JUMP_S,
      DATA_STREAM_FLUX_JUMP_0_S,
      DATA_STREAM_FLUX_JUMP_1_S,
      DATA_STREAM_S,
      FLUX_DEBUG_S,
      LOOP_DONE_S,
      DEBUG_0_S);

   type RegType is record
      fllEnable          : sl;
      rowEnableMask      : slv(255 downto 0);
      rowEnabled         : sl;
      outputMode         : slv(1 downto 0);
      state              : StateType;
      logicalRow           : slv(ROW_ADDR_BITS_G-1 downto 0);
      sq1FbDacIn         : slv(13 downto 0);
      accumSamples       : ufixed(31 downto 0);
      accumError         : sfixed(ACCUM_BITS_C-1 downto 0);
      lastAccumError     : sfixed(ACCUM_BITS_C-1 downto 0);
      sumAccum           : sfixed(SUM_BITS_C-1 downto 0);
      accumShift         : slv(3 downto 0);
      pidMultiplier      : sfixed(ACCUM_BITS_C-1 downto 0);
      pidCoef            : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      p                  : slv(COEF_BITS_C-1 downto 0);  -- sfixed(COEF_HIGH_C downto COEF_LOW_C);
      i                  : slv(COEF_BITS_C-1 downto 0);  -- sfixed(COEF_HIGH_C downto COEF_LOW_C);
      d                  : slv(COEF_BITS_C-1 downto 0);  -- sfixed(COEF_HIGH_C downto COEF_LOW_C);
      pidResult          : sfixed(RESULT_HIGH_C downto RESULT_LOW_C);
      sq1Fb              : sfixed(13 downto 0);
      sq1FbValid         : sl;
      sq1FbFull          : sfixed(SQ1FB_FULL_HIGH_C downto RESULT_LOW_C);
      -- Signed net count, saturating at -256/+255. Beyond that range the
      -- actuator still wraps but reconstructed readout loses a quantum.
      numFluxJumps       : slv(8 downto 0);
      fluxQuantum        : slv(13 downto 0);
      clearPidState      : sl;
      clearPidStateBusy  : sl;
      pidStateRamAddr    : slv(ROW_ADDR_BITS_G-1 downto 0);
      accumErrorRamWrEn  : sl;
      accumErrorRamWrData : slv(ACCUM_BITS_C-1 downto 0);
      sumAccumRamWrEn    : sl;
      sumAccumRamWrData  : slv(SUM_BITS_C-1 downto 0);
      pidResultRamWrEn   : sl;
      pidResultRamWrData : slv(RESULT_BITS_C-1 downto 0);
      fluxJumpRamWrEn    : sl;
      fluxJumpRamWrData  : slv(8 downto 0);
      sq1FbFullRamWrEn   : sl;
      sq1FbFullRamWrData : slv(SQ1FB_FULL_RAM_BITS_C-1 downto 0);
      dropCount          : ufixed(31 downto 0);
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
      logicalRow           => (others => '0'),
      sq1FbDacIn         => (others => '0'),
      accumSamples       => (others => '0'),
      accumError         => (others => '0'),
      lastAccumError     => (others => '0'),
      sumAccum           => (others => '0'),
      accumShift         => toSlv(0, 4),
      pidMultiplier      => (others => '0'),
      pidCoef            => (others => '0'),
      p                  => (others => '0'),
      i                  => (others => '0'),
      d                  => (others => '0'),
      pidResult          => (others => '0'),
      sq1Fb              => (others => '0'),
      sq1FbValid         => '0',
      sq1FbFull          => (others => '0'),
      numFluxJumps       => (others => '0'),
      fluxQuantum        => (others => '0'),
      clearPidState      => '0',
      clearPidStateBusy  => '0',
      pidStateRamAddr    => (others => '0'),
      accumErrorRamWrEn  => '0',
      accumErrorRamWrData => (others => '0'),
      sumAccumRamWrEn    => '0',
      sumAccumRamWrData  => (others => '0'),
      pidResultRamWrEn   => '0',
      pidResultRamWrData => (others => '0'),
      fluxJumpRamWrEn    => '0',
      fluxJumpRamWrData  => (others => '0'),
      sq1FbFullRamWrEn   => '0',
      sq1FbFullRamWrData => (others => '0'),
      dropCount          => (others => '0'),
      axilPidDebugEnable => '0',
      pidDebugEnable     => '0',
      pidDebugMaster     => axiStreamMasterInit(AXIS_DEBUG_CFG_C),
      pidStreamMaster    => axiStreamMasterInit(PID_DATA_AXIS_CFG_C),
      axilWriteSlave     => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave      => AXI_LITE_READ_SLAVE_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal accumRamOut       : slv(ACCUM_BITS_C-1 downto 0);
   signal sumRamOut         : slv(SUM_BITS_C-1 downto 0);
   signal pidRamOut         : slv(RESULT_BITS_C-1 downto 0);
   signal fluxJumpRamOut    : slv(8 downto 0);
   signal sq1FbFullRamOut    : slv(SQ1FB_FULL_RAM_BITS_C-1 downto 0);

--   signal pidStreamMaster    : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal filterStreamMaster : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;

   signal pidDebugCtrl : AxiStreamCtrlType := AXI_STREAM_CTRL_UNUSED_C;

   -------------------------------------------------------------------------------------------------
   -- AXIL Signals
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



begin

   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => XBAR_CONFIG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => timingRxClk125,       -- [in]
         axiClkRst           => timingRxRst125,       -- [in]
         sAxiWriteMasters(0) => sAxilWriteMaster,     -- [in]
         sAxiWriteSlaves(0)  => sAxilWriteSlave,      -- [out]
         sAxiReadMasters(0)  => sAxilReadMaster,      -- [in]
         sAxiReadSlaves(0)   => sAxilReadSlave,       -- [out]
         mAxiWriteMasters    => locAxilWriteMasters,  -- [out]
         mAxiWriteSlaves     => locAxilWriteSlaves,   -- [in]
         mAxiReadMasters     => locAxilReadMasters,   -- [out]
         mAxiReadSlaves      => locAxilReadSlaves);   -- [in]

--    U_AxiLiteAsync_1 : entity surf.AxiLiteAsync
--       generic map (
--          TPD_G            => TPD_G,
--          RST_ASYNC_G      => RST_ASYNC_G,
--          AXI_ERROR_RESP_G => AXI_ERROR_RESP_G,
--          COMMON_CLK_G     => COMMON_CLK_G,
--          NUM_ADDR_BITS_G  => NUM_ADDR_BITS_G,
--          PIPE_STAGES_G    => PIPE_STAGES_G)
--       port map (
--          sAxiClk         => timingRxClk125,                       -- [in]
--          sAxiClkRst      => axilClkRst,                    -- [in]
--          sAxiReadMaster  => locAxilReadMasters(LOCAL_C),   -- [in]
--          sAxiReadSlave   => locAxilReadSlaves(LOCAL_C),    -- [out]
--          sAxiWriteMaster => locAxilWriteMasters(LOCAL_C),  -- [in]
--          sAxiWriteSlave  => locAxilWriteSlaves(LOCAL_C),   -- [out]
--          mAxiClk         => timingRxClk125,                -- [in]
--          mAxiClkRst      => timingRxRst125,                -- [in]
--          mAxiReadMaster  => timingAxilReadMaster,          -- [out]
--          mAxiReadSlave   => timingAxilReadSlave,           -- [in]
--          mAxiWriteMaster => timingAxilWriteMaster,         -- [out]
--          mAxiWriteSlave  => timingAxilWriteSlave);         -- [in]

   timingAxilReadMaster        <= locAxilReadMasters(LOCAL_C);
   locAxilReadSlaves(LOCAL_C)  <= timingAxilReadSlave;
   timingAxilWriteMaster       <= locAxilWriteMasters(LOCAL_C);
   locAxilWriteSlaves(LOCAL_C) <= timingAxilWriteSlave;


   -- RAM for ADC Baselines
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
         DATA_WIDTH_G     => 9)
      port map (
         axiClk         => timingRxClk125,                    -- [in]
         axiRst         => timingRxRst125,                    -- [in]
         axiReadMaster  => locAxilReadMasters(FLUX_JUMP_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(FLUX_JUMP_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(FLUX_JUMP_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(FLUX_JUMP_C),   -- [out]
         clk            => timingRxClk125,                    -- [in]
         rst            => timingRxRst125,                    -- [in]
         addr           => r.pidStateRamAddr,                -- [in]
         dout           => fluxJumpRamOut,                    -- [out]
         we             => r.fluxJumpRamWrEn,                -- [in]
         din            => r.fluxJumpRamWrData);             -- [in]

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
         DATA_WIDTH_G     => ACCUM_BITS_C)
      port map (
         axiClk         => timingRxClk125,                      -- [in]
         axiRst         => timingRxRst125,                      -- [in]
         axiReadMaster  => locAxilReadMasters(ACCUM_ERROR_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(ACCUM_ERROR_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(ACCUM_ERROR_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(ACCUM_ERROR_C),   -- [out]
         clk            => timingRxClk125,                      -- [in]
         rst            => timingRxRst125,                      -- [in]
         addr           => r.pidStateRamAddr,                  -- [in]
         we             => r.accumErrorRamWrEn,                -- [in]
         din            => r.accumErrorRamWrData,              -- [in]
         dout           => accumRamOut);                        -- [in]


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
         DATA_WIDTH_G     => SUM_BITS_C)
      port map (
         axiClk         => timingRxClk125,                    -- [in]
         axiRst         => timingRxRst125,                    -- [in]
         axiReadMaster  => locAxilReadMasters(SUM_ACCUM_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(SUM_ACCUM_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(SUM_ACCUM_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(SUM_ACCUM_C),   -- [out]
         clk            => timingRxClk125,                    -- [in]
         rst            => timingRxRst125,                    -- [in]
         addr           => r.pidStateRamAddr,                -- [in]
         we             => r.sumAccumRamWrEn,                -- [in]
         din            => r.sumAccumRamWrData,              -- [in]
         dout           => sumRamOut);                        -- [in]

   -- Retained for per-row software diagnostics; pidRamOut is not servo state.
   -- TODO: consider removing/reusing this RAM once per-row PidResults polling
   -- is no longer needed. Update the software register map at the same time;
   -- the current correction is also carried in the PID-debug stream.
   U_AxiDualPortRam_PID_RESULTS : entity surf.AxiDualPortRam
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
         DATA_WIDTH_G     => RESULT_BITS_C)
      port map (
         axiClk         => timingRxClk125,                      -- [in]
         axiRst         => timingRxRst125,                      -- [in]
         axiReadMaster  => locAxilReadMasters(PID_RESULTS_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(PID_RESULTS_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(PID_RESULTS_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(PID_RESULTS_C),   -- [out]
         clk            => timingRxClk125,                      -- [in]
         rst            => timingRxRst125,                      -- [in]
         addr           => r.pidStateRamAddr,                  -- [in]
         we             => r.pidResultRamWrEn,                 -- [in]
         din            => r.pidResultRamWrData,               -- [in]
         dout           => pidRamOut);                          -- [in]


   -- Full feedback at 0x7000 + 8*row: signed bits 37:0, binary point at -23,
   -- and valid bit 38. Matches the existing three-cycle state-RAM wait.
   -- Reset leaves FLL disabled; its rising enable clears every RAM address
   -- before the first update, just as StartRun/ClearPidState/I changes do.
   U_Sq1FbFullRam : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "block",
         READ_LATENCY_G   => 3,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => true,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => true,
         ADDR_WIDTH_G     => ROW_ADDR_BITS_G,
         DATA_WIDTH_G     => SQ1FB_FULL_RAM_BITS_C)
      port map (
         axiClk         => timingRxClk125,
         axiRst         => timingRxRst125,
         axiReadMaster  => locAxilReadMasters(SQ1FB_FULL_C),
         axiReadSlave   => locAxilReadSlaves(SQ1FB_FULL_C),
         axiWriteMaster => locAxilWriteMasters(SQ1FB_FULL_C),
         axiWriteSlave  => locAxilWriteSlaves(SQ1FB_FULL_C),
         clk            => timingRxClk125,
         rst            => timingRxRst125,
         we             => r.sq1FbFullRamWrEn,
         addr           => r.pidStateRamAddr,
         din            => r.sq1FbFullRamWrData,
         dout           => sq1FbFullRamOut);

   comb : process (accumIn, accumRamOut, accumValid, sq1FbFullRamOut, fluxJumpRamOut, pidDebugCtrl, r,
                   sumRamOut, timingAxilReadMaster, timingAxilWriteMaster,
                   timingRxData, timingRxRst125) is
      variable v                 : RegType;
      variable pSfixed           : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      variable iSfixed           : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      variable dSfixed           : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      variable fluxQuantumFixed  : sfixed(13 downto 0);
      variable numFluxJumpsFixed : sfixed(8 downto 0);
      variable pidStateRamAddrFixed : ufixed(ROW_ADDR_BITS_G-1 downto 0);
      variable pidResultNext     : sfixed(RESULT_HIGH_C downto RESULT_LOW_C);
      variable iContribution     : sfixed(RESULT_HIGH_C downto RESULT_LOW_C);
      variable requestClear      : boolean;
      variable allowIntegrate    : boolean;
      variable axilEp            : AxiLiteEndpointType;

   begin
      v := r;

      -- Treat clearPidState like a touch-one command from software.
      v.clearPidState := '0';

      ----------------------------------------------------------------------------------------------
      -- AXI Lite Registers
      ----------------------------------------------------------------------------------------------
      axiSlaveWaitTxn(axilEp, timingAxilWriteMaster, timingAxilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.fllEnable);

      axiSlaveRegister(axilEp, X"00", 8, v.outputMode);
      axiSlaveRegister(axilEp, X"00", 16, v.accumShift);
      axiSlaveRegister(axilEp, X"04", 0, v.p);
      axiSlaveRegister(axilEp, X"08", 0, v.i);
      axiSlaveRegister(axilEp, X"0c", 0, v.d);

      axiSlaveRegister(axilEp, X"40", 0, v.fluxQuantum);
      axiSlaveRegisterR(axilEp, X"44", 0, r.numFluxJumps);

      axiSlaveRegister(axilEp, X"50", 0, v.axilPidDebugEnable);

      axiSlaveRegister(axilEp, X"60", 0, v.rowEnableMask);

      axiSlaveRegisterR(axilEp, X"10", 0, to_slv(r.accumError));
      axiSlaveRegisterR(axilEp, X"14", 0, to_slv(r.lastAccumError));
      axiSlaveRegisterR(axilEp, X"18", 0, to_slv(r.sumAccum));
      axiSlaveRegisterR(axilEp, X"20", 0, to_slv(r.pidResult));
      axiSlaveRegisterR(axilEp, X"28", 0, to_slv(r.sq1Fb));


      axiSlaveRegister(axilEp, X"30", 0, v.clearPidState);


      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      ----------------------------------------------------------------------------------------------

      v.sq1FbValid      := '0';
      v.pidStateRamAddr := r.logicalRow;
      v.accumErrorRamWrEn   := '0';
      v.accumErrorRamWrData := to_slv(r.accumError);
      v.sumAccumRamWrEn     := '0';
      v.sumAccumRamWrData   := to_slv(r.sumAccum);
      v.pidResultRamWrEn    := '0';
      v.pidResultRamWrData  := to_slv(r.pidResult);
      v.fluxJumpRamWrEn     := '0';
      v.fluxJumpRamWrData   := r.numFluxJumps;
      v.sq1FbFullRamWrEn   := '0';
      v.sq1FbFullRamWrData := '1' & to_slv(r.sq1FbFull);

      v.pidStreamMaster := axiStreamMasterInit(PID_DATA_AXIS_CFG_C);

      v.pidDebugMaster       := axiStreamMasterInit(AXIS_DEBUG_CFG_C);
      v.pidDebugMaster.tDest := toSlv(1, 8);  -- Board-local PID-debug stream (DataPath U_AxiStreamMux_1 ROUTED re-stamps this anyway).

      pSfixed           := to_sfixed(r.p, pSfixed);
      iSfixed           := to_sfixed(r.i, iSfixed);
      dSfixed           := to_sfixed(r.d, dSfixed);
      fluxQuantumFixed  := to_sfixed(r.fluxQuantum, fluxQuantumFixed);
      numFluxJumpsFixed := to_sfixed(r.numFluxJumps, numFluxJumpsFixed);
      pidStateRamAddrFixed := to_ufixed(r.pidStateRamAddr, pidStateRamAddrFixed);
      requestClear      := false;

      if (timingRxData.startRun = '1') then
         v.dropCount := (others => '0');
         requestClear := true;
      end if;

      if (v.clearPidState = '1') then
         requestClear := true;
      end if;

      if (r.fllEnable = '0' and v.fllEnable = '1') then
         requestClear := true;
      end if;

      if (v.i /= r.i) then
         requestClear := true;
      end if;

      if (requestClear) then
         v.clearPidStateBusy := '1';
         v.state             := IDLE_S;
         v.rowEnabled        := '0';
         v.accumSamples      := (others => '0');
         v.accumError        := (others => '0');
         v.lastAccumError    := (others => '0');
         v.sumAccum          := (others => '0');
         v.pidMultiplier     := (others => '0');
         v.pidCoef           := (others => '0');
         v.pidResult         := (others => '0');
         v.sq1FbValid        := '0';
         v.sq1FbFull         := (others => '0');
         v.numFluxJumps      := (others => '0');
         v.pidDebugEnable    := '0';
         v.pidStateRamAddr   := (others => '0');
         v.accumErrorRamWrEn   := '1';
         v.accumErrorRamWrData := (others => '0');
         v.sumAccumRamWrEn     := '1';
         v.sumAccumRamWrData   := (others => '0');
         v.pidResultRamWrEn    := '1';
         v.pidResultRamWrData  := (others => '0');
         v.fluxJumpRamWrEn     := '1';
         v.fluxJumpRamWrData   := (others => '0');
         v.sq1FbFullRamWrEn   := '1';
         v.sq1FbFullRamWrData := (others => '0');
      elsif (r.clearPidStateBusy = '1') then
         v.state             := IDLE_S;
         v.rowEnabled        := '0';
         v.accumSamples      := (others => '0');
         v.accumError        := (others => '0');
         v.lastAccumError    := (others => '0');
         v.sumAccum          := (others => '0');
         v.pidMultiplier     := (others => '0');
         v.pidCoef           := (others => '0');
         v.pidResult         := (others => '0');
         v.sq1FbValid        := '0';
         v.sq1FbFull         := (others => '0');
         v.numFluxJumps      := (others => '0');
         v.pidDebugEnable    := '0';
         v.accumErrorRamWrEn   := '1';
         v.accumErrorRamWrData := (others => '0');
         v.sumAccumRamWrEn     := '1';
         v.sumAccumRamWrData   := (others => '0');
         v.pidResultRamWrEn    := '1';
         v.pidResultRamWrData  := (others => '0');
         v.fluxJumpRamWrEn     := '1';
         v.fluxJumpRamWrData   := (others => '0');
         v.sq1FbFullRamWrEn   := '1';
         v.sq1FbFullRamWrData := (others => '0');

         if (r.pidStateRamAddr = CLEAR_LAST_ADDR_C) then
            v.clearPidStateBusy := '0';
         else
            v.pidStateRamAddr := to_slv(resize(pidStateRamAddrFixed + 1, pidStateRamAddrFixed));
         end if;
      elsif (r.fllEnable = '0' and accumValid = '1' and accumIn.seqStart = '1') then
         v.pidStreamMaster.tValid := '1';
         v.pidStreamMaster.tKeep  := (others => '0');
         v.pidStreamMaster.tLast  := '1';

      elsif (r.fllEnable = '1') then
         case r.state is
            when IDLE_S =>
               v.pidDebugEnable := not pidDebugCtrl.pause and r.axilPidDebugEnable;
               if (r.axilPidDebugEnable = '1' and pidDebugCtrl.pause = '1') then
                  v.dropCount := resize(r.dropCount + 1, r.dropCount);
               end if;

               if (accumValid = '1') then
                  v.logicalRow     := accumIn.logicalRow(ROW_ADDR_BITS_G-1 downto 0);
                  -- Drive the per-row state RAM address from accumIn directly
                  -- (not the registered r.logicalRow) so it is applied a cycle
                  -- earlier; combined with PREP_WAIT_S this gives the
                  -- READ_LATENCY_G=3 RAMs enough setup before PREP_PID_S reads.
                  v.pidStateRamAddr := accumIn.logicalRow(ROW_ADDR_BITS_G-1 downto 0);
                  -- SATURATE the 32-bit accumulated error into the 18-bit PID
                  -- accumulator instead of slicing the low bits. The pre-split DSP
                  -- accumulated directly into this sfixed and its resize saturated;
                  -- a bare low-18-bit slice WRAPS (e.g. +249000 -> -13144),
                  -- reversing the correction sign on overflow. resize into
                  -- sfixed(17:0) saturates by fixed_pkg default (clamp +/-131071).
                  -- The shared AdcAccumulator keeps the full 32-bit sum because the
                  -- FP DSP (AdcDspFp) needs it, so the clamp lives here.
                  v.accumError   := resize(to_sfixed(accumIn.accumError, 31, 0), v.accumError);
                  -- accumIn.numSamples is unsigned(7 downto 0); accumSamples is
                  -- ufixed(31 downto 0). Use the numeric unsigned->ufixed
                  -- conversion (which resizes) rather than the slv overload,
                  -- which requires matching vector widths and otherwise trips a
                  -- length-mismatch bounds check under fixed_pkg.
                  v.accumSamples := to_ufixed(accumIn.numSamples, v.accumSamples);
                  v.sq1FbDacIn   := accumIn.sq1FbDac;
                  v.rowEnabled   := r.rowEnableMask(to_integer(unsigned(accumIn.logicalRow)));

                  -- Frame word 0: shared identity header (SOF here). The old
                  -- col/row/runTime word is demoted to a body word (DEBUG_BODY_S).
                  emitFrameHeaderWord0(
                     axisConfig => AXIS_DEBUG_CFG_C,
                     axisMaster => v.pidDebugMaster,
                     formatType => FRAME_FORMAT_PID_FIXED_C,
                     boardId    => "00000" & config.boardId,
                     groupId    => config.groupId,
                     valid      => v.pidDebugEnable,
                     formatVersion => FRAME_FORMAT_PID_FIXED_VERSION_C);

                  if (accumIn.seqStart = '1') then
                     v.pidStreamMaster.tValid := '1';
                     v.pidStreamMaster.tKeep  := (others => '0');
                     v.pidStreamMaster.tLast  := '1';
                  end if;

                  v.state := DEBUG_HDR1_S;
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
               v.pidDebugMaster.tValid              := r.pidDebugEnable;
               v.pidDebugMaster.tData(3 downto 0)   := toSlv(COLUMN_NUM_G, 4);
               v.pidDebugMaster.tData(15 downto 8)  := resize(r.logicalRow, 8);
               v.state                              := PREP_WAIT_S;

            -- One-cycle hold so the per-row state RAMs (READ_LATENCY_G=3),
            -- addressed by pidStateRamAddr since accumValid, present the current
            -- row's stored accumError/sumAccum/etc before PREP_PID_S reads them.
            when PREP_WAIT_S =>
               v.state := PREP_PID_S;

            when PREP_PID_S =>
               -- Write the accumError from last stage into ram
               v.accumErrorRamWrEn   := '1';
               v.accumErrorRamWrData := to_slv(r.accumError);
               -- Register values from RAM for PID calculation
               v.lastAccumError := to_sfixed(accumRamOut, r.lastAccumError);
               v.sumAccum       := to_sfixed(sumRamOut, r.sumAccum);
               v.numFluxJumps   := fluxJumpRamOut;
               -- Register current sq1FB here
               -- Convert offset binary to 2-s complement
               -- Store in sfixed type register
               v.sq1FB          := to_sfixed(convOffsetBin(r.sq1FbDacIn), r.sq1FB);
               -- Seed from the applied DAC on the first enabled update after
               -- a clear. Thereafter the full-precision state is authoritative;
               -- quantizing the output must not quantize the next loop's base.
               if (sq1FbFullRamOut(SQ1FB_FULL_BITS_C) = '1') then
                  v.sq1FbFull := to_sfixed(sq1FbFullRamOut(SQ1FB_FULL_BITS_C-1 downto 0), v.sq1FbFull);
               else
                  v.sq1FbFull := resize(v.sq1Fb, v.sq1FbFull);
               end if;

               -- Body word 1 is accum error
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0) := to_slv(resize(r.accumError, 31, 0));

               -- Prep for P stage
               v.pidCoef       := pSfixed;
               v.pidMultiplier := r.accumError;     -- Prep accumError for P stage
               v.pidResult     := (others => '0');  -- Clear pid result
               v.state         := PID_P_S;          --PID_PRESHIFT_S;

--             when PID_PRESHIFT_S =>
--                v.pidMultiplier := shift_right(r.pidMultiplier, to_integer(unsigned(r.accumShift)));
--                v.state         := PID_P_S;

            when PID_P_S =>
               -- Body word 2 is starting SQ1FB
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(13 downto 0) := resize(convOffsetBin(to_slv(r.sq1FB)), 14);

               -- Calcualte PID Stage
               v.pidResult     := resize(r.pidResult + (r.pidCoef * r.pidMultiplier), v.pidResult);  -- r.accumError;
               -- Prep for I Stage
               v.pidCoef       := iSfixed;
               v.pidMultiplier := r.sumAccum;
               v.state         := PID_I_S;

            when PID_I_S =>
               -- Body word 3 is SumAccum
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0) := to_slv(resize(r.pidMultiplier, 31, 0));

               -- Calculate PID stage
               v.pidResult     := resize(r.pidResult + (r.pidCoef * r.pidMultiplier), v.pidResult);  -- r.sumAccum
               -- Prep for D stage
               v.pidCoef       := dSfixed;
               v.pidMultiplier := resize(r.lastAccumError - r.accumError, v.pidMultiplier);  -- Prep for D stage
               v.state         := PID_D_S;

            when PID_D_S =>
               -- Body word 4 is diff multiplier result
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0) := to_slv(resize(r.pidMultiplier, 31, 0));


               -- Calculate PID Stage
               pidResultNext := resize(r.pidResult + (r.pidCoef * r.pidMultiplier), pidResultNext);
               v.pidResult   := pidResultNext;

               if (r.i = ZERO_COEF_C) then
                  v.sumAccum := (others => '0');
               else
                  iContribution := resize(iSfixed * r.accumError, iContribution);
                  allowIntegrate := true;

                  -- The fixed_pkg addition keeps its carry and fraction here;
                  -- preserve the existing directional, pre-wrap I-state check.
                  if ((r.sq1FbFull + pidResultNext > SQ1FB_MAX_C) and (iContribution > 0)) then
                     allowIntegrate := false;
                  elsif ((r.sq1FbFull + pidResultNext < SQ1FB_MIN_C) and (iContribution < 0)) then
                     allowIntegrate := false;
                  end if;

                  if (allowIntegrate) then
                     v.sumAccum := resize(r.sumAccum + r.accumError, v.sumAccum);
                  else
                     v.sumAccum := r.sumAccum;
                  end if;
               end if;

               -- Save result and sumAccum in RAM
               v.sumAccumRamWrEn    := '1';
               v.sumAccumRamWrData  := to_slv(v.sumAccum);
               v.pidResultRamWrEn   := '1';
               v.pidResultRamWrData := to_slv(v.pidResult);
               v.state              := SQ1FB_ADJUST_S;

            when SQ1FB_ADJUST_S =>
               -- Body word 5 is PID result
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(63 downto 0) := resize(to_slv(r.pidResult), 64);

               -- Keep the fraction and guard bit through the flux adjustment.
               -- sq1Fb is only the applied/commanded integer DAC value.
               v.sq1FbFull := resize(r.sq1FbFull + r.pidResult, v.sq1FbFull);
               v.state    := FLUX_JUMP_S;

            when FLUX_JUMP_S =>
               -- Zero quantum disables wrapping and must not consume count
               -- range. A physical wrap requires a positive signed quantum.
               if (fluxQuantumFixed /= 0 and r.sq1FbFull > FLUX_JUMP_THRESHOLD_C) then
                  v.sq1FbFull       := resize(r.sq1FbFull - fluxQuantumFixed, v.sq1FbFull);
                  numFluxJumpsFixed := resize(numFluxJumpsFixed + 1, numFluxJumpsFixed);
               elsif (fluxQuantumFixed /= 0 and r.sq1FbFull < -FLUX_JUMP_THRESHOLD_C) then
                  v.sq1FbFull       := resize(r.sq1FbFull + fluxQuantumFixed, v.sq1FbFull);
                  numFluxJumpsFixed := resize(numFluxJumpsFixed - 1, numFluxJumpsFixed);
               end if;
               -- Clamp the retained state as well as the actuator, discarding
               -- any overrange value that one flux adjustment cannot recover.
               if (v.sq1FbFull > SQ1FB_MAX_C) then
                  v.sq1FbFull := to_sfixed(SQ1FB_MAX_C, v.sq1FbFull);
               elsif (v.sq1FbFull < SQ1FB_MIN_C) then
                  v.sq1FbFull := to_sfixed(SQ1FB_MIN_C, v.sq1FbFull);
               end if;
               -- The sole feedback-to-DAC conversion (nearest-even rounding).
               v.sq1Fb := resize(v.sq1FbFull, v.sq1Fb);
               -- Commit with the DAC command. A masked visit neither advances
               -- existing state nor initializes a row from an unapplied command.
               v.sq1FbFullRamWrEn   := r.rowEnabled;
               v.sq1FbFullRamWrData := '1' & to_slv(v.sq1FbFull);

               v.numFluxJumps      := to_slv(numFluxJumpsFixed);
               -- The count and local feedback are one state pair. Commit
               -- both only when the corresponding DAC command is enabled.
               v.fluxJumpRamWrEn   := r.rowEnabled;
               v.fluxJumpRamWrData := to_slv(numFluxJumpsFixed);
               v.sq1FbValid        := r.rowEnabled;
               v.state             := DATA_STREAM_FLUX_JUMP_0_S;

            when DATA_STREAM_FLUX_JUMP_0_S =>
               -- Body word 6: post-wrap/clamp feedback, before DAC rounding.
               -- Sign-extend Q15.23 to 64 bits; no valid bit in the stream.
               -- Like sq1FbEnd, this is computed but not committed if masked.
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(63 downto 0) := to_slv(resize(r.sq1FbFull, 40, RESULT_LOW_C));

               v.pidResult     := to_sfixed(to_slv(resize(r.sq1Fb, r.pidResult'length-1, 0)), r.pidResult);
               v.pidMultiplier := to_sfixed(to_slv(resize(numFluxJumpsFixed, r.pidMultiplier'length-1, 0)), r.pidMultiplier);
               v.pidCoef       := to_sfixed(to_slv(resize(fluxQuantumFixed, r.pidCoef'length-1, 0)), r.pidCoef);
               v.state         := DATA_STREAM_FLUX_JUMP_1_S;

            when DATA_STREAM_FLUX_JUMP_1_S =>
               v.pidResult := resize(r.pidResult + (r.pidCoef * r.pidMultiplier), v.pidResult);
               v.state     := DATA_STREAM_S;

            when DATA_STREAM_S =>
               -- Output PID Stream
               v.pidStreamMaster.tValid := r.rowEnabled;
               if (r.outputMode = "00") then
                  v.pidStreamMaster.tData(31 downto 0) := resize(to_slv(r.pidResult), 32);
               elsif (r.outputMode = "01") then
                  v.pidStreamMaster.tData(31 downto 0) := to_slv(resize(r.accumError, 31, 0));
               elsif (r.outputMode = "10") then
                  v.pidStreamMaster.tData(31 downto 0) := timingRxData.rowSeqCount(31 downto 0);
               end if;

               v.pidStreamMaster.tId(ROW_ADDR_BITS_G-1 downto 0) := r.logicalRow;

               v.state := FLUX_DEBUG_S;

            when FLUX_DEBUG_S =>
               -- Body word 7: signed net count, including its ninth bit.
               v.pidDebugMaster.tValid            := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0) := to_slv(resize(numFluxJumpsFixed, 31, 0));

               v.state := LOOP_DONE_S;

            when LOOP_DONE_S =>
               -- Word 8 is new sq1Fb
               v.pidDebugMaster.tValid              := r.pidDebugEnable;
               v.pidDebugMaster.tData(13 downto 0)  := resize(convOffsetBin(to_slv(r.sq1Fb)), 14);
               v.pidDebugMaster.tData(63 downto 32) := to_slv(r.dropCount);

               v.state := DEBUG_0_S;

            when DEBUG_0_S =>
               -- Word 9 is Number of accum samples and readout count
               v.pidDebugMaster.tValid              := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0)  := slv(r.accumSamples);
               v.pidDebugMaster.tData(63 downto 32) := timingRxData.rowSeqCount(31 downto 0);
               v.pidDebugMaster.tLast               := '1';

               v.state := IDLE_S;

         end case;
      end if;

      if (v.clearPidStateBusy = '0') then
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
   -- Convert debug stream to axisClk
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
            SYNTH_MODE_G        => STREAM_FIFO_SYNTH_MODE_C,
            MEMORY_TYPE_G       => "bram",
            INT_WIDTH_SELECT_G  => "WIDE",
            SLAVE_AXI_CONFIG_G  => AXIS_DEBUG_CFG_C,
            MASTER_AXI_CONFIG_G => DATA_AXIS_CONFIG_C)
         port map (
            sAxisClk    => timingRxClk125,    -- [in]
            sAxisRst    => timingRxRst125,    -- [in]
            sAxisMaster => r.pidDebugMaster,  -- [in]
            sAxisSlave  => open,              -- [out]
            sAxisCtrl   => pidDebugCtrl,      -- [out]
            mAxisClk    => axisClk,           -- [in]
            mAxisRst    => axisRst,           -- [in]
            mAxisMaster => pidDebugMaster,    -- [out]
            mAxisSlave  => pidDebugSlave);    -- [in]
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
         SYNTH_MODE_G        => STREAM_FIFO_SYNTH_MODE_C,
         MEMORY_TYPE_G       => "distributed",
         INT_WIDTH_SELECT_G  => "WIDE",
         SLAVE_AXI_CONFIG_G  => PID_DATA_AXIS_CFG_C,
         MASTER_AXI_CONFIG_G => PID_DATA_AXIS_CFG_C)
      port map (
         sAxisClk    => timingRxClk125,     -- [in]
         sAxisRst    => timingRxRst125,     -- [in]
         sAxisMaster => r.pidStreamMaster,  -- [in]
         sAxisSlave  => open,               -- [out]
         sAxisCtrl   => open,               -- [out]
         mAxisClk    => timingRxClk125,     -- [in]
         mAxisRst    => timingRxRst125,     -- [in]
         mAxisMaster => pidStreamMaster,    -- [out]
         mAxisSlave  => pidStreamSlave);    -- [in]



   -------------------------------------------------------------------------------------------------
   -- sq1Fb Updates written to fifo
   -- Convert back to inverted offsset binary first
   -------------------------------------------------------------------------------------------------
   sq1fbOffsetBin <= convOffsetBin(to_slv(r.sq1Fb));
   logicalRow8      <= resize(r.logicalRow, 8);

   U_Fifo_1 : entity surf.Fifo
      generic map (
         TPD_G           => TPD_G,
         GEN_SYNC_FIFO_G => false,
         FWFT_EN_G       => true,
         SYNTH_MODE_G    => STREAM_FIFO_SYNTH_MODE_C,
         MEMORY_TYPE_G   => "distributed",
         PIPE_STAGES_G   => 0,
         DATA_WIDTH_G    => 22,
         ADDR_WIDTH_G    => 4)
      port map (
         rst               => timingRxRst125,  -- [in]
         wr_clk            => timingRxClk125,  -- [in]
         wr_en             => r.sq1FbValid,    -- [in]
         din(13 downto 0)  => sq1fbOffsetBin,  -- [in]
         din(21 downto 14) => logicalRow8,       -- [in]
         overflow          => open,            -- [out]
         rd_clk            => timingRxClk125,  -- [in]
         rd_en             => axilR.fifoRd,    -- [in]
         dout              => fifoDout,        -- [out]
         valid             => fifoValid);      -- [out]

   U_AxiLiteMaster_1 : entity surf.AxiLiteMaster
      generic map (
         TPD_G       => TPD_G,
         RST_ASYNC_G => false)
      port map (
         axilClk         => timingRxClk125,    -- [in]
         axilRst         => timingRxRst125,    -- [in]
         req             => axilR.req,         -- [in]
         ack             => ack,               -- [out]
         axilWriteMaster => mAxilWriteMaster,  -- [out]
         axilWriteSlave  => mAxilWriteSlave,   -- [in]
         axilReadMaster  => mAxilReadMaster,   -- [out]
         axilReadSlave   => mAxilReadSlave);   -- [in]
   --
   axilComb : process (ack, axilR, fifoDout, fifoValid, timingRxRst125) is
      variable v : AxilRegType := AXIL_REG_INIT_C;
   begin
      v := axilR;

      v.req.rnw := '0';
      v.fifoRd  := '0';

      -- Consume one FIFO entry per completed request/acknowledgement handshake.
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
