-------------------------------------------------------------------------------
-- This file is part of 'warm-tdm'. It is subject to the license terms in the
-- LICENSE.txt file found in the top-level directory of this distribution and at:
-- https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of 'warm-tdm', including this file, may be copied, modified,
-- propagated, or distributed except according to the terms of that license.
-------------------------------------------------------------------------------
-- Characterize queued replies at an unthrottled PGP receiver. This is a buffer
-- test, not a complete ring, SRP endpoint, GTX, or RSSI simulation.
-- The source represents responses to requests already accepted before pause.
-- Releasing the sink and sending fresh frames also checks post-loss framing.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
use surf.Pgp2bPkg.all;
use surf.AxiStreamPacketizer2Pkg.all;
entity RingRxBufferTb is
   generic (RX_DEPTH_G : positive := 8; BRIDGE_DEPTH_G : positive := 5;
            PAYLOAD_BYTES_G : positive := 4120; FRAMES_G : positive := 1;
            STALL_G : boolean := true; READY_G : boolean := false);
end entity;
architecture tb of RingRxBufferTb is
   constant CFG_C : AxiStreamConfigType := ssiAxiStreamConfig(8, tDestBits=>8);
   signal clk : sl := '0';
   signal ethClk : sl := '0';
   signal axisClk : sl := '0';
   signal rst : sl := '1';
   signal src, pkt, phy, rx, dep, ob : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal srcSl, pktSl, rxSl, depSl : AxiStreamSlaveType := AXI_STREAM_SLAVE_INIT_C;
   signal sinkSl : AxiStreamSlaveType := AXI_STREAM_SLAVE_INIT_C;
   signal ctrl : AxiStreamCtrlType;
   signal dbg : Packetizer2DebugType;
   signal byteCount, frameCount, overflowCount, errorCount, eofeCount : natural := 0;
   signal probeFrames, probeWords, pauseWords : natural := 0;
   signal recovery : boolean := false;
   signal seenPause : boolean := false;
