三项 F1  JD 0.814  简历 1.000  匹配 1.000  n=100/100/100  mock=False
覆盖率  见 pytest --cov
学习路径抽检  3/20 条有可打开链接
freeze.json sha256  5194b7b806d8fb48714ad3b9f91fe1556a737d36750fe41ab7946a4aadcec438
JD 低于线  F1 0.814 < 0.90
JD 差距样本  jd-0001、jd-0002、jd-0003
JD 下一修复方向 先用冻结词表做候选召回，再让模型判断职责/要求和必备/加分，最后处理别名与复合技能对齐。

## 供应商验证

- Tuzi `gpt-5.6-luna`：真实最小 JSON smoke 成功，使用 `TUZI_BASE_URL=https://api.tu-zi.com/v1`、`TUZI_REASONING_EFFORT=none`，约 4 秒返回合法 JSON；真实 PDF 简历上传、单岗诊断和双岗诊断均成功。
- Tuzi 长 JD 评测：16 路并发曾完成 61/100，4 路曾完成 13/100；剩余请求在网关响应头阶段长期等待，未将半程结果计入 F1 基线。默认并发保留 16，发布评测可用 `EVAL_WORKERS` 降低。
- B.AI `deepseek-v4-flash-vision-exp`：`/v1/models` 与最小 JSON smoke 已成功；本文件首行三项 F1 仍使用此前完整 100/100 结果，不以供应商半程结果替换。
