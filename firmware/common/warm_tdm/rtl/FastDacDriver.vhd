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
      timingClk125 : in sl;
      timingRst125 : in sl;

      timingData : in LocalTimingType;

      dacDb    : out slv14Array(3 downto 0);
      dacWrt   : out sl;
      dacClk   : out sl;
      dacSel   : out sl;
      dacReset : out sl := '0';
      dacSleep : out sl := '0';

      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType);

end entity FastDacDriver;

architecture rtl of FastDacDriver is

   constant XBAR_COFNIG_C : AxiLiteCrossbarMasterConfigArray(7 downto 0) := genAxiLiteConfig(8, AXIL_BASE_ADDR_G, 12, 8);

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(7 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(7 downto 0);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(7 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(7 downto 0);

   type StateType is (WAIT_ROW_STROBE_S, DATA_0_S, WRITE_0_S, DATA_1_S, WRITE_1_S);

   type RegType is record
      state  : StateType;
      dacDb  : slv14Array(3 downto 0);
      dacWrt : sl;
      dacClk : sl;
      dacSel : sl;
   end record RegType;

   constant REG_INIT_C : RegType := (
      state  => WAIT_ROW_STROBE_S,
      dacDb  => (others => (others => '0')),
      dacWrt => '0',
      dacClk => '0',
      dacSel => '0');

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal ramDout : slv16Array(7 downto 0);

begin

   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => 8,
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
            axiClk         => axilClk,                 -- [in]
            axiRst         => axilRst,                 -- [in]
            axiReadMaster  => locAxilReadMasters(i),   -- [in]
            axiReadSlave   => locAxilReadSlaves(i),    -- [out]
            axiWriteMaster => locAxilWriteMasters(i),  -- [in]
            axiWriteSlave  => locAxilWriteSlaves(i),   -- [out]
            clk            => timingClk125,            -- [in]
--          en             => en,              -- [in]
--          we             => we,              -- [in]
            rst            => timingRst125,            -- [in]
            addr           => timingData.rowNum,                  -- [in]
--         din            => din,             -- [in]
            dout           => ramDout(i));                 -- [out]
   end generate GEN_AXIL_RAM;


   comb : process (r, ramDout, timingData, timingRst125) is
      variable v : RegType;
   begin
      v := r;

      v.dacWrt := '0';
      v.dacClk := '0';
      case r.state is
         when WAIT_ROW_STROBE_S =>
            if (timingData.rowStrobe = '1') then
               v.state := DATA_0_S;
            end if;
         when DATA_0_S =>
            v.dacSel := '0';
            for i in 3 downto 0 loop
               v.dacDb(i) := ramDout(i*2)(13 downto 0);
            end loop;
            v.state := WRITE_0_S;
         when WRITE_0_S =>
            v.dacWrt := '1';
            v.state  := DATA_1_S;
         when DATA_1_S =>
            v.dacSel := '1';
            for i in 3 downto 0 loop
               v.dacDb(i) := ramDout(i*2+1)(13 downto 0);
            end loop;
            v.state := WRITE_1_S;
         when WRITE_1_S =>
            v.dacWrt := '1';
            v.dacClk := '1';
            v.state  := WAIT_ROW_STROBE_S;
         when others => null;
      end case;

      if (timingRst125 = '1') then
         v := REG_INIT_C;
      end if;

      dacDb  <= r.dacDb;
      dacWrt <= r.dacWrt;
      dacSel <= r.dacSel;
      dacClk <= r.dacClk;

      rin <= v;

   end process comb;

   seq : process (timingClk125) is
   begin
      if (rising_edge(timingClk125)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

end architecture rtl;
