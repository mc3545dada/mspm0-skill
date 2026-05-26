# UART0 DMA TX Example

Minimal reference for sending repeated text lines from the LCKFB Tianmengxing MSPM0G3507 board to a PC over UART0 by DMA.

This example was captured from `26testproject4` after debugging a real failure where the program sent once and then stopped. It is not a complete CCS import project; it is an agent-readable reference package.

Do not treat the `BSP/` folder in this example as a required project layout. When applying this pattern to another project, preserve that project's existing structure and copy only the UART/DMA/NVIC pieces that are needed.

## Clock Note

This example uses the same 80 MHz clock-tree family as `uart_blocking_tx`:

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
- UART interrupt: `DMA_DONE_TX`

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

`UART_init()` must enable `UART_0_INST_INT_IRQN`:

```c
void UART_init(void) {
    NVIC_ClearPendingIRQ(UART_0_INST_INT_IRQN);
    NVIC_EnableIRQ(UART_0_INST_INT_IRQN);
}
```

Without this call, the first DMA transmit can still run, but `UART0_IRQHandler()` will not execute on `DL_UART_IIDX_DMA_DONE_TX`. The `UART0TxDMADone` flag remains `0`, and the next `UART0_printfDMA()` call blocks forever in `while (!UART0TxDMADone);`.

## Files

- `example.syscfg`: 80 MHz clock tree, PB22 LED, UART0 TX/RX, UART DMA TX trigger
- `src/empty.c`: main loop, interrupt handler, and required `UART_init()` call
- `src/BSP/UART.c`: DMA TX helper and completion flag
- `src/BSP/UART.h`: helper declarations
- `manifest.json`: machine-readable summary for example selection

## Debug Notes

The failure was confirmed with CCS-DSS:

- Before the fix, halting after a few seconds showed PC at `0x1bc0`, inside `UART0_printfDMA()`'s `while (!UART0TxDMADone)` loop.
- After adding `UART_init()`, the program no longer halted in that wait loop.
- A no-flash symbol-only breakpoint on `BSP/UART.c:75` / `UART0_DMADoneTxCallback` confirmed that the DMA completion path can execute.

Useful commands:

```powershell
python scripts\ccs_dss_debug.py <project-dir> load-symbols --symbol UART0_printfDMA --symbol UART0_DMADoneTxCallback --symbol UART0TxDMADone
python scripts\ccs_dss_debug.py <project-dir> break-line --source BSP/UART.c --line 75 --symbols --reset "System Reset" --leave-running
python scripts\ccs_dss_debug.py <project-dir> break-address --address 0x2564 --symbols --reset "System Reset" --leave-running
```

Always inspect the target project's generated `ti_msp_dl_config.h`; generated names and line addresses can differ.