begin
   process begin
      wait for 300 us;
      assert false report "Buffer test did not finish" severity failure;
   end process;
   clk <= not clk after 8 ns;
   axisClk <= not axisClk after 4 ns;
   ethClk <= not ethClk after 3.2 ns;
   rst <= '0' after 160 ns;
   packetizer : entity surf.AxiStreamPacketizer2
      generic map (CRC_MODE_G=>"NONE", MAX_PACKET_BYTES_G=>512, TDEST_BITS_G=>8)
      port map (axisClk=>clk, axisRst=>rst, rearbitrate=>open,
         sAxisMaster=>src, sAxisSlave=>srcSl, mAxisMaster=>pkt, mAxisSlave=>pktSl);
   serializer : entity surf.AxiStreamGearbox
      generic map (SLAVE_AXI_CONFIG_G=>CFG_C, MASTER_AXI_CONFIG_G=>SSI_PGP2B_CONFIG_C)
      port map (axisClk=>clk, axisRst=>rst, sAxisMaster=>pkt, sAxisSlave=>pktSl,
         mAxisMaster=>phy, mAxisSlave=>AXI_STREAM_SLAVE_FORCE_C);
   receiver : entity surf.PgpRxVcFifo
      generic map (ROGUE_SIM_EN_G=>READY_G, INT_PIPE_STAGES_G=>1, PIPE_STAGES_G=>0,
         VALID_THOLD_G=>64, VALID_BURST_MODE_G=>true, SYNTH_MODE_G=>"inferred",
         MEMORY_TYPE_G=>"block", GEN_SYNC_FIFO_G=>false,
         FIFO_ADDR_WIDTH_G=>RX_DEPTH_G, FIFO_PAUSE_THRESH_G=>192,
         PHY_AXI_CONFIG_G=>SSI_PGP2B_CONFIG_C, APP_AXI_CONFIG_G=>CFG_C)
      port map (pgpClk=>clk, pgpRst=>rst, rxlinkReady=>'1', pgpRxMaster=>phy,
         pgpRxCtrl=>ctrl, pgpRxSlave=>open, axisClk=>axisClk, axisRst=>rst,
         axisMaster=>rx, axisSlave=>rxSl);
   depacketizer : entity surf.AxiStreamDepacketizer2
      generic map (MEMORY_TYPE_G=>"bram", REG_EN_G=>false, CRC_MODE_G=>"NONE",
         TDEST_BITS_G=>8, INPUT_PIPE_STAGES_G=>0, OUTPUT_PIPE_STAGES_G=>0)
      port map (axisClk=>axisClk, axisRst=>rst, linkGood=>'1', debug=>dbg,
         sAxisMaster=>rx, sAxisSlave=>rxSl, mAxisMaster=>dep, mAxisSlave=>depSl);
   bridge : entity surf.AxiStreamFifoV2
      generic map (INT_PIPE_STAGES_G=>1, PIPE_STAGES_G=>0, SLAVE_READY_EN_G=>true,
         VALID_THOLD_G=>1, GEN_SYNC_FIFO_G=>false, SYNTH_MODE_G=>"inferred",
         MEMORY_TYPE_G=>"block", FIFO_ADDR_WIDTH_G=>BRIDGE_DEPTH_G,
         SLAVE_AXI_CONFIG_G=>CFG_C, MASTER_AXI_CONFIG_G=>CFG_C)
      port map (sAxisClk=>axisClk, sAxisRst=>rst, sAxisMaster=>dep, sAxisSlave=>depSl,
         mAxisClk=>ethClk, mAxisRst=>rst, mAxisMaster=>ob, mAxisSlave=>sinkSl);
   process(clk) begin
      if rising_edge(clk) and rst='0' then
         if ctrl.overflow='1' then overflowCount<=overflowCount+1; end if;
         if ctrl.pause='1' and now>10 us and not seenPause then
            report "FIRST_PAUSE at " & time'image(now);
            seenPause <= true;
         end if;
         if seenPause and phy.tValid='1' then pauseWords<=pauseWords+1; end if;
      end if;
   end process;
   process(axisClk) begin
      if rising_edge(axisClk) and rst='0' and dbg.packetError='1' then
         errorCount<=errorCount+1;
      end if;
   end process;
   process(ethClk)
      variable pendingBytes : natural := 0;
      variable validProbe : boolean := true;
   begin
      if rising_edge(ethClk) and ob.tValid='1' and sinkSl.tReady='1' then
         byteCount <= byteCount + getTKeep(ob.tKeep, CFG_C);
         if pendingBytes=0 then
            validProbe := recovery and ssiGetUserSof(CFG_C,ob)='1';
         end if;
         validProbe := validProbe and
            ob.tData(63 downto 32)=x"12345678" and
            ob.tData(31 downto 0)=std_logic_vector(to_unsigned(pendingBytes/8,32)) and
            getTKeep(ob.tKeep, CFG_C)=8;
         pendingBytes := pendingBytes + getTKeep(ob.tKeep, CFG_C);
         if recovery and ob.tData(63 downto 32)=x"12345678" then
            probeWords<=probeWords+1;
         end if;
         if ob.tLast='1' then
            frameCount<=frameCount+1;
            if ssiGetUserEofe(CFG_C,ob)='1' then eofeCount<=eofeCount+1; end if;
            if recovery then
               report "RECOVERY_FRAME bytes=" & integer'image(pendingBytes) &
                  " eofe=" & sl'image(ssiGetUserEofe(CFG_C,ob));
               if pendingBytes=32 and validProbe and ssiGetUserEofe(CFG_C,ob)='0' then
                  probeFrames<=probeFrames+1;
               end if;
            end if;
            pendingBytes := 0;
         end if;
      end if;
   end process;
   process
      variable tx : AxiStreamMasterType;
   begin
      if not STALL_G then sinkSl.tReady<='1'; end if;
      wait for 10 us;
      for f in 1 to FRAMES_G loop
         for w in 0 to PAYLOAD_BYTES_G/8-1 loop
            tx := axiStreamMasterInit(CFG_C);
            tx.tValid:='1'; tx.tDest:=x"18";
            tx.tData(63 downto 0):=std_logic_vector(to_unsigned(w,64));
            if w=0 then ssiSetUserSof(CFG_C,tx,'1'); end if;
            if w=PAYLOAD_BYTES_G/8-1 then tx.tLast:='1'; end if;
            wait until falling_edge(clk);
            src<=tx;
            loop
               wait until rising_edge(clk);
               exit when srcSl.tReady='1';
            end loop;
         end loop;
         wait until falling_edge(clk); src.tValid<='0';
      end loop;
      -- Keep the sink blocked until the pre-existing response backlog arrived.
      wait for 2 us;
      sinkSl.tReady<='1';
      wait for 20 us;
      report "BURST_RESULT rxDepth=" & integer'image(RX_DEPTH_G) &
         " sent=" & integer'image(PAYLOAD_BYTES_G*FRAMES_G) &
         " received=" & integer'image(byteCount) & " frames=" & integer'image(frameCount) &
         " overflow_cycles=" & integer'image(overflowCount) & " packet_errors=" & integer'image(errorCount) &
         " eofe=" & integer'image(eofeCount) & " phy_bytes_after_pause=" & integer'image(pauseWords*2);
      recovery<=true;
      for f in 1 to 3 loop
         for w in 0 to 3 loop
            tx := axiStreamMasterInit(CFG_C);
            tx.tValid:='1'; tx.tDest:=x"18";
            tx.tData(63 downto 32):=x"12345678";
            tx.tData(31 downto 0):=std_logic_vector(to_unsigned(w,32));
            if w=0 then ssiSetUserSof(CFG_C,tx,'1'); end if;
            if w=3 then tx.tLast:='1'; end if;
            wait until falling_edge(clk); src<=tx;
            loop
               wait until rising_edge(clk);
               exit when srcSl.tReady='1';
            end loop;
         end loop;
         wait until falling_edge(clk); src.tValid<='0';
         wait for 3 us;
      end loop;
      report "RECOVERY_RESULT probes_good=" & integer'image(probeFrames) &
         " probe_words=" & integer'image(probeWords) & " packet_errors=" & integer'image(errorCount) &
         " eofe=" & integer'image(eofeCount);
      if overflowCount=0 and not READY_G then
         assert byteCount=PAYLOAD_BYTES_G*FRAMES_G+96 and frameCount=FRAMES_G+3
            report "Unexpected loss without overflow" severity failure;
      end if;
      -- Check the recovery probes independently of any lost frame preceding them.
      assert probeWords=12 report "Fresh probe data did not drain" severity failure;
      std.env.stop;
      wait;
   end process;
end architecture;
