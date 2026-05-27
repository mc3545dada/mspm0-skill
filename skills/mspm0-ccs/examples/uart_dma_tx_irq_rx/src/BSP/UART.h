#ifndef __USER_UART_H__
#define __USER_UART_H__

#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include "ti_msp_dl_config.h"

#define UART_TX_BUF_SIZE      256
#define UART_RX_BUF_SIZE      256
#define UART_FLOAT_BUF_SIZE   256
#define UART_MAX_CONTEXTS     4
#define UART_RX_TERMINATOR    '\n'

typedef struct {
    UART_Regs *inst;
    volatile uint8_t txDMADone;
    volatile uint8_t rxDone;
    volatile uint8_t rxBuf[UART_RX_BUF_SIZE];
    volatile uint8_t rxWorkBuf[UART_RX_BUF_SIZE];
    volatile uint16_t rxPos;
    volatile uint16_t rxLen;
    volatile uint32_t rxFrameCount;
    volatile uint8_t rxOvf;
    float floatBuf[UART_FLOAT_BUF_SIZE];
    volatile uint16_t floatLen;
    volatile uint8_t floatParseError;
} UART_Context;

UART_Context *UART_getContext(UART_Regs *uart);

UART_Context *UART_init(UART_Regs *uart);
int UART_sendStr(UART_Regs *uart, const char *str);
int UART_printf(UART_Regs *uart, char *fmt, ...);
void UART_sendStrDMA(UART_Regs *uart, const char *str, uint16_t len);
void UART_printfDMA(UART_Regs *uart, char *fmt, ...);
uint8_t UART_trySendStrDMA(UART_Regs *uart, const char *str, uint16_t len);
uint8_t UART_tryPrintfDMA(UART_Regs *uart, char *fmt, ...);
void UART_startReceive(UART_Regs *uart);
uint8_t UART_hasNewFrame(UART_Regs *uart);
void UART_clearNewFrame(UART_Regs *uart);
uint16_t UART_parseRxFloats(UART_Regs *uart);

void UART_DMADoneTxCallback(UART_Regs *uart);
uint8_t UART_RxCallback(UART_Regs *uart);

#endif
