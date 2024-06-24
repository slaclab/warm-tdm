-------------------------------------------------------------------------------
-- Title      : Warm TDM Common2 Components
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Common2 components that are in all variants of the firmware
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
use surf.AxiLitePkg.all;
use surf.I2cPkg.all;

library warm_tdm;

entity WarmTdmCommon2 is

   generic (
      TPD_G                : time                     := 1 ns;
      SIMULATION_G         : boolean                  := false;
      BUILD_INFO_G         : BuildInfoType;
      AXIL_BASE_ADDR_G     : slv(31 downto 0)         := (others => '0');
      LOC_XADC_AUX_CHANS_G : IntegerArray(5 downto 0) := (9, 10, 1, 11, 0, 3);
      FE_XADC_AUX_CHANS_G  : IntegerArray(1 downto 0) := (2, 8);
      AXIL_CLK_FREQ_G      : real                     := 125.0E6);

   port (
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType;

      -- Boot PROM interface
      bootCsL  : out sl;
      bootMosi : out sl;
      bootMiso : in  sl;

      -- Local I2C PROM
      locScl     : inout sl;
      locSda     : inout sl;
      tempAlertL : in    sl;

      -- Power Monitor I2C
      pwrScl : inout sl;
      pwrSda : inout sl;

      -- SFP I2C
      sfpScl : inout slv(1 downto 0);
      sfpSda : inout slv(1 downto 0);

      -- VR Synchronization
      pwrSyncA : out sl := '0';
      pwrSyncB : out sl := '0';
      pwrSyncC : out sl := '0';

      -- XADC
      localThermistorP : in slv(5 downto 0);
      localThermistorN : in slv(5 downto 0);
      feThermistorP    : in slv(1 downto 0);
      feThermistorN    : in slv(1 downto 0);

      -- Amplifier power down
      ampPdB : out slv(7 downto 0) := (others => '1'));


end entity WarmTdmCommon2;

architecture rtl of WarmTdmCommon2 is

   constant NUM_AXIL_MASTERS_C : integer := 8;
   constant AXIL_VERSION_C     : integer := 0;
   constant AXIL_XADC_C        : integer := 1;
   constant AXIL_BOOT_C        : integer := 2;
   constant AXIL_PWR_I2C_C     : integer := 3;
   constant AXIL_LOC_I2C_C     : integer := 4;
   constant AXIL_AMP_PD_C      : integer := 5;
   constant AXIL_SFP_I2C_0_C   : integer := 6;
   constant AXIL_SFP_I2C_1_C   : integer := 7;


   constant AXIL_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_MASTERS_C-1 downto 0) := (
      AXIL_VERSION_C   => (
         baseAddr      => AXIL_BASE_ADDR_G + X"00000000",
         addrBits      => 12,
         connectivity  => X"FFFF"),
      AXIL_XADC_C      => (
         baseAddr      => AXIL_BASE_ADDR_G + X"00001000",
         addrBits      => 12,
         connectivity  => X"FFFF"),
      AXIL_BOOT_C      => (
         baseAddr      => AXIL_BASE_ADDR_G + X"00002000",
         addrBits      => 12,
         connectivity  => X"FFFF"),
      AXIL_PWR_I2C_C   => (
         baseAddr      => AXIL_BASE_ADDR_G + X"00003000",
         addrBits      => 12,
         connectivity  => X"FFFF"),
      AXIL_LOC_I2C_C   => (
         baseAddr      => AXIL_BASE_ADDR_G + X"00100000",
         addrBits      => 20,
         connectivity  => X"FFFF"),
      AXIL_AMP_PD_C    => (
         baseAddr      => AXIL_BASE_ADDR_G + X"00004000",
         addrBits      => 8,
         connectivity  => X"FFFF"),
      AXIL_SFP_I2C_0_C => (
         baseAddr      => AXIL_BASE_ADDR_G + X"00005000",
         addrBits      => 12,
         connectivity  => X"FFFF"),
      AXIL_SFP_I2C_1_C => (
         baseAddr      => AXIL_BASE_ADDR_G + X"00006000",
         addrBits      => 12,
         connectivity  => X"FFFF"));


   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_MASTERS_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_MASTERS_C-1 downto 0);

   signal bootSck : sl;

   signal locAuxP : slv(15 downto 0) := (others => '0');
   signal locAuxN : slv(15 downto 0) := (others => '0');

   function genSeqVauxSelEn
      return BooleanArray is
      variable ret : BooleanArray(15 downto 0) := (others => false);
   begin
      for i in LOC_XADC_AUX_CHANS_G'range loop
         ret(LOC_XADC_AUX_CHANS_G(i)) := true;
      end loop;
      for i in FE_XADC_AUX_CHANS_G'range loop
         ret(FE_XADC_AUX_CHANS_G(i)) := true;
      end loop;
      return ret;
   end function genSeqVauxSelEn;

   constant SEQ_VAUX_SEL_EN_C : BooleanArray(15 downto 0) := genSeqVauxSelEn;

