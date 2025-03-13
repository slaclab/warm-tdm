-------------------------------------------------------------------------------
-- Title      : 
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
use warm_tdm.TimingPkg.all;

entity PwrSync is

   generic (
      TPD_G : time := 1 ns);
   port (
      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;

      -- Local RX timing data
      timingRxClk  : out sl;
      timingRxRst  : out sl;
      timingRxData : out LocalTimingType;

      -- Output ports
      pwrSyncA : out sl := '0';
      pwrSyncB : out sl := '0';
      pwrSyncC : out sl := '1');

end entity PwrSync;

architecture rtl of PwrSync is

   constant DIV_CLK_COUNT_C : integer         := integer(125.0e6 / (2*2000000))+1;
   constant PWR_SYNC_LOW_C  : slv(1 downto 0) := "00";
   constant PWR_SYNC_HIGH_C : slv(1 downto 0) := "01";
   constant PWR_SYNC_OSC_C  : SLV(1 downto 0) := "10";

   type RegType is record
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

   signal syncAxilWriteMaster : AxiLiteWriteMasterType;
   signal syncAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal syncAxilReadMaster  : AxiLiteReadMasterType;
   signal syncAxilReadSlave   : AxiLiteReadSlaveType;


begin

   U_AxiLiteAsync_1 : entity surf.AxiLiteAsync
      generic map (
         TPD_G         => TPD_G,
         PIPE_STAGES_G => 0)
      port map (
         sAxiClk         => axilClk,              -- [in]
         sAxiClkRst      => axilRst,              -- [in]
         sAxiReadMaster  => axilReadMaster,       -- [in]
         sAxiReadSlave   => axilReadSlave,        -- [out]
         sAxiWriteMaster => axilWriteMaster,      -- [in]
         sAxiWriteSlave  => axilWriteSlave,       -- [out]
         mAxiClk         => timingRxClk,          -- [in]
         mAxiClkRst      => timingRxRst,          -- [in]
         mAxiReadMaster  => syncAxilReadMaster,   -- [out]
         mAxiReadSlave   => syncAxilReadSlave,    -- [in]
         mAxiWriteMaster => syncAxilWriteMaster,  -- [out]
         mAxiWriteSlave  => syncAxilWriteSlave);  -- [in]



   comb : process (axilReadMaster, axilWriteMaster, r, timingRxData, timingRxRst) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndpointType;
   begin
      v := r;

      v.resetCounter := '0';

      --------------------
      -- AXI Lite
      --------------------
      axiSlaveWaitTxn(axilEp, axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"04", 0, v.pwrSyncACfg);
      axiSlaveRegister(axilEp, X"08", 0, v.pwrSyncBCfg);
      axiSlaveRegister(axilEp, X"0C", 0, v.pwrSyncCCfg);
      axiSlaveRegister(axilEp, X"10", 0, v.syncPeriodDiv2);
      axiWrDetect(axilEp, X"10", v.resetCounter);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);


      -- Run the clock divide counter
      v.clkCount := r.clkCount + 1;
      if (r.clkCount = r.syncPeriodDiv2 - 1 or v.resetCounter = '1' or timingRxData.startRun = '1') then
         v.clkCount := (others => '0');
      end if;


      if (r.pwrSyncACfg = PWR_SYNC_HIGH_C) then
         v.pwrSyncA := '0';             -- Don't allow pwrSyncA set high
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

      if (timingRxRst = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      syncAxilWriteSlave <= r.axilWriteSlave;
      syncAxilReadSlave  <= r.axilReadSlave;

      pwrSyncA <= r.pwrSyncA;
      pwrSyncB <= r.pwrSyncB;
      pwrSyncC <= r.pwrSyncC;

   end process;

   seq : process (timingRxClk) is
   begin
      if (rising_edge(timingRxClk)) then
         r <= rin after TPD_G;
      end if;
   end process;

end architecture rtl;
