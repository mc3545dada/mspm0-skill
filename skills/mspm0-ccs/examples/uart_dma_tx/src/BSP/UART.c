#include "UART.h"

volatile uint8_t UART0TxDMADone = 1; // UART0发送DMA完成标志

void UART_init(void) {
    NVIC_ClearPendingIRQ(UART_0_INST_INT_IRQN);
    NVIC_EnableIRQ(UART_0_INST_INT_IRQN);
}

/**
 * @brief UART0发送字符串
 * @note 使用阻塞方式
 * @param str 待发送字符串指针
 * @return 字符串长度
 */
int UART0_sendStr(const char* str) {
    int cnt = 0;
    while (*str) {
        DL_UART_transmitDataBlocking(UART_0_INST, (uint8_t)*str);
        str++;
        cnt++;
    }
    return cnt;
}

/**
 * @brief UART0 printf
 * @param fmt 格式控制字符串与参数列表
 * @return 字符串长度(vsprintf返回值)
 */
int UART0_printf(char* fmt, ...) {
    static char buf[UART_TX_BUF_SIZE];
    int len;
    va_list args;
    va_start(args, fmt);
    len = vsprintf(buf, fmt, args);
    va_end(args);
    UART0_sendStr(buf);
    return len;
}

/**
 * @brief UART0使用DMA方式发送字符串
 * @note 调用该函数时, 若上次UART DMA已传送完成, 则占用时间最短
 * @param str 待发送字符串指针
 * @param len 字符串长度
 */
void UART0_sendStrDMA(const char* str, uint16_t len) {
    while (!UART0TxDMADone);
    UART0TxDMADone = 0;
    DL_DMA_setSrcAddr(DMA, DMA_UART0Tx_CHAN_ID, (uint32_t)str);
    DL_DMA_setDestAddr(DMA, DMA_UART0Tx_CHAN_ID, (uint32_t)(&UART_0_INST->TXDATA));
    DL_DMA_setTransferSize(DMA, DMA_UART0Tx_CHAN_ID, len);
    DL_DMA_enableChannel(DMA, DMA_UART0Tx_CHAN_ID);
}

/**
 * @brief UART0 printf (使用DMA方式)
 * @note 调用该函数时, 若上次UART DMA已传送完成, 则占用时间最短
 * @param fmt 格式控制字符串与参数列表
 */
void UART0_printfDMA(char* fmt, ...) {
    static char buf[UART_TX_BUF_SIZE];
    uint16_t len;
    va_list args;
    while (!UART0TxDMADone);
    va_start(args, fmt);
    len = (uint16_t)vsprintf(buf, fmt, args);
    va_end(args);
    UART0_sendStrDMA(buf, len);
}

// UART0 DMA Tx完成中断回调
void UART0_DMADoneTxCallback(void) {
    UART0TxDMADone = 1;
}

