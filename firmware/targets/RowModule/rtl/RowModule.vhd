-------------------------------------------------------------------------------
-- Title      : Warm TDM Row Module
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Top level of RowModule 
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

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;

library warm_tdm;

entity RowModule is

   generic (
      TPD_G        : time    := 1 ns;
      SIMULATION_G : boolean := false;
      BUILD_INFO_G : BuildInfoType);

   port (
      -- Clocks
      gtRefClk0P : in sl;
      gtRefClk0N : in sl;
      gtRefClkP1 : in sl;
      gtRefClk1N : in sl;

      -- PGP Interface
      pgpTxP : out sl;
      pgpTxN : out sl;
      pgpRxP : in  sl;
      pgpRxN : in  sl;

      -- Timing Interface
--       timingRxP : in sl;
--       timingRxN : in sl;

      -- Generic SFP interfaces
--       sfp0TxP : out sl;
--       sfp0TxN : out sl;
--       sfp0RxP : in  sl;
--       sfp0RxN : in  sl;
--       sfp1TxP : out sl;
--       sfp1TxN : out sl;
--       sfp1RxP : in  sl;
--       sfp1RxN : in  sl;

      -- DAC Interfaces
      dacCsB      : out slv(11 downto 0);
      dacSdio     : out slv(11 downto 0);
      dacSdi2     : in  slv(11 downto 0);
      dacSclk     : out slv(11 downto 0);
      dacResetB   : out slv(11 downto 0) := (others => '1');
      dacTriggerB : out slv(11 downto 0) := (others => '1');
      dacClkP     : out slv(11 downto 0);
      dacClkN     : out slv(11 downto 0);

      promScl : inout sl;
      promSda : inout sl;

      pwrScl : inout sl;
      pwrSda : inout sl;

      leds : out slv(3 downto 0));

end entity RowModule;

architecture rtl of RowModule is

   constant NUM_AXIL_MASTERS_C : integer := 6;
   constant AXIL_VERSION_C     : integer := 0;
   constant AXIL_XADC_C        : integer := 1;
   constant AXIL_PWR_C         : integer := 2;
   constant AXIL_BOOT_C        : integer := 3;
   constant AXIL_EEPROM_C      : integer := 4;
   constant AXIL_DACS_C        : integer := 5;

   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_VERSION_C  => (
         baseAddr     => X"00000000",
         addrBits     => 12,
         connectivity => X"FFFF"),
      AXIL_XADC_C     => (
         baseAddr     => X"00100000",
         addrBits     => 12,
         connectivity => X"FFFF"),
      AXIL_PWR_C      => (
         baseAddr     => X"00200000",
         addrBits     => 16,
         connectivity => X"FFFF"),
      AXIL_BOOT_C     => (
         baseAddr     => X"00300000",
         addrBits     => 12,
         connectivity => X"FFFF"),
      AXIL_EEPROM_C   => (
         baseAddr     => X"00400000",
         addrBits     => 16,
         connectivity => X"FFFF"),
      AXIL_DACS_C     => (
         baseAddr     => X"01000000",
         addrBits     => 24,
         connectivity => X"FFFF"));

   signal axilClk : sl;
   signal axilRst : sl;

   signal pgpAxilWriteMaster : AxiLiteWriteMasterType;
   signal pgpAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal pgpAxilReadMaster  : AxiLiteReadMasterType;
   signal pgpAxilReadSlave   : AxiLiteReadSlaveType;

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);

   constant DAC_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(11 downto 0) := genAxiLiteConfig(12, AXIL_DACS_C, 24, 20);
   
   signal dacAxilWriteMasters : AxiLiteWriteMasterArray(11 downto 0);
   signal dacAxilWriteSlaves  : AxiLiteWriteSlaveArray(11 downto 0);
   signal dacAxilReadMasters  : AxiLiteReadMasterArray(11 downto 0);
   signal dacAxilReadSlaves   : AxiLiteReadSlaveArray(11 downto 0);
   
