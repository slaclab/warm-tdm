-------------------------------------------------------------------------------
-- Title      : I2C Core for AwaXe ASIC Interface
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: 
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

library surf;
use surf.StdRtlPkg.all;
use surf.I2cPkg.all;
use surf.AxiLitePkg.all;

entity AwaXeI2c is

   generic (
      TPD_G           : time            := 1 ns;
      CHIP_ADDR_G     : slv(2 downto 0) := "000";
      AXIL_CLK_FREQ_G : real            := 125.0e6);

   port (
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType;

      sda : inout sl;
      scl : inout sl);

end entity AwaXeI2c;

architecture rtl of AwaXeI2c is

   constant I2C_CONFIG_C : I2cAxiLiteDevArray(9 downto 0) := (
      -- Channel 0 DACs
      0              => MakeI2cAxiLiteDevType(  -- 1.8mA CH 0 - AXIL 0x000
         i2cAddress  => "0000" & CHIP_ADDR_G,
         dataSize    => 8,
         addrSize    => 0,
         endianness  => '0',
         repeatStart => '0'),
      1              => MakeI2cAxiLiteDevType(  -- 300uA CH 0.0 - AXIL 0x080
         i2cAddress  => "1000" & CHIP_ADDR_G,
         dataSize    => 8,
         addrSize    => 0,
         endianness  => '0',
         repeatStart => '0'),
      2              => MakeI2cAxiLiteDevType(  -- 300uA CH 0.1 - AXIL 0x100
         i2cAddress  => "1001" & CHIP_ADDR_G,
         dataSize    => 8,
         addrSize    => 0,
         endianness  => '0',
         repeatStart => '0'),
      3              => MakeI2cAxiLiteDevType(  -- 300uA CH 0.2 - AXIL 0x180
         i2cAddress  => "1010" & CHIP_ADDR_G,
         dataSize    => 8,
         addrSize    => 0,
         endianness  => '0',
         repeatStart => '0'),
      4              => MakeI2cAxiLiteDevType(  -- 300uA CH 0.3 - AXIL 0x200
         i2cAddress  => "1011" & CHIP_ADDR_G,
         dataSize    => 8,
         addrSize    => 0,
         endianness  => '0',
         repeatStart => '0'),

      -- Channel 1 DACS
      5              => MakeI2cAxiLiteDevType(  -- 1.8mA CH 1 - AXIL 0x280
         i2cAddress  => "0100" & CHIP_ADDR_G,
         dataSize    => 8,
         addrSize    => 0,
         endianness  => '0',
         repeatStart => '0'),
      6              => MakeI2cAxiLiteDevType(  -- 300uA CH 1.0 - AXIL 0x300
         i2cAddress  => "1100" & CHIP_ADDR_G,
         dataSize    => 8,
         addrSize    => 0,
         endianness  => '0',
         repeatStart => '0'),
      7              => MakeI2cAxiLiteDevType(  -- 300uA CH 1.1 - AXIL 0x380
         i2cAddress  => "1101" & CHIP_ADDR_G,
         dataSize    => 8,
         addrSize    => 0,
         endianness  => '0',
         repeatStart => '0'),
      8              => MakeI2cAxiLiteDevType(  -- 300uA CH 1.2 - AXIL 0x400
         i2cAddress  => "1110" & CHIP_ADDR_G,
         dataSize    => 8,
         addrSize    => 0,
         endianness  => '0',
         repeatStart => '0'),
      9              => MakeI2cAxiLiteDevType(  -- 300uA CH 1.3 - AXIL 0x480
         i2cAddress  => "1111" & CHIP_ADDR_G,
         dataSize    => 8,
         addrSize    => 0,
         endianness  => '0',
         repeatStart => '0'));

begin

   U_AxiI2cRegMaster_FE_I2C : entity surf.AxiI2cRegMaster
      generic map (
         TPD_G           => TPD_G,
         DEVICE_MAP_G    => I2C_CONFIG_C,
         I2C_SCL_FREQ_G  => ite(SIMULATION_G, 2.0e6, 100.0E+3),
         I2C_MIN_PULSE_G => ite(SIMULATION_G, 50.0e-9, 100.0E-9),
         AXI_CLK_FREQ_G  => AXIL_CLK_FREQ_G)
      port map (
         axiClk         => axilClk,          -- [in]
         axiRst         => axilRst,          -- [in]
         axiReadMaster  => axilReadMaster,   -- [in]
         axiReadSlave   => axilReadSlave,    -- [out]
         axiWriteMaster => axilWriteMaster,  -- [in]
         axiWriteSlave  => axilWriteSlave,   -- [out]
         scl            => scl,              -- [inout]
         sda            => sda);             -- [inout]


end architecture rtl;

