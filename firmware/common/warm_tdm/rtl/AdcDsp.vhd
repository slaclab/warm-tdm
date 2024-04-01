library ieee;
use ieee.std_logic_1164.all;

package local_fixed_pkg is new ieee.fixed_generic_pkg  generic map (
   fixed_round_style => IEEE.fixed_float_types.fixed_truncate,
   fixed_guard_bits  => 0);

use work.local_fixed_pkg.all;

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

entity AdcDsp is

   generic (
      TPD_G            : time                 := 1 ns;
      COLUMN_NUM_G     : integer range 0 to 7 := 0;
      AXIL_BASE_ADDR_G : slv(31 downto 0)     := (others => '0');
      SQ1FB_RAM_ADDR_G : slv(31 downto 0)     := (others => '0'));

   port (
      -- Timing interface
      timingRxClk125   : in  sl;
      timingRxRst125   : in  sl;
      timingRxData     : in  LocalTimingType;
      -- Incomming ADC Stream
      adcAxisMaster    : in  AxiStreamMasterType;
      -- AXI-Lite
--       axilClk          : in  sl;
--       timingRxRst125          : in  sl;
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

      axisClk        : in  sl;
      axisRst        : in  sl;
      pidDebugMaster : out AxiStreamMasterType;
      pidDebugSlave  : in  AxiStreamSlaveType;
      dataMaster     : out AxiStreamMasterType;
      dataSlave      : in  AxiStreamSlaveType);

end entity;

