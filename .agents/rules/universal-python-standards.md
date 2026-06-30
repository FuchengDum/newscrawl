---
trigger: always_on
---

# Antigravity Python 优雅工程代码规范与工作流指南 (Engineering & Workflow Standards)

本规则文件（Rule File）旨在深度融合 Antigravity 的自动化能力与 14 项核心技能，为 Python 项目构建一套兼顾代码优雅性、工程健壮性与团队协同高效性的通用规范。

---

## 1. 核心元规则与本地化约束 (Core Meta-Rules & Localization)

* **Plan 文件中文输出约束 (Mandatory)**：当激活 `writing-plans`、`writing-skills` 或 `brainstorming` 技能时，**所有生成的计划文件（如 `*.plan`）、架构设计文档、技术方案及头脑风暴记录必须全中文输出**。代码内部的注释、Docstring 则保持英文标准，以确保国际化通用性。
* **计划驱动执行 (Plan-Driven Execution)**：激活 `executing-plans` 技能时，智能体必须严格按照 `.plan` 文件中拆解的中文里程碑和步骤逐项执行。严禁在未同步更新 Plan 的情况下进行越界或即兴的代码开发。

---

## 2. 优雅 Python 代码标准 (Elegant Pythonic Standards)

* **PEP 8 严格合规**：代码结构必须严格遵守 PEP 8 规范。
    * 推荐使用 **Black** 风格（单行最高 88 字符）。
    * 使用 4 空格缩进，禁止使用 Tab。
    * 函数、类、变量命名清晰且具备自解释性（小蛇形命名法 `snake_case` 用于函数和变量，大驼峰命名法 `PascalCase` 用于类）。
* **强制类型提示 (Strict Type Hinting)**：所有函数和方法签名必须包含完整的显式类型提示。
    ```python
    # Good
    def fetch_user_payload(user_id: int, timeout: float = 5.0) -> dict[str, Any]:
        ...
    ```
* **标准 Google 风格文档字符串 (Docstrings)**：所有公开的模块、类、高阶函数必须配备完整的 Google-style Docstring，清晰说明功能、参数类型/含义、返回值类型及可能抛出的异常。
* **高阶语言特性运用**：激活 `using-superpowers` 技能时，鼓励优先采用 Python 优雅的高阶特性（如生成器 `generators`、装饰器 `decorators`、上下文管理器 `contextmanagers` 及 `asyncio` 异步生态），消除臃肿的模板代码（Boilerplate）。

---

## 3. 健壮的错误处理与资源管理 (Error Handling & Resource Management)

* **显式异常捕获 (Explicit Exceptions)**：严禁使用裸 `except:` 或捕获宽泛的 `Exception`。必须针对性捕获具体异常（如 `ValueError`, `KeyError`, `FileNotFoundError`），并在捕获后附带业务上下文。
* **资源安全闭环 (Context Managers)**：所有涉及文件 I/O、网络连接、数据库会话、线程/进程锁的操作，必须使用 `with` 语句（上下文管理器），确保资源在任何异常情况下均能正确释放。

---

## 4. 智能体协同与并行编排 (Agent Orchestration & Decoupling)

* **松耦合架构设计**：当触发 `dispatching-parallel-agents` 或 `subagent-driven-development` 技能时，系统任务必须被清晰解耦为高内聚、低耦合的独立 Python 模块或微型服务。
* **子智能体隔离约束**：分发给子智能体（Subagents）的任务边界必须由主智能体用中文严格定义，确保各并行节点之间在代码修改、用例编写上互不干扰，避免发生 Git 树冲突。

---

## 5. 测试驱动开发与系统级调试 (TDD & Systematic Debugging)

* **TDD 严格闭环 (Test-Driven Development)**：激活 `test-driven-development` 技能时，开发流程必须严格遵循 **编写测试用例（Fail） -> 编写刚好让测试通过的代码（Pass） -> 重构代码以追求优雅（Refactor）** 的三步循环。
* **防御性用例设计**：测试用例应覆盖核心业务逻辑、边界条件（如空值、极大值）以及异常链路。对于外部 API、数据库依赖，必须使用 `pytest-mock` 或 `unittest.mock` 进行严格打桩（Mocking）。
* **系统级结构化日志 (No print)**：激活 `systematic-debugging` 技能时，**严禁使用 `print()` 语句进行调试**。必须使用 Python 原生 `logging` 模块。生产环境代码应配置结构化（如 JSON 格式）日志输出，详细记录 `DEBUG`、`INFO`、`WARNING`、`ERROR` 各级别数据。

---

## 6. 代码评审、分支控制与完工校验 (Gatekeepers)

* **Git Worktree 物理隔离**：激活 `using-git-worktrees` 技能时，多任务并行开发、紧急 Bug 修复或实验性尝试（Spikes）必须在独立的 Git Worktrees 中进行，确保本地各工作空间干净隔离。
* **完工质量卡点 (Pre-Completion Audit)**：激活 `verification-before-completion` 技能时，在向用户声明任务完成前，智能体必须**强制执行本地静态代码检查与自动化测试（如 `ruff check .`，`mypy .`，`pytest`）**，自我审计是否 100% 契合本规则文件。
* **分支集成规范**：当触发 `finishing-a-development-branch` 技能时，必须将当前分支与主干（`main`/`master`）进行变基（Rebase）或无冲突合并，确保线性提交历史的整洁。
* **双向评审闭环 (Code Review)**：
    * 激活 `requesting-code-review` 时，须附带一份中文编写的变更摘要（PR Summary）。
    * 激活 `receiving-code-review` 时，智能体需自动解析反馈意见，定位重构点，自动修改代码并重新触发 `verification-before-completion` 校验流水线。