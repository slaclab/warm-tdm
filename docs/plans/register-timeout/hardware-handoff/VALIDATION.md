# Local validation

Prepared 2026-09-24. No physical hardware run was performed here.

- The client probe and packet decoder passed syntax parsing and `--help` execution.
- Virtual-client probe dispatch was exercised with a mocked RPC endpoint for each read case. Checks covered explicit waitEach arguments, rejection of forced-serialized batched targets, no preliminary identity read in `version-only`, and no writes in read cases.
- ScratchPad tests restored the saved value after both successful writes and an injected write exception. This checks control flow, not restoration after process death or a hardware/transport failure.
- The packet decoder was checked using the 80 IPv4 packets reconstructed from the user's pasted tcpdump capture. All 80 RSSI header checksums and 47 complete packetizer CRCs passed. The expected first outgoing SRP ID 1 / RSSI sequence 156 and first incoming SRP ID 2 / RSSI sequence 129 were recovered.
- The same packets passed with synthetic raw-IP, Ethernet, Linux SLL and Linux SLL2 capture wrappers. This does not validate all possible traffic or packet fragmentation.
- Server construction and RPC interfaces were inspected against the Warm-TDM checkout and Rogue v6.15.0 source. The handoff uses `software/scripts/warmTdmServer.py` with diagnostic flags in its shared `runServer` implementation; an actual startup check on the target machine remains required.
- The real server and GUI entry scripts were exercised with the real CLI parser and mocked Rogue/hardware dependencies. Checks covered unchanged ordinary defaults, opt-in log filters, metadata output, column overrides before startup, `--no-initRead`, both GUI entry paths, CLI help, and rejection of a column override when no column board is configured. No hardware connection was opened.
