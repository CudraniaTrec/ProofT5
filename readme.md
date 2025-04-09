## 项目结构
1. coq_model/ : 存储Coq证明相关的文件
   - program_model.py : java程序的Coq证明，在Python中的建模，以及（反）序列化函数
   - java2impp.py : java程序到DSL的转化，以及序列化反序列化的检查
   - prepare_data.py : 生成Coq证明序列的数据供后续的模型训练
   - coq_code/syntax.v : java程序的Coq证明，Coq代码
   - coq_code/mbjp/ : 各个mbjp程序生成过程之中产生的，待检查的Coq证明
   - mxeval/ : mbjp自带的正确性判断函数库
   - myjavalang/ : java程序的解析器库
   - datas/ : mbjp程序的数据
     - mbjp/ : mbjp程序的java文件,对应的coq证明文件，以及序列化后的文件
     - coq_tokenizer.pkl/ : 添加了新词汇之后的tokenizer
     - grammart5rules.pkl : grammart5的词表
     - mbjp.json : 完整的mbjp数据集
     - rules.json ： 添加了新词汇之后的词表
2. Utils/ : 存储数据，以及与之相关的辅助函数
   - evaluator/ : 存储计算BLEU分数相关的函数
   - models/ : 存储训练的模型
   - output/ : 存储模型代码生成，输出的结果
   - processdata/ : 存储将java程序语法树化的函数
     - 运行方式: `python -m processdata.solvembjp`
     - solvembjp.py : 将mbjp数据集中的java程序语法树化的函数（主函数）
     - process_utils.py : 定义了本项目的树结构 - Node类，与一些其他的辅助函数,可以设置`postfix`变量，来控制语法展开规则是否是grammart5见过的（mbjp/mbjp_blind）
     - solvedata.py : 将tree-sitter的树结构转化为本项目的树结构
     - solvetree.py : 将树结构的程序，按照展开式的规则序列化，并根据新添加的token扩充词表
     - stringfy.py : 将本项目的树结构转化为字符串(合法的java程序)
     - parser/ : tree-sitter的各种语言的解析器
   - data/???/ : 存储???数据集相关的各种文件
     - train/test/valid.json : 训练，测试，验证集的json格式的数据
     - train/test/valid.pkl : 训练，测试，验证集的pkl格式的数据(和json格式相同)
     - config.json : 数据集特定的模型训练配置文件
     - rules.pkl/json : 数据集的规则表
     - groundvalid : ???数据集的验证集的所有程序连在一起，用于计算BLEU分数
     - valid/test_nl.json : 用于验证/测试的自然语言输入
     - test/valid/i.pkl : 测试，验证集的第i道题目的程序的pkl格式的数据
   - tree_sitter_dsl/ : tree-sitter实现的dsl parser
     - grammar.js : dsl的语法
     - parser.so : 生成的parser
     - solvedsl.py : 将dsl程序变成本项目的树结构，进而变成rules序列，相当于solvembjp+solvetree+solvedata 三个文件的功能
     - stringfy.py : 将本项目的树结构变成dsl程序
   - score_output/ : 检查模型生成的代码的效果的函数
   - requirements.txt : 项目的python依赖
3. tmp/: 存储程序运行需要的临时文件
   - communicate.json : 多进程同步的文件
   - data_train/valid/test.pkl : 被切分的数据集，分给不同进程使用
   - out.txt : 模型对于验证集生成的结果，与groungvalid文件比对计算bleu值
4. wandb/: 存储wandb的日志文件
5. beamsearch.py : 定义了beamsearch的类
6. beamsearch_coq.py : 定义了beamsearch的包含coq检查的类
7. beamsearch_dsl.py : 用于dsl程序的beamsearch代码，和`beamsearch.py`几乎一致
8.  Dataset.py : 定义了数据集加载与使用的类
9.  Model.py : 定义了模型的类
10. trans_dsl_program.py : 将dsl程序转化为可以执行的程序
11. run.py : `主函数`
12. run.sh : 运行run.py的脚本
13. run_overall.sh : 一次性运行所有的实验的脚本
14. acc_config.yaml : accelerator的配置文件