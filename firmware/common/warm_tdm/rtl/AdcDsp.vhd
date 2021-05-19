library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

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
      TPD_G            : time                    := 1 ns;
      AXIL_BASE_ADDR_G : slv(31 downto 0)        := (others => '0');
      NUM_ROWS_G       : integer range 2 to 1024 := 64);

   port (
      -- Timing interface
      timingRxClk125 : in sl;
      timingRxRst125 : in sl;
      timingRxData   : in LocalTimingType;
      -- Incomming ADC Stream
      adcAxisMaster  : in AxiStreamMasterType;

      -- Local register access
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);

end entity;

architecture rtl of AdcDsp is

   constant ROW_BITS_C : integer := log2(NUM_ROWS_G);

   constant NUM_AXIL_MASTERS_C : integer := 9;
   constant ADC_OFFSET_C       : integer := 0;
   constant ACCUM_ERROR_C      : integer := 1;
   constant SUM_ACCUM_C        : integer := 2;
   constant P_TERMS_C          : integer := 3;
   constant I_TERMS_C          : integer := 4;
   constant D_TERMS_C          : integer := 5;
   constant PID_RESULTS_C      : integer := 6;
   constant FILTER_RESULTS_C   : integer := 7;
   constant FILTER_COEF_C      : integer := 8;

   constant XBAR_CONFIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) :=
      genAxiLiteConfig(NUM_AXIL_MASTERS_C, AXIL_BASE_ADDR_G, 16, 12);

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);

   constant ACCUM_BITS_C  : integer := 16;
   constant COEF_BITS_C   : integer := 12;
   constant SUM_BITS_C    : integer := 18;
   constant RESULT_BITS_C : integer := 32;

   type RegType is record
      accumValid : sl;
      accumRow   : slv(ROW_BITS_C-1 downto 0);
      accumError : signed(ACCUM_BITS_C-1 downto 0);
      p          : signed(COEF_BITS_C-1 downto 0);
      i          : signed(COEF_BITS_C-1 downto 0);
      d          : signed(COEF_BITS_C-1 downto 0);
      lastAccum  : signed(ACCUM_BITS_C-1 downto 0);
      pidValid   : sl;
      sumAccum   : signed(SUM_BITS_C-1 downto 0);
      pidResult  : signed(RESULT_BITS_C-1 downto 0);
   end record;

   constant REG_INIT_C : RegType := (
      accumValid => '0',
      accumError => (others => '0'),
      accumRow   => (others => '0'),
      p          => (others => '0'),
      i          => (others => '0'),
      d          => (others => '0'),
      lastAccum  => (others => '0'),
      pidValid   => '0',
      sumAccum   => (others => '0'),
      pidResult  => (others => '0'));

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal adcOffsetRamOut : slv(15 downto 0);
   signal accumRamOut     : slv(ACCUM_BITS_C-1 downto 0);
   signal pRamOut         : slv(COEF_BITS_C-1 downto 0);
   signal iRamOut         : slv(COEF_BITS_C-1 downto 0);
   signal dRamOut         : slv(COEF_BITS_C-1 downto 0);
   signal sumRamOut       : slv(SUM_BITS_C-1 downto 0);
   signal pidRamOut       : slv(RESULT_BITS_C-1 downto 0);

   signal accumError : slv(ACCUM_BITS_C-1 downto 0);
   signal sumAccum   : slv(SUM_BITS_C-1 downto 0);
   signal pidResult  : slv(RESULT_BITS_C-1 downto 0);

   signal pidStreamMaster    : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal filterStreamMaster : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;

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

   -- RAM for ADC Offsets
   U_AxiDualPortRam_ADC_OFFSET : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => 6,                                -- 64 Rows
         DATA_WIDTH_G     => adcOffsetRamOut'length)
      port map (
         axiClk         => axilClk,                            -- [in]
         axiRst         => axilRst,                            -- [in]
         axiReadMaster  => locAxilReadMasters(ADC_OFFSET_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(ADC_OFFSET_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(ADC_OFFSET_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(ADC_OFFSET_C),   -- [out]
         clk            => timingRxClk125,                     -- [in]
         rst            => timingRxRst125,                     -- [in]
         addr           => timingRxData.rowNum(5 downto 0),    -- [in]
         dout           => adcOffsetRamOut);                   -- [out]

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
         ADDR_WIDTH_G     => ROW_BITS_C,                        -- 64 Rows
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
         addr           => r.accumRow,                          -- [in]         
         we             => r.accumValid,                        -- [in]
         din            => accumError,                          -- [in]
         dout           => accumRamOut);                        -- [in]

   U_AxiDualPortRam_P_TERMS : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => ROW_BITS_C,                    -- 64 Rows
         DATA_WIDTH_G     => COEF_BITS_C,
         INIT_G           => X"010")
      port map (
         axiClk         => axilClk,                         -- [in]
         axiRst         => axilRst,                         -- [in]
         axiReadMaster  => locAxilReadMasters(P_TERMS_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(P_TERMS_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(P_TERMS_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(P_TERMS_C),   -- [out]
         clk            => timingRxClk125,                  -- [in]
         rst            => timingRxRst125,                  -- [in]
         addr           => r.accumRow,                      -- [in]         
         dout           => pRamOut);                        -- [in]

   U_AxiDualPortRam_I_TERMS : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => ROW_BITS_C,                    -- 64 Rows
         DATA_WIDTH_G     => COEF_BITS_C,
         INIT_G           => X"008")
      port map (
         axiClk         => axilClk,                         -- [in]
         axiRst         => axilRst,                         -- [in]
         axiReadMaster  => locAxilReadMasters(I_TERMS_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(I_TERMS_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(I_TERMS_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(I_TERMS_C),   -- [out]
         clk            => timingRxClk125,                  -- [in]
         rst            => timingRxRst125,                  -- [in]
         addr           => r.accumRow,                      -- [in]         
         dout           => iRamOut);                        -- [in]

   U_AxiDualPortRam_D_TERMS : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => ROW_BITS_C,                    -- 64 Rows
         DATA_WIDTH_G     => COEF_BITS_C,
         INIT_G           => X"004")
      port map (
         axiClk         => axilClk,                         -- [in]
         axiRst         => axilRst,                         -- [in]
         axiReadMaster  => locAxilReadMasters(D_TERMS_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(D_TERMS_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(D_TERMS_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(D_TERMS_C),   -- [out]
         clk            => timingRxClk125,                  -- [in]
         rst            => timingRxRst125,                  -- [in]
         addr           => r.accumRow,                      -- [in]         
         dout           => dRamOut);                        -- [in]

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
         ADDR_WIDTH_G     => ROW_BITS_C,                      -- 64 Rows
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
         addr           => r.accumRow,                        -- [in]         
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
         ADDR_WIDTH_G     => ROW_BITS_C,                        -- 64 Rows
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
         addr           => r.accumRow,                          -- [in]         
         we             => r.pidValid,                          -- [in]
         din            => pidResult,                           -- [in]
         dout           => pidRamOut);                          -- [in]

   -- PID results streamed through and FIR filter
   U_FirFilterMultiChannel_1 : entity surf.FirFilterMultiChannel
      generic map (
         TPD_G         => TPD_G,
         TAP_SIZE_G    => 10,
         CH_SIZE_G     => NUM_ROWS_G,
         PARALLEL_G    => 1,
         WIDTH_G       => 16,                                    --RESULT_BITS_C,
         MEMORY_TYPE_G => "block",
         SYNTH_MODE_G  => "inferred")
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
         ADDR_WIDTH_G     => ROW_BITS_C,                                        -- 64 Rows
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
         addr           => r.accumRow,                                          -- [in]         
         we             => filterStreamMaster.tValid,                           -- [in]
         din            => filterStreamMaster.tData(RESULT_BITS_C-1 downto 0),  -- [in]
         dout           => open);                                               -- [in]

   comb : process (accumRamOut, adcAxisMaster, adcOffsetRamOut, dRamOut, iRamOut, pRamOut,
                   pidResult, r, sumRamOut, timingRxData, timingRxRst125) is
      variable v               : RegType;
      variable adcValueSigned  : signed(13 downto 0);
      variable adcOffsetSigned : signed(13 downto 0);
   begin
      v := r;

      v.accumValid := '0';
      v.pidValid   := '0';

      adcValueSigned  := signed(adcAxisMaster.tData(15 downto 2));
      adcOffsetSigned := signed(adcOffsetRamOut(15 downto 2));

      -- Add up the errors from all the samples
      -- rowNum may advance before calculation done, so save it in a register at start      
      if (timingRxData.sample = '1') then
         if timingRxData.firstSample = '1' then
            v.accumError := (others => '0');
            v.accumRow   := timingRxData.rowNum(5 downto 0);
         end if;
--         if adcAxisMaster.tValid = '1' then
         v.accumError := (adcValueSigned - adcOffsetSigned) + v.accumError;
--         end if;
      end if;

      -- Indicate new accumulated error value is ready
      if timingRxData.lastSample = '1' then
         v.accumValid := '1';

         -- Register values from RAM for PID calculation
         v.p         := signed(pRamOut);
         v.i         := signed(iRamOut);
         v.d         := signed(dRamOut);
         v.lastAccum := signed(accumRamOut);
         v.sumAccum  := signed(sumRamOut);

      end if;

      if (r.accumValid = '1') then
         v.pidResult := resize((r.p * r.accumError) + (r.i * r.sumAccum) + (r.d * (r.lastAccum-r.accumError)), RESULT_BITS_C);
         v.sumAccum  := r.sumAccum + r.accumError;
         v.pidValid  := '1';
      end if;


      if (timingRxRst125 = '1') then
         v := REG_INIT_C;
      end if;


      rin <= v;

      pidStreamMaster.tValid             <= r.pidValid;
      pidStreamMaster.tData(15 downto 0) <= pidResult(31 downto 16);

   end process;

   seq : process (timingRxClk125) is
   begin
      if (rising_edge(timingRxClk125)) then
         r <= rin after TPD_G;
      end if;
   end process;




end rtl;
