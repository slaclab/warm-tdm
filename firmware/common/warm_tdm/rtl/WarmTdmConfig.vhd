-------------------------------------------------------------------------------
-- Title      : Warm TDM Configuration Registers
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
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.WarmTdmPkg.all;

entity WarmTdmConfig is

   generic (
      TPD_G           : time := 1 ns;
      AXIL_CLK_FREQ_G : real := 125.0e6);
   port (
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;

      -- Status inputs
      timingRxClkLocked : in sl;

      -- Output ports
      anaPwrEn : out sl              := '1';
      pwrSyncA : out sl              := '0';
      pwrSyncB : out sl              := '0';
      pwrSyncC : out sl              := '1';
      ampPdB   : out slv(7 downto 0) := (others => '1')

      );

end entity WarmTdmConfig;

architecture rtl of WarmTdmConfig is

   constant DIV_CLK_COUNT_C : integer         := integer(AXIL_CLK_FREQ_G / (2*2000000))+1;
   constant PWR_SYNC_LOW_C  : slv(1 downto 0) := "00";
   constant PWR_SYNC_HIGH_C : slv(1 downto 0) := "01";
   constant PWR_SYNC_OSC_C  : SLV(1 downto 0) := "10";

   type RegType is record
      anaPwrEn       : sl;
      anaPwrEnAxi    : sl;
      pwrSyncACfg    : slv(1 downto 0);
      pwrSyncBCfg    : slv(1 downto 0);
      pwrSyncCCfg    : slv(1 downto 0);
      pwrSyncA       : sl;
      pwrSyncB       : sl;
      pwrSyncC       : sl;
      syncPeriodDiv2 : slv(31 downto 0);
      clkCount       : slv(31 downto 0);
      resetCounter   : sl;
      axilWriteSlave : AxiLiteWriteSlaveType;
      axilReadSlave  : AxiLiteReadSlaveType;
   end record;

   constant REG_INIT_C : RegType := (
      anaPwrEn       => '0',
      anaPwrEnAxi    => '1',
      pwrSyncACfg    => PWR_SYNC_LOW_C,
      pwrSyncBCfg    => PWR_SYNC_LOW_C,
      pwrSyncCCfg    => PWR_SYNC_HIGH_C,
      pwrSyncA       => '0',
      pwrSyncB       => '0',
      pwrSyncC       => '1',
      syncPeriodDiv2 => toSlv(DIV_CLK_COUNT_C, 32),
      clkCount       => (others => '0'),
      resetCounter   => '0',
      axilWriteSlave => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave  => AXI_LITE_READ_SLAVE_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal timingRxClkLockedSync : sl;

begin

   U_Synchronizer_1 : entity surf.Synchronizer
      generic map (
         TPD_G => TPD_G)
      port map (
         clk     => axilClk,                 -- [in]
         rst     => axilRst,                 -- [in]
         dataIn  => timingRxClkLocked,       -- [in]
         dataOut => timingRxClkLockedSync);  -- [out]

   comb : process (axilReadMaster, axilRst, axilWriteMaster, r, timingRxClkLockedSync) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndpointType;
   begin
      v := r;

      v.resetCounter := '0';

      --------------------
      -- AXI Lite
      --------------------
      axiSlaveWaitTxn(axilEp, axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.anaPwrEnAxi);
      axiSlaveRegisterR(axilEp, X"00", 1, r.anaPwrEn);
      axiSlaveRegister(axilEp, X"04", 0, v.pwrSyncACfg);
      axiSlaveRegister(axilEp, X"08", 0, v.pwrSyncBCfg);
      axiSlaveRegister(axilEp, X"0C", 0, v.pwrSyncCCfg);
      axiSlaveRegister(axilEp, X"10", 0, v.syncPeriodDiv2);
      axiWrDetect(axilEp, X"10", v.resetCounter);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      -- Turn on analog power on startup once rx clock is locked
      if (r.anaPwrEn = '0' and r.anaPwrEnAxi = '1' and timingRxClkLockedSync = '1') then
         v.anaPwrEn := '1';
      end if;

      if (r.anaPwrEnAxi = '0') then
         v.anaPwrEn := '0';
      end if;


      -- Run the clock divide counter
      v.clkCount := r.clkCount + 1;
      if (r.clkCount = r.syncPeriodDiv2 - 1 or v.resetCounter = '1') then
         v.clkCount := (others => '0');
      end if;


      if (r.pwrSyncACfg = PWR_SYNC_HIGH_C) then
         v.pwrSyncA := '1';
      elsif (r.pwrSyncACfg = PWR_SYNC_LOW_C) then
         v.pwrSyncA := '0';
      elsif (r.pwrSyncACfg = PWR_SYNC_OSC_C) then
         if (r.clkCount = r.syncPeriodDiv2 - 1) then
            v.pwrSyncA := not r.pwrSyncA;
         end if;
      end if;

      if (r.pwrSyncBCfg = PWR_SYNC_HIGH_C) then
         v.pwrSyncB := '1';
      elsif (r.pwrSyncBCfg = PWR_SYNC_LOW_C) then
         v.pwrSyncB := '0';
      elsif (r.pwrSyncBCfg = PWR_SYNC_OSC_C) then
         if (r.clkCount = r.syncPeriodDiv2 - 1) then
            v.pwrSyncB := not r.pwrSyncB;
         end if;
      end if;

      if (r.pwrSyncCCfg = PWR_SYNC_HIGH_C) then
         v.pwrSyncC := '1';
      elsif (r.pwrSyncCCfg = PWR_SYNC_LOW_C) then
         v.pwrSyncC := '0';
      elsif (r.pwrSyncCCfg = PWR_SYNC_OSC_C) then
         if (r.clkCount = r.syncPeriodDiv2 - 1) then
            v.pwrSyncC := not r.pwrSyncC;
         end if;
      end if;

      if (axilRst = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      axilWriteSlave <= r.axilWriteSlave;
      axilReadSlave  <= r.axilReadSlave;

      pwrSyncA <= r.pwrSyncA;
      pwrSyncB <= r.pwrSyncB;
      pwrSyncC <= r.pwrSyncC;
      anaPwrEn <= r.anaPwrEn;

   end process;

   seq : process (axilClk) is
   begin
      if (rising_edge(axilClk)) then
         r <= rin after TPD_G;
      end if;
   end process;

end architecture rtl;
