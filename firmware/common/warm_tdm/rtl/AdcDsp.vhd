library ieee;
use ieee.std_logic_1164.all;
use ieee.fixed_pkg.all;

library unisim;
use unisim.vcomponents.all;



library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity AdcDsp is

   generic (
      TPD_G            : time             := 1 ns;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := (others => '0'));

   port (
      -- Timing interface
      timingRxClk125   : in  sl;
      timingRxRst125   : in  sl;
      timingRxData     : in  LocalTimingType;
      -- Incomming ADC Stream
      adcAxisMaster    : in  AxiStreamMasterType;
      -- AXI-Lite
      axilClk          : in  sl;
      axilRst          : in  sl;
      -- Local register access      
      sAxilReadMaster  : in  AxiLiteReadMasterType;
      sAxilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      sAxilWriteMaster : in  AxiLiteWriteMasterType;
      sAxilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      -- DAC RAM updates
      mAxilReadMaster  : out AxiLiteReadMasterType;
      mAxilReadSlave   : in  AxiLiteReadSlaveType;
      mAxilWriteMaster : out AxiLiteWriteMasterType;
      mAxilWriteSlave  : in  AxiLiteWriteSlaveType);

end entity;

architecture rtl of AdcDsp is

   constant ROW_ADDR_BITS_C : integer := 8;

   constant NUM_AXIL_MASTERS_C : integer := 7;
   constant LOCAL_C            : integer := 0;
   constant ADC_BASELINE_C     : integer := 1;
   constant ACCUM_ERROR_C      : integer := 2;
   constant SUM_ACCUM_C        : integer := 3;
   constant PID_RESULTS_C      : integer := 4;
   constant FILTER_RESULTS_C   : integer := 5;
   constant FILTER_COEF_C      : integer := 6;

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
   constant COEF_HIGH_C  : integer := 1;
   constant COEF_LOW_C   : integer := -8;
   constant COEF_BITS_C  : integer := COEF_HIGH_C - COEF_LOW_C + 1;

   constant SUM_BITS_C    : integer := ACCUM_BITS_C;
   constant RESULT_HIGH_C : integer := 26;
   constant RESULT_LOW_C  : integer := -8;
   constant RESULT_BITS_C : integer := RESULT_HIGH_C - RESULT_LOW_C + 1;

   constant FILTER_COEFFICIENTS_C : IntegerArray(0 to 10) := (5 => 2**15-1, others => 0);

   type StateType is (WAIT_ROW_STROBE_S, WAIT_FIRST_SAMPLE_S, ACCUMULATE_S, PREP_PID_S, PID_P_S, PID_I_S, PID_D_S, SQ1FB_ADJUST_S);

   type RegType is record
      state      : StateType;
      accumValid : sl;
      rowIndex   : slv(ROW_ADDR_BITS_C-1 downto 0);
      accumError : sfixed(ACCUM_BITS_C-1 downto 0);
      p          : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      i          : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      d          : sfixed(COEF_HIGH_C downto COEF_LOW_C);
      lastAccum  : sfixed(ACCUM_BITS_C-1 downto 0);
      pidValid   : sl;
      sumAccum   : sfixed(SUM_BITS_C-1 downto 0);
      pidResult  : sfixed(RESULT_BITS_C-1 downto 0);
      sq1Fb      : sfixed(13 downto 0);
      sq1FbValid : sl;
   end record;

   constant REG_INIT_C : RegType := (
      state      => WAIT_ROW_STROBE_S;
      accumValid => '0',
      accumError => (others => '0'),
      rowIndex   => (others => '0'),
      p          => (others => '0'),
      i          => (others => '0'),
      d          => (others => '0'),
      lastAccum  => (others => '0'),
      pidValid   => '0',
      sumAccum   => (others => '0'),
      pidResult  => (others => '0'),
      sq1Fb      => (others => '0'),
      sq1FbValid => '0');

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal adcBaselineRamOut : slv(15 downto 0);
   signal accumRamOut       : slv(ACCUM_BITS_C-1 downto 0);
   signal sumRamOut         : slv(SUM_BITS_C-1 downto 0);
   signal pidRamOut         : slv(RESULT_BITS_C-1 downto 0);

   signal accumError : slv(ACCUM_BITS_C-1 downto 0);
   signal sumAccum   : slv(SUM_BITS_C-1 downto 0);
   signal pidResult  : slv(RESULT_BITS_C-1 downto 0);

   signal pidStreamMaster    : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal filterStreamMaster : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;

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

   signal fifoDout : slv(23 downto 0);
   signal ack      : AxiLiteAckType;


