# AdcDspFp generated-IP assertions

This native VHDL bench avoids the cocotb/VCS VHDL-runner limitation. It uses
the production Int2Fp, Fp2Int and FpMac XCIs loaded by the common ruckus file;
it does **not** load the GHDL arithmetic models. RAM/FIFO implementations use
the controller's inferred simulation configuration.

From a configured Linux firmware environment:

```bash
source /sdf/group/faders/tools/xilinx/2024.1/Vivado/2024.1/settings64.sh
cd firmware/simulations/AdcDspFpTb
make xsim
```

Alternatively, with VCS and its Vivado simulation libraries configured:

```bash
make vcs
cd ../../build/AdcDspFpTb/AdcDspFpTb_project.sim/sim_1/behav
./sim_vcs_mx.sh
./simv
```

`make vcs` exports the scripts; the last two commands compile and run them.
Require **`AdcDspFpTb PASSED`** and no assertion failures. A 1 ms watchdog
fails stalled simulations. Inspect `firmware/build/AdcDspFpTb/` directly (build
is a symlink). Record the Vivado/core version and transcript with the result.

Assertions cover positive/negative seeds, nearest-even conversion at and
around half-integers, quotient ties and multi-quantum wrapping, retained
fractions at ±256 physical quanta, masked state, integral-only gain resets,
clipping/reversal, stale inverse with zero period, ordered stalled writes and
AXI error counting. The larger GHDL/cocotb suite also checks 256 rows, both DAC
polarities, debug/readout decoding, lifecycle races, overflow and visit loss.

Local check of the native bench itself, using **test models**:

```bash
.venv/bin/python -m pytest tests/warm_tdm/adc_dsp/test_AdcDspFp_native.py -q
```

That local pass is not generated-IP qualification. Actual Vivado/VCS/XSIM
execution, XPM/system integration, timing closure and hardware remain pending.
