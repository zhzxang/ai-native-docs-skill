# Inventory CLI

一个使用 Python 标准库的本地库存命令行项目。库存保存在 JSON 文件中，没有服务端或数据库依赖。

Python 3.10 或更高版本即可运行，不需要安装第三方包。

```sh
python -m inventory_cli --data data/example.json list
python -m inventory_cli --data /tmp/my-inventory.json add Pencil 3
python -m inventory_cli --data /tmp/my-inventory.json remove Pencil
python -m unittest discover -s tests
```

默认数据文件是当前目录下的 `.inventory.json`。`list` 只读取数据；`add` 和 `remove` 会写入指定数据文件。