architecture rtl of AdcDsp is

   constant ROW_ADDR_BITS_C : integer := 8;

   constant NUM_AXIL_MASTERS_C : integer := 8;
   constant LOCAL_C            : integer := 0;
   constant ADC_BASELINE_C     : integer := 1;
   constant ACCUM_ERROR_C      : integer := 2;
   constant SUM_ACCUM_C        : integer := 3;
   constant PID_RESULTS_C      : integer := 4;
   constant FILTER_RESULTS_C   : integer := 5;
   constant FILTER_COEF_C      : integer := 6;
   constant FLUX_JUMP_C        : integer := 7;

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
   constant ACCUM_BITS_C : integer := 22;
   constant COEF_HIGH_C  : integer := 0;
   constant COEF_LOW_C   : integer := -17;
   constant COEF_BITS_C  : integer := COEF_HIGH_C - COEF_LOW_C + 1;

   constant SUM_BITS_C    : integer := ACCUM_BITS_C;
   constant RESULT_HIGH_C : integer := sfixed_high(COEF_HIGH_C, COEF_LOW_C, '*', ACCUM_BITS_C-1, 0);  --26;
   constant RESULT_LOW_C  : integer := sfixed_low(COEF_HIGH_C, COEF_LOW_C, '*', ACCUM_BITS_C-1, 0);  --8;
   constant RESULT_BITS_C : integer := RESULT_HIGH_C - RESULT_LOW_C + 1;

   constant FILTER_COEFFICIENTS_C : IntegerArray(0 to 10) := (5 => 2**7-1, others => 0);

   constant AXIS_DEBUG_CFG_C : AxiStreamConfigType := ssiAxiStreamConfig(
      dataBytes => 8,
      tKeepMode => TKEEP_COMP_C,
      tDestBits => 4);

   constant AXIS_DATA_CFG_C : AxiStreamConfigType := ssiAxiStreamConfig(
      dataBytes => 2,
      tKeepMode => TKEEP_COMP_C,
      tDestBits => 8);



   type StateType is (
      WAIT_ROW_STROBE_S,
      WAIT_FIRST_SAMPLE_S,
      ACCUMULATE_S,
      PREP_PID_S,
      PID_PRESHIFT_S,
      PID_P_S,
      PID_I_S,
      PID_D_S,
      SQ1FB_ADJUST_S,
      FLUX_JUMP_S,
      FLUX_DEBUG_S,
      LOOP_DONE_S);

   type RegType is record
      fllEnable          : sl;
      state              : StateType;
      rowIndex           : slv(ROW_ADDR_BITS_C-1 downto 0);
      accumValid         : sl;
      accumError         : sfixed(ACCUM_BITS_C-1 downto 0);
      lastAccum          : sfixed(ACCUM_BITS_C-1 downto 0);
      sumAccum           : sfixed(SUM_BITS_C-1 downto 0);
      accumShift         : slv(3 downto 0);
      pidMultiplier      : sfixed(ACCUM_BITS_C-1 downto 0);
      pidCoef            : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      p                  : slv(COEF_BITS_C-1 downto 0);  -- sfixed(COEF_HIGH_C downto COEF_LOW_C);
      i                  : slv(COEF_BITS_C-1 downto 0);  -- sfixed(COEF_HIGH_C downto COEF_LOW_C);
      d                  : slv(COEF_BITS_C-1 downto 0);  -- sfixed(COEF_HIGH_C downto COEF_LOW_C);
      pidValid           : sl;
      pidResult          : sfixed(RESULT_HIGH_C downto RESULT_LOW_C);
      sq1Fb              : sfixed(13 downto 0);
      sq1FbValid         : sl;
      numFluxJumps       : slv(7 downto 0);
      fluxQuantum        : slv(13 downto 0);
      fluxJumpWrValid    : sl;
      clearRams          : sl;
      axilPidDebugEnable : sl;
      pidDebugEnable     : sl;
      pidDebugMaster     : AxiStreamMasterType;
      axilWriteSlave     : AxiLiteWriteSlaveType;
      axilReadSlave      : AxiLiteReadSlaveType;
   end record;

   constant REG_INIT_C : RegType := (
      fllEnable          => '0',
      state              => WAIT_ROW_STROBE_S,
      rowIndex           => (others => '0'),
      accumValid         => '0',
      accumError         => (others => '0'),
      lastAccum          => (others => '0'),
      sumAccum           => (others => '0'),
      accumShift         => toSlv(0, 4),
      pidMultiplier      => (others => '0'),
      pidCoef            => (others => '0'),
      p                  => (others => '0'),
      i                  => (others => '0'),
      d                  => (others => '0'),
      pidValid           => '0',
      pidResult          => (others => '0'),
      sq1Fb              => (others => '0'),
      sq1FbValid         => '0',
      numFluxJumps       => (others => '0'),
      fluxQuantum        => (others => '0'),
      fluxJumpWrValid    => '0',
      clearRams          => '0',
      axilPidDebugEnable => '0',
      pidDebugEnable     => '0',
      pidDebugMaster     => axiStreamMasterInit(AXIS_DEBUG_CFG_C),
      axilWriteSlave     => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave      => AXI_LITE_READ_SLAVE_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal adcBaselineRamOut : slv(15 downto 0);
   signal accumRamOut       : slv(ACCUM_BITS_C-1 downto 0);
   signal sumRamOut         : slv(SUM_BITS_C-1 downto 0);
   signal pidRamOut         : slv(RESULT_BITS_C-1 downto 0);
   signal fluxJumpRamOut    : slv(7 downto 0);

   signal accumError : slv(ACCUM_BITS_C-1 downto 0);
   signal sumAccum   : slv(SUM_BITS_C-1 downto 0);
   signal pidResult  : slv(RESULT_BITS_C-1 downto 0);

   signal pidStreamMaster    : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal filterStreamMaster : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;

   signal pidDebugCtrl : AxiStreamCtrlType;

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

   signal fifoDout  : slv(21 downto 0);
   signal fifoValid : sl;
   signal ack       : AxiLiteAckType;

   -------------------------------------------------------------------------------------------------
   -- Convert DAC format to 2s complement and back
   -------------------------------------------------------------------------------------------------
   function convInvOffsetBin (
      vec : slv(13 downto 0))
      return slv is
      variable ret : slv(13 downto 0);
   begin
      ret(13)          := vec(13);
      ret(12 downto 0) := not vec(12 downto 0);
      return ret;
   end function convInvOffsetBin;

   signal sq1fbInvOffsetBin : slv(13 downto 0);



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
         ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
         DATA_WIDTH_G     => adcBaselineRamOut'length)
      port map (
         axiClk         => timingRxClk125,                       -- [in]
         axiRst         => timingRxRst125,                       -- [in]
         axiReadMaster  => locAxilReadMasters(ADC_BASELINE_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(ADC_BASELINE_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(ADC_BASELINE_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(ADC_BASELINE_C),   -- [out]
         clk            => timingRxClk125,                       -- [in]
         rst            => timingRxRst125,                       -- [in]
         addr           => r.rowIndex,                           -- [in]
         dout           => adcBaselineRamOut);                   -- [out]

   U_AxiDualPortRam_FLUX_JUMP : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 1,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
         DATA_WIDTH_G     => 8)
      port map (
         axiClk         => timingRxClk125,                    -- [in]
         axiRst         => timingRxRst125,                    -- [in]
         axiReadMaster  => locAxilReadMasters(FLUX_JUMP_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(FLUX_JUMP_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(FLUX_JUMP_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(FLUX_JUMP_C),   -- [out]
         clk            => timingRxClk125,                    -- [in]
         rst            => timingRxRst125,                    -- [in]
         addr           => r.rowIndex,                        -- [in]
         dout           => fluxJumpRamOut,                    -- [out]
         we             => r.fluxJumpWrValid,                 -- [in]
         din            => r.numFluxJumps);                   -- [in]


   accumError <= slv(r.accumError);
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
         ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
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
         addr           => r.rowIndex,                          -- [in]         
         we             => r.accumValid,                        -- [in]
         din            => accumError,                          -- [in]
         dout           => accumRamOut);                        -- [in]


   sumAccum <= slv(r.sumAccum);
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
         ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
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
         addr           => r.rowIndex,                        -- [in]         
         we             => r.pidValid,                        -- [in]
         din            => sumAccum,                          -- [in]
         dout           => sumRamOut);                        -- [in]   

   pidResult <= to_slv(r.pidResult);
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
         ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
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
         addr           => r.rowIndex,                          -- [in]         
         we             => r.pidValid,                          -- [in]
         din            => pidResult,                           -- [in]
         dout           => pidRamOut);                          -- [in]

   -- PID results streamed through and FIR filter
   U_FirFilterMultiChannel_1 : entity surf.FirFilterMultiChannel
      generic map (
         TPD_G          => TPD_G,
         NUM_TAPS_G     => 11,
         NUM_CHANNELS_G => 256,
         PARALLEL_G     => 1,
         DATA_WIDTH_G   => 14,                                   --RESULT_BITS_C,
         COEFF_WIDTH_G  => 8,
         COEFFICIENTS_G => FILTER_COEFFICIENTS_C,
         MEMORY_TYPE_G  => "block",
         SYNTH_MODE_G   => "xpm")
      port map (
         axisClk         => timingRxClk125,                      -- [in]
         axisRst         => timingRxRst125,                      -- [in]
         sAxisMaster     => pidStreamMaster,                     -- [in]
         sAxisSlave      => open,                                -- [out]
         mAxisMaster     => filterStreamMaster,                  -- [out]
         mAxisSlave      => AXI_STREAM_SLAVE_FORCE_C,            -- [in]
         axilClk         => timingRxClk125,                      -- [in]
         axilRst         => timingRxRst125,                      -- [in]
         axilReadMaster  => locAxilReadMasters(FILTER_COEF_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(FILTER_COEF_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(FILTER_COEF_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(FILTER_COEF_C));  -- [out]

   -- FIR filter results streamed into an AXIL RAM
   U_AxiDualPortRam_FILTER_RESULTS : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "block",
         READ_LATENCY_G   => 3,
         AXI_WR_EN_G      => false,
         SYS_WR_EN_G      => true,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
         DATA_WIDTH_G     => RESULT_BITS_C)
      port map (
         axiClk         => timingRxClk125,                                      -- [in]
         axiRst         => timingRxRst125,                                      -- [in]
         axiReadMaster  => locAxilReadMasters(FILTER_RESULTS_C),                -- [in]
         axiReadSlave   => locAxilReadSlaves(FILTER_RESULTS_C),                 -- [out]
         axiWriteMaster => locAxilWriteMasters(FILTER_RESULTS_C),               -- [in]
         axiWriteSlave  => locAxilWriteSlaves(FILTER_RESULTS_C),                -- [out]
         clk            => timingRxClk125,                                      -- [in]
         rst            => timingRxRst125,                                      -- [in]
         addr           => filterStreamMaster.tDest(7 downto 0),                -- [in]         
         we             => filterStreamMaster.tValid,                           -- [in]
         din            => filterStreamMaster.tData(RESULT_BITS_C-1 downto 0),  -- [in]
         dout           => open);                                               -- [in]

   comb : process (accumRamOut, adcAxisMaster, adcBaselineRamOut, fluxJumpRamOut, pidDebugCtrl, r,
                   sumRamOut, timingAxilReadMaster, timingAxilWriteMaster, timingRxRst125) is
      variable v                 : RegType;
      variable sq1FbSlv          : slv(13 downto 0);
      variable adcValueSfixed    : sfixed(13 downto 0);
      variable adcBaselineSfixed : sfixed(13 downto 0);
      variable pSfixed           : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      variable iSfixed           : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      variable dSfixed           : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      variable fluxQuantumFixed  : sfixed(13 downto 0);
      variable numFluxJumpsFixed : sfixed(7 downto 0);
      variable axilEp            : AxiLiteEndpointType;

   begin
      v := r;

      -- Rams clear on clock reset or axil command
      v.clearRams := timingRxRst125;

      ----------------------------------------------------------------------------------------------
      -- AXI Lite Registers
      ----------------------------------------------------------------------------------------------
      axiSlaveWaitTxn(axilEp, timingAxilWriteMaster, timingAxilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.fllEnable);
      axiSlaveRegister(axilEp, X"00", 16, v.accumShift);
      axiSlaveRegister(axilEp, X"04", 0, v.p);
      axiSlaveRegister(axilEp, X"08", 0, v.i);
      axiSlaveRegister(axilEp, X"0c", 0, v.d);

      axiSlaveRegister(axilEp, X"40", 0, v.fluxQuantum);
      axiSlaveRegisterR(axilEp, X"44", 0, r.numFluxJumps);

      axiSlaveRegister(axilEp, X"50", 0, v.axilPidDebugEnable);

      axiSlaveRegisterR(axilEp, X"10", 0, to_slv(r.accumError));
      axiSlaveRegisterR(axilEp, X"14", 0, to_slv(r.lastAccum));
      axiSlaveRegisterR(axilEp, X"18", 0, to_slv(r.sumAccum));
      axiSlaveRegisterR(axilEp, X"20", 0, to_slv(r.pidResult));
      axiSlaveRegisterR(axilEp, X"28", 0, to_slv(r.sq1Fb));


      axiSlaveRegister(axilEp, X"30", 0, v.clearRams);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      ----------------------------------------------------------------------------------------------

      v.accumValid      := '0';
      v.pidValid        := '0';
      v.sq1FbValid      := '0';
      v.fluxJumpWrValid := '0';

      v.pidDebugMaster       := axiStreamMasterInit(AXIS_DEBUG_CFG_C);
      v.pidDebugMaster.tDest := toSlv(8, 8);

      adcValueSfixed    := to_sfixed(adcAxisMaster.tData(15 downto 2), adcValueSFixed);
      adcBaselineSfixed := to_sfixed(adcBaselineRamOut(15 downto 2), adcBaselineSFixed);
      pSfixed           := to_sfixed(r.p, pSfixed);
      iSfixed           := to_sfixed(r.i, iSfixed);
      dSfixed           := to_sfixed(r.d, dSfixed);
      fluxQuantumFixed  := to_sfixed(r.fluxQuantum, fluxQuantumFixed);
      numFluxJumpsFixed := to_sfixed(r.numFluxJumps, numFluxJumpsFixed);

      if (r.fllEnable = '1') then
         case r.state is
            when WAIT_ROW_STROBE_S =>
               -- Watch pidDebugPuase while we wait
               v.pidDebugEnable := not pidDebugCtrl.pause and r.axilPidDebugEnable;

               -- Row strobe comes first (bit 26).
               -- Register the rowIndex (23:16) and reset accumulated error
               if (adcAxisMaster.tUser(2) = '1') then
                  v.rowIndex   := adcAxisMaster.tId(7 downto 0);
                  v.accumError := (others => '0');

                  -- First word is Column number
                  ssiSetUserSof(AXIS_DEBUG_CFG_C, v.pidDebugMaster, '1');
                  v.pidDebugMaster.tValid             := v.pidDebugEnable;
                  v.pidDebugMaster.tData(3 downto 0)  := toSlv(COLUMN_NUM_G, 4);
                  v.pidDebugMaster.tData(15 downto 8) := v.rowIndex;
                  v.state                             := WAIT_FIRST_SAMPLE_S;
               end if;


            when WAIT_FIRST_SAMPLE_S =>
               -- Activate and deactivate the accumulator
               -- RAMs have a 3 cycle latency so this needs to happen at least 3 cycles after row strobe
               -- In practice it will always be much longer than 3 cycles
               if (adcAxisMaster.tUser(0) = '1') then
                  -- Second word is baseline
                  v.pidDebugMaster.tValid             := r.pidDebugEnable;
                  v.pidDebugMaster.tData(31 downto 0) := resize(adcBaselineRamOut, 32);
                  v.state                             := ACCUMULATE_S;
               end if;

            when ACCUMULATE_S =>
               v.accumError := resize((adcValueSfixed - adcBaselineSfixed) + v.accumError, v.accumError);

               if (adcAxisMaster.tUser(1) = '1') then
                  v.state := PREP_PID_S;
               end if;

            when PREP_PID_S =>
               -- Write the accumError from last stage into ram
               v.accumValid   := '1';
               -- Register values from RAM for PID calculation
               v.lastAccum    := to_sfixed(accumRamOut, r.lastAccum);
               v.sumAccum     := to_sfixed(sumRamOut, r.sumAccum);
               v.numFluxJumps := fluxJumpRamOut;
               -- Register current sq1FB here
               -- Invert LSB to convert inverted offset binary to 2-s complement
               -- Store in sfixed type register
               v.sq1FB        := to_sfixed(convInvOffsetBin(adcAxisMaster.tData(29 downto 16)), r.sq1FB);

               -- Third word is accum error
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0) := resize(to_slv(r.accumError), 32);

               -- Prep for P stage
               v.pidCoef       := pSfixed;
               v.pidMultiplier := r.accumError;     -- Prep accumError for P stage
               v.pidResult     := (others => '0');  -- Clear pid result
               v.state         := PID_PRESHIFT_S;

            when PID_PRESHIFT_S =>
               v.pidMultiplier := shift_right(r.pidMultiplier, to_integer(unsigned(r.accumShift)));
               v.state         := PID_P_S;

            when PID_P_S =>
               -- Fourth Word is starting SQ1FB
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(13 downto 0) := resize(convInvOffsetBin(to_slv(r.sq1FB)), 14);

               -- Calcualte PID Stage
               v.pidResult     := resize(r.pidResult + (r.pidCoef * r.pidMultiplier), v.pidResult);  -- r.accumError;
               -- Prep for I Stage
               v.pidCoef       := iSfixed;
               v.pidMultiplier := r.sumAccum;
               v.state         := PID_I_S;

            when PID_I_S =>
               -- Fifth Word is SumAccum
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0) := resize(to_slv(r.pidMultiplier), 32);

               -- Calculate PID stage
               v.pidResult     := resize(r.pidResult + (r.pidCoef * r.pidMultiplier), v.pidResult);  -- r.sumAccum
               -- Prep for D stage
               v.pidCoef       := dSfixed;
               v.pidMultiplier := resize(r.lastAccum - r.accumError, v.pidMultiplier);  -- Prep for D stage
               v.state         := PID_D_S;

            when PID_D_S =>
               -- Sixth Word is diff multiplier result
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(31 downto 0) := resize(to_slv(r.pidMultiplier), 32);


               -- Calculate PID Stage
               v.pidResult := resize(r.pidResult + (r.pidCoef * r.pidMultiplier), v.pidResult);
               v.sumAccum  := resize(r.sumAccum + r.accumError, v.sumAccum);
               v.pidValid  := '1';
               v.state     := SQ1FB_ADJUST_S;

            when SQ1FB_ADJUST_S =>
               -- Seventh Word is PID result
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(63 downto 0) := resize(to_slv(r.pidResult), 64);

               v.sq1Fb := resize(r.sq1Fb + r.pidResult, v.sq1Fb);
               v.state := FLUX_JUMP_S;

            when FLUX_JUMP_S =>
               if (r.sq1Fb > 7862) then
                  v.sq1Fb           := resize(r.sq1Fb - fluxQuantumFixed, v.sq1Fb);
                  numFluxJumpsFixed := resize(numFluxJumpsFixed + 1, numFluxJumpsFixed);
               elsif (r.sq1Fb < -7862) then
                  v.sq1Fb           := resize(r.sq1Fb + fluxQuantumFixed, v.sq1Fb);
                  numFluxJumpsFixed := resize(numFluxJumpsFixed - 1, numFluxJumpsFixed);
               end if;

               v.numFluxJumps    := to_slv(numFluxJumpsFixed);
               v.fluxJumpWrValid := '1';
               v.sq1FbValid      := '1';

               v.state := FLUX_DEBUG_S;

            when FLUX_DEBUG_S =>
               v.pidDebugMaster.tValid            := r.pidDebugEnable;
               v.pidDebugMaster.tData(7 downto 0) := resize(to_slv(r.numFluxJumps), 8);

               v.state := LOOP_DONE_S;

            when LOOP_DONE_S =>
               -- Ninth word is new sq1Fb
               v.pidDebugMaster.tValid             := r.pidDebugEnable;
               v.pidDebugMaster.tData(13 downto 0) := resize(convInvOffsetBin(to_slv(r.sq1Fb)), 14);
               v.pidDebugMaster.tLast              := '1';

               v.state := WAIT_ROW_STROBE_S;

         end case;
      end if;

      if (timingRxRst125 = '1') then
         v := REG_INIT_C;
      end if;


      rin <= v;

      pidStreamMaster.tValid                            <= r.sq1FbValid;
      pidStreamMaster.tData(13 downto 0)                <= to_slv(r.sq1Fb);
      pidStreamMaster.tId(ROW_ADDR_BITS_C-1 downto 0) <= r.rowIndex;

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
   U_AxiStreamFifoV2_PID_DEBUG : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 0,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => false,
         VALID_THOLD_G       => 0,
         VALID_BURST_MODE_G  => true,
         FIFO_PAUSE_THRESH_G => 15,
         GEN_SYNC_FIFO_G     => false,
         FIFO_ADDR_WIDTH_G   => 5,
         SYNTH_MODE_G        => "xpm",
         MEMORY_TYPE_G       => "distributed",
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

   U_AxiStreamFifoV2_DATA : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 0,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => false,
         VALID_THOLD_G       => 0,
         VALID_BURST_MODE_G  => true,
         FIFO_PAUSE_THRESH_G => 15,
         GEN_SYNC_FIFO_G     => false,
         FIFO_ADDR_WIDTH_G   => 5,
         SYNTH_MODE_G        => "xpm",
         MEMORY_TYPE_G       => "distributed",
         INT_WIDTH_SELECT_G  => "WIDE",
         SLAVE_AXI_CONFIG_G  => AXIS_DATA_CFG_C,
         MASTER_AXI_CONFIG_G => SQ1FB_DATA_AXIS_CONFIG_C)
      port map (
         sAxisClk    => timingRxClk125,      -- [in]
         sAxisRst    => timingRxRst125,      -- [in]
         sAxisMaster => pidStreamMaster,  -- [in]
         sAxisSlave  => open,                -- [out]
         sAxisCtrl   => open,        -- [out]
         mAxisClk    => axisClk,             -- [in]
         mAxisRst    => axisRst,             -- [in]
         mAxisMaster => dataMaster,      -- [out]
         mAxisSlave  => dataSlave);      -- [in]



   -------------------------------------------------------------------------------------------------
   -- sq1Fb Updates written to fifo
   -- Convert back to inverted offsset binary first
   -------------------------------------------------------------------------------------------------
   sq1fbInvOffsetBin <= convInvOffsetBin(to_slv(r.sq1Fb));

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
         rst               => timingRxRst125,     -- [in]
         wr_clk            => timingRxClk125,     -- [in]
         wr_en             => r.sq1FbValid,       -- [in]
         din(13 downto 0)  => sq1fbInvOffsetBin,  -- [in]
         din(21 downto 14) => r.rowIndex,         -- [in]
         overflow          => open,               -- [out]
         rd_clk            => timingRxClk125,     -- [in]
         rd_en             => axilR.fifoRd,       -- [in]
         dout              => fifoDout,           -- [out]
         valid             => fifoValid);         -- [out]

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
