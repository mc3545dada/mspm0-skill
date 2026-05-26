#include "BSP/UART.h"
#include "ti_msp_dl_config.h"


int main(void)
{
    uint16_t floatCount;


    SYSCFG_DL_init();
    UART_init();

    while (1) {

        if (UART0RxDone) {
            floatCount = UART0_parseRxFloats();


            UART0_printfDMA("Received %d bytes: %s\n", UART0RxLen, UART0RxBuf);
            UART0_printfDMA("Parsed %d floats err=%d ovf=%d: %.2f,%.2f,%.2f\n",
                floatCount, UART0FloatParseError, UART0RxOvf,
                UART0FloatBuf[0], UART0FloatBuf[1], UART0FloatBuf[2]);
            UART0_startReceive();
        }
        

    }
}


void UART0_IRQHandler(void) {
    switch (DL_UART_getPendingInterrupt(UART_0_INST)) {
        case DL_UART_IIDX_DMA_DONE_TX:
            UART0_DMADoneTxCallback();
            break;
        case DL_UART_IIDX_RX:
            UART0_RxCallback();
            break;
        default:
            break;
    }
}