begin

   -------------------------------------------------------------------------------------------------
   -- Crossbar
   -------------------------------------------------------------------------------------------------
   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_MASTERS_C,
         MASTERS_CONFIG_G   => AXIL_XBAR_CFG_C,
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
   -- AXI Version
   -------------------------------------------------------------------------------------------------
   U_AxiVersion_1 : entity surf.AxiVersion
      generic map (
         TPD_G           => TPD_G,
         BUILD_INFO_G    => BUILD_INFO_G,
         CLK_PERIOD_G    => (1.0/AXIL_CLK_FREQ_G),               --6.4E-9,
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
--    LOC_AUX_LOOP : for i in LOC_XADC_AUX_CHANS_G'range generate
--       locAuxP(LOC_XADC_AUX_CHANS_G(i)) <= localThermistorP(i);
--       locAuxN(LOC_XADC_AUX_CHANS_G(i)) <= localThermistorN(i);
--    end generate LOC_AUX_LOOP;

--    FE_AUX_LOOP : for i in FE_XADC_AUX_CHANS_G'range generate
--       locAuxP(FE_XADC_AUX_CHANS_G(i)) <= feThermistorP(i);
--       locAuxN(FE_XADC_AUX_CHANS_G(i)) <= feThermistorN(i);
--    end generate FE_AUX_LOOP;


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
         SEQ_VAUX_SEL_EN_G        => SEQ_VAUX_SEL_EN_C)
      port map (
         axilClk             => axilClk,                           -- [in]
         axilRst             => axilRst,                           -- [in]
         axilReadMaster      => locAxilReadMasters(AXIL_XADC_C),   -- [in]
         axilReadSlave       => locAxilReadSlaves(AXIL_XADC_C),    -- [out]
         axilWriteMaster     => locAxilWriteMasters(AXIL_XADC_C),  -- [in]
         axilWriteSlave      => locAxilWriteSlaves(AXIL_XADC_C),   -- [out]
         xadcClk             => axilClk,                           -- [in]
         xadcRst             => axilClk,                           -- [in]
         vAuxP(0)            => localThermistorP(4),               -- [in]
         vAuxP(1)            => localThermistorP(2),
         vAuxP(2)            => feThermistorP(0),
         vAuxP(3)            => localThermistorP(5),
         vAuxP(7 downto 4)   => "0000",
         vAuxP(8)            => feThermistorP(1),
         vAuxP(9)            => localThermistorP(0),
         vAuxP(10)           => localThermistorP(1),
         vAuxP(11)           => localThermistorP(3),
         vAuxP(15 downto 12) => "0000",
         vAuxN(0)            => localThermistorN(4),               -- [in]
         vAuxN(1)            => localThermistorN(2),
         vAuxN(2)            => feThermistorN(0),
         vAuxN(3)            => localThermistorN(5),
         vAuxN(7 downto 4)   => "0000",
         vAuxN(8)            => feThermistorN(1),
         vAuxN(9)            => localThermistorN(0),
         vAuxN(10)           => localThermistorN(1),
         vAuxN(11)           => localThermistorN(3),
         vAuxN(15 downto 12) => "0000",
         alm                 => open,                              -- [out]
         ot                  => open);                             -- [out]

   ----------------------
   -- AXI-Lite: Boot Prom
   ----------------------
   U_SpiProm : entity surf.AxiMicronN25QCore
      generic map (
         TPD_G          => TPD_G,
         AXI_CLK_FREQ_G => AXIL_CLK_FREQ_G,       --125.0E+6,
         SPI_CLK_FREQ_G => (AXIL_CLK_FREQ_G/12))  --(125.0E+6/12.0))
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
   -- Board temperature
   -------------------------------------------------------------------------------------------------
   U_AxiI2cRegMaster_POWER : entity surf.AxiI2cRegMaster
      generic map (
         TPD_G            => TPD_G,
         DEVICE_MAP_G     => (
            0             => MakeI2cAxiLiteDevType(              -- LTC4151 Digital Power
               i2cAddress => "1101111",
               dataSize   => 8,
               addrSize   => 8,
               endianness => '0'),
            1             => MakeI2cAxiLiteDevType(              -- LTC4151 Analog Power
               i2cAddress => "1101010",
               dataSize   => 8,
               addrSize   => 8,
               endianness => '0')),
         I2C_SCL_FREQ_G   => ite(SIMULATION_G, 2.0e6, 100.0E+3),
         I2C_MIN_PULSE_G  => ite(SIMULATION_G, 50.0e-9, 100.0E-9),
         AXI_CLK_FREQ_G   => AXIL_CLK_FREQ_G)                    --156.25E+6)
      port map (
         axiClk         => axilClk,                              -- [in]
         axiRst         => axilRst,                              -- [in]
         axiReadMaster  => locAxilReadMasters(AXIL_PWR_I2C_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(AXIL_PWR_I2C_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(AXIL_PWR_I2C_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(AXIL_PWR_I2C_C),   -- [out]
         scl            => pwrScl,                               -- [inout]
         sda            => pwrSda);                              -- [inout]

   -------------------------------------------------------------------------------------------------
   -- I2C EEPROM - 24LC64F
   -------------------------------------------------------------------------------------------------
   U_AxiI2cRegMaster_EEPROM : entity surf.AxiI2cRegMaster
      generic map (
         TPD_G            => TPD_G,
         DEVICE_MAP_G     => (
            0             => MakeI2cAxiLiteDevType(              -- 24LC64FT
               i2cAddress => "1010000",
               dataSize   => 8,
               addrSize   => 16,
               endianness => '1'),
            1             => MakeI2cAxiLiteDevType(              -- SA56004EDP Temp Monitor
               i2cAddress => "1001100",
               dataSize   => 8,
               addrSize   => 8,
               endianness => '1')),
         I2C_SCL_FREQ_G   => ite(SIMULATION_G, 2.0e6, 100.0E+3),
         I2C_MIN_PULSE_G  => ite(SIMULATION_G, 50.0e-9, 100.0E-9),
         AXI_CLK_FREQ_G   => AXIL_CLK_FREQ_G)
      port map (
         axiClk         => axilClk,                              -- [in]
         axiRst         => axilRst,                              -- [in]
         axiReadMaster  => locAxilReadMasters(AXIL_LOC_I2C_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(AXIL_LOC_I2C_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(AXIL_LOC_I2C_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(AXIL_LOC_I2C_C),   -- [out]
         scl            => locScl,                               -- [inout]
         sda            => locSda);                              -- [inout]

   -------------------------------------------------------------------------------------------------
   -- SFP I2C 0
   -------------------------------------------------------------------------------------------------
   U_Sff8472_0 : entity surf.Sff8472
      generic map (
         TPD_G           => TPD_G,
         I2C_SCL_FREQ_G  => ite(SIMULATION_G, 2.0e6, 100.0E+3),
         I2C_MIN_PULSE_G => ite(SIMULATION_G, 50.0e-9, 100.0E-9),
         AXI_CLK_FREQ_G  => AXIL_CLK_FREQ_G)
      port map (
         scl             => sfpScl(0),                              -- [inout]
         sda             => sfpSda(0),                              -- [inout]
         axilReadMaster  => locAxilReadMasters(AXIL_SFP_I2C_0_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_SFP_I2C_0_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_SFP_I2C_0_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SFP_I2C_0_C),   -- [out]
         axilClk         => axilClk,                                -- [in]
         axilRst         => axilRst);                               -- [in]

   -------------------------------------------------------------------------------------------------
   -- SFP I2C 0
   -------------------------------------------------------------------------------------------------
   U_Sff8472_1 : entity surf.Sff8472
      generic map (
         TPD_G           => TPD_G,
         I2C_SCL_FREQ_G  => ite(SIMULATION_G, 2.0e6, 100.0E+3),
         I2C_MIN_PULSE_G => ite(SIMULATION_G, 50.0e-9, 100.0E-9),
         AXI_CLK_FREQ_G  => AXIL_CLK_FREQ_G)
      port map (
         scl             => sfpScl(1),                              -- [inout]
         sda             => sfpSda(1),                              -- [inout]
         axilReadMaster  => locAxilReadMasters(AXIL_SFP_I2C_1_C),   -- [in]
         axilReadSlave   => locAxilReadSlaves(AXIL_SFP_I2C_1_C),    -- [out]
         axilWriteMaster => locAxilWriteMasters(AXIL_SFP_I2C_1_C),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(AXIL_SFP_I2C_1_C),   -- [out]
         axilClk         => axilClk,                                -- [in]
         axilRst         => axilRst);                               -- [in]



end architecture rtl;
