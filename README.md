# C 子集语法分析器（递归下降，LL(1)）

- 词法：沿用你现有 `Lexer`（Python）
- 语法：递归下降，无回溯，等价于 LL(1) 预测分析
- 文法：见《语法规则.docx》与 `service/parser.py` 中的函数划分

## 运行

```bash
python main_parser.py path/to/test.c
```