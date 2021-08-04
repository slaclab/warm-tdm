-------------------------------------------------------------------------------
-- Title      : Fast DAC Driver
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Drives AD9767 DACs for SQ1 Bias, SQ1 Feedback or SA Feedback
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
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity FastDacDriver is

   generic (
      TPD_G            : time             := 1 ns;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := (others => '0'));

   port (
      timingRxClk125 : in sl;
      timingRxRst125 : in sl;

      timingRxData : in LocalTimingType;

      dacDb    : out slv(13 downto 0);
      dacWrt   : out slv(3 downto 0);
      dacClk   : out slv(3 downto 0);
      dacSel   : out slv(3 downto 0);
      dacReset : out slv(3 downto 0) := (others => '0');

      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType);

end entity FastDacDriver;

architecture rtl of FastDacDriver is

   constant NUM_AXIL_C : integer := 9;

   constant XBAR_COFNIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_C, AXIL_BASE_ADDR_G, 12, 8);

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_C-1 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_C-1 downto 0);

   type StateType is (
      WAIT_ROW_STROBE_S,
      DATA_S,
      WRITE_S,
      WRITE_FALL_S,
      OVER_SEL_S,
      OVER_WRITE_S,
      CLK_0_RISE_S,
      CLK_0_FALL_S,
      CLK_1_RISE_S);

   type RegType is record
      state  : StateType;
      dacNum : slv(2 downto 0);
      dacDb  : slv(13 downto 0);
      dacWrt : slv(3 downto 0);
      dacClk : slv(3 downto 0);
      dacSel : slv(3 downto 0);
   end record RegType;

   constant REG_INIT_C : RegType := (
      state  => WAIT_ROW_STROBE_S,
      dacNum => (others => '0'),
      dacDb  => (others => '0'),
      dacWrt => (others => '0'),
      dacClk => (others => '0'),
      dacSel => (others => '0'));

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal ramDout : slv16Array(7 downto 0);

   signal overrideWrValid : sl;
   signal overrideWrAddr  : slv(2 downto 0);
   signal overrideWrData  : slv(15 downto 0);

begin

   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_C,
         MASTERS_CONFIG_G   => XBAR_COFNIG_C,
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

   GEN_AXIL_RAM : for i in 7 downto 0 generate
      U_AxiDualPortRam_1 : entity surf.AxiDualPortRam
         generic map (
            TPD_G            => TPD_G,
            SYNTH_MODE_G     => "inferred",
            MEMORY_TYPE_G    => "distributed",
            READ_LATENCY_G   => 0,
            AXI_WR_EN_G      => true,
            SYS_WR_EN_G      => false,
            SYS_BYTE_WR_EN_G => false,
            COMMON_CLK_G     => false,
            ADDR_WIDTH_G     => 6,
            DATA_WIDTH_G     => 16)
         port map (
            axiClk         => axilClk,                          -- [in]
            axiRst         => axilRst,                          -- [in]
            axiReadMaster  => locAxilReadMasters(i),            -- [in]
            axiReadSlave   => locAxilReadSlaves(i),             -- [out]
            axiWriteMaster => locAxilWriteMasters(i),           -- [in]
            axiWriteSlave  => locAxilWriteSlaves(i),            -- [out]
            clk            => timingRxClk125,                   -- [in]
--          en             => en,              -- [in]
--          we             => we,              -- [in]
            rst            => timingRxRst125,                   -- [in]
            addr           => timingRxData.rowNum(5 downto 0),  -- [in]
--         din            => din,             -- [in]
            dout           => ramDout(i));                      -- [out]
   end generate GEN_AXIL_RAM;

   U_AxiDualPortRam_1 : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => 3,
         DATA_WIDTH_G     => 16)
      port map (
         axiClk         => axilClk,                 -- [in]
         axiRst         => axilRst,                 -- [in]
         axiReadMaster  => locAxilReadMasters(8),   -- [in]
         axiReadSlave   => locAxilReadSlaves(8),    -- [out]
         axiWriteMaster => locAxilWriteMasters(8),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(8),   -- [out]
         clk            => timingRxClk125,          -- [in]
         rst            => timingRxRst125,          -- [in]
         addr           => (others => '0'),         -- [in]
         dout           => open,                    -- [out]
         axiWrValid     => overrideWrValid,         -- [out]
         axiWrAddr      => overrideWrAddr,          -- [out]
         axiWrData      => overrideWrData);         -- [out]

   comb : process (overrideWrAddr, overrideWrData, overrideWrValid, r, ramDout, timingRxData,
                   timingRxRst125) is
      variable v : RegType;
   begin
      v := r;

      v.dacWrt := (others => '0');
      v.dacClk := (others => '0');
--      v.dacSel := (others => '0');

      case r.state is
         when WAIT_ROW_STROBE_S =>
            v.dacNum := (others => '0');
            if (timingRxData.rowStrobe = '1') then
               v.state := DATA_S;
            end if;

            if (overrideWrValid = '1') then
               v.dacDb  := overrideWrData(13 downto 0);
               v.dacNum := overrideWrAddr;
               v.state  := OVER_SEL_S;
            end if;

         when DATA_S =>
            v.dacSel(conv_integer(r.dacNum(2 downto 1))) := r.dacNum(0);
            v.dacDb                                      := ramDout(conv_integer(r.dacNum(2 downto 1)))(13 downto 0);
            v.state                                      := WRITE_S;

         when WRITE_S =>
            v.dacWrt(conv_integer(r.dacNum(2 downto 1))) := '1';
            v.state                                      := WRITE_FALL_S;

         when WRITE_FALL_S =>
            -- Wait 1 cycle for write strobe to fall back to 0
            -- Might not be necessary but doesn't hurt
            v.dacNum := r.dacNum + 1;
            v.state  := DATA_S;
            if (r.dacNum = 7) then
               v.state := CLK_0_RISE_S;
            end if;

         when OVER_SEL_S =>
            v.dacSel(conv_integer(r.dacNum(2 downto 1))) := r.dacNum(0);
            v.state                                      := OVER_WRITE_S;

         when OVER_WRITE_S =>
            v.dacWrt(conv_integer(r.dacNum(2 downto 1))) := '1';
            v.dacNum                                     := "111";
            v.state                                      := WRITE_FALL_S;

         when CLK_0_RISE_S =>
            v.dacClk := (others => '1');
            v.state  := CLK_0_FALL_S;

         when CLK_0_FALL_S =>
            v.dacClk := (others => '0');
            v.state  := CLK_1_RISE_S;

         when CLK_1_RISE_S =>
            v.dacClk := (others => '1');
            v.dacSel := (others => '0');
            v.state  := WAIT_ROW_STROBE_S;


         when others => null;
      end case;

      if (timingRxRst125 = '1') then
         v := REG_INIT_C;
      end if;

      dacDb  <= r.dacDb;
      dacWrt <= r.dacWrt;
      dacSel <= r.dacSel;
      dacClk <= r.dacClk;

      rin <= v;

   end process comb;

   seq : process (timingRxClk125) is
   begin
      if (rising_edge(timingRxClk125)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

end architecture rtl;
