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
│   ├── interim/        # 列名/类型标准化（parquet）
│   ├── clean/          # 业务清洗后输出（xlsx + parquet）
│   └── marts/          # 分析就绪宽表（parquet）
├── reports/            # ydata-profiling 数据质量 HTML 报告
├── suggestions/        # suggest_dict.py 输出的字典建议
├── dict/               # 字典 / 映射表
│   ├── sex.csv
│   ├── unit.csv
│   ├── lab_item.csv
│   └── diagnosis_icd10.csv
├── tests/              # pytest 端到端测试
└── scripts/
    ├── _common.py
    ├── _config.py
    ├── schemas.py          # Pandera DataFrameModel 数据契约
    ├── make_demo_data.py   # Faker 生成带"脏数据"的演示 Excel
    ├── profile.py          # ydata-profiling 数据体检
    ├── suggest_dict.py     # 指纹聚类，自动建议字典新增条目
    ├── clean_lab.py
    ├── clean_emr.py
    └── clean_followup.py
```

## 快速开始

```bash
# 1. 安装依赖（建议 Python 3.10+）
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

# 5. 看一下还有哪些字典条目缺失
python cli.py suggest-dict      # 输出到 suggestions/*.csv

# 6. 在 data/clean/ 和 data/marts/ 查看输出

# 7. 跑测试（可选）
pytest tests/
```

> 旧用法仍然支持：`python scripts/clean_lab.py` 等脚本可以独立运行。

## 数据分层（dbt 风格）

```
data/raw/      原始 Excel，只读不改
   ↓ load_excel + clean_names
data/interim/  列名 / 类型标准化（parquet，问题排查用）
   ↓ 字典映射 + 模糊匹配 + 单位换算 + 日期解析 + 脱敏
data/clean/    业务清洗后宽表（xlsx + parquet + log csv）
   ↓ pivot / 汇总
data/marts/    分析就绪宽表（parquet，followup_wide 含 miss_type 计数）
```


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

- **配置即代码**：路径/字典名/模糊阈值/脱敏策略全在 `config.yaml`，改字典/阈值不改代码。
- **数据契约**：所有 schema 集中在 `scripts/schemas.py`（Pandera `DataFrameModel`）。
- **数据分层**：`raw → interim → clean → marts`，原始数据永远只读。
- **随访长表**：随访数据**永远存长表**（patient_id × indicator × month），分析时再 pivot（`marts/followup_wide.parquet`）。
- **脱敏前置**：病历数据在 `clean_emr.py` 中已对 `name`/`id_card` 做 hash + 删除处理；如果安装了 `presidio-analyzer` 还会进一步脱敏 `history_text` 中的姓名/电话/邮箱等。

## 扩展建议

- 复杂诊断映射：接入 [MedCAT](https://github.com/CogStack/MedCAT)
- PII 自动识别（已可选启用）：[Presidio](https://github.com/microsoft/presidio) — 取消 `requirements.txt` 中的注释即可
- 持续质量监控：接入 [Great Expectations](https://greatexpectations.io/)
- 数据版本：[DVC](https://dvc.org/) 跟踪 `data/clean/` / `data/marts/`
- 流水线编排：[Prefect](https://www.prefect.io/) / [Dagster](https://dagster.io/)

## License

与本仓库一致。
