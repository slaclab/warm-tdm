-------------------------------------------------------------------------------
-- Title      : Row Module DAC Interface
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Array for SPI interfaces to AD9106 DACs
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

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity RowModuleDacs is

   generic (
      TPD_G            : time             := 1 ns;
      SIMULATION_G     : boolean          := false;
      AXIL_CLK_FREQ_G  : real             := 125.0E6;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := X"00000000");
   port (
      -- AXI Lite Slave
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType;

      -- Timing Interface
      timingRxClk125 : in sl;
      timingRxRst125 : in sl;
      timingRxData   : in LocalTimingType;

      -- DAC Interfaces
      dacCsB      : out slv(11 downto 0);
      dacSdio     : out slv(11 downto 0);
      dacSdo      : in  slv(11 downto 0);
      dacSclk     : out slv(11 downto 0);
      dacResetB   : out slv(11 downto 0) := (others => '1');
      dacTriggerB : out slv(11 downto 0) := (others => '1');
      dacClkP     : out slv(11 downto 0);
      dacClkN     : out slv(11 downto 0));
end entity;

architecture rtl of RowModuleDacs is

   -- DAC SPI AXIL
   constant DAC_XBAR_CFG_C : AxiLiteCrossbarMasterConfigArray(11 downto 0) := genAxiLiteConfig(12, AXIL_BASE_ADDR_G, 24, 20);

   signal dacAxilWriteMasters : AxiLiteWriteMasterArray(11 downto 0);
   signal dacAxilWriteSlaves  : AxiLiteWriteSlaveArray(11 downto 0);
   signal dacAxilReadMasters  : AxiLiteReadMasterArray(11 downto 0);
   signal dacAxilReadSlaves   : AxiLiteReadSlaveArray(11 downto 0);

begin

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
         axiClk              => axilClk,              -- [in]
         axiClkRst           => axilRst,              -- [in]
         sAxiWriteMasters(0) => axilWriteMaster,      -- [in]
         sAxiWriteSlaves(0)  => axilWriteSlave,       -- [out]
         sAxiReadMasters(0)  => axilReadMaster,       -- [in]
         sAxiReadSlaves(0)   => axilReadSlave,        -- [out]
         mAxiWriteMasters    => dacAxilWriteMasters,  -- [out]
         mAxiWriteSlaves     => dacAxilWriteSlaves,   -- [in]
         mAxiReadMasters     => dacAxilReadMasters,   -- [out]
         mAxiReadSlaves      => dacAxilReadSlaves);   -- [in]

   -- DAC Config interfaces
   DAC_SPI_GEN : for i in 11 downto 0 generate
      U_AxiSpiMaster_1 : entity surf.AxiSpiMaster
         generic map (
            TPD_G             => TPD_G,
            ADDRESS_SIZE_G    => 15,
            DATA_SIZE_G       => 16,
            MODE_G            => "RW",
            SHADOW_EN_G       => false,
            CPHA_G            => '1',
            CPOL_G            => '1',
            CLK_PERIOD_G      => 1.0/AXIL_CLK_FREQ_G,
            SPI_SCLK_PERIOD_G => ite(SIMULATION_G, 51.2e-9, 1.0E-6),
            SPI_NUM_CHIPS_G   => 1)
         port map (
            axiClk         => axilClk,                 -- [in]
            axiRst         => axilRst,                 -- [in]
            axiReadMaster  => dacAxilReadMasters(i),   -- [in]
            axiReadSlave   => dacAxilReadSlaves(i),    -- [out]
            axiWriteMaster => dacAxilWriteMasters(i),  -- [in]
            axiWriteSlave  => dacAxilWriteSlaves(i),   -- [out]
            coreSclk       => dacSclk(i),              -- [out]
            coreSDin       => dacSdo(i),               -- [in]
            coreSDout      => dacSdio(i),              -- [out]
            coreMCsb(0)    => dacCsB(i));              -- [out]


      U_ClkOutBufDiff_1 : entity surf.ClkOutBufDiff
         generic map (
            TPD_G => TPD_G)
         port map (
            clkIn   => timingRxClk125,  -- [in]
            clkOutP => dacClkP(i),      -- [out]
            clkOutN => dacClkN(i));     -- [out]

--       U_ClkOutBufDiff_1 : OBUFDS
--          port map (
--             i  => timingRxData.rowStrobe,  -- [in]
--             o  => dacClkP(i),              -- [out]
--             ob => dacClkN(i));             -- [out]

      dacTriggerB(i) <= not timingRxData.running;
   end generate DAC_SPI_GEN;



end architecture rtl;
