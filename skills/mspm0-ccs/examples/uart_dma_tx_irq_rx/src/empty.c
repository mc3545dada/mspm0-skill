#include "BSP/UART.h"
#include "ti_msp_dl_config.h"

static UART_Context *uart0;
static UART_Context *uart1;

static void UART_RxCompleteCallback(UART_Context *uart)
{
    uint8_t sent;

    if (uart == 0) {
        return;
    }

    UART_parseRxFloats(uart->inst);
    sent = UART_tryPrintfDMA(uart->inst, "%s | %.2f,%.2f,%.2f\n",
        uart->rxBuf,
        uart->floatBuf[0], uart->floatBuf[1], uart->floatBuf[2]);
    (void) sent;

    UART_clearNewFrame(uart->inst);
    // Keep PC-to-MCU send rate modest; this example targets low-rate parameter debugging.
}

int main(void)
{
    SYSCFG_DL_init();
    uart0 = UART_init(UART_0_INST, UART_RX_MODE_ISR_CALLBACK, UART_RxCompleteCallback);
    uart1 = UART_init(UART_1_INST, UART_RX_MODE_POLL, UART_RxCompleteCallback);

    while (1) {
        UART_poll(UART_1_INST);
    }
}

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

void UART1_IRQHandler(void)
{
    switch (DL_UART_getPendingInterrupt(UART_1_INST)) {
        case DL_UART_IIDX_DMA_DONE_TX:
            UART_DMADoneTxCallback(UART_1_INST);
            break;
        case DL_UART_IIDX_RX:
            UART_RxIRQHandler(UART_1_INST);
            break;
        default:
            break;
    }
}
