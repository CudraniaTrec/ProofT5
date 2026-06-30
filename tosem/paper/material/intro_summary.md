# 论文 Intro 部分总结：新旧版本对比与修改指南

---

# 第一部分：原版本故事（Type-Guided Synthesis 视角）

## 核心概念

- **Type Derivation Tree**：类型推导树，证明程序类型正确
- **Synthesis Derivation Tree**：合成推导树，构造程序的过程
- **Type System**：类型系统，包含 typing rules
- **Synthesis System**：合成系统，包含 synthesis rules

## 核心思路

**关键洞察：Type Derivation Tree ≅ Synthesis Derivation Tree（同构）**

基于此洞察，用 Type-Guided Synthesis 作为新的程序表示：
- 原本 LM 生成的是 token 序列（程序文本）
- 现在 LM 生成的是 synthesis derivation tree（合成推导树）
- 由于同构性，LM 在生成 synthesis tree 时，隐式地也在构造 type derivation tree

## 故事提纲

### 1. 问题引入：LM生成代码的类型错误问题
- LM在代码生成方面取得巨大成功，但经常产生类型错误
- 数据支撑：
  - 类型错误占LM生成失败程序的 **33.6%**
  - GitHub Copilot在LeetCode上 **24%** 的建议导致编译错误
- 在资源受限语言或复杂类型系统中问题更严重

### 2. 为什么类型正确性重要
- 类型系统本质是静态分析系统，可以强制执行任何可判定的安全属性
- 即使LM能学会满足简单约束，外部辅助仍能提升整体性能（释放计算资源用于更高层任务如算法设计）

### 3. 挑战分析（Gap的本质）

核心问题：**文本token序列表示与结构化类型检查过程之间存在巨大鸿沟**

**训练时的挑战**：
- LM只能看到token序列，难以恢复完整类型系统
- 例如：Java的auto-unboxing规则被隐藏在文本序列中
- LM无法从序列中学习到完整的 **type derivation tree**

**生成时的挑战**：
- 类型检查需要复杂的上下文推理（如变量作用域判断）
- LM难以处理长上下文的全局推理

### 4. 现有方法的不足

**Constrained Decoding**：
- 只能排除ill-typed程序
- 但会扰乱well-typed程序的分布

**生成 Type Derivation Tree**：
- 让模型先生成程序，再生成其 **type derivation tree**
- 问题：训练时程序与类型证明分离，需要额外对齐
- 推理时上下文推理挑战仍存在

### 5. 核心洞察与方法：Type-Guided Synthesis

**关键洞察：Type Derivation Tree ≅ Synthesis Derivation Tree（同构）**
- 类型规则与合成规则之间存在**双射对应**
- 任何程序的 **type derivation tree** 都有结构相同的 **synthesis derivation tree**，反之亦然

**方法：据此用 Type-Guided Synthesis 作为新表示**
- 不再让 LM 生成 token 序列
- 而是让 LM 生成 **synthesis derivation tree**
- 由于同构性：生成 synthesis tree = 隐式生成 type derivation tree

**Type-Guided Synthesis 的核心方法论**：
- 将类型系统形式化为合成过程
- 初始目标：在类型约束下合成程序
- 通过应用 typing rules 逐步分解为子程序的子目标

### 6. 四个关键性质

| 性质 | 描述 | 如何满足 |
|------|------|----------|
| **Type Explicitness** | 在决策过程中追踪 type derivation | 直接构造 synthesis derivation tree 本身就携带同构的 type derivation tree |
| **Context Locality** | 每步决策在小上下文窗口内提供必要类型信息 | 每个 synthesis 决策处理一个局部化的目标 |
| **Derivation Vicinality** | 程序片段与其 type derivation 相邻 | 同构性确保 synthesis 序列天然编码 type derivation 结构 |
| **Data Usability** | 决策序列与源代码可自动双向转换 | 从 type derivation tree 提取序列，从序列重建程序 |

### 7. 三大贡献

**贡献1**：基于 Type-Guided Synthesis 的合成系统
- 类型系统与合成系统**同构**
- 满足性质：Type Explicitness, Context Locality

