# Python 单测开发修复规范

## 适用场景

- “修复这个 pytest 失败”
- “补一下这个文件的单测”
- “只改单测，不改源码”
- “把测试改成 unittest + @patch / @patch.object”
- “修单测”

## 工作流

1. 读取失败日志、测试文件、对应源码文件。
2. 优先一次只处理一个文件；必要时一次只补一个 case。
3. 修改后先跑定点测试，再决定是否扩大验证范围。
4. 最终说明根因、改动点、验证结果，以及是否仍有未覆盖风险。

## 强制规则

- 默认使用 `unittest`。
- 如果当前项目下存在 `.venv` 或 `venv` 目录，执行 Python 命令时优先使用虚拟环境中的 Python（如 `.venv/bin/python` 或 `venv/bin/python`）。
- Mock 必须写成 `@patch` 或 `@patch.object` 装饰器形式；不要写 `with patch(...)`。
- 不要直接修改、替换或 patch `sys.modules`。
- 不要通过手写 stub module、临时 module 对象或 `types.ModuleType(...)` 的方式 mock module。
- 用户要求只改单测时，不要按照单测改业务代码；仅在优化导入链时可以调整import语句；若必须改源码，先解释原因并等用户确认。
- 不要为了通过测试而削弱断言或改变测试语义。

## Mock 规范

- 把 `@patch` / `@patch.object` 当成 Python 单测的默认写法，而不是可选风格。
- 需要 mock 时，优先在测试方法或测试类上使用装饰器；不要改成 `with patch(...)` 上下文管理器。
- 需要多个 mock 时，叠加多个 `@patch` / `@patch.object` 装饰器，不要在函数体里写多个 `with patch(...)`。
- 不要直接改 `sys.modules`，也不要用 `patch.dict(sys.modules, ...)`、手写 stub module、临时 module 对象、`types.ModuleType(...)` 这类方式伪造模块依赖。
- 如果遇到 import 链问题，优先 patch 当前测试真正依赖的函数、类、对象或模块内符号；不要通过伪造整个 module 来绕过导入。
- 如果当前修改范围内已经存在 `with patch(...)`，且你正在触碰这段测试，优先顺手改成装饰器形式，避免同一文件混用两种风格。
- 写完测试后，先自查一次：是否出现了 `with patch(`、是否修改了 `sys.modules`、是否用了 stub module mock、是否所有 mock 都是装饰器形式。

允许示例：

```python
from unittest.mock import patch


@patch("pkg.module.fetch_data")
def test_run_returns_result(mock_fetch_data):
    mock_fetch_data.return_value = {"ok": True}

    result = run()

    assert result == {"ok": True}
```

禁止示例：

```python
from unittest.mock import patch


def test_run_returns_result():
    with patch("pkg.module.fetch_data") as mock_fetch_data:
        mock_fetch_data.return_value = {"ok": True}

        result = run()

    assert result == {"ok": True}
```

禁止 `sys.modules` / stub module 示例：

```python
from types import ModuleType
from unittest.mock import patch


artifact_proxy_module = ModuleType("aida.adaptor.artifact_proxy")


@patch.dict(sys.modules, {"aida.adaptor.artifact_proxy": artifact_proxy_module})
def test_run_returns_result():
    result = run()

    assert result == {"ok": True}
```

## 推荐验证方式

```bash
zsh -lc pytest -q <target> -vv'
```
