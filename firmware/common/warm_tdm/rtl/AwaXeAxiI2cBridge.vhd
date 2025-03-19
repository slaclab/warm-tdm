-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Maps a number of I2C devices on an I2C bus onto an AXI Bus.
-------------------------------------------------------------------------------
-- This file is part of 'SLAC Firmware Standard Library'.
-- It is subject to the license terms in the LICENSE.txt file found in the
-- top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of 'SLAC Firmware Standard Library', including this file,
-- may be copied, modified, propagated, or distributed except according to
-- the terms contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;


library surf;
use surf.StdRtlPkg.all;
use surf.AxiLitePkg.all;
use surf.I2cPkg.all;

entity AwaXeAxiI2cBridge is

   generic (
      TPD_G           : time    := 1 ns;
      SIMULATION_G    : boolean := false;
      I2C_SCL_FREQ_G  : real    := 100.0E+3;    -- units of Hz
      I2C_MIN_PULSE_G : real    := 100.0E-9;    -- units of seconds
      AXIL_CLK_FREQ_G : real    := 156.25E+6);  -- units of Hz
   port (
      axilClk : in sl;
      axilRst : in sl;

      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType;

      sda : inout sl;
      scl : inout sl);

end entity AwaXeAxiI2cBridge;

architecture rtl of AwaXeAxiI2cBridge is

   constant I2C_SCL_5xFREQ_C : real    := 5.0 * I2C_SCL_FREQ_G;
   constant PRESCALE_C       : natural := (getTimeRatio(AXIL_CLK_FREQ_G, I2C_SCL_5xFREQ_C)) - 1;
   constant FILTER_C         : natural := natural(AXIL_CLK_FREQ_G * I2C_MIN_PULSE_G) + 1;
   constant TIMOUT_COUNT_C : integer := ite(SIMULATION_G, 12500, 12500000);

   type StateType is (WAIT_AXIL_S, START_ACK_S, WR_ACK_S, RD_ACK_S);

   type RegType is record
      state          : StateType;
      startup        : sl;
      axilReadSlave  : AxiLiteReadSlaveType;
      axilWriteSlave : AxiLiteWriteSlaveType;
      i2cMasterIn    : I2cMasterInType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      state          => WAIT_AXIL_S,
      startup        => '0',
      axilReadSlave  => AXI_LITE_READ_SLAVE_INIT_C,
      axilWriteSlave => AXI_LITE_WRITE_SLAVE_INIT_C,
      i2cMasterIn    => (
         enable      => '0',
         prescale    => (others => '0'),
         filter      => (others => '0'),
         txnReq      => '0',
         stop        => '0',
         op          => '0',
         busReq      => '0',
         addr        => (others => '0'),
         tenbit      => '0',
         wrValid     => '0',
         wrData      => (others => '0'),
         rdAck       => '0'));

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal i2cMasterOut : I2cMasterOutType;

   signal i2ci : i2c_in_type;
   signal i2co : i2c_out_type;

   signal startup : sl;

begin

   U_PwrUpRst_1 : entity surf.PwrUpRst
      generic map (
         TPD_G          => TPD_G,
         OUT_POLARITY_G => '0',
         DURATION_G     => ite(SIMULATION_G, 12500, 125000000))
      port map (
         arst   => axilRst,             -- [in]
         clk    => axilClk,             -- [in]
         rstOut => startup);            -- [out]

   -------------------------------------------------------------------------------------------------
   -- Main Comb Process
   -------------------------------------------------------------------------------------------------
   comb : process (axilReadMaster, axilRst, axilWriteMaster, i2cMasterOut, r, startup) is
      variable v          : RegType;
      variable axilResp   : slv(1 downto 0);
      variable axilStatus : AxiLiteStatusType;

   begin
      v := r;

      v.startup := startup;

      v.i2cMasterIn.enable   := '1';
      v.i2cMasterIn.prescale := (others => '0');
      v.i2cMasterIn.filter   := (others => '0');  -- Not using dynamic filtering
      v.i2cMasterIn.tenbit   := '0';

      axiSlaveWaitTxn(axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave, axilStatus);

      case r.state is
         when WAIT_AXIL_S =>
            v.i2cMasterIn.txnReq := '0';
            v.i2cMasterIn.rdAck  := '0';
            v.i2cMasterIn.wrValid := '0';
            if (axilStatus.writeEnable = '1' and i2cMasterOut.wrAck = '0') then
               v.i2cMasterIn.txnReq  := '1';
               v.i2cMasterIn.op      := '1';
               v.i2cMasterIn.stop    := '1';
               v.i2cMasterIn.addr    := "000" & axilWriteMaster.awaddr(5 downto 2) & axilWriteMaster.awaddr(8 downto 6);
               v.i2cMasterIn.wrValid := '1';
               v.i2cMasterIn.wrData  := axilWriteMaster.wdata(7 downto 0);
               v.state               := WR_ACK_S;
            end if;

            -- Send a dummy transaction after power up to unstick the bus
            if (startup = '1' and r.startup = '0') then
               v.i2cMasterIn.txnReq  := '1';
               v.i2cMasterIn.op      := '1';
               v.i2cMasterIn.stop    := '1';
               v.i2cMasterIn.addr    := "0000000000";
               v.i2cMasterIn.wrValid := '1';
               v.i2cMasterIn.wrData  := "00000000";
