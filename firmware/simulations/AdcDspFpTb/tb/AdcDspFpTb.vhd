-- Warm TDM; subject to the license terms in the repository's LICENSE.txt.
-- Native VHDL assertions: binds the generated FP cores under Vivado/VCS/XSIM.
-- Also run with explicit arithmetic models under GHDL to check the bench itself.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library surf;
use surf.StdRtlPkg.all;
use surf.AxiLitePkg.all;
library warm_tdm;
use warm_tdm.TimingPkg.all;

entity AdcDspFpTb is end entity;
architecture rtl of AdcDspFpTb is
   signal clk : sl := '0';
   signal rst : sl := '1';
   signal timing : LocalTimingType := LOCAL_TIMING_INIT_C;
   signal valid : sl := '0';
   signal error : slv(31 downto 0) := (others => '0');
   signal row : slv(7 downto 0) := (others => '0');
   signal seed : slv(13 downto 0) := (others => '0');
   signal stall : sl := '0';
   signal fail : sl := '0';
   signal wrValid : sl;
   signal wrAddr : slv(7 downto 0);
   signal wrData : slv(31 downto 0);
   signal wm : AxiLiteWriteMasterType := AXI_LITE_WRITE_MASTER_INIT_C;
   signal ws : AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_INIT_C;
   signal rm : AxiLiteReadMasterType := AXI_LITE_READ_MASTER_INIT_C;
   signal rs : AxiLiteReadSlaveType := AXI_LITE_READ_SLAVE_INIT_C;
   type IntArray is array (0 to 255) of integer;
   signal addresses, values : IntArray := (others => 0);
   signal writes : natural := 0;