**贡献2**：基于合成决策序列的新程序表示
- 脱离传统的文本tokenization
- 满足性质：Derivation Vicinality

**贡献3**：\mainname 自动化系统
- 输入：语言定义 + 训练任务
- 输出：训练组件（从 type derivation tree 提取决策序列）+ 生成组件
- 满足性质：Data Usability

### 8. 技术要点
- 所有 typing rules 表示为**约束Horn子句 (CHC)**
- 可扩展到任意图灵可计算规约

### 原版本一句话总结

> 基于 **Type Derivation Tree ≅ Synthesis Derivation Tree** 的同构洞察，用 **Type-Guided Synthesis** 作为新的程序表示，让 LM 生成 synthesis tree 时隐式学习 type derivation tree。

---

# 第二部分：新版本故事（构造性逻辑 + Program-Proof 同构视角）

## 核心概念转变

| 原概念 | 新概念 | 说明 |
|--------|--------|------|
| Type Derivation Tree | **Type Correctness Proof** | 对程序类型正确性的证明 |
| Synthesis Derivation Tree | **Program Synthesis (Process)** | 构造程序的过程 |
| Type System | **Proof System** | 构造证明的规则系统 |
| Typing Rules | **Proof Rules** | 证明中的推理规则 |
| （无） | **Constructive Logic（构造性逻辑）** | 同构的理论基础 |

## 核心思路

**理论基础：构造性逻辑（Constructive Logic）**

在构造性逻辑中，证明一个命题必须通过**构造**一个见证（witness）来完成。这意味着：
- 证明的过程本身就是构造的过程
- 证明 "存在满足类型约束的程序" = 构造出这个程序

**关键洞察：由于构造性逻辑，Type Correctness Proof ≅ Program Synthesis（同构）**

- 构造 **Type Correctness Proof** 的过程，本身就是 **Program Synthesis** 的过程
- 证明的每一步推理，对应程序构造的每一步
- 因此：**构造证明 = 合成程序**，两者是同一过程的两面

**核心转变**：
- **原故事**：Type Derivation Tree ≅ Synthesis Derivation Tree（两棵树同构）
- **新故事**：由于**构造性逻辑**，**Type Correctness Proof ≅ Program Synthesis**（构造证明的过程就是程序合成的过程）

## 故事提纲

### 1. 问题引入：LM生成代码的类型错误问题
（与原版本相同）

### 2. 为什么类型正确性重要
（与原版本相同）

### 3. 挑战分析（Gap的本质）

核心问题：**文本token序列无法表达 Type Correctness Proof**

**训练时的挑战**：
- LM只能看到token序列
- **Type correctness proof** 隐藏在文本背后，LM无法学习如何构造证明

**生成时的挑战**：
- LM难以在生成过程中构造 **proof**

### 4. 现有方法的不足

**Constrained Decoding**：
（与原版本相同）

**显式生成 Type Correctness Proof**：
- 让模型先生成程序，再生成其 **type correctness proof**
- 问题：程序与 **proof** 分离，难以对齐

### 5. 核心洞察与方法：基于构造性逻辑的 Program-Proof 同构

**理论基础：构造性逻辑（Constructive Logic）**

在构造性逻辑中：
- 证明 $\exists x. P(x)$ 必须**构造**出一个具体的 $x$ 并证明 $P(x)$
- 证明 "程序满足类型约束" 必须**构造**出满足约束的程序
- 因此，**构造证明的过程本身就是程序合成的过程**

**核心洞察：Type Correctness Proof ≅ Program Synthesis（同构！）**

由于构造性逻辑的特性：
- **Type Correctness Proof**：通过应用 proof rules 构造的推导，证明程序满足类型约束
- **Program Synthesis**：通过应用 synthesis rules 构造程序的过程

两者之间存在**双射对应**：
- 每个 proof rule 对应一个 synthesis rule
- 构造 **proof** 的每一步，同时也是构造 **program** 的一步
- **构造证明 = 合成程序**

**方法：据此设计新的合成框架，同时表示 Program 和 Proof**

