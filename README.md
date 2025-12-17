# parser_c

基于 **LL(1)** 的 C 子集语法分析程序。  
复用你现有的 **lexer_c**（`service/token.py`, `service/matcher.py`, `service/lexer.py`），在其之上完成：

- FIRST / FOLLOW / SELECT 集合计算  
- LL(1) 预测分析表构造  
- 语法分析（分析栈 + 输入指针）  
- 友好报错（行/列/遇到的记号/期望候选）

> 说明：文件名按你的要求使用 `grammer.py`（不是 grammar）。

---

## 环境要求

- Python **3.9+**（推荐 3.10+）
- 复制你自己的 `lexer_c` 三个文件到 `service/` 目录：
  - `service/token.py`
  - `service/matcher.py`
  - `service/lexer.py`

---

## 目录结构
```
parser_c/
    README.md
    main.py
    test.c
    service/
        grammer.py # 文法&产生式（build_grammar）
        first_follow.py # FIRST / FOLLOW / SELECT
        parse_table.py # LL(1) 预测分析表
        parser.py # 预测分析器（调用 lexer_c）
        lexer.py 
        matcher.py 
        token.py 
```
---

## 快速开始
**运行**  
```bash
python main.py test.c
```
`--show-ff`：打印 FIRST/FOLLOW/SELECT 部分结果与表格规模
`--trace`：打印分析过程（栈/剩余输入/用到的产生式），便于调试或写实验报告
`--export-xlsx [file]`：导出 LL(1) 预测分析表为 xlsx，默认文件名 `parse_table.xlsx`

示例：解析并导出表格  
```bash
python main.py test.c --export-xlsx  # 生成 parse_table.xlsx
python main.py test.c --export-xlsx my_table.xlsx  # 自定义文件名
```
