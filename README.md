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

---

## 命令行参数

- `--show-ff`：打印 **FIRST/FOLLOW/SELECT**（默认 SELECT 只显示少量示例）以及表格规模统计
- `--show-select-all`：配合 `--show-ff`，打印**所有产生式**的 SELECT 集（输出会很长）
- `--show-ff-used`：只打印“本次解析该源文件时**实际用到**的非终结符 FIRST/FOLLOW，以及**实际选用**的产生式 SELECT”（更像“针对 test.c 的分析”）
- `--ff-lookahead-only`：配合 `--show-ff-used`，把 FIRST/FOLLOW/SELECT 中的元素进一步过滤为“本次解析过程中实际出现过的 lookahead 终结符集合”（更贴近手工 LL(1) 推导时的关注点）
- `--show-table`：打印 LL(1) 预测分析表 `M[非终结符, 终结符] = 产生式`（输出可能很长）
- `--show-table-used`：只打印“本次解析该源文件时实际查询到的预测分析表单元”（更像“针对 test.c 的表格”）
- `--table-nt <NonTerminal>`：配合 `--show-table`，只输出某个非终结符对应的表行（推荐）
- `--table-limit N`：配合 `--show-table`，限制输出表项数量（`0` 表示全部；默认 `200`）
- `--trace`：打印分析过程（栈/剩余输入/用到的产生式），便于调试或写实验报告
- `--trace-limit N`：配合 `--trace`，限制输出 trace 行数（`0` 表示全部；默认 `200`）
- `--trace-table`：以“步骤表格”的形式输出 LL(1) 分析过程（分析栈/符号串/产生式/动作）
- `--trace-table-limit N`：配合 `--trace-table`，限制输出表格行数（`0` 表示全部；默认 `200`）
- `--export-trace-xlsx [file]`：导出 LL(1) 分析步骤表为 xlsx，默认文件名 `trace_table.xlsx`
- `--show-tree`：打印解析树（Parse Tree，包含非终结符展开与终结符匹配；空产生式会显示 `ε`）
- `--show-ast`：打印更简洁的抽象语法树（AST，用于写实验报告更方便）
- `--export-xlsx [file]`：导出 LL(1) 预测分析表为 xlsx，默认文件名 `parse_table.xlsx`
- `--export-xlsx-used [file]`：导出“本次解析实际用到的预测分析表项”为 xlsx，默认文件名 `parse_table_used.xlsx`

> 说明：FIRST/FOLLOW/SELECT 是“文法整体”的属性，严格来说不随输入文件变化；`--show-ff-used` 只是把输出过滤到本次解析过程中涉及到的那部分。

示例：解析并导出表格  
```bash
python main.py test.c --export-xlsx  # 生成 parse_table.xlsx
python main.py test.c --export-xlsx my_table.xlsx  # 自定义文件名
```

只导出“本次解析实际用到”的表项：
```bash
python main.py test.c --export-xlsx-used  # 生成 parse_table_used.xlsx
python main.py test.c --export-xlsx-used used.xlsx  # 自定义文件名
```

---

## 常用示例

只看某个非终结符的预测分析表（更清晰）：
```bash
python main.py test.c --show-table --table-nt Expr --table-limit 200
```

只看“本次解析实际用到的预测分析表项”（推荐）：
```bash
python main.py test.c --show-table-used --table-limit 200
```

把 FIRST/FOLLOW/SELECT 全量输出到文件（避免终端刷屏）：
```bash
python main.py test.c --show-ff --show-select-all > ff_select.txt
```

只输出“本次解析实际用到”的 FIRST/FOLLOW/SELECT（推荐）：
```bash
python main.py test.c --show-ff-used
```

只输出“本次解析实际用到”，并且集合元素只保留本次解析出现过的 lookahead 终结符（方案 B）：
```bash
python main.py test.c --show-ff-used --ff-lookahead-only
```

输出类似课件/教材的 LL(1) 分析步骤表：
```bash
python main.py test.c --trace-table --trace-table-limit 50
```

导出 LL(1) 分析步骤表（xlsx）：
```bash
python main.py test.c --export-trace-xlsx
python main.py test.c --export-trace-xlsx trace.xlsx
```

打印解析树：
```bash
python main.py test.c --show-tree
```

打印抽象语法树（更简洁）：
```bash
python main.py test.c --show-ast
```

---

## 注意事项（与 C 语法相关）

- `struct/union` 的“类型定义”在 C 中必须以分号结尾：`struct S { ... };`。缺少 `;` 会导致下一条顶层定义（例如 `void main()`）无法归约，从而报语法错误。
- 代码读取使用 `utf-8-sig`，可自动处理 UTF-8 BOM（`\ufeff`）导致的词法错误。
