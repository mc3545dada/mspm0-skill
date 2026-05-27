# MSPM0 Skill

面向 TI MSPM0 + SysConfig + DriverLib 的 AI 编程助手 skill 包。

它主要服务于国内 MSPM0 开发、电赛备赛、TI 官方开发板和立创天猛星 MSPM0G3507 等场景，帮助 Claude Code、OpenCode、OpenClaw、Continue、Cursor、Codex 等 CLI / 编辑器 Agent 更安全地理解、修改、编译、烧录和调试 MSPM0 工程。

当前重点支持 CCS / CCS Theia + SysConfig + TI Arm Clang 工作流，同时包含 Keil/uVision、CMake + GCC + OpenOCD 项目的识别和使用说明。

## 快速安装

推荐使用：

```bash
npx skills add mc3545dada/mspm0-skill@mspm0-ccs
```

也可以手动复制可安装 skill 目录：

```text
skills/mspm0-ccs/
```

常见安装位置：

```text
Claude Code:  ~/.claude/skills/mspm0-ccs/
Codex 等:     ~/.agents/skills/mspm0-ccs/
OpenClaw:     ~/.openclaw/skills/mspm0-ccs/
```

Windows PowerShell 示例：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse -Force .\skills\mspm0-ccs "$env:USERPROFILE\.claude\skills\mspm0-ccs"
```

## 快速使用

安装后，在 MSPM0 工程目录中可以这样要求 Agent：

```text
请使用 mspm0-ccs skill，先检查当前工程的 .syscfg 和 ti_msp_dl_config.h，
然后帮我给立创天猛星 PB22 板载 LED 配置 1 秒闪烁，并编译烧录。
```

```text
请使用 mspm0-ccs skill，参考 UART DMA 收发例程，
帮我配置 UART0 发送和换行帧接收，并用 Python 串口工具验证回显。
```

```text
请使用 mspm0-ccs skill，检查这个 MSPM0 工程属于 CCS、Keil 还是 CMake/OpenOCD 工作流，
不要修改生成文件，先给我说明构建和烧录路径。
```

## 功能概览

| 能力 | 说明 |
| --- | --- |
| SysConfig 辅助 | 检查并修改 `.syscfg`，避免直接改 `ti_msp_dl_config.c/.h` 这类生成文件 |
| 编译烧录 | 固化 SysConfig CLI、gmake、DSLite/J-Link、OpenOCD 等链路的经验 |
| 串口工具 | Python 串口收发、文本帧测试、为后续 PID/参数调试做基础 |
| CCS-DSS 调试 | 基于 CCS Debug Server Scripting 的探针连接、断点、符号加载辅助 |
| 例程管理 | 提供已验证例程，也支持从用户项目抽取精简例程包 |
| 模块驱动 | 提供某个模块/传感器/电机的手册后要求Agent制作驱动 |

## 已验证环境

主要验证组合：

- 开发板：立创天猛星 MSPM0G3507
- 开发环境：CCS / CCS Theia
- SDK：MSPM0 SDK 2.10.00.04
- SysConfig：1.26.2
- 编译器：TI Arm Clang 4.x LTS
- 烧录器：J-Link
- 烧录工具：UniFlash / DSLite
- 已验证外设：PB22 板载 LED、PWM 呼吸灯、UART 阻塞发送、UART DMA 发送 + 中断/轮询接收

其他开发板、芯片封装、SDK/CCS/Keil/CMake 版本、调试器或烧录方式可能也能使用，但没有完全保证。迁移到其他组合时，建议先做最小点灯、串口或 PWM 验证。

## 使用示例

Claude Code 调用 skill 配置 MSPM0G3507 工程：

![Claude Code 调用 mspm0-ccs skill](skills/mspm0-ccs/assets/screenshots/claude-code-skill-start.png)

编译、烧录后的总结：

![Claude Code 完成 SysConfig、编译和烧录后的总结](skills/mspm0-ccs/assets/screenshots/claude-code-summary.png)

Codex 配置外设并用 VOFA+ 查看串口输出：

![Codex 调用 mspm0-ccs skill 配置工程](skills/mspm0-ccs/assets/screenshots/codex-ask.png)

![Codex 调用 mspm0-ccs skill 配置工程](skills/mspm0-ccs/assets/screenshots/vofa-output.png)
完整演示视频：[Bilibili 完整使用视频](https://www.bilibili.com/video/BV1RbLY6xECu)

更多截图见：`skills/mspm0-ccs/assets/screenshots/`

## 常用脚本

以下命令默认在本仓库根目录执行；如果你在其他目录打开终端，请把脚本路径改成绝对路径。

检查 MSPM0 工程：

```powershell
python skills\mspm0-ccs\scripts\check_syscfg.py C:\Users\3545\workspace_ccstheia\26testproject1
```

串口收发测试：

```powershell
python skills\mspm0-ccs\scripts\serial_console.py --list
python skills\mspm0-ccs\scripts\serial_console.py -p COM6 -b 115200 --timestamp --duration 10
python skills\mspm0-ccs\scripts\serial_console.py -p COM6 -b 115200 --send "ping" --send-line --timestamp --duration 3
```

列出 skill 内例程：

```powershell
python skills\mspm0-ccs\scripts\list_examples.py
```

搜索本地 TI SDK 官方例程：

```powershell
python skills\mspm0-ccs\scripts\index_syscfg_examples.py C:\ti\mspm0_sdk_2_10_00_04 --board LP_MSPM0G3507 --module UART
```

CCS-DSS 调试链路只适用于 CCS / CCS Theia / UniFlash Debug Server Scripting，不是 OpenOCD/GDB：

```powershell
python skills\mspm0-ccs\scripts\ccs_dss_debug.py C:\Users\3545\workspace_ccstheia\26testproject2 probe --leave-running
python skills\mspm0-ccs\scripts\ccs_dss_debug.py C:\Users\3545\workspace_ccstheia\26testproject2 run-to-symbol --symbol main --load --reset "System Reset"
```

## 内置例程

| 例程 | 频率 | 主要内容 |
| --- | --- | --- |
| `empty_project` | 32MHz | 空工程基线 |
| `led_blink` | 32MHz | PB22 板载 LED 闪烁 |
| `pwm_breath_led` | 80MHz | PB22 / TIMG PWM 呼吸灯 |
| `uart_blocking_tx` | 80MHz | UART0 阻塞发送字符串 |
| `uart_dma_tx_irq_rx` | 80MHz | UART DMA 发送 + 中断/轮询接收 + 文本帧解析示例 |

例程是“可参考的已验证样例”，不是必须照搬的工程模板。Agent 使用例程时应以用户当前工程结构为准，可以只复制 `.syscfg` 字段、代码片段或调试经验，不应强行把例程里的 `BSP/`、`app/` 等目录结构搬进用户工程。

## 关键提醒

- 修改 `.syscfg` 后需要重新运行 SysConfig 或重新构建工程。
- 烧录前确认 CCS 的 `targetConfigs/*.ccxml`、Keil 调试器配置或 OpenOCD `.cfg` 与实际硬件一致。
- 立创天猛星环境中，自动烧录建议优先使用 DSLite System Reset：`-e -r 2 -u`。
- CCS-DSS 调试和 OpenOCD/GDB 调试是两条不同路径

更详细的 Agent 行为规则和经验记录见：

- `skills/mspm0-ccs/SKILL.md`
- `skills/mspm0-ccs/references/sysconfig_ccs_workflow.md`
- `skills/mspm0-ccs/references/hardware_validation_notes.md`
- `skills/mspm0-ccs/references/ccs_dss_debug.md`

## 参考资料

- [TI SysConfig](https://www.ti.com/tool/SYSCONFIG)
- [TI MSPM0 SDK](https://www.ti.com/tool/MSPM0-SDK)
- [TI MSPM0 SysConfig Guide](https://software-dl.ti.com/msp430/esd/MSPM0-SDK/2_05_01_00/docs/english/tools/sysconfig_guide/doc_guide/doc_guide-srcs/sysconfig_guide.html)
- [TI LP-MSPM0G3507](https://www.ti.com.cn/tool/cn/LP-MSPM0G3507)
- [立创天猛星 MSPM0G3507 文档](https://wiki.lckfb.com/zh-hans/tmx-mspm0g3507/)

## 开源协议

本项目使用 [MIT License](LICENSE)。
