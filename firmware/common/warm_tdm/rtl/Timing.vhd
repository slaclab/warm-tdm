-------------------------------------------------------------------------------
-- Title      : Timing Rx
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

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity Timing is

   generic (
      TPD_G             : time                  := 1 ns;
      SIMULATION_G      : boolean               := false;
      AXIL_CLK_FREQ_G   : real                  := 156.26E6;
      AXIL_BASE_ADDR_G  : slv(31 downto 0)      := (others => '0');
      IODELAY_GROUP_G   : string                := "DEFAULT_GROUP";
      IDELAYCTRL_FREQ_G : real                  := 200.0;
      DEFAULT_DELAY_G   : integer range 0 to 31 := 0);

   port (
      -- Reference clock
      timingRefClkP   : in  sl;
      timingRefClkN   : in  sl;
      timingRefClkOut : out sl;

      -- RX Timing Serial Interface
      timingRxClkP  : in sl;
      timingRxClkN  : in sl;
      timingRxDataP : in sl;
      timingRxDataN : in sl;

      -- Local RX timing data for app
      timingClkOut  : out sl;
      timingRstOut  : out sl;
      timingDataOut : out LocalTimingType;

      -- TX Timing Serial Interface
      timingTxClkP  : out sl;
      timingTxClkN  : out sl;
      timingTxDataP : out sl;
      timingTxDataN : out sl;

      -- Configuration
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);

end entity Timing;

architecture rtl of Timing is

   signal timingRefClk  : sl;
   signal timingRefClkG : sl;

   signal idelayClk : sl;
   signal idelayRst : sl;

   signal timingClk125 : sl;
   signal timingRst125 : sl;

   attribute IODELAY_GROUP                 : string;
   attribute IODELAY_GROUP of IDELAYCTRL_0 : label is IODELAY_GROUP_G;

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(1 downto 0);


begin



   -------------------------------------------------------------------------------------------------
   -- USE Timing Refclk to create 125 MHz Timing TX clock and 200 MHz IDELAYCTRL clock
   -------------------------------------------------------------------------------------------------
   U_IBUFDS_GTE2 : IBUFDS_GTE2
      port map (
         I     => timingRefClkP,
         IB    => timingRefClkN,
         CEB   => '0',
         ODIV2 => open,
         O     => timingRefClk);

   U_BUFG : BUFG
      port map (
         I => timingRefClk,
         O => timingRefClkG);

   U_MMCM_IDELAY : entity surf.ClockManager7
      generic map(
         TPD_G              => TPD_G,
         TYPE_G             => "MMCM",
         INPUT_BUFG_G       => false,
         FB_BUFG_G          => true,    -- Without this, will never lock in simulation
         RST_IN_POLARITY_G  => '1',
         NUM_CLOCKS_G       => 2,
         -- MMCM attributes
         BANDWIDTH_G        => "OPTIMIZED",
         CLKIN_PERIOD_G     => 4.0,     -- 250 MHz
         DIVCLK_DIVIDE_G    => 1,       -- 250 MHz
         CLKFBOUT_MULT_F_G  => 4.0,     -- 1.0GHz =  250 MHz x 4
         CLKOUT0_DIVIDE_F_G => 8.0,     -- 125 MHz = 1.0GHz/8
         CLKOUT1_DIVIDE_G   => 5)       --  = 200 MHz = 1.0GHz/5
      port map(
         clkIn     => timingRefClkG,
         rstIn     => '0',
         clkOut(0) => timingClk125,
         clkOut(1) => idelayClk,
         rstOut(0) => timingRst125,
         rstOut(1) => idelayRst,
         locked    => open);

   timingRefClkOut <= timingClk125;

   -------------
   -- IDELAYCTRL
   -------------
   IDELAYCTRL_0 : IDELAYCTRL
      port map (
         RDY    => open,
         REFCLK => idelayClk,
         RST    => idelayRst);

   --------------------------
   -- AXI Lite crossbar
   --------------------------
   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 2,
         MASTERS_CONFIG_G   => (
            0               => (
               baseAddr     => AXIL_BASE_ADDR_G + X"0000",
               addrBits     => 8,
               connectivity => X"FFFF"),
            1               => (
               baseAddr     => AXIL_BASE_ADDR_G + X"0100",
               addrBits     => 8,
               connectivity => X"FFFF")),
         DEBUG_G            => true)
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

   ---------------------------
   -- Timing RX
   ---------------------------
   U_TimingRx_1 : entity warm_tdm.TimingRx
      generic map (
         TPD_G             => TPD_G,
         SIMULATION_G      => SIMULATION_G,
         AXIL_CLK_FREQ_G   => AXIL_CLK_FREQ_G,
         IODELAY_GROUP_G   => IODELAY_GROUP_G,
         IDELAYCTRL_FREQ_G => IDELAYCTRL_FREQ_G,
         DEFAULT_DELAY_G   => DEFAULT_DELAY_G)
      port map (
         timingRxClkP    => timingRxClkP,            -- [in]
         timingRxClkN    => timingRxClkN,            -- [in]
         timingRxDataP   => timingRxDataP,           -- [in]
         timingRxDataN   => timingRxDataN,           -- [in]
         timingRxClkOut  => timingClkOut,            -- [out]
         timingRxRstOut  => timingRstOut,            -- [out]
         timingDataOut   => timingDataOut,           -- [out]
         axilClk         => axilClk,                 -- [in]
         axilRst         => axilRst,                 -- [in]
         axilWriteMaster => locAxilWriteMasters(0),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(0),   -- [out]
         axilReadMaster  => locAxilReadMasters(0),   -- [in]
         axilReadSlave   => locAxilReadSlaves(0));   -- [out]

   U_TimingTx_1 : entity warm_tdm.TimingTx
      generic map (
         TPD_G        => TPD_G,
         SIMULATION_G => SIMULATION_G)
      port map (
         timingClk125    => timingClk125,            -- [in]
         timingRst125    => timingRst125,            -- [in]
         timingTxClkP    => timingTxClkP,            -- [out]
         timingTxClkN    => timingTxClkN,            -- [out]
         timingTxDataP   => timingTxDataP,           -- [out]
         timingTxDataN   => timingTxDataN,           -- [out]
         axilClk         => axilClk,                 -- [in]
         axilRst         => axilRst,                 -- [in]
         axilWriteMaster => locAxilWriteMasters(1),  -- [in]
         axilWriteSlave  => locAxilWriteSlaves(1),   -- [out]
         axilReadMaster  => locAxilReadMasters(1),   -- [in]
         axilReadSlave   => locAxilReadSlaves(1));   -- [out]

end architecture rtl;
