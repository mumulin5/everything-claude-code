# 医学 Excel 清洗项目骨架 (Medical Excel Cleaning Skeleton)

一套针对**检验 / 病历 / 随访**三类医学 Excel 数据的最小可用清洗骨架。
基于 `pandas + pyjanitor + pandera + RapidFuzz`，开箱即用。

## 适用场景

| 数据类型 | 典型问题                                           | 对应脚本                  |
| -------- | -------------------------------------------------- | ------------------------- |
| 检验     | 单位不统一、`<0.01`/`>1000`、项目名多种写法        | `scripts/clean_lab.py`    |
| 病历     | 诊断写法五花八门、日期格式乱、姓名/身份证需脱敏    | `scripts/clean_emr.py`    |
| 随访     | 宽表/长表混乱、缺失分类（失访 vs 未到访）、量表评分 | `scripts/clean_followup.py` |

## 目录结构

```
medical-excel-cleaning/
├── README.md
├── requirements.txt
├── config.yaml         # 路径 / 字典名 / 模糊阈值 / 脱敏策略集中配置
├── cli.py              # 统一命令行入口（typer）
├── data/
│   ├── raw/            # 原始 Excel，只读不改
│   ├── interim/        # 清洗中间产物
│   └── clean/          # 清洗后输出
├── reports/            # ydata-profiling 数据质量 HTML 报告
├── dict/               # 字典 / 映射表
│   ├── sex.csv
│   ├── unit.csv
│   ├── lab_item.csv
│   └── diagnosis_icd10.csv
└── scripts/
    ├── _common.py
    ├── _config.py
    ├── make_demo_data.py   # Faker 生成带"脏数据"的演示 Excel
    ├── profile.py          # ydata-profiling 数据体检
    ├── clean_lab.py
    ├── clean_emr.py
    └── clean_followup.py
```

## 快速开始

```bash
# 1. 安装依赖（建议 Python 3.9+）
pip install -r requirements.txt

# 2A. 没有自己的数据？一键生成演示数据
python cli.py demo

# 2B. 有自己的数据？把原始 Excel 放入 data/raw/
#    - lab.xlsx       列: item, value, unit, ref_range
#    - emr.xlsx       列: name, id_card, sex, birth_date,
#                         admit_date, discharge_date,
#                         diagnosis, history_text
#    - followup.xlsx  宽表，列名形如 bp_m3, bp_m6, bp_m12 ...
#    - followup_status.xlsx  列: patient_id, last_visit_month, lost

# 3. （可选）清洗前先看一眼数据长什么样
python cli.py profile           # 输出到 reports/*.html

# 4. 一条命令跑完三类清洗
python cli.py all
# 或单独跑：python cli.py lab | emr | followup

# 5. 在 data/clean/ 查看输出
```

> 旧用法仍然支持：`python scripts/clean_lab.py` 等脚本可以独立运行。

## 通用清洗 7 步法

1. **读入** —— 全部按字符串读入，避免身份证/编号被科学计数化
2. **列名标准化** —— `pyjanitor.clean_names()` 转 snake_case
3. **类型转换** —— 数值/日期显式 `to_numeric` / `to_datetime(errors="coerce")`
4. **缺失/异常处理** —— 区分"缺失"和"异常"，不要全填 0
5. **文本/编码标准化** —— 字典映射 + RapidFuzz 模糊匹配
6. **schema 校验** —— `pandera` 强制规则，新数据自动校验
7. **输出 + 留痕日志** —— `*_clean.xlsx` 配套 `*_log.csv`

## 工具组合速查

| 维度       | 检验                    | 病历                          | 随访                            |
| ---------- | ----------------------- | ----------------------------- | ------------------------------- |
| 主力清洗   | pandas + pyjanitor      | pandas + pyjanitor            | pandas + pyjanitor              |
| 文本归一   | RapidFuzz + LOINC 字典  | RapidFuzz + ICD-10            | （量表字典）                    |
| 单位/日期  | pint                    | dateparser                    | —                               |
| 校验       | pandera（数值范围）     | pandera                       | pandera（唯一性）               |
| 脱敏       | —                       | hash / presidio               | hash / presidio                 |
| 下游分析   | 统计/可视化             | 队列筛选                      | lifelines 生存分析              |

## 关键约定

- **字典即配置**：所有字段映射放在 `dict/*.csv`，改字典不改代码。
- **数据分层**：`raw → interim → clean`，原始数据永远只读。
- **随访长表**：随访数据**永远存长表**（patient_id × indicator × month），做报表时再 pivot。
- **脱敏前置**：病历数据在 `clean_emr.py` 中已对 `name`/`id_card` 做 hash + 删除处理。

## 扩展建议

- 复杂诊断映射：接入 [MedCAT](https://github.com/CogStack/MedCAT)
- PII 自动识别：接入 [presidio](https://github.com/microsoft/presidio)
- 持续质量监控：接入 [Great Expectations](https://greatexpectations.io/)
- 单位换算：[pint](https://github.com/hgrecco/pint)
- 杂乱日期解析：[dateparser](https://github.com/scrapinghub/dateparser)

## License

与本仓库一致。