--               v.state               := START_ACK_S;
            end if;

            if (axilStatus.readEnable = '1' and i2cMasterOut.rdValid = '0') then
               v.i2cMasterIn.txnReq := '1';
               v.i2cMasterIn.op     := '0';
               v.i2cMasterIn.stop   := '1';
               v.i2cMasterIn.addr   := "000" & axilReadMaster.araddr(5 downto 2) & axilReadMaster.araddr(8 downto 6);
               v.state              := RD_ACK_S;
            end if;

         when START_ACK_S =>
            -- Don't care about response
            v.i2cMasterIn.txnReq := '0';
            if (i2cMasterOut.wrAck = '1') then
               v.i2cMasterIn.wrValid := '0';
               v.i2cMasterIn.txnReq  := '0';
               v.state               := WAIT_AXIL_S;
            end if;

         when WR_ACK_S =>

            if (i2cMasterOut.wrAck = '1') then
               v.i2cMasterIn.wrValid := '0';
               v.i2cMasterIn.txnReq  := '0';
               axilResp              := ite(i2cMasterOut.txnError = '1', AXI_RESP_SLVERR_C, AXI_RESP_OK_C);
               axiSlaveWriteResponse(v.axilWriteSlave, axilResp);
               v.state               := WAIT_AXIL_S;
            end if;

         when RD_ACK_S =>
            v.i2cMasterIn.txnReq := '0';
            if (i2cMasterOut.rdValid = '1') then
               v.i2cMasterIn.rdAck               := '1';
               v.i2cMasterIn.txnReq              := '0';
               v.axilReadSlave.rdata(7 downto 0) := i2cMasterOut.rdData;
               axilResp                          := ite(i2cMasterOut.txnError = '1', AXI_RESP_SLVERR_C, AXI_RESP_OK_C);
               axiSlaveReadResponse(v.axilReadSlave, axilResp);
               v.state                           := WAIT_AXIL_S;
            end if;

      end case;


      ----------------------------------------------------------------------------------------------
      -- Reset
      ----------------------------------------------------------------------------------------------
      if (axilRst = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      axilReadSlave  <= r.axilReadSlave;
      axilWriteSlave <= r.axilWriteSlave;

   end process comb;

-------------------------------------------------------------------------------------------------
-- Sequential Process
-------------------------------------------------------------------------------------------------
   seq : process (axilClk) is
   begin
      if (rising_edge(axilClk)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

   i2cMaster_1 : entity surf.I2cMaster
      generic map (
         TPD_G                => TPD_G,
         OUTPUT_EN_POLARITY_G => 0,
         PRESCALE_G           => PRESCALE_C,
         FILTER_G             => FILTER_C,
         DYNAMIC_FILTER_G     => 0)
      port map (
         clk          => axilClk,
         srst         => axilRst,
         arst         => '0',
         i2cMasterIn  => r.i2cMasterIn,
         i2cMasterOut => i2cMasterOut,
         i2ci         => i2ci,
         i2co         => i2co);

   IOBUF_SCL : entity surf.IoBufWrapper
      port map (
         O  => i2ci.scl,                -- Buffer output
         IO => scl,                     -- Buffer inout port (connect directly to top-level port)
         I  => i2co.scl,                -- Buffer input
         T  => i2co.scloen);            -- 3-state enable input, high=input, low=output

   IOBUF_SDA : entity surf.IoBufWrapper
      port map (
         O  => i2ci.sda,                -- Buffer output
         IO => sda,                     -- Buffer inout port (connect directly to top-level port)
         I  => i2co.sda,                -- Buffer input
         T  => i2co.sdaoen);            -- 3-state enable input, high=input, low=output

end architecture rtl;

