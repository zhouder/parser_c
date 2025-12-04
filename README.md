# C 子集语法分析器（递归下降/LL(1)）

## 功能
- 词法：识别关键字、标识符、10/8/16 进制整数、浮点、字符串/字符常量、运算符、界符，支持 // 和 /* */ 注释，非法数字后缀报错。
- 语法：递归下降（等价 LL(1)）；支持类型/变量声明、union、函数定义、块、if/while/for/return/break/continue、表达式优先级、函数调用/数组/成员访问/自增自减。
- 预处理：简单处理 `#include <...>`。
- 错误恢复：在 `;`/`}` 上同步，输出行列信息。

## 目录
- `main_parser.py`：入口，读取源文件，调用词法/语法，打印错误或 AST 概览。
- `service/lexer.py`、`matcher.py`、`token.py`：词法分析与记号定义。
- `service/parser.py`：语法分析。
- `service/ast.py`：AST 节点定义。
- `test.c`：示例 C 程序。

## 运行
```bash
python main_parser.py test.c
```

## 输出
- 通过时：打印 “语法分析通过，AST 概览：” 以及 AST 摘要。
- 出错时：打印错误数和列表，如 `[行:列] 错误信息`。
