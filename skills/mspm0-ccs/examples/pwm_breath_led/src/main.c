/*
 * Copyright (c) 2021, Texas Instruments Incorporated
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * *  Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 *
 * *  Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * *  Neither the name of Texas Instruments Incorporated nor the names of
 *    its contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
 * THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR
 * CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
 * PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
 * OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
 * WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
 * OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
 * EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include "ti_msp_dl_config.h"

#define PWM_PERIOD     1000
#define PWM_MIN        1
#define PWM_MAX        (PWM_PERIOD - 1)
#define FADE_STEP      10
#define FADE_DELAY_CYC 800000

int main(void)
{
    SYSCFG_DL_init();
    DL_TimerG_setCaptureCompareValue(PWM_0_INST, PWM_MAX, GPIO_PWM_0_C1_IDX);
    DL_TimerG_startCounter(PWM_0_INST);

    while (1) {
        for (int duty = PWM_MAX; duty >= PWM_MIN; duty -= FADE_STEP) {
            DL_TimerG_setCaptureCompareValue(PWM_0_INST, duty, GPIO_PWM_0_C1_IDX);
            delay_cycles(FADE_DELAY_CYC);
        }

        for (int duty = PWM_MIN; duty <= PWM_MAX; duty += FADE_STEP) {
            DL_TimerG_setCaptureCompareValue(PWM_0_INST, duty, GPIO_PWM_0_C1_IDX);
            delay_cycles(FADE_DELAY_CYC);
        }
    }
}
