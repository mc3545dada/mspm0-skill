# UART DMA TX + IRQ RX Echo

Reference for a complete, hardware-verified UART send/receive smoke test on the LCKFB Tianmengxing MSPM0G3507 board. The MCU receives newline-terminated text frames through UART RX interrupts and replies through UART TX DMA.

This example was validated on `26testproject4`. It is meant to help agents test both directions of a UART link from Python/VOFA/other PC tools. The ASCII float parser is only one optional demonstration feature built on top of the verified TX/RX path.

It is an agent-readable reference package, not a complete CCS import project. Do not force another project to adopt this `BSP/` folder layout; copy only the SysConfig settings, interrupt pattern, echo logic, parser pieces, or debugging lessons that match the user's project.

## What It Demonstrates

- PC to MCU: UART RX interrupt receives one text frame ending with `\n`.
- MCU to PC: UART TX uses DMA and `DMA_DONE_TX` to echo/debug responses.
- `UART_Context` stores per-UART TX/RX state so the helper is not hard-wired to UART0.
- `UART_init(UART_0_INST)` returns the context pointer and starts RX.
- `UART_tryPrintfDMA()` is nonblocking and is suitable for a short RX-complete callback.
- Overlong RX frames are truncated safely instead of writing past the RX buffer.
- The example can be tested directly with `scripts/serial_console.py --send ... --send-line`.
- Optional: `UART_parseRxFloats()` parses the current RX frame into `context->floatBuf[]`.
- Optional: the float buffer is cleared on every parse call, then replaced with the latest frame's values.
- Invalid float fields set `context->floatParseError`.

## Echo Protocol

Send any ASCII line ending with LF:

```text
ping\n
```

The MCU stores the frame in `uart->rxBuf`, sets `uart->rxDone = 1`, and the RX-complete callback echoes the received text plus parsed float values over DMA TX.

The line terminator matters. If the PC sends text without `\n`, `UART_RxCallback()` will not publish a frame until the RX buffer reaches its overflow guard.

## Optional Float Protocol

Send ASCII text values separated by comma, semicolon, spaces, or tabs, with LF as the frame terminator:

```text
1.23,44,55.7\n
```

Call `UART_parseRxFloats(uart->inst)` after `UART_RxCallback()` reports a complete frame:

```c
static void UART_RxCompleteCallback(UART_Context *uart)
{
    if (uart == 0) {
        return;
    }

    UART_parseRxFloats(uart->inst);
    (void) UART_tryPrintfDMA(uart->inst, "%s | %.2f,%.2f,%.2f\n",
        uart->rxBuf,
        uart->floatBuf[0], uart->floatBuf[1], uart->floatBuf[2]);
    UART_clearNewFrame(uart->inst);
}
```

Example result:

```c
uart->floatLen = 3;
uart->floatBuf[0] = 1.23f;
uart->floatBuf[1] = 44.0f;
uart->floatBuf[2] = 55.7f;
uart->floatParseError = 0;
```

If the PC sends `1.23,abc,55.7\n`, parsing stops at `abc`:

```c
uart->floatLen = 1;
uart->floatParseError = 1;
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

- UART instance used by this example: UART0
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

Initialize the context after `SYSCFG_DL_init()`:

```c
static UART_Context *uart0;

int main(void)
{
    SYSCFG_DL_init();
    uart0 = UART_init(UART_0_INST);

    while (1) {
    }
}
```

`UART_init()` starts RX, marks DMA TX as idle, clears the pending IRQ, and enables the matching UART IRQ at the NVIC level. Without this call, the first DMA transmit can still run, but the TX-done callback will not execute and later blocking sends can wait forever.

Also make sure SysConfig enables both UART interrupt sources:

```js
UART1.enabledInterrupts = ["DMA_DONE_TX", "RX"];
```

If `RX` is not enabled in SysConfig, incoming bytes will not drive `UART_RxCallback()`.

Handle the interrupt by passing the matching SysConfig instance:

```c
void UART0_IRQHandler(void)
{
    switch (DL_UART_getPendingInterrupt(UART_0_INST)) {
        case DL_UART_IIDX_DMA_DONE_TX:
            UART_DMADoneTxCallback(UART_0_INST);
            break;
        case DL_UART_IIDX_RX:
            if (UART_RxCallback(UART_0_INST)) {
                UART_RxCompleteCallback(uart0);
            }
            break;
        default:
            break;
    }
}
```

For another UART instance, use that instance's generated IRQ handler and generated `UART_x_INST` macros. Do not leave the handler name or instance macro mismatched.

## Blocking vs Nonblocking Send

- `UART_printfDMA()` waits until the previous DMA TX is done. Use it in `main()`, tasks, or low-risk foreground code.
- `UART_tryPrintfDMA()` returns immediately. Use it in short callbacks/ISRs; if the previous DMA TX is still busy, it returns `0` and skips this send.
- `UART_clearNewFrame()` clears the current frame flag after the application has handled that frame. In this interrupt-driven echo example, it is called in `UART_RxCompleteCallback()`.

Do not send at a very high PC-to-MCU rate with this compact example. It targets low-rate command, debug, and parameter-tuning traffic. For high-rate telemetry or binary protocols, prefer DMA RX with idle/timeout framing or a ring buffer.

## Files

- `example.syscfg`: 80 MHz clock tree, PB22 LED, UART0 TX/RX, UART DMA TX trigger, UART RX interrupt
- `src/empty.c`: main, interrupt handler, RX-complete callback, parser call, and echo output
- `src/BSP/UART.c`: generic UART context helper, DMA TX, RX interrupt buffer, overflow guard, and float parser
- `src/BSP/UART.h`: helper declarations and `UART_Context`
- `manifest.json`: machine-readable summary for example selection

## Verified Tests

Build and flash succeeded through the CCS/SysConfig/DSLite chain. Runtime tests used the skill serial tool on CH340 COM7:

```powershell
python scripts\serial_console.py -p COM7 -b 115200 --send "1.23,44,55.7" --send-line --timestamp --duration 4
```

Observed:

```text
1.23,44,55.7 | 1.23,44.00,55.70
```

Repeated frame test:

```powershell
python scripts\serial_console.py -p COM7 -b 115200 --send "2,3,4" --send-line --repeat 2 --interval 0.5 --timestamp --duration 4
```

Observed two replies:

```text
2,3,4 | 2.00,3.00,4.00
2,3,4 | 2.00,3.00,4.00
```