begin

   -------------------------------------------------------------------------------------------------
   -- PGP Interface
   -------------------------------------------------------------------------------------------------
   U_RowModulePgp_1 : entity warm_tdm.RowModulePgp
      generic map (
         TPD_G          => TPD_G,
         SIMULATION_G   => SIMULATION_G,
         SIM_PORT_NUM_G => SIM_PORT_NUM_G)
      port map (
         pgpRefClkP      => pgpRefClkP,          -- [in]
         pgpRefClkN      => pgpRefClkN,          -- [in]
         pgpTxP          => pgpTxP,              -- [out]
         pgpTxN          => pgpTxN,              -- [out]
         pgpRxP          => pgpRxP,              -- [in]
         pgpRxN          => pgpRxN,              -- [in]
         axilClk         => axilClk,             -- [out]
         axilRst         => axilRst,             -- [out]
         axilWriteMaster => pgpAxilWriteMaster,  -- [out]
         axilWriteSlave  => pgpAxilWriteSlave,   -- [in]
         axilReadMaster  => pgpAxilReadMaster,   -- [out]
         axilReadSlave   => pgpAxilReadSlave);   -- [in]

   -------------------------------------------------------------------------------------------------
   -- Main crossbar
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_Main : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => AXIL_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => axilClk,              -- [in]
         axiClkRst           => axilRst,              -- [in]
         sAxiWriteMasters(0) => pgpAxilWriteMaster,   -- [in]
         sAxiWriteSlaves(0)  => pgpAxilWriteSlave,    -- [out]
         sAxiReadMasters(0)  => pgpAxilReadMaster,    -- [in]
         sAxiReadSlaves(0)   => pgpAxilReadSlave,     -- [out]
         mAxiWriteMasters    => locAxilWriteMasters,  -- [out]
         mAxiWriteSlaves     => locAxilWriteSlaves,   -- [in]
         mAxiReadMasters     => locAxilReadMasters,   -- [out]
         mAxiReadSlaves      => locAxilReadSlaves);   -- [in]

   -------------------------------------------------------------------------------------------------
   -- AXI Version
   -------------------------------------------------------------------------------------------------
   U_AxiVersion_1 : entity surf.AxiVersion
      generic map (
         TPD_G           => TPD_G,
         BUILD_INFO_G    => BUILD_INFO_G,
         CLK_PERIOD_G    => 6.4E-9,
         XIL_DEVICE_G    => "7SERIES",
         EN_DEVICE_DNA_G => true,
         EN_DS2411_G     => false,
         EN_ICAP_G       => true,
         USE_SLOWCLK_G   => false,
         BUFR_CLK_DIV_G  => 8)
      port map (
         axiClk         => axilClk,                              -- [in]
         axiRst         => axilRst,                              -- [in]
         axiReadMaster  => locAxilReadMasters(AXIL_VERSION_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(AXIL_VERSION_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(AXIL_VERSION_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(AXIL_VERSION_C));  -- [out]

   -------------------------------------------------------------------------------------------------
   -- XADC
   -------------------------------------------------------------------------------------------------
   U_XadcSimpleCore_1 : entity surf.XadcSimpleCore
      generic map (
         TPD_G                    => TPD_G,
         COMMON_CLK_G             => true,
         SEQUENCER_MODE_G         => "CONTINUOUS",
         SAMPLING_MODE_G          => "CONTINUOUS",
         MUX_EN_G                 => false,
         ADCCLK_RATIO_G           => 5,
         SAMPLE_AVG_G             => "00",
         COEF_AVG_EN_G            => true,
         OVERTEMP_AUTO_SHDN_G     => true,
         OVERTEMP_ALM_EN_G        => true,
         OVERTEMP_LIMIT_G         => 80.0,
         OVERTEMP_RESET_G         => 30.0,
         TEMP_ALM_EN_G            => false,
         TEMP_UPPER_G             => 70.0,
         TEMP_LOWER_G             => 0.0,
         VCCINT_ALM_EN_G          => false,
         VCCAUX_ALM_EN_G          => false,
         VCCBRAM_ALM_EN_G         => false,
         ADC_OFFSET_CORR_EN_G     => false,
         ADC_GAIN_CORR_EN_G       => true,
         SUPPLY_OFFSET_CORR_EN_G  => false,
         SUPPLY_GAIN_CORR_EN_G    => true,
         SEQ_XADC_CAL_SEL_EN_G    => false,
         SEQ_TEMPERATURE_SEL_EN_G => true,
         SEQ_VCCINT_SEL_EN_G      => true,
         SEQ_VCCAUX_SEL_EN_G      => true,
         SEQ_VCCBRAM_SEL_EN_G     => true,
         SEQ_VAUX_SEL_EN_G        => (others => false))        -- All AUX voltages on
      port map (
         axilClk         => axilClk,                           -- [in]
         axilRst         => axilRst,                           -- [in]
         axilReadMaster  => locAxilReadMasters(AXIL_XADC_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_XADC_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_XADC_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_XADC_C),   -- [out]
         xadcClk         => axilClk,                           -- [in]
         xadcRst         => axilClk,                           -- [in]
         alm             => open,                              -- [out]
         ot              => open);                             -- [out]

   -------------------------------------------------------------------------------------------------
   -- Board temperature
   -------------------------------------------------------------------------------------------------
   U_AxiI2cRegMaster_1 : entity surf.AxiI2cRegMaster
      generic map (
         TPD_G            => TPD_G,
         DEVICE_MAP_G     => (
            0             => MakeI2cAxiLiteDevType(
               i2cAddress => "1001000",
               dataSize   => 8,
               addrSize   => 8,
               endianness => '1')),
         I2C_SCL_FREQ_G   => 100.0E+3,
         I2C_MIN_PULSE_G  => 100.0E-9,
         AXI_CLK_FREQ_G   => 156.25E+6)
      port map (
         axiClk         => axilClk,                          -- [in]
         axiRst         => axilRst,                          -- [in]
         axiReadMaster  => locAxilReadMasters(AXIL_PWR_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(AXIL_PWR_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(AXIL_PWR_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(AXIL_PWR_C),   -- [out]
         scl            => pwrScl,                           -- [inout]
         sda            => pwrSda);                          -- [inout]

   ----------------------
   -- AXI-Lite: Boot Prom
   ----------------------
   U_SpiProm : entity surf.AxiMicronN25QCore
      generic map (
         TPD_G          => TPD_G,
         AXI_CLK_FREQ_G => 125.0E+6,
         SPI_CLK_FREQ_G => (125.0E+6/12.0))
      port map (
         -- FLASH Memory Ports
         csL            => bootCsL,
         sck            => bootSck,
         mosi           => bootMosi,
         miso           => bootMiso,
         -- AXI-Lite Register Interface
         axiReadMaster  => locAxilReadMasters(AXIL_BOOT_C),
         axiReadSlave   => locAxilReadSlaves(AXIL_BOOT_C),
         axiWriteMaster => locAxilWriteMasters(AXIL_BOOT_C),
         axiWriteSlave  => locAxilWriteSlaves(AXIL_BOOT_C),
         -- Clocks and Resets
         axiClk         => axilClk,
         axiRst         => axilRst);

   -----------------------------------------------------
   -- Using the STARTUPE2 to access the FPGA's CCLK port
   -----------------------------------------------------
   U_STARTUPE2 : STARTUPE2
      port map (
         CFGCLK    => open,             -- 1-bit output: Configuration main clock output
         CFGMCLK   => open,  -- 1-bit output: Configuration internal oscillator clock output
         EOS       => open,  -- 1-bit output: Active high output signal indicating the End Of Startup.
         PREQ      => open,             -- 1-bit output: PROGRAM request to fabric output
         CLK       => '0',              -- 1-bit input: User start-up clock input
         GSR       => '0',  -- 1-bit input: Global Set/Reset input (GSR cannot be used for the port name)
         GTS       => '0',  -- 1-bit input: Global 3-state input (GTS cannot be used for the port name)
         KEYCLEARB => '0',  -- 1-bit input: Clear AES Decrypter Key input from Battery-Backed RAM (BBRAM)
         PACK      => '0',              -- 1-bit input: PROGRAM acknowledge input
         USRCCLKO  => bootSck,          -- 1-bit input: User CCLK input
         USRCCLKTS => '0',              -- 1-bit input: User CCLK 3-state enable input
         USRDONEO  => '1',              -- 1-bit input: User DONE pin output control
         USRDONETS => '1');             -- 1-bit input: User DONE 3-state enable output

   -------------------------------------------------------------------------------------------------
   -- I2C EEPROM - 24LC64F
   -------------------------------------------------------------------------------------------------
   U_AxiI2cRegMaster_EEPROM : entity surf.AxiI2cRegMaster
      generic map (
         TPD_G            => TPD_G,
         DEVICE_MAP_G     => (
            0             => MakeI2cAxiLiteDevType(
               i2cAddress => "1010000",
               dataSize   => 8,
               addrSize   => 16,
               endianness => '1')),
         I2C_SCL_FREQ_G   => 400.0E+3,
         I2C_MIN_PULSE_G  => 100.0E-9,
         AXI_CLK_FREQ_G   => 156.25E+6)
      port map (
         axiClk         => axilClk,                             -- [in]
         axiRst         => axilRst,                             -- [in]
         axiReadMaster  => locAxilReadMasters(AXIL_EEPROM_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(AXIL_EEPROM_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(AXIL_EEPROM_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(AXIL_EEPROM_C),   -- [out]
         scl            => promScl,                             -- [inout]
         sda            => promSda);                            -- [inout]

   -- 
   -------------------------------------------------------------------------------------------------
   -- DAC Config Crossbar
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_DACs : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 12,
         MASTERS_CONFIG_G   => DAC_XBAR_CFG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => axilClk,                           -- [in]
         axiClkRst           => axilRst,                           -- [in]
         sAxiWriteMasters(0) => locAxilWriteMasters(AXIL_DACS_C),  -- [in]
         sAxiWriteSlaves(0)  => locAxilWriteSlaves(AXIL_DACS_C),   -- [out]
         sAxiReadMasters(0)  => locAxilReadMasters(AXIL_DACS_C),   -- [in]
         sAxiReadSlaves(0)   => locAxilReadSlaves(AXIL_DACS_C),    -- [out]
         mAxiWriteMasters    => dacAxilWriteMasters,               -- [out]
         mAxiWriteSlaves     => dacAxilWriteSlaves,                -- [in]
         mAxiReadMasters     => dacAxilReadMasters,                -- [out]
         mAxiReadSlaves      => dacAxilReadSlaves);                -- [in]

   -- DAC Config interfaces
   DAC_SPI_GEN : for i in 11 downto 0 generate
      U_AxiSpiMaster_1 : entity surf.AxiSpiMaster
         generic map (
            TPD_G             => TPD_G,
            ADDRESS_SIZE_G    => 16,
            DATA_SIZE_G       => 16,
            MODE_G            => "RW",
            SHADOW_EN_G       => false,
            CPHA_G            => '1',
            CPOL_G            => '1',
            CLK_PERIOD_G      => 156.25E+6,
            SPI_SCLK_PERIOD_G => 100.0E-6,
            SPI_NUM_CHIPS_G   => 1)
         port map (
            axiClk         => axilClk,                 -- [in]
            axiRst         => axilRst,                 -- [in]
            axiReadMaster  => dacAxilReadMasters(i),   -- [in]
            axiReadSlave   => dacAxilReadSlaves(i),    -- [out]
            axiWriteMaster => dacAxilWriteMasters(i),  -- [in]
            axiWriteSlave  => dacAxilWriteSlaves(i),   -- [out]
            coreSclk       => dacSclk(i),              -- [out]
            coreSDin       => dacSdi2(i),              -- [in]
            coreSDout      => dacSdio(i),              -- [out]
            coreMCsb(0)    => dacCsB(i));              -- [out]
   end generate DAC_SPI_GEN;


end architecture rtl;
