# 功能对比矩阵

[English](https://github.com/ZengZichao/FigTreeKit/blob/main/docs/comparison_EN.md) | [中文文档](#)

FigTreeKit 与现有系统发育树工具与库的对比。

## 汇总表

| 功能 | FigTreeKit | DendroPy | ETE3 | Bio.Phylo | TreeGraph2 | TreeViewer |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| **解析** |  |  |  |  |  |  |
| Newick 解析 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nexus 解析 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nexus 多树 | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| PhyloXML | ⚠️ 可校验，但无法加载并注入样式 | ✅ | ❌ | ✅ | ❌ | ❌ |
| **FigTree 注解** |  |  |  |  |  |  |
| `!hilight` 注入 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `!color` 注入 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `!font` 注入（Java 格式） | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| FigTree 设置块 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `begin figtree; ... end;` | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **分类学分析** |  |  |  |  |  |  |
| 嵌入式分类学解析（`_d_`/`_p_`） | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GTDB 风格表格解析（`d__`/`p__`） | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 混合格式支持 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 单系性检测 | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 特殊标识符（LUCA/LACA/LBCA） | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 按分类群名称折叠类群 | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **验证** |  |  |  |  |  |  |
| 括号平衡检查 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 负分支长度检测 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 重复末端名检测 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 自循环检测 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 控制字符/双向文本覆盖扫描 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 树-序列交叉验证 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| FASTA/FASTQ 验证 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 字母表检测（DNA/RNA/protein） | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **样式 API** |  |  |  |  |  |  |
| 布局配置 | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 类群高亮 | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| 分支着色 | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| 字体配置 | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| 比例尺/坐标轴 | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **导出** |  |  |  |  |  |  |
| Nexus 导出 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 无副作用导出（不修改内部树，可复现） | ✅ | ❌ | ❌ | ❌ | N/A | ✅ |
| 保留已有注解 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 图片渲染（PNG/PDF/SVG/JPEG） | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ |
| **接口** |  |  |  |  |  |  |
| Python API | ✅ | ✅ | ✅ | ✅ | ❌ (GUI) | ❌ |
| CLI 批量处理 | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ |
| JSON 配置文件 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 自检模式 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 实时日志（ISO 8601） | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **质量** |  |  |  |  |  |  |
| 类型提示（PEP 561） | ✅ | ❌ | ❌ | ❌ | N/A | N/A |
| 测试覆盖率 | 整体 80.9%（语句加权）；包接口 78.5%、CLI 83.1%、解析 85.8%、NEXUS 序列化 89.3%、样式层 83.1%、分类学 81.6%、输入验证 85.9%、渲染 73.9%、环境安装 37.6%（按模块统计的语句覆盖率，汇总自 v1.1.4 测试作业的 coverage.xml，该作业以 `--cov=figtreekit` 运行 pytest；见 `.github/workflows/ci.yml`） | ~70% | ~60% | ~75% | N/A | N/A |
| Python 3.11 支持 | ✅ | ✅ | ❌ (3.8 max) | ✅ | N/A | N/A |

> 注：格式检测与结构校验均能识别 PhyloXML，但 `--validate` 会将其判为 "not a tree format" 并以退出码 3 结束，且 `FigTreeStyler` 无法加载 PhyloXML 以注入样式。

## 核心差异化

### 1. FigTree 注解注入

FigTreeKit 是**唯一**能程序化注入 FigTree 特定注解到 Nexus 文件的 Python 库。这是通过研究并复刻 FigTree 1.4.4 公开可用的 Java 源码（`FigTreeNexusExporter.java`、`AttributableDecorator.java`）实现的。

**实际意义：**
- 其他库可以*解析*树并*导出* Nexus，但导出的文件会丢失所有 FigTree 专属样式
- FigTreeKit 生成的 Nexus 文件用 FigTree 打开时，所有注解、颜色、字体与布局均已预先配置好
- 由此实现可复现、可脚本化的树样式工作流

### 2. 分类学感知分析

FigTreeKit 的独特之处在于同时支持两种格式的分类学提取：

- **格式 A（嵌入式）**：`_d_Bacteria_p_Cyanobacteriota_c_...` 编码在标签中
- **格式 B（表格）**：`d__Archaea;p__Thermoproteota;...` 来自映射文件
- **混合模式**：同一棵树中两种格式，可配置优先级

由此实现按分类群名称进行单系性检测与类群折叠——其他任何 Python 树库均不提供这些功能。

### 3. 深度输入验证

FigTreeKit 会执行其他树库所跳过的全面验证：

| 检查项 | FigTreeKit | 其他 |
| --- | :---: | :---: |
| 括号平衡（带位置） | ✅ | ❌ |
| 负分支长度（CRITICAL） | ✅ | ❌ |
| 重复末端名（ERROR） | ✅ | ❌ |
| 空节点名（ERROR） | ✅ | ❌ |
| 自循环检测 | ✅ | ❌ |
| 控制字符/双向文本覆盖扫描 | ✅ | ❌ |
| FASTA 重复 ID 检测 | ✅ | ❌ |
| 字母表验证（带行号） | ✅ | ❌ |

### 4. 无副作用导出

FigTreeKit 的导出过程不会修改内部树内容（`_tree_content`）。写入前，注解会被解析到一个本地副本中，因此同一 `FigTreeStyler` 实例多次调用 `export()` 不会产生副作用，输出结果始终一致，从而保证自动化流水线的可复现性。

### 5. 自检模式

`figtreekit --self-test` 运行 11 项内置检查，覆盖：
- 依赖版本
- Newick/FASTA 解析
- 分类学提取（两种格式）
- 单系性逻辑（单系性判断 + 特殊标识符）
- 导出往返
- 对抗性输入检测

其他树库均无此内置验证。

## 使用场景推荐

| 使用场景 | 推荐工具 |
| --- | --- |
| 用脚本生成用于出版的 FigTree 样式树 | **FigTreeKit** |
| 分类学感知树分析（单系性、折叠） | **FigTreeKit** |
| 系统发育流水线输入验证 | **FigTreeKit** |
| 程序化系统发育分析（树操作、模拟） | DendroPy |
| Python 可视化（matplotlib 渲染） | ETE3 |
| Bio* 工作流中的简单 Newick/Nexus I/O | Bio.Phylo |
| 交互式 GUI 树编辑 | TreeGraph2 或 FigTree |
| GUI/CLI 模块化树绘图（跨平台、>10 万分类单元） | TreeViewer |

## 复现对比

如需验证以上声明，可运行：

```bash
# 安装所有工具
pip install figtreekit dendropy ete3 biopython

# 运行 FigTreeKit 自检
figtreekit --self-test

# 运行 FigTreeKit 基准测试
python benchmarks/performance.py

# 运行 FigTreeKit 测试套件并查看覆盖率
pytest test/ --cov=figtreekit
```
