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

entity RowDacDriver is

   generic (
      TPD_G            : time             := 1 ns;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := (others => '0'));

   port (
      timingRxClk125 : in sl;
      timingRxRst125 : in sl;

      timingRxData : in LocalTimingType;

      dacDb    : out slv(13 downto 0);
      dacWrt   : out slv(15 downto 0);
      dacClk   : out slv(15 downto 0);
      dacSel   : out slv(15 downto 0);
      dacReset : out slv(15 downto 0) := (others => '0');

      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType);

end entity RowDacDriver;

architecture rtl of RowDacDriver is

   constant NUM_AXIL_C : integer := 2;

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
      startup  : sl;
      mode     : sl;
      rowMsb   : sl;
      state    : StateType;
      rowNum   : slv(5 downto 0);
      dacDb    : slv(13 downto 0);
      dacWrt   : slv(15 downto 0);
      dacClk   : slv(15 downto 0);
      dacSel   : slv(15 downto 0);
      dacReset : slv(15 downto 0);
   end record RegType;

   constant REG_INIT_C : RegType := (
      startup  => '1',
      mode     => TIMING_MODE_C,
      rowMsb   => '0',
      state    => WAIT_ROW_STROBE_S,
      rowNum   => (others => '0'),
      dacDb    => (others => '0'),
      dacWrt   => (others => '0'),
      dacClk   => (others => '0'),
      dacSel   => (others => '0'),
      dacReset => (others => '0'));

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal fasOnDout : slv(15 downto 0);

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


   U_AxiDualPortRam_FAS_ON : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => 5,
         DATA_WIDTH_G     => 16,
         INIT_G           => X"2000")                        -- init to midscale for DAC
      port map (
         axiClk         => axilClk,                          -- [in]
         axiRst         => axilRst,                          -- [in]
         axiReadMaster  => locAxilReadMasters(1),            -- [in]
         axiReadSlave   => locAxilReadSlaves(1),             -- [out]
         axiWriteMaster => locAxilWriteMasters(1),           -- [in]
         axiWriteSlave  => locAxilWriteSlaves(1),            -- [out]
         clk            => timingRxClk125,                   -- [in]
--          en             => en,              -- [in]
--          we             => we,              -- [in]
         rst            => timingRxRst125,                   -- [in]
         addr           => timingRxData.rowNum(4 downto 0),  -- [in]
--         din            => din,             -- [in]
         dout           => fasOnDout,                        -- [out]
         axiWrValid     => overrideWrValid,                  -- [out]
         axiWrAddr      => overrideWrAddr,                   -- [out]
         axiWrData      => overrideWrData);                  -- [out]


   comb : process (fasOnDout, locAxilReadMasters, locAxilWriteMasters, overrideWrData,
                   overrideWrValid, r, timingRxData, timingRxRst125) is
      variable v       : RegType;
      variable dacInt  : integer range 0 to 7;
      variable dacChip : integer range 0 to 3;
   begin
      v := r;

      ----------------------------------------------------------------------------------------------
      -- Configuration Registers
      ----------------------------------------------------------------------------------------------
      axiSlaveWaitTxn(axilEp, locAxilWriteMasters(0), locAxilReadMasters(0), v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.mode);
      axiSlaveRegister(axilEp, X"04", 0, v.rowMsb);
      axiSlaveRegister(axilEp, X"08", 0, v.dacReset);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      dacInt  := conv_integer(r.rowNum(4 downto 0));
      dacChip := conv_integer(r.rowNum(4 downto 1));


      v.dacWrt := (others => '0');
      v.dacClk := (others => '0');

      case r.state is
         when IDLE_S =>
            v.rowNum := (others => '0');

            -- In timing mode, wait for row strobe to set next RS DAC
            if (r.mode = TIMING_MODE_C) then
               if (timingRxData.rowStrobe = '1' or r.startup = '1') then
                  v.startup := '0';
                  v.rowNum = timingRxData.rowNum(5 downto 0);
                  v.state   := DATA_S;
               end if;
            elsif (r.mode = MANUAL_MODE_C) then
               if (overrideWrValid = '1') then
                  dacDb   := overrideWrData(13 downto 0);
                  v.rowNum = r.rowMsb & overrideWrAddr;
                  v.state := OVER_SEL_S;
               end if;
            end if;

         when CLEAR_ALL_DATA_0_S =>
            v.dacDb  := (others => '0');
            v.dacSel := (others => '0');
            v.state  := CLEAR_ALL_WRITE_0_S;

         when CLEAR_ALL_WRITE_0_S =>
            -- Write 0 to all dacs channel 0
            v.dacWrt := (others => '1');
            v.state  := CLEAR_ALL_DATA_1_S;

         when CLEAR_ALL_WRITE_0_FALL_S =>
            -- Allow a cycle for wrt to fall
            v.state := CLEAR_ALL_DATA_1_S;

         when CLEAR_ALL_DATA_1_S =>
            v.dacDb  := (others => '0');
            v.dacSel := (others => '1');
            v.state  := CLEAR_ALL_WRITE_1_S;

         when CLEAR_ALL_WRITE_1_S =>
            v.dacWrt := (others => '1');

         when CLEAR_ALL_WRITE_1_FALL_S =>
            -- Allow a cycle for wrt to fall
            v.state := DATA_S;

         when DATA_S =>
            v.dacSel(dacChip) := not r.rowNum(0);
            v.dacDb           := fasOnDout(13 downto 0);
            v.state           := WRITE_S;

         when WRITE_S =>
            -- Write the DAC if row is on this board
            if (r.rowNum(5) = r.rowMsb) then
               v.dacWrt(dacChip) := '1';
            end if;
            v.state := WRITE_FALL_S;

         when WRITE_FALL_S =>
            -- Wait 1 cycle for wrt to fall
            v.state := CLK_0_RISE_S;

         when OVER_SEL_S =>
            v.dacSel(dacChip) := not r.rowNum(0);
            v.state           := OVER_WRITE_S;

         when OVER_WRITE_S =>
            v.dacWrt(dacChip) := '1';
            v.rowNum          := "111";
            v.state           := WRITE_FALL_S;

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

      dacDb    <= r.dacDb;
      dacWrt   <= r.dacWrt;
      dacSel   <= r.dacSel;
      dacClk   <= r.dacClk;
      dacReset <= r.dacReset;

      axilReadSlave(0)  <= r.axilReadSlave;
      axilWriteSlave(0) <= r.axilWriteSlave;

      rin <= v;

   end process comb;

   seq : process (timingRxClk125) is
   begin
      if (rising_edge(timingRxClk125)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

end architecture rtl;
