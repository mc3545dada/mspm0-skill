# UART DMA TX + IRQ RX Echo

Hardware-verified UART send/receive reference for the LCKFB Tianmengxing MSPM0G3507 board. It uses UART RX interrupts to collect `\n`-terminated text frames and UART TX DMA for replies/debug output.

This is an agent-readable reference package, not a complete CCS import project. Do not force another project to adopt this `BSP/` layout; copy only the SysConfig settings, interrupt pattern, helper API, or lessons that match the user's project.

## What It Demonstrates

- UART0: PA10/PA11, DMA_CH0, verified through COM7.
- UART1: PB6/PB7, DMA_CH1, verified through COM9.
- Per-UART `UART_Context`, so DMA state, RX buffers, parsed float buffers, and printf TX buffers are not shared between UART instances.
- Three RX handling modes selected at `UART_init()` time:
  - `UART_RX_MODE_NONE`: TX-only; RX bytes are discarded if an RX interrupt occurs.
  - `UART_RX_MODE_POLL`: RX interrupt collects frames, foreground code calls `UART_poll()`.
  - `UART_RX_MODE_ISR_CALLBACK`: complete-frame callback runs from the UART ISR.
- Optional ASCII float parsing with `UART_parseRxFloats()`.

## API Shape

Initialize after `SYSCFG_DL_init()`:

```c
static UART_Context *uart0;
static UART_Context *uart1;

uart0 = UART_init(UART_0_INST, UART_RX_MODE_ISR_CALLBACK, UART_RxCompleteCallback);
uart1 = UART_init(UART_1_INST, UART_RX_MODE_POLL, UART_RxCompleteCallback);
```

TX-only UART:

```c
uart1 = UART_init(UART_1_INST, UART_RX_MODE_NONE, 0);
UART_printfDMA(UART_1_INST, "debug %.2f\n", value);
```

Poll-mode processing:

```c
while (1) {
    UART_poll(UART_1_INST);
}
```

Interrupt handlers stay small and instance-specific:

```c
void UART0_IRQHandler(void)
{
    switch (DL_UART_getPendingInterrupt(UART_0_INST)) {
        case DL_UART_IIDX_DMA_DONE_TX:
            UART_DMADoneTxCallback(UART_0_INST);
            break;
        case DL_UART_IIDX_RX:
            UART_RxIRQHandler(UART_0_INST);
            break;
        default:
            break;
    }
}
```

## Frame Callback

The same callback can be reused by ISR and poll modes:

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

If different UARTs need different behavior, compare the context pointer:

```c
if (uart == uart0) {
    /* command parser */
} else if (uart == uart1) {
    /* debug console */
}
```

## Important Lessons

- Do not use a function-static printf buffer for DMA TX when multiple UARTs are supported. DMA transmits asynchronously; this example stores `txBuf` inside `UART_Context`.
- Keep RX ISRs short. `UART_RX_MODE_ISR_CALLBACK` is convenient for one low-rate command UART, but heavy work such as `strtof()` and float `printf` is safer in `UART_RX_MODE_POLL` or an RTOS task.
- This helper keeps only the latest complete RX frame. If two frames arrive before the application polls or clears the first one, the newer frame can replace the older one. Use a queue/ring buffer for lossless high-rate protocols.
- `UART_RX_MODE_NONE` is useful for debug-only TX UARTs. The UART IRQ remains enabled so `DMA_DONE_TX` can release `txDMADone`; RX bytes are read and discarded.
- `PB6/PB7` must be wired crossed: MCU PB6/TX to USB-serial RX, MCU PB7/RX to USB-serial TX, and common GND.

## SysConfig Setup

- Clock: 80 MHz CPUCLK, SYSPLL from 40 MHz HFXT, MFCLK enabled.
- UART0: PA10 TX, PA11 RX, 115200 8N1, DMA_CH0 TX, `DMA_DONE_TX` + `RX` interrupts.
- UART1: PB6 TX, PB7 RX, 115200 8N1, DMA_CH1 TX, `DMA_DONE_TX` + `RX` interrupts.
- PB22 LED remains present as the Tianmengxing onboard LED reference pin.

Observed generated names:

```c
#define UART_0_INST             UART0
#define UART_0_INST_INT_IRQN    UART0_INT_IRQn
#define DMA_UART0Tx_CHAN_ID     (0)
#define UART_1_INST             UART1
#define UART_1_INST_INT_IRQN    UART1_INT_IRQn
#define DMA_UART1Tx_CHAN_ID     (1)
```

## Verified Tests

Build and flash succeeded through CCS/SysConfig/DSLite on Tianmengxing MSPM0G3507 + J-Link.

Low-rate dual-UART test:

```powershell
python scripts\serial_console.py -p COM7 -b 115200 --send "7.1,7.2,7.3" --send-line --repeat 5 --interval 0.5 --timestamp --duration 5
python scripts\serial_console.py -p COM9 -b 115200 --send "9.1,9.2,9.3" --send-line --repeat 5 --interval 0.5 --timestamp --duration 5
```

Both ports replied with their own parsed values, with no cross-UART DMA buffer corruption.

Higher-rate smoke test:

```powershell
python scripts\serial_console.py -p COM7 -b 115200 --send "7.1,7.2,7.3" --send-line --repeat 10 --interval 0.08 --timestamp --duration 4
python scripts\serial_console.py -p COM9 -b 115200 --send "9.1,9.2,9.3" --send-line --repeat 10 --interval 0.08 --timestamp --duration 4
```

The current ISR/poll split passed this test. A previous design that parsed and formatted both UARTs inside RX ISRs could drop or corrupt occasional bytes at this rate.
