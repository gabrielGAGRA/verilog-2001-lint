# Verilog-2001 Testbench & Simulation Standard

---

## 1. Testbench Module Architecture

1. **Closed Module**:
   * Testbench modules ***must not*** declare input or output ports:
     ```verilog
     module counter_tb;  // Correct
     // module counter_tb (input clk); // Banned
     ```
2. **File Naming**:
   * Testbench files ***must*** be named `<module>_tb.v` and placed in the verification directory.
3. **Timescale and Directives**:
   * Testbench files ***must*** specify `` `timescale 1ns/1ps `` and enforce `` `default_nettype none ``.

---

## 2. Deterministic Execution & Self-Checking

1. **Self-Checking Mandatory**:
   * Testbenches ***must not*** rely on manual waveform inspection to determine success or failure.
   * Every testbench ***must*** maintain `errors = 0` and `tests_run = 0` counters.
2. **Deterministic Termination**:
   * Test execution ***must*** conclude with `$finish;`.
   * `$stop;` is prohibited as a final completion signal because it halts headless CI/CD execution into an interactive prompt.
3. **Mandatory Watchdog Timer**:
   * Every testbench ***must*** instantiate an independent watchdog timer to kill simulation if a deadlock occurs:
     ```verilog
     localparam WatchdogNs = 100000;
     initial begin
       #WatchdogNs;
       $display("[FATAL] %0t ns: Watchdog timeout - simulation deadlocked.", $time);
       $finish;
     end
     ```
4. **Summary Banner**:
   * Upon completion, the testbench ***must*** output an unambiguous summary line:
     * `ALL TESTS PASSED` when `errors == 0`.
     * `TESTBENCH FAILED with N error(s)` when `errors > 0`.

---

## 3. Clocking, Driving & Sampling Discipline

1. **Clock Generation**:
   ```verilog
   localparam ClkPeriodNs = 20;
   reg clk;
   initial clk = 1'b0;
   always #(ClkPeriodNs / 2) clk = ~clk;
   ```
2. **Race-Free Stimulus**:
   * Synchronous inputs to the DUT ***must*** be driven on the inactive clock edge (`@(negedge clk)`) or with a small delta delay after edge (`@(posedge clk); #1;`).
3. **Sampling Stability**:
   * Output verification checks ***must*** sample data when signals are completely settled (`@(negedge clk)` or `#1` after active clock edge).
4. **Unknown State Checks**:
   * Verify absence of unknown states using identity operators (`===` and `!==`):
     ```verilog
     if (out_data === 8'bx) begin
       $display("[FAIL] %0t ns: Output is uninitialized 'X'.", $time);
       errors = errors + 1;
     end
     ```

---

## 4. Canonical Testbench Skeleton

```verilog
`timescale 1ns / 1ps
`default_nettype none

module my_module_tb;
  localparam ClkPeriodNs = 20;
  localparam WatchdogNs  = 50000;

  reg clk;
  reg rst;
  reg in_val;
  wire out_val;

  integer errors = 0;
  integer tests_run = 0;

  initial clk = 1'b0;
  always #(ClkPeriodNs / 2) clk = ~clk;

  my_module #(.SimSpeedup(1'b1)) dut (
    .clk(clk),
    .rst(rst),
    .in_val(in_val),
    .out_val(out_val)
  );

  // Mandatory Watchdog Timer
  initial begin
    #WatchdogNs;
    $display("[FATAL] %0t ns: Watchdog timeout.", $time);
    $finish;
  end

  task setup;
    begin
      rst <= 1'b1;
      in_val <= 1'b0;
      repeat (2) @(posedge clk);
      @(negedge clk) rst <= 1'b0;
      @(posedge clk);
    end
  endtask

  task expect_val(input exp, input [127:0] tag);
    if (out_val !== exp) begin
      $display("[FAIL] %0t ns | %0s: expected %0b, got %0b", $time, tag, exp, out_val);
      errors = errors + 1;
    end
  endtask

  initial begin
    tests_run = tests_run + 1;
    setup();

    @(negedge clk) in_val <= 1'b1;
    @(posedge clk); #1;
    expect_val(1'b1, "BASIC_STIMULUS");

    $display("----------------------------------------");
    if (errors == 0) begin
      $display("ALL TESTS PASSED (%0d tests)", tests_run);
    end else begin
      $display("TESTBENCH FAILED: %0d error(s)", errors);
    end
    $display("----------------------------------------");
    $finish;
  end

endmodule
`default_nettype wire
```
