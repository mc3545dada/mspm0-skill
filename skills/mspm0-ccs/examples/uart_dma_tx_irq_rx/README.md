# UART0 DMA TX + IRQ RX Echo

Reference for a complete, hardware-verified UART send/receive smoke test on the LCKFB Tianmengxing MSPM0G3507 board. The MCU receives newline-terminated text frames through UART RX interrupts and replies through UART TX DMA.

This example was validated on `26testproject4`. It is meant to help agents test both directions of a UART link from Python/VOFA/other PC tools. The ASCII float parser is only one optional demonstration feature built on top of the verified TX/RX path.

It is an agent-readable reference package, not a complete CCS import project. Do not force another project to adopt this `BSP/` folder layout; copy only the SysConfig settings, interrupt pattern, echo logic, parser pieces, or debugging lessons that match the user's project.

## What It Demonstrates

- PC to MCU: UART0 RX interrupt receives one text frame ending with `\n`.
- MCU to PC: UART0 TX uses DMA and `DMA_DONE_TX` to echo/debug responses.
- `UART0TxDMADone` prevents overlapping DMA TX transfers.
- Overlong RX frames are truncated safely instead of writing past `UART0RxBuf`.
- The example can be tested directly with `scripts/serial_console.py --send ... --send-line`.
- Optional: `UART0_parseRxFloats()` parses the current RX frame into `UART0FloatBuf[]`.
- Optional: the float buffer is cleared on every parse call, then replaced with the latest frame's values.
- Invalid float fields set `UART0FloatParseError`.

## Echo Protocol

Send any ASCII line ending with LF:

```text
ping\n
```

The MCU stores the frame in `UART0RxBuf`, sets `UART0RxDone = 1`, and the main loop echoes the received text plus parse diagnostics over DMA TX.

The line terminator matters. If the PC sends text without `\n`, `UART0RxDone` will not become `1` until the RX buffer reaches its overflow guard.

## Optional Float Protocol

Send ASCII text values separated by comma, semicolon, spaces, or tabs, with LF as the frame terminator:

```text
1.23,44,55.7\n
```

After `UART0RxDone` becomes `1`, call `UART0_parseRxFloats()` before `UART0_startReceive()`:

```c
if (UART0RxDone) {
    uint16_t count = UART0_parseRxFloats();
    /* Use UART0FloatBuf[0..count-1] here. */
    UART0_startReceive();
}
```

Example result:

```c
UART0FloatLen = 3;
UART0FloatBuf[0] = 1.23f;
UART0FloatBuf[1] = 44.0f;
UART0FloatBuf[2] = 55.7f;
UART0FloatParseError = 0;
```

If the PC sends `1.23,abc,55.7\n`, parsing stops at `abc`:

```c
UART0FloatLen = 1;
UART0FloatParseError = 1;
```

## Clock Note

This example uses the 80 MHz clock-tree family:

- CPUCLK: 80 MHz
- UART0 clock: BUSCLK, generated divisor for 40 MHz UART instance frequency
- HFXT: 40 MHz input on PA5 / PA6
- SYSPLL: enabled
- ULPCLK divider: 2
- MFCLK gate: enabled

The older `empty_project` and `led_blink` examples are 32 MHz baseline examples.

## UART / DMA Setup

- UART instance: UART0
- TX: PA10
- RX: PA11
- Baud rate: 115200
- Data format: 8N1
- DMA channel: DMA_CH0, byte width, source increment, destination unchanged
- UART interrupts: `DMA_DONE_TX` and `RX`

The verified generated header contained:

```c
#define UART_0_INST              UART0
#define UART_0_INST_INT_IRQN     UART0_INT_IRQn
#define UART_0_INST_DMA_TRIGGER  (DMA_UART0_TX_TRIG)
#define DMA_UART0Tx_CHAN_ID      (0)
```

## Critical Runtime Pattern

Enable the UART interrupt at the NVIC level after `SYSCFG_DL_init()`:

```c
SYSCFG_DL_init();
UART_init();
```

`UART_init()` must enable `UART_0_INST_INT_IRQN`. Without this call, the first DMA transmit can still run, but `UART0_IRQHandler()` will not execute on `DL_UART_IIDX_DMA_DONE_TX`; later `UART0_printfDMA()` calls can block forever in `while (!UART0TxDMADone);`.

Also make sure SysConfig enables both UART interrupt sources:

```js
UART1.enabledInterrupts = ["DMA_DONE_TX", "RX"];
```

If `RX` is not enabled in SysConfig, incoming bytes will not drive `UART0_RxCallback()`.

## Files

- `example.syscfg`: 80 MHz clock tree, PB22 LED, UART0 TX/RX, UART DMA TX trigger, UART RX interrupt
- `src/empty.c`: main loop, interrupt handler, parser call, and echo output
- `src/BSP/UART.c`: DMA TX helper, RX interrupt buffer, overflow guard, and float parser
- `src/BSP/UART.h`: helper declarations and public buffers
- `manifest.json`: machine-readable summary for example selection

## Verified Tests

Build and flash succeeded through the CCS/SysConfig/DSLite chain. Runtime tests used the skill serial tool on CH340 COM7:

```powershell
python scripts\serial_console.py -p COM7 -b 115200 --send "1.23,44,55.7" --send-line --timestamp --duration 4
```

Observed:

```text
Received 12 bytes: 1.23,44,55.7
Parsed 3 floats err=0 ovf=0: 1.23,44.00,55.70
```

Invalid field test:

```powershell
python scripts\serial_console.py -p COM7 -b 115200 --send "1.23,abc,55.7" --send-line --timestamp --duration 4
```

Observed:

```text
Parsed 1 floats err=1 ovf=0: 1.23,0.00,0.00
```

Overlong frame test sent 300 bytes without LF and produced a truncated 255-byte frame with a nonzero `ovf` marker.

## Limits

This is a simple UART TX/RX smoke-test and text-parameter example. It is not a high-throughput UART RX design. For high-rate telemetry or binary protocols, prefer DMA RX with idle/timeout framing or a ring buffer.