begin
   clk <= not clk after 4 ns;
   U_DUT : entity warm_tdm.AdcDspFpCocotbWrapper
      generic map (ROW_ADDR_BITS_G => 3, INVERT_SQ1FB_G => true)
      port map (
         clk => clk, rst => rst, TIMING_RX_DATA => toSlv(timing),
         ACCUM_VALID => valid, ACCUM_ERROR => error, ACCUM_NUM_SAMPLES => X"01",
         ACCUM_ROW_INDEX => row, ACCUM_SQ1FB_DAC => seed,
         DAC_STALL => stall, DAC_FAIL => fail, DAC_WR_VALID => wrValid,
         DAC_WR_ADDR => wrAddr, DAC_WR_DATA => wrData,
         DEBUG_TDATA => open, DEBUG_TVALID => open, DEBUG_TLAST => open,
         PID_TDATA => open, PID_TVALID => open, PID_TKEEP => open, PID_TID => open,
         S_AXIL_AWADDR => wm.awaddr(15 downto 0), S_AXIL_AWPROT => wm.awprot,
         S_AXIL_AWVALID => wm.awvalid, S_AXIL_AWREADY => ws.awready,
         S_AXIL_WDATA => wm.wdata, S_AXIL_WSTRB => wm.wstrb,
         S_AXIL_WVALID => wm.wvalid, S_AXIL_WREADY => ws.wready,
         S_AXIL_BRESP => ws.bresp, S_AXIL_BVALID => ws.bvalid, S_AXIL_BREADY => wm.bready,
         S_AXIL_ARADDR => rm.araddr(15 downto 0), S_AXIL_ARPROT => rm.arprot,
         S_AXIL_ARVALID => rm.arvalid, S_AXIL_ARREADY => rs.arready,
         S_AXIL_RDATA => rs.rdata, S_AXIL_RRESP => rs.rresp,
         S_AXIL_RVALID => rs.rvalid, S_AXIL_RREADY => rm.rready);

   monitor : process
   begin
      wait until rising_edge(clk);
      wait for 2 ns;
      if rst = '0' and wrValid = '1' then
         addresses(writes) <= to_integer(unsigned(wrAddr));
         values(writes) <= to_integer(signed(wrData(13 downto 0) xor "01111111111111"));
         writes <= writes + 1;
      end if;
   end process;

   test : process
      procedure clocks(n : positive) is
      begin
         for k in 1 to n loop
            wait until rising_edge(clk);
            wait for 2 ns;
         end loop;
      end procedure;
      procedure put(addr : natural; data : slv(31 downto 0)) is
      begin
         axiLiteBusSimWrite(clk, wm, ws, toSlv(addr, 32), data, true);
      end procedure;
      procedure expect(addr : natural; expected : slv(31 downto 0)) is
         variable data : slv(31 downto 0);
      begin
         axiLiteBusSimRead(clk, rm, rs, toSlv(addr, 32), data, true);
         assert data = expected report "Register " & integer'image(addr) &
            " expected " & to_hstring(expected) & " got " & to_hstring(data) severity failure;
      end procedure;
      procedure idle is
         variable data : slv(31 downto 0);
      begin
         for k in 0 to 100 loop
            axiLiteBusSimRead(clk, rm, rs, X"00000034", data, true);
            if data(1 downto 0) = "00" then return; end if;
         end loop;
         assert false report "Controller/DAC queue did not drain" severity failure;
      end procedure;
      procedure visit(e : integer := 0; r : natural := 0; s : integer := 0) is
      begin
         error <= slv(to_signed(e, 32));
         row <= toSlv(r, 8);
         seed <= slv(to_signed(s, 14)) xor "01111111111111";
         valid <= '1';
         clocks(1);
         valid <= '0';
         clocks(100);
      end procedure;
      procedure trial(f : slv(31 downto 0); j, d : integer) is
         variable previous : natural;
      begin
         put(16#3000#, f);
         previous := writes;
         visit;
         idle;
         expect(16#3000#, f);
         expect(16#4000#, slv(to_signed(j, 32)));
         assert writes = previous + 1 and values(writes-1) = d
            report "Wrong rounded/wrapped DAC command" severity failure;
      end procedure;
      variable previous : natural;
   begin
      clocks(8);
      rst <= '0';
      timing.running <= '1';
      clocks(8);
      put(0, X"00000001");
      idle;
      -- Zero gain seeds, including negative feedback and a different row.
      visit(s => 377);
      expect(16#3000#, X"43BC8000");
      visit(r => 7, s => -1234);
      expect(16#301C#, X"C49A4000");
      -- Nearest-even DAC conversion (no wrapping), both signs and adjacent values.
      trial(X"3F000000", 0, 0);  -- +0.5
      trial(X"BF000000", 0, 0);  -- -0.5
      trial(X"3F002000", 0, 1);  -- +0.50048828125
      trial(X"BF002000", 0, -1);
      trial(X"3FC00000", 0, 2);  -- +1.5
      trial(X"C0200000", 0, -2); -- -2.5
      -- Centered wrapping, ties and multiple quanta. R=1024, inverse=2^-10.
      put(16#40#, X"44800000");
      put(16#44#, X"3A800000");
      trial(X"44000000", 0, 512);
      trial(X"C4000000", 0, -512);
      trial(X"44002000", 1, -512); -- +512.5
      trial(X"C4002000", -1, 512);
      trial(X"44C00000", 2, -512); -- +1536
      trial(X"C4C00000", -2, 512);
      trial(X"48800004", 256, 0); -- 256*1024 + 0.125, retain fraction
      trial(X"C8800004", -256, 0);
      -- A masked row holds full feedback, sum and quotient.
      put(16#60#, X"FFFFFFFE");
      put(4, X"3F800000");
      previous := writes;
      visit(e => 99);
      expect(16#3000#, X"C8800004");
      expect(16#4000#, X"FFFFFF00");
      assert writes = previous report "Masked DAC write" severity failure;
      put(16#60#, X"FFFFFFFF");
      -- I changes clear S while preserving unwrapped F and J.
      put(8, X"3E800000");
      idle;
      expect(16#2000#, X"00000000");
      expect(16#3000#, X"C8800004");
      expect(16#4000#, X"FFFFFF00");
      put(8, X"80000000");
      idle;
      expect(8, X"00000000");
      -- Clipping with wraps disabled tracks the rails and reverses immediately.
      put(16#40#, X"00000000"); -- stale inverse must not enable wrapping
      put(16#3000#, X"00000000");
      visit(e => 9000);
      expect(16#3000#, X"45FFF800");
      assert values(writes-1) = 8191 severity failure;
      visit(e => -1);
      expect(16#3000#, X"45FFF000");
      put(16#3000#, X"00000000");
      visit(e => -9000);
      expect(16#3000#, X"C6000000");
      visit(e => 1);
      expect(16#3000#, X"C5FFF800");
      -- Stalled, distinct row/value requests arrive exactly once in order.
      put(16#30#, X"00000001");
      idle;
      previous := writes;
      stall <= '1';
      for k in 0 to 4 loop visit(e => k+1, r => k, s => 100*k); end loop;
      assert writes = previous severity failure;
      stall <= '0';
      idle;
      assert writes = previous+5 report "Lost or duplicate queued write" severity failure;
      for k in 0 to 4 loop
         assert addresses(previous+k) = k and values(previous+k) = 101*k+1
            report "Queued write changed or reordered" severity failure;
      end loop;
      expect(16#88#, X"00000000");
      fail <= '1';
      visit;
      idle;
      expect(16#8C#, X"00000001");
      report "AdcDspFpTb PASSED" severity note;
      std.env.finish;
      wait;
   end process;
   watchdog : process
   begin
      wait for 1 ms;
      assert false report "AdcDspFpTb timed out" severity failure;
   end process;
end architecture;