begin

   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => XBAR_CONFIG_C,
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
         TPD_G            => TPD_G,
         RST_ASYNC_G      => RST_ASYNC_G,
         AXI_ERROR_RESP_G => AXI_ERROR_RESP_G,
         COMMON_CLK_G     => COMMON_CLK_G,
         NUM_ADDR_BITS_G  => NUM_ADDR_BITS_G,
         PIPE_STAGES_G    => PIPE_STAGES_G)
      port map (
         sAxiClk         => axilClk,                       -- [in]
         sAxiClkRst      => axilClkRst,                    -- [in]
         sAxiReadMaster  => locAxilReadMasters(LOCAL_C),   -- [in]
         sAxiReadSlave   => locAxilReadSlaves(LOCAL_C),    -- [out]
         sAxiWriteMaster => locAxilWriteMasters(LOCAL_C),  -- [in]
         sAxiWriteSlave  => locAxilWriteSlaves(LOCAL_C),   -- [out]
         mAxiClk         => timingRxClk125,                -- [in]
         mAxiClkRst      => timingRxRst125,                -- [in]
         mAxiReadMaster  => timingAxilReadMaster,          -- [out]
         mAxiReadSlave   => timingAxilReadSlave,           -- [in]
         mAxiWriteMaster => timingAxilWriteMaster,         -- [out]
         mAxiWriteSlave  => timingAxilWriteSlave);         -- [in]

   -- RAM for ADC Baselines
   U_AxiDualPortRam_ADC_BASELINE : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
         DATA_WIDTH_G     => adcBaselineRamOut'length)
      port map (
         axiClk         => axilClk,                              -- [in]
         axiRst         => axilRst,                              -- [in]
         axiReadMaster  => locAxilReadMasters(ADC_BASELINE_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(ADC_BASELINE_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(ADC_BASELINE_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(ADC_BASELINE_C),   -- [out]
         clk            => timingRxClk125,                       -- [in]
         rst            => timingRxRst125,                       -- [in]
         addr           => timingRxData.rowIndex,                -- [in]
         dout           => adcBaselineRamOut);                   -- [out]

   accumError <= slv(r.accumError);
   U_AxiDualPortRam_ACCUM_ERROR : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => false,
         SYS_WR_EN_G      => true,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
         DATA_WIDTH_G     => ACCUM_BITS_C)
      port map (
         axiClk         => axilClk,                             -- [in]
         axiRst         => axilRst,                             -- [in]
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

--    U_AxiDualPortRam_P_TERMS : entity surf.AxiDualPortRam
--       generic map (
--          TPD_G            => TPD_G,
--          SYNTH_MODE_G     => "inferred",
--          MEMORY_TYPE_G    => "distributed",
--          READ_LATENCY_G   => 0,
--          AXI_WR_EN_G      => true,
--          SYS_WR_EN_G      => false,
--          SYS_BYTE_WR_EN_G => false,
--          COMMON_CLK_G     => false,
--          ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
--          DATA_WIDTH_G     => COEF_BITS_C,
--          INIT_G           => X"010")
--       port map (
--          axiClk         => axilClk,                         -- [in]
--          axiRst         => axilRst,                         -- [in]
--          axiReadMaster  => locAxilReadMasters(P_TERMS_C),   -- [in]
--          axiReadSlave   => locAxilReadSlaves(P_TERMS_C),    -- [out]
--          axiWriteMaster => locAxilWriteMasters(P_TERMS_C),  -- [in]
--          axiWriteSlave  => locAxilWriteSlaves(P_TERMS_C),   -- [out]
--          clk            => timingRxClk125,                  -- [in]
--          rst            => timingRxRst125,                  -- [in]
--          addr           => r.rowIndex,                 -- [in]         
--          dout           => pRamOut);                        -- [in]

--    U_AxiDualPortRam_I_TERMS : entity surf.AxiDualPortRam
--       generic map (
--          TPD_G            => TPD_G,
--          SYNTH_MODE_G     => "inferred",
--          MEMORY_TYPE_G    => "distributed",
--          READ_LATENCY_G   => 0,
--          AXI_WR_EN_G      => true,
--          SYS_WR_EN_G      => false,
--          SYS_BYTE_WR_EN_G => false,
--          COMMON_CLK_G     => false,
--          ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
--          DATA_WIDTH_G     => COEF_BITS_C,
--          INIT_G           => X"008")
--       port map (
--          axiClk         => axilClk,                         -- [in]
--          axiRst         => axilRst,                         -- [in]
--          axiReadMaster  => locAxilReadMasters(I_TERMS_C),   -- [in]
--          axiReadSlave   => locAxilReadSlaves(I_TERMS_C),    -- [out]
--          axiWriteMaster => locAxilWriteMasters(I_TERMS_C),  -- [in]
--          axiWriteSlave  => locAxilWriteSlaves(I_TERMS_C),   -- [out]
--          clk            => timingRxClk125,                  -- [in]
--          rst            => timingRxRst125,                  -- [in]
--          addr           => r.rowIndex,                 -- [in]         
--          dout           => iRamOut);                        -- [in]

--    U_AxiDualPortRam_D_TERMS : entity surf.AxiDualPortRam
--       generic map (
--          TPD_G            => TPD_G,
--          SYNTH_MODE_G     => "inferred",
--          MEMORY_TYPE_G    => "distributed",
--          READ_LATENCY_G   => 0,
--          AXI_WR_EN_G      => true,
--          SYS_WR_EN_G      => false,
--          SYS_BYTE_WR_EN_G => false,
--          COMMON_CLK_G     => false,
--          ADDR_WIDTH_G     => ROW_ADDR_BITS_C,
--          DATA_WIDTH_G     => COEF_BITS_C,
--          INIT_G           => X"004")
--       port map (
--          axiClk         => axilClk,                         -- [in]
--          axiRst         => axilRst,                         -- [in]
--          axiReadMaster  => locAxilReadMasters(D_TERMS_C),   -- [in]
--          axiReadSlave   => locAxilReadSlaves(D_TERMS_C),    -- [out]
--          axiWriteMaster => locAxilWriteMasters(D_TERMS_C),  -- [in]
--          axiWriteSlave  => locAxilWriteSlaves(D_TERMS_C),   -- [out]
--          clk            => timingRxClk125,                  -- [in]
--          rst            => timingRxRst125,                  -- [in]
--          addr           => r.rowIndex,                 -- [in]         
--          dout           => dRamOut);                        -- [in]

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
         axiClk         => axilClk,                           -- [in]
         axiRst         => axilRst,                           -- [in]
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

   pidResult <= slv(r.pidResult);
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
         axiClk         => axilClk,                             -- [in]
         axiRst         => axilRst,                             -- [in]
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
         DATA_WIDTH_G   => 16,                                   --RESULT_BITS_C,
         COEFF_WIDTH_G  => 16,
         COEFFICIENTS_G => FILTER_COEFFICIENTS_C,
         MEMORY_TYPE_G  => "distributed",
         SYNTH_MODE_G   => "xpm")
      port map (
         axisClk         => timingRxClk125,                      -- [in]
         axisRst         => timingRxRst125,                      -- [in]
         sAxisMaster     => pidStreamMaster,                     -- [in]
         sAxisSlave      => open,                                -- [out]
         mAxisMaster     => filterStreamMaster,                  -- [out]
         mAxisSlave      => AXI_STREAM_SLAVE_FORCE_C,            -- [in]
         axilClk         => axilClk,                             -- [in]
         axilRst         => axilRst,                             -- [in]
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
         axiClk         => axilClk,                                             -- [in]
         axiRst         => axilRst,                                             -- [in]
         axiReadMaster  => locAxilReadMasters(FILTER_RESULTS_C),                -- [in]
         axiReadSlave   => locAxilReadSlaves(FILTER_RESULTS_C),                 -- [out]
         axiWriteMaster => locAxilWriteMasters(FILTER_RESULTS_C),               -- [in]
         axiWriteSlave  => locAxilWriteSlaves(FILTER_RESULTS_C),                -- [out]
         clk            => timingRxClk125,                                      -- [in]
         rst            => timingRxRst125,                                      -- [in]
         addr           => r.rowIndex,                                          -- [in]         
         we             => filterStreamMaster.tValid,                           -- [in]
         din            => filterStreamMaster.tData(RESULT_BITS_C-1 downto 0),  -- [in]
         dout           => open);                                               -- [in]

   comb : process (accumRamOut, adcAxisMaster, adcBaselineRamOut, r, sumRamOut,
                   timingAxilReadMaster, timingAxilWriteMaster, timingRxRst125) is
      variable v                 : RegType;
      variable adcValueSfixed    : sfixed(13 downto 0);
      variable adcBaselineSfixed : sfixed(13 downto 0);
      variable axilEp            : AxiLiteEndpointType;
   begin
      v := r;

      ----------------------------------------------------------------------------------------------
      -- AXI Lite Registers
      ----------------------------------------------------------------------------------------------
      axiSlaveWaitTxn(axilEp, timingAxilWriteMaster, timingAxilReadMaster, v.axiWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.p);
      axiSlaveRegister(axilEp, X"04", 0, v.i);
      axiSlaveRegister(axilEp, X"08", 0, v.d);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      ----------------------------------------------------------------------------------------------

      v.accumValid := '0';
      v.pidValid   := '0';
      v.sq1FbValid := '0';

      adcValueSfixed    := to_sfixed(adcAxisMaster.tData(15 downto 2), adcValueSFixed);
      adcBaselineSfixed := to_sfixed(adcBaselineRamOut(15 downto 2), adcBaselineSFixed);


      case r.state is
         when WAIT_ROW_STROBE_S =>
            -- Row strobe comes first.
            -- Register the rowIndex and reset accumulated error
            if (adcAxisMaster.tData(26) = '1') then
               v.rowIndex   := adcAxisMaster.tData(23 downto 16);
               v.accumError := (others => '0');
               v.state      := WAIT_FIRST_SAMPLE_S;
            end if;

         when WAIT_FIRST_SAMPLE_S =>
            -- Activate and deactivate the accumulator
            if (adcAxisMaster.tdata(24) = '1') then
               v.date := ACCUMULATE_S;
            end if;

         when ACCUMULATE_S =>
            v.accumError := (adcValueSfixed - adcBaselineSfixed) + v.accumError;

            if (adcAxisMaster.tdata(25) = '1') then
               v.state := PREP_PID_S;
            end if;

         when PREP_PID_S =>
            v.accumValid := '1';
            -- Register values from RAM for PID calculation
            v.lastAccum  := to_sfixed(accumRamOut, r.lastAccum);
            v.sumAccum   := to_sfixed(sumRamOut, r.sumAccum);
            -- Register current sq1FB here
            v.sq1FB      := to_sfixed(adcAxisMaster.tData(37 downto 24), r.sq1FB);
            v.state      := PID_P_S;

         when PID_P_S =>
            v.pidResult := r.p * r.accumError;
            v.state     := PID_I_S;

         when PID_I_S =>
            v.pidResult := r.pidResult + (r.i * r.sumAccum);
            v.state     := PID_D_S;

         when PID_D_S =>
            v.pidResult := r.pidResult + (r.d * (r.lastAccum-r.accumError));
            v.sumAccum  := r.sumAccum + r.accumError;
            v.pidValid  := '1';
            v.state     := SQ1FB_ADJUST_S;

         when SQ1FB_ADJUST_S =>
            v.sq1Fb      := r.sq1Fb + r.pidResult;
            v.sq1FbValid := '1';
            v.state      := WAIT_ROW_STROBE_S;

      end case;



      if (timingRxRst125 = '1') then
         v := REG_INIT_C;
      end if;


      rin <= v;

      pidStreamMaster.tValid             <= r.sq1FbValid;
      pidStreamMaster.tData(15 downto 0) <= r.sq1Fb(31 downto 16);

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
   -- sq1Fb Updates written to fifo
   -------------------------------------------------------------------------------------------------
   U_Fifo_1 : entity surf.Fifo
      generic map (
         TPD_G           => TPD_G,
         GEN_SYNC_FIFO_G => false,
         FWFT_EN_G       => true,
         SYNTH_MODE_G    => "xpm",
         MEMORY_TYPE_G   => "distributed",
         PIPE_STAGES_G   => 0,
         DATA_WIDTH_G    => 24,
         ADDR_WIDTH_G    => 4)
      port map (
         rst               => axilRst,         -- [in]
         wr_clk            => timingRxClk125,  -- [in]
         wr_en             => r.sq1FbValid,    -- [in]
         din(15 downto 0)  => r.sq1Fb,         -- [in]
         din(23 downto 16) => r.rowIndex,      -- [in]
         overflow          => fifoOverflow,    -- [out]
         rd_clk            => axilClk,         -- [in]
         rd_en             => axilR.fifoRd,    -- [in]
         dout              => fifoDout,        -- [out]
         valid             => fifoValid);      -- [out]

   U_AxiLiteMaster_1 : entity surf.AxiLiteMaster
      generic map (
         TPD_G       => TPD_G,
         RST_ASYNC_G => RST_ASYNC_G)
      port map (
         axilClk         => axilClk,           -- [in]
         axilRst         => axilRst,           -- [in]
         req             => axilR.req,         -- [in]
         ack             => ack,               -- [out]
         axilWriteMaster => mAxilWriteMaster,  -- [out]
         axilWriteSlave  => mAxilWriteSlave,   -- [in]
         axilReadMaster  => mAxilReadMaster,   -- [out]
         axilReadSlave   => mAxilReadSlave);   -- [in]
   -- 
   axilComb : process (ack, axilR, axilRst, fifoDout) is
      variable v : AxilRegType := AXIL_REG_INIT_C;
   begin
      v := axilR;

      v.req.rnw := '0';
      v.fifoRd  := '0';

      if (fifoValid = '1' and ack.done = '1') then
         v.req.request := '1';
         v.req.address := DAC_RAM_ADDR_G(31 downto 10) & fifoDout(23 downto 16) & "00";
         v.req.wrData  := fifoDout(15 downto 0);
         v.fifoRd      := '1';
      end if;

      if (axilR.req.request = '1' and ack.done = '1') then
         v.req.request := '0';
      end if;

      if (axilRst = '1') then
         v := AXIL_REG_INIT_C;
      end if;

      axilRin <= v;


   end process axilComb;


   axilSeq : process (axilClk) is
   begin
      if (rising_edge(axilClk)) then
         axilR <= axilRin after TPD_G;
      end if;
   end process axilSeq;

end rtl;