基于这一同构关系，我们设计了一套新的 program synthesis 框架：
- 合成过程的每一步，既是程序构造的一步，也是证明构造的一步
- **训练时**：从程序及其 **proof** 提取统一的合成序列
- **生成时**：LM 执行合成过程，同时产生 **program** 和 **proof**

LM 学习的是这个统一的合成过程，从而自然地内化类型系统。

### 6. 四个关键性质

| 性质 | 描述 | 如何满足 |
|------|------|----------|
| **Type Explicitness** | 追踪 **proof** 构造过程 | 由于构造性逻辑，合成过程本身就是 **proof** 构造过程 |
| **Context Locality** | 每步决策在小上下文窗口内 | 每步对应 **proof** 中的一步局部推理 |
| **Derivation Vicinality** | **Program** 与 **Proof** 天然统一表示 | 构造性逻辑确保两者是同一过程 |
| **Data Usability** | 决策序列与源代码可双向转换 | 从 **program/proof** 提取序列，从序列重建两者 |

### 7. 三大贡献

**贡献1**：基于构造性逻辑，建立 Type Correctness Proof ≅ Program Synthesis 的同构关系，设计新的合成框架
- 利用构造性逻辑的特性：构造证明 = 合成程序
- 将 **type correctness proof** 形式化
- 证明 **proof** 与 **synthesis** 之间的双射对应
- 设计同时表示两者的合成框架

**贡献2**：基于同构的程序表示
- 合成序列同时编码 **program** 和其 **type correctness proof**
- LM 学习的是"如何构造证明"，由于构造性逻辑，这同时也是"如何合成程序"

**贡献3**：\mainname 自动化系统
- **训练**：从程序及其 **proof** 自动提取统一的合成序列
- **生成**：LM 执行合成过程 = 同时生成程序及其 **proof**

### 8. 技术要点
- 所有 proof rules 表示为**约束Horn子句 (CHC)**
- 可扩展到任意可判定的程序性质证明
- **构造性逻辑**是 **Type Correctness Proof ↔ Program Synthesis 同构**的理论基础

### 新版本一句话总结

> 基于**构造性逻辑**，构造 **Type Correctness Proof** 的过程本身就是 **Program Synthesis** 的过程；据此设计新的合成框架，让 LM 执行合成过程时同时生成程序及其证明，自然内化类型系统。

---

# 第三部分：整体叙事流程对比

## 原叙事流程
```
LM生成代码有类型错误
    ↓
挑战：LM难以学习 Type System（token序列 vs type derivation tree）
    ↓
现有方法不足：Constrained Decoding / 生成 Type Derivation Tree（分离）
    ↓
关键洞察：Type Derivation Tree ≅ Synthesis Derivation Tree
    ↓
我们的方法：据此用 Type-Guided Synthesis 作为新表示
    ↓
结果：LM 生成 synthesis tree，隐式学习 type derivation tree
```

## 新叙事流程
```
LM生成代码有类型错误
    ↓
挑战：LM难以学习如何构造 Type Correctness Proof
    ↓
现有方法不足：Constrained Decoding / 显式生成 Proof（分离）
    ↓
理论基础：构造性逻辑（Constructive Logic）
    ↓
核心洞察：由于构造性逻辑，Type Correctness Proof ≅ Program Synthesis（构造证明 = 合成程序）
    ↓
我们的方法：据此设计新的合成框架，同时表示 Program 和 Proof
    ↓
结果：LM 执行合成过程 = 同时生成程序和证明
```

## 关键区别

| 方面 | 原故事 | 新故事 |
|------|--------|--------|
| **理论基础** | （无明确理论基础） | **构造性逻辑（Constructive Logic）** |
| **同构对象** | Type Derivation Tree ≅ Synthesis Derivation Tree | Type Correctness Proof ≅ Program Synthesis |
| **同构原因** | 规则之间的双射对应 | **构造性逻辑**：构造证明的过程就是程序合成的过程 |
| **强调点** | Type-Guided（类型指导） | Proof-Synthesis 同构（构造证明 = 合成程序） |
| **LM 生成什么** | Synthesis Derivation Tree | 统一的合成序列（同时产生 Program 和 Proof） |
| **框架定位** | 用现有的 Type-Guided Synthesis | 设计新的合成框架 |
